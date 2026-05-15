"""Tests for Feature 2 — LFO PAN (ESP32 stereo only)."""

import pytest
from dsl.parser import parse
from dsl.semantic import validate
from dsl.codegen import generate


_BASE = """
BPM 120

INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    PAN 127
    VOLUME 200
    LFO 0.5 80 PAN

SEQUENCE mel:
    PLAY lead C4 1

PLAY_SEQUENCE mel
"""


class TestLfoPanParse:
    def test_parses_lfo_pan(self) -> None:
        prog = parse(_BASE)
        inst = prog.instruments["lead"]
        assert inst.lfo_pan is not None
        assert inst.lfo_pan.rate == pytest.approx(0.5)
        assert inst.lfo_pan.depth == 80

    def test_lfo_pan_does_not_set_lfo_volume(self) -> None:
        prog = parse(_BASE)
        assert prog.instruments["lead"].lfo_volume is None


class TestLfoPanSemantic:
    def test_valid_emits_esp32_only_warning(self) -> None:
        result = validate(parse(_BASE))
        assert result.ok
        assert any("esp32" in d.message.lower() for d in result.warnings)

    def test_rate_too_low(self) -> None:
        src = _BASE.replace("LFO 0.5 80 PAN", "LFO 0.05 80 PAN")
        result = validate(parse(src))
        assert not result.ok
        assert any("rate" in d.message.lower() for d in result.errors)

    def test_rate_too_high(self) -> None:
        src = _BASE.replace("LFO 0.5 80 PAN", "LFO 25.0 80 PAN")
        result = validate(parse(src))
        assert not result.ok

    def test_depth_out_of_range(self) -> None:
        src = _BASE.replace("LFO 0.5 80 PAN", "LFO 0.5 300 PAN")
        result = validate(parse(src))
        assert not result.ok
        assert any("depth" in d.message.lower() for d in result.errors)

    def test_rate_above_10hz_warns(self) -> None:
        src = _BASE.replace("LFO 0.5 80 PAN", "LFO 12.0 80 PAN")
        result = validate(parse(src))
        assert result.ok
        assert any("audio range" in d.message.lower() for d in result.warnings)

    def test_drum_warns(self) -> None:
        src = """
BPM 120
INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    VOLUME 200
    LFO 1.0 50 PAN
SEQUENCE s:
    PLAY kick 1
PLAY_SEQUENCE s
"""
        result = validate(parse(src))
        assert any("no effect" in d.message.lower() for d in result.warnings)


class TestLfoPanCodegen:
    def _code(self, src: str = _BASE) -> str:
        return generate(parse(src))

    def test_avr_error_emitted(self) -> None:
        code = self._code()
        assert "#ifdef __AVR__" in code
        assert '#error "LFO PAN requires ESP32 with I2S DAC"' in code
        assert "#endif" in code

    def test_avr_error_before_includes(self) -> None:
        code = self._code()
        avr_pos = code.index("#ifdef __AVR__")
        include_pos = code.index("#include <Mozzi.h>")
        assert avr_pos < include_pos

    def test_stereo_output(self) -> None:
        code = self._code()
        assert "StereoOutput::from8Bit(" in code

    def test_i2s_dac_define(self) -> None:
        code = self._code()
        assert "MOZZI_OUTPUT_I2S_DAC" in code

    def test_stereo_channels_define(self) -> None:
        code = self._code()
        assert "MOZZI_STEREO" in code or "MOZZI_AUDIO_CHANNELS" in code

    def test_lfo_pan_phase_counter(self) -> None:
        assert "lfoPanPhase0" in self._code()

    def test_cur_pan_mutable(self) -> None:
        code = self._code()
        # curPan must be mutable (not const) for LFO pan
        assert "uint8_t curPan[" in code
        assert "const uint8_t curPan[" not in code

    def test_lfo_pan_tick_in_update_control(self) -> None:
        code = self._code()
        uc_start = code.index("void updateControl()")
        ua_start = code.index("AudioOutput updateAudio()")
        uc_body = code[uc_start:ua_start]
        assert "lfoPanPhase0" in uc_body
        assert "curPan[0]" in uc_body

    def test_no_lfo_pan_tick_in_update_audio(self) -> None:
        code = self._code()
        ua_start = code.index("AudioOutput updateAudio()")
        loop_start = code.index("void loop()")
        ua_body = code[ua_start:loop_start]
        assert "lfoPanPhase0" not in ua_body

    def test_cur_pan_used_in_stereo_mix(self) -> None:
        code = self._code()
        ua_start = code.index("AudioOutput updateAudio()")
        loop_start = code.index("void loop()")
        ua_body = code[ua_start:loop_start]
        assert "curPan[0]" in ua_body

    def test_no_float_in_update_control(self) -> None:
        code = self._code()
        uc_start = code.index("void updateControl()")
        ua_start = code.index("AudioOutput updateAudio()")
        uc_body = code[uc_start:ua_start]
        for token in ["float ", "double "]:
            assert token not in uc_body
