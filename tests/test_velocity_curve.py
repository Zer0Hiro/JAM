"""Tests for Feature 4 — VELOCITY_CURVE compile-time interpolation."""

import re
import pytest
from dsl.parser import parse
from dsl.semantic import validate
from dsl.codegen import generate
from dsl.ast_nodes import PlayNote, VelocityCurve


_CRESCENDO_SRC = """
BPM 120

INSTRUMENT lead:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE mel:
    VELOCITY_CURVE CRESCENDO 60 200 5
    PLAY lead C4 1
    PLAY lead D4 1
    PLAY lead E4 1
    PLAY lead F4 1
    PLAY lead G4 1

PLAY_SEQUENCE mel
"""

_DECRESCENDO_SRC = """
BPM 120

INSTRUMENT lead:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE mel:
    VELOCITY_CURVE DECRESCENDO 200 60 3
    PLAY lead C4 1
    PLAY lead D4 1
    PLAY lead E4 1

PLAY_SEQUENCE mel
"""


def _extract_velocities(code: str) -> list[int]:
    """Extract velocity values from PROGMEM event table rows."""
    # Rows look like: {ch, freq, dur, isRest, simNext, velocity, cutoffOvr},
    rows = re.findall(r'\{(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)\}', code)
    return [int(r[5]) for r in rows if r[3] == "0"]  # exclude rest rows


class TestVelocityCurveParse:
    def test_parses_crescendo(self) -> None:
        prog = parse(_CRESCENDO_SRC)
        seq = prog.sequences["mel"]
        curves = [ev for ev in seq.events if isinstance(ev, VelocityCurve)]
        assert len(curves) == 1
        assert curves[0].kind == "CRESCENDO"
        assert curves[0].start_vel == 60
        assert curves[0].end_vel == 200
        assert curves[0].note_count == 5

    def test_parses_decrescendo(self) -> None:
        prog = parse(_DECRESCENDO_SRC)
        seq = prog.sequences["mel"]
        curves = [ev for ev in seq.events if isinstance(ev, VelocityCurve)]
        assert curves[0].kind == "DECRESCENDO"

    def test_parses_off(self) -> None:
        src = """
BPM 120
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200
SEQUENCE m:
    VELOCITY_CURVE CRESCENDO 60 200 4
    PLAY lead C4 1
    VELOCITY_CURVE OFF
    PLAY lead D4 1
PLAY_SEQUENCE m
"""
        prog = parse(src)
        events = prog.sequences["m"].events
        off_curves = [ev for ev in events if isinstance(ev, VelocityCurve) and ev.kind == "OFF"]
        assert len(off_curves) == 1


class TestVelocityCurveSemantic:
    def test_valid_crescendo_passes(self) -> None:
        assert validate(parse(_CRESCENDO_SRC)).ok

    def test_start_vel_out_of_range(self) -> None:
        src = _CRESCENDO_SRC.replace("CRESCENDO 60 200 5", "CRESCENDO 300 200 5")
        result = validate(parse(src))
        assert not result.ok
        assert any("start_vel" in d.message for d in result.errors)

    def test_end_vel_out_of_range(self) -> None:
        src = _CRESCENDO_SRC.replace("CRESCENDO 60 200 5", "CRESCENDO 60 300 5")
        result = validate(parse(src))
        assert not result.ok
        assert any("end_vel" in d.message for d in result.errors)

    def test_note_count_zero_errors(self) -> None:
        src = _CRESCENDO_SRC.replace("CRESCENDO 60 200 5", "CRESCENDO 60 200 0")
        result = validate(parse(src))
        assert not result.ok
        assert any("note_count" in d.message for d in result.errors)

    def test_note_count_too_large_errors(self) -> None:
        src = _CRESCENDO_SRC.replace("CRESCENDO 60 200 5", "CRESCENDO 60 200 200")
        result = validate(parse(src))
        assert not result.ok
        assert any("note_count" in d.message for d in result.errors)

    def test_note_count_128_valid(self) -> None:
        # Build a 128-note sequence
        notes = "\n".join(f"    PLAY lead C4 1" for _ in range(128))
        src = f"""
BPM 120
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200
SEQUENCE m:
    VELOCITY_CURVE CRESCENDO 0 255 128
{notes}
PLAY_SEQUENCE m
"""
        assert validate(parse(src)).ok

    def test_note_count_exceeds_remaining_warns(self) -> None:
        src = _CRESCENDO_SRC.replace("CRESCENDO 60 200 5", "CRESCENDO 60 200 10")
        result = validate(parse(src))
        assert result.ok
        assert any("extends beyond" in d.message.lower() for d in result.warnings)

    def test_boundary_velocities_valid(self) -> None:
        src = _CRESCENDO_SRC.replace("CRESCENDO 60 200 5", "CRESCENDO 0 255 5")
        assert validate(parse(src)).ok


