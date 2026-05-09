"""Tests for dsl.codegen — C++ code generation."""

import pytest
from dsl.parser import parse
from dsl.codegen import generate


SIMPLE_SOURCE = """
BPM 120

INSTRUMENT tone:
    TYPE SYNTH
    WAVE SIN
    ADSR 10 50 200 100
    VOLUME 200

SEQUENCE melody:
    PLAY tone C4 2
    REST 1
    PLAY tone E4 1

PLAY_SEQUENCE melody
"""

MULTI_CHANNEL_SOURCE = """
BPM 120

INSTRUMENT bass:
    TYPE SYNTH
    WAVE SAW
    VOLUME 220

INSTRUMENT lead:
    TYPE SYNTH
    WAVE TRIANGLE
    VOLUME 180

SEQUENCE line:
    PLAY bass C2 1
    PLAY lead E4 1

PLAY_SEQUENCE line
"""


class TestGenerateStructure:
    """Test that generated C++ has correct Mozzi 2.0 structure."""

    def test_includes_mozzi_h(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        assert "#include <Mozzi.h>" in code

    def test_not_mozzi_guts(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        assert "MozziGuts" not in code

    def test_loop_only_audiohook(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        # Extract the loop function
        loop_start = code.index("void loop()")
        loop_body = code[loop_start:]
        assert "audioHook();" in loop_body
        # loop() should have nothing else besides audioHook
        lines = [l.strip() for l in loop_body.split("\n") if l.strip()]
        # Should be: void loop() {, audioHook();, }
        assert len(lines) == 3

    def test_setup_calls_start_mozzi(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        assert "startMozzi(" in code

    def test_update_audio_returns_mono_output(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        assert "MonoOutput::from8Bit(" in code

    def test_no_float_in_update_audio(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        # Extract updateAudio function
        start = code.index("AudioOutput updateAudio()")
        end = code.index("void loop()")
        audio_func = code[start:end]
        assert "float" not in audio_func
        # No division operator in audio path
        # (>> is ok, / is not)
        lines = audio_func.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("//"):
                continue
            assert " / " not in stripped, f"Division found in updateAudio: {stripped}"


class TestGenerateOscillators:
    """Test oscillator declarations in generated code."""

    def test_oscil_template(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        assert "Oscil<2048, MOZZI_AUDIO_RATE>" in code

    def test_sin_wavetable(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        assert "SIN2048_DATA" in code
        assert 'tables/sin2048_int8.h' in code

    def test_saw_wavetable(self) -> None:
        code = generate(parse(MULTI_CHANNEL_SOURCE))
        assert "SAW2048_DATA" in code

    def test_adsr_template(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        assert "ADSR<MOZZI_CONTROL_RATE, MOZZI_AUDIO_RATE>" in code


class TestGenerateEvents:
    """Test event table generation."""

    def test_event_count(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        # 3 events: C4, rest, E4
        assert "#define NUM_EVENTS 3" in code

    def test_c4_frequency(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        # C4 = 262 Hz
        assert "262" in code

    def test_progmem(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        assert "PROGMEM" in code

    def test_note_event_struct(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        assert "struct NoteEvent" in code


class TestGenerateMultiChannel:
    """Test multi-channel code generation."""

    def test_two_oscillators(self) -> None:
        code = generate(parse(MULTI_CHANNEL_SOURCE))
        assert "osc0" in code
        assert "osc1" in code
        assert "env0" in code
        assert "env1" in code

    def test_channel_dispatch(self) -> None:
        code = generate(parse(MULTI_CHANNEL_SOURCE))
        assert "ev.channel == 0" in code
        assert "ev.channel == 1" in code

    def test_clipping_prevention(self) -> None:
        code = generate(parse(MULTI_CHANNEL_SOURCE))
        assert "sample >>=" in code


PLAY_TOGETHER_SOURCE = """
BPM 120

INSTRUMENT bass:
    TYPE SYNTH
    WAVE SAW
    VOLUME 220

INSTRUMENT lead:
    TYPE SYNTH
    WAVE TRIANGLE
    VOLUME 180

SEQUENCE bassline:
    PLAY bass C2 1
    PLAY bass G2 1

SEQUENCE melody:
    PLAY lead E4 0.5
    PLAY lead G4 0.5
    PLAY lead A4 1

PLAY_TOGETHER:
    PLAY_SEQUENCE bassline
    PLAY_SEQUENCE melody
"""


class TestGeneratePlayTogether:
    """Test PLAY_TOGETHER code generation."""

    def test_simultaneous_events_generated(self) -> None:
        code = generate(parse(PLAY_TOGETHER_SOURCE))
        assert "[SIM]" in code

    def test_both_channels_present(self) -> None:
        code = generate(parse(PLAY_TOGETHER_SOURCE))
        assert "bass" in code
        assert "lead" in code

    def test_first_events_simultaneous(self) -> None:
        code = generate(parse(PLAY_TOGETHER_SOURCE))
        lines = code.split("\n")
        event_lines = [l for l in lines if "// bass" in l or "// lead" in l]
        assert len(event_lines) >= 2
        assert "[SIM]" in event_lines[0]


class TestGenerateConfigMacros:
    """Test that config macros are emitted before includes."""

    def test_macros_before_include(self) -> None:
        code = generate(parse(SIMPLE_SOURCE))
        macro_pos = code.index("#define MOZZI_AUDIO_RATE")
        include_pos = code.index("#include <Mozzi.h>")
        assert macro_pos < include_pos

    def test_custom_audio_rate(self) -> None:
        source = "AUDIO_RATE 32768\n" + SIMPLE_SOURCE
        code = generate(parse(source))
        assert "#define MOZZI_AUDIO_RATE 32768" in code
