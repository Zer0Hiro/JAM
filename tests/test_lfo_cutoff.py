"""Tests for Feature 1 — LFO CUTOFF modulation."""

import pytest
from dsl.parser import parse
from dsl.semantic import validate
from dsl.codegen import generate


_BASE = """
BPM 120

INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    CUTOFF 5000
    RESONANCE 50
    VOLUME 200
    LFO 2.0 100 CUTOFF

SEQUENCE mel:
    PLAY lead C4 1

PLAY_SEQUENCE mel
"""


class TestLfoCutoffParse:
    def test_parses_lfo_cutoff(self) -> None:
        prog = parse(_BASE)
        inst = prog.instruments["lead"]
        assert inst.lfo_cutoff is not None
        assert inst.lfo_cutoff.rate == pytest.approx(2.0)
        assert inst.lfo_cutoff.depth == 100

    def test_lfo_cutoff_separate_from_lfo_volume(self) -> None:
        prog = parse(_BASE)
        inst = prog.instruments["lead"]
        assert inst.lfo_volume is None
        assert inst.lfo_cutoff is not None


class TestLfoCutoffSemantic:
    def test_valid_passes(self) -> None:
        result = validate(parse(_BASE))
        assert result.ok

    def test_rate_too_low(self) -> None:
        src = _BASE.replace("LFO 2.0 100 CUTOFF", "LFO 0.05 100 CUTOFF")
        result = validate(parse(src))
        assert not result.ok
        assert any("rate" in d.message.lower() for d in result.errors)

    def test_rate_too_high(self) -> None:
        src = _BASE.replace("LFO 2.0 100 CUTOFF", "LFO 25.0 100 CUTOFF")
        result = validate(parse(src))
        assert not result.ok
        assert any("rate" in d.message.lower() for d in result.errors)

    def test_depth_out_of_range(self) -> None:
        src = _BASE.replace("LFO 2.0 100 CUTOFF", "LFO 2.0 300 CUTOFF")
        result = validate(parse(src))
        assert not result.ok
        assert any("depth" in d.message.lower() for d in result.errors)

    def test_rate_above_10hz_warns(self) -> None:
        src = _BASE.replace("LFO 2.0 100 CUTOFF", "LFO 15.0 100 CUTOFF")
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
    CUTOFF 3000
    LFO 1.0 50 CUTOFF
    VOLUME 200
SEQUENCE s:
    PLAY kick 1
PLAY_SEQUENCE s
"""
        result = validate(parse(src))
        assert any("no effect" in d.message.lower() for d in result.warnings)

    def test_more_than_2_cutoff_lfos_warns(self) -> None:
        instruments = ""
        for i in range(3):
            instruments += f"""
INSTRUMENT s{i}:
    TYPE SYNTH
    WAVE SIN
    CUTOFF 3000
    LFO 1.0 50 CUTOFF
    VOLUME 200
"""
        src = instruments + "\nSEQUENCE m:\n    PLAY s0 C4 1\nPLAY_SEQUENCE m\n"
        result = validate(parse(src))
        assert any("more than 2" in d.message.lower() for d in result.warnings)


class TestLfoCutoffCodegen:
    def _code(self, src: str = _BASE) -> str:
        return generate(parse(src))

    def test_includes_state_variable(self) -> None:
        assert "#include <StateVariable.h>" in self._code()

    def test_declares_svf(self) -> None:
        code = self._code()
        assert "StateVariable<LOW_PASS> svf0" in code

    def test_declares_lfo_phase_counter(self) -> None:
        code = self._code()
        assert "lfoCutoffPhase0" in code

    def test_declares_lfo_period_define(self) -> None:
        code = self._code()
        assert "LFO_CUTOFF_PERIOD_0" in code

    def test_lfo_tick_in_update_control(self) -> None:
        code = self._code()
        uc_start = code.index("void updateControl()")
        ua_start = code.index("AudioOutput updateAudio()")
        uc_body = code[uc_start:ua_start]
        assert "lfoCutoffPhase0" in uc_body
        assert "setCutoffFreqAndResonance" in uc_body

    def test_no_lfo_tick_in_update_audio(self) -> None:
        code = self._code()
        ua_start = code.index("AudioOutput updateAudio()")
        loop_start = code.index("void loop()")
        ua_body = code[ua_start:loop_start]
        assert "lfoCutoffPhase0" not in ua_body

    def test_svf_next_in_update_audio(self) -> None:
        code = self._code()
        ua_start = code.index("AudioOutput updateAudio()")
        loop_start = code.index("void loop()")
        ua_body = code[ua_start:loop_start]
        assert "svf0.next(" in ua_body

    def test_no_float_in_update_audio(self) -> None:
        code = self._code()
        ua_start = code.index("AudioOutput updateAudio()")
        loop_start = code.index("void loop()")
        ua_body = code[ua_start:loop_start]
        for token in ["0.0", "0.5", "1.0", "float ", "double "]:
            assert token not in ua_body, f"Float found in updateAudio: {token!r}"

    def test_no_float_in_update_control_lfo(self) -> None:
        code = self._code()
        uc_start = code.index("void updateControl()")
        ua_start = code.index("AudioOutput updateAudio()")
        uc_body = code[uc_start:ua_start]
        for token in ["float ", "double "]:
            assert token not in uc_body, f"Float type in updateControl: {token!r}"

    def test_hz_to_q8n0_helper_emitted(self) -> None:
        assert "hzToQ8n0" in self._code()

    def test_base_cutoff_constant(self) -> None:
        code = self._code()
        assert "LFO_CUTOFF_BASE_0" in code
        # Base cutoff is 5000 Hz from _BASE
        assert "5000" in code

    def test_old_iir_not_used(self) -> None:
        code = self._code()
        assert "lpfState" not in code
        assert "channelCutoff" not in code
        assert "alpha" not in code