class TestVelocityCurveCodegen:
    def test_crescendo_velocities_linear(self) -> None:
        code = generate(parse(_CRESCENDO_SRC))
        vels = _extract_velocities(code)
        assert len(vels) == 5
        assert vels[0] == 60
        assert vels[4] == 200
        # Linear: 60, 95, 130, 165, 200
        assert vels[1] == 95
        assert vels[2] == 130
        assert vels[3] == 165

    def test_decrescendo_velocities_linear(self) -> None:
        code = generate(parse(_DECRESCENDO_SRC))
        vels = _extract_velocities(code)
        assert len(vels) == 3
        assert vels[0] == 200
        assert vels[2] == 60
        assert vels[1] == 130

    def test_single_note_curve(self) -> None:
        src = """
BPM 120
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200
SEQUENCE m:
    VELOCITY_CURVE CRESCENDO 120 120 1
    PLAY lead C4 1
PLAY_SEQUENCE m
"""
        code = generate(parse(src))
        vels = _extract_velocities(code)
        assert vels[0] == 120

    def test_explicit_velocity_overrides_curve(self) -> None:
        src = """
BPM 120
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200
SEQUENCE m:
    VELOCITY_CURVE CRESCENDO 60 200 4
    PLAY lead C4 1
    PLAY lead D4 1 99
    PLAY lead E4 1
    PLAY lead F4 1
PLAY_SEQUENCE m
"""
        code = generate(parse(src))
        vels = _extract_velocities(code)
        assert len(vels) == 4
        # Curve: 60→200 over 4 notes (denominator = n-1 = 3)
        # pos 0: 60, pos 1: explicit 99 (curve pos still advances),
        # pos 2: 60+140*2//3=153, pos 3: 200
        assert vels[0] == 60
        assert vels[1] == 99
        assert vels[2] == 153
        assert vels[3] == 200

    def test_velocity_curve_off_stops_curve(self) -> None:
        src = """
BPM 120
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200
SEQUENCE m:
    VELOCITY_CURVE CRESCENDO 60 200 4
    PLAY lead C4 1
    PLAY lead D4 1
    VELOCITY_CURVE OFF
    PLAY lead E4 1
    PLAY lead F4 1
PLAY_SEQUENCE m
"""
        code = generate(parse(src))
        vels = _extract_velocities(code)
        # After OFF, notes revert to default 255
        assert vels[2] == 255
        assert vels[3] == 255

    def test_no_velocity_curve_in_generated_cpp(self) -> None:
        code = generate(parse(_CRESCENDO_SRC))
        # VelocityCurve is compile-time only — no C++ runtime mention
        assert "VELOCITY_CURVE" not in code
        assert "CRESCENDO" not in code

    def test_no_extra_ram_cost(self) -> None:
        code = generate(parse(_CRESCENDO_SRC))
        # Velocity curve should not add any new arrays or state variables
        assert "velocityCurve" not in code
        assert "curvePhase" not in code
