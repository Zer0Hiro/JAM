"""Tests for Feature 3 — per-note CUTOFF override in PLAY and BEAT."""

import pytest
from dsl.parser import parse
from dsl.semantic import validate
from dsl.codegen import generate


_BASE_SEQ = """
BPM 120

INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    CUTOFF 5000
    RESONANCE 30
    VOLUME 200

SEQUENCE mel:
    PLAY lead C4 1 CUTOFF:1000
    PLAY lead E4 1
    PLAY lead G4 1 CUTOFF:8000

PLAY_SEQUENCE mel
"""

_BASE_PAT = """
BPM 120

INSTRUMENT snare:
    TYPE DRUM
    WAVE SIN
    FREQ 200
    CUTOFF 4000
    VOLUME 200

PATTERN beat:
    BEAT 1: snare CUTOFF:500
    BEAT 3: snare

PLAY_PATTERN beat
"""


class TestCutoffOverrideParse:
    def test_parses_cutoff_override_in_play(self) -> None:
        prog = parse(_BASE_SEQ)
        seq = prog.sequences["mel"]
        from dsl.ast_nodes import PlayNote
        plays = [ev for ev in seq.events if isinstance(ev, PlayNote)]
        assert plays[0].cutoff_override == 1000
        assert plays[1].cutoff_override is None
        assert plays[2].cutoff_override == 8000

    def test_parses_cutoff_override_in_beat(self) -> None:
        prog = parse(_BASE_PAT)
        pat = prog.patterns["beat"]
        beats_sorted = sorted(pat.events, key=lambda e: e.beat_position)
        assert beats_sorted[0].cutoff_override == 500
        assert beats_sorted[1].cutoff_override is None

    def test_cutoff_override_with_velocity(self) -> None:
        src = """
BPM 120
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SIN
    CUTOFF 5000
    VOLUME 200
SEQUENCE m:
    PLAY lead C4 1 180 CUTOFF:2000
PLAY_SEQUENCE m
"""
        prog = parse(src)
        from dsl.ast_nodes import PlayNote
        play = next(ev for ev in prog.sequences["m"].events if isinstance(ev, PlayNote))
        assert play.velocity == 180
        assert play.cutoff_override == 2000


class TestCutoffOverrideSemantic:
    def test_valid_passes(self) -> None:
        assert validate(parse(_BASE_SEQ)).ok

    def test_cutoff_below_20_errors(self) -> None:
        src = _BASE_SEQ.replace("CUTOFF:1000", "CUTOFF:10")
        result = validate(parse(src))
        assert not result.ok
        assert any("20" in d.message for d in result.errors)

    def test_cutoff_above_20000_errors(self) -> None:
        src = _BASE_SEQ.replace("CUTOFF:1000", "CUTOFF:25000")
        result = validate(parse(src))
        assert not result.ok
        assert any("20000" in d.message for d in result.errors)

    def test_boundary_20_valid(self) -> None:
        src = _BASE_SEQ.replace("CUTOFF:1000", "CUTOFF:20")
        assert validate(parse(src)).ok

    def test_boundary_20000_valid(self) -> None:
        src = _BASE_SEQ.replace("CUTOFF:1000", "CUTOFF:20000")
        assert validate(parse(src)).ok

    def test_no_cutoff_on_instrument_warns(self) -> None:
        src = """
BPM 120
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200
SEQUENCE m:
    PLAY lead C4 1 CUTOFF:2000
PLAY_SEQUENCE m
"""
        result = validate(parse(src))
        assert result.ok
        assert any("no effect" in d.message.lower() for d in result.warnings)

    def test_pattern_cutoff_no_instrument_cutoff_warns(self) -> None:
        src = """
BPM 120
INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    VOLUME 200
PATTERN p:
    BEAT 1: kick CUTOFF:1000
PLAY_PATTERN p
"""
        result = validate(parse(src))
        assert result.ok
        assert any("no effect" in d.message.lower() for d in result.warnings)


class TestCutoffOverrideCodegen:
    def _code(self, src: str = _BASE_SEQ) -> str:
        return generate(parse(src))

    def test_note_event_struct_has_cutoff_field(self) -> None:
        code = self._code()
        assert "cutoffOvr" in code
        assert "uint16_t cutoffOvr" in code

    def test_cutoff_override_in_progmem_table(self) -> None:
        code = self._code()
        # First event has cutoff 1000; the comment should mention it
        assert "cutoff=1000Hz" in code

    def test_apply_cutoff_override_called(self) -> None:
        code = self._code()
        assert "applyCutoffOverride(" in code

    def test_apply_cutoff_override_helper_emitted(self) -> None:
        code = self._code()
        assert "void applyCutoffOverride(" in code

    def test_restore_at_note_off(self) -> None:
        code = self._code()
        # triggerNoteOff should check cutoffOvrActive and restore baseCutoffQ
        assert "cutoffOvrActive" in code
        assert "baseCutoffQ" in code

    def test_cutoff_override_active_initialized_false(self) -> None:
        code = self._code()
        assert "cutoffOvrActive[i] = false" in code

    def test_svf_declared(self) -> None:
        assert "StateVariable<LOW_PASS> svf0" in self._code()

    def test_zero_override_emitted_for_no_override_notes(self) -> None:
        code = self._code()
        # Second event (E4) has no override — its cutoffOvr should be 0
        # Check that 0 appears as the last field in at least one event row
        # Format: {channel, freq, duration, isRest, simNext, velocity, cutoffOvr}
        import re
        rows = re.findall(r'\{[^}]+\}', code)
        # At least one row should end with ", 0}" (no override)
        assert any(row.rstrip().endswith(", 0}") for row in rows)
