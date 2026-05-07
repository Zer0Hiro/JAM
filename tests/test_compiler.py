"""Integration tests — compile full .mdsl examples end-to-end."""

import pytest
from pathlib import Path
from dsl.parser import parse
from dsl.codegen import generate
from dsl.semantic import validate


EXAMPLES_DIR = Path(__file__).parent.parent / "dsl_examples"


def _compile_example(name: str) -> str:
    """Parse, validate, and generate C++ for a named example file."""
    path = EXAMPLES_DIR / name
    source = path.read_text(encoding="utf-8")
    program = parse(source)
    result = validate(program)
    assert result.ok, f"Validation errors: {[str(e) for e in result.errors]}"
    return generate(program)


class TestExamplesCompile:
    """Verify all DSL examples produce valid-looking C++ output."""

    @pytest.mark.parametrize("example", [
        "simple_tone.mdsl",
        "melody.mdsl",
        "drums.mdsl",
        "multi_track.mdsl",
        "envelope.mdsl",
    ])
    def test_example_compiles(self, example: str) -> None:
        code = _compile_example(example)
        # Verify essential Mozzi 2.0 structure
        assert "#include <Mozzi.h>" in code
        assert "void setup()" in code
        assert "startMozzi(" in code
        assert "void updateControl()" in code
        assert "AudioOutput updateAudio()" in code
        assert "MonoOutput::from8Bit(" in code
        assert "void loop()" in code
        assert "audioHook();" in code
        # No floats in audio path
        audio_start = code.index("AudioOutput updateAudio()")
        audio_end = code.index("void loop()")
        audio_func = code[audio_start:audio_end]
        assert "float" not in audio_func

    def test_simple_tone_frequencies(self) -> None:
        code = _compile_example("simple_tone.mdsl")
        assert "262" in code   # C4
        assert "330" in code   # E4
        assert "392" in code   # G4

    def test_drums_has_three_channels(self) -> None:
        code = _compile_example("drums.mdsl")
        assert "#define NUM_CHANNELS 3" in code
        assert "osc0" in code
        assert "osc1" in code
        assert "osc2" in code

    def test_melody_has_loop_unrolled(self) -> None:
        code = _compile_example("melody.mdsl")
        # LOOP 3 over a 6-event sequence = 18 events + 5 resolve events = 23
        assert "#define NUM_EVENTS 23" in code

    def test_multi_track_has_all_wavetables(self) -> None:
        code = _compile_example("multi_track.mdsl")
        assert "SAW2048_DATA" in code
        assert "TRIANGLE2048_DATA" in code
        assert "SIN2048_DATA" in code

    def test_envelope_adsr_values(self) -> None:
        code = _compile_example("envelope.mdsl")
        # pad: ADSR 300 100 400 500
        assert "setTimes(300, 100, 400, 500)" in code
        # pluck: ADSR 2 80 0 60
        assert "setTimes(2, 80, 0, 60)" in code
