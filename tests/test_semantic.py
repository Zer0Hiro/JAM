"""Tests for dsl.semantic — validation pass."""

import pytest
from dsl.parser import parse
from dsl.semantic import validate


class TestValidateInstruments:
    """Test instrument validation."""

    def test_valid_instrument_passes(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    ADSR 10 50 200 100
    VOLUME 200

SEQUENCE m:
    PLAY s C4 1

PLAY_SEQUENCE m
"""
        result = validate(parse(source))
        assert result.ok

    def test_volume_out_of_range(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    VOLUME 300
"""
        result = validate(parse(source))
        assert not result.ok
        assert any("volume" in d.message.lower() for d in result.errors)

    def test_negative_adsr(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    ADSR -10 50 200 100
"""
        result = validate(parse(source))
        assert not result.ok

    def test_warns_on_many_synths(self) -> None:
        instruments = ""
        for i in range(5):
            instruments += f"""
INSTRUMENT s{i}:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200
"""
        result = validate(parse(instruments))
        assert any("RAM" in d.message for d in result.warnings)


class TestValidateReferences:
    """Test that references to sequences/patterns/instruments are validated."""

    def test_undefined_instrument(self) -> None:
        source = """
INSTRUMENT real:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE m:
    PLAY fake C4 1
"""
        result = validate(parse(source))
        assert not result.ok
        assert any("fake" in d.message for d in result.errors)

    def test_undefined_sequence(self) -> None:
        source = """
PLAY_SEQUENCE nonexistent
"""
        result = validate(parse(source))
        assert not result.ok
        assert any("nonexistent" in d.message for d in result.errors)

    def test_undefined_pattern(self) -> None:
        source = """
PLAY_PATTERN nonexistent
"""
        result = validate(parse(source))
        assert not result.ok

    def test_valid_note(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE m:
    PLAY s C4 1
    PLAY s D#3 1
    PLAY s Bb2 1
"""
        result = validate(parse(source))
        assert result.ok

    def test_loop_references(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE m:
    PLAY s C4 1

LOOP 2:
    PLAY_SEQUENCE missing
"""
        result = validate(parse(source))
        assert not result.ok
        assert any("missing" in d.message for d in result.errors)


class TestValidateConfig:
    """Test configuration validation."""

    def test_zero_bpm(self) -> None:
        source = "BPM 0"
        result = validate(parse(source))
        assert not result.ok

    def test_high_bpm_warning(self) -> None:
        source = "BPM 400"
        result = validate(parse(source))
        assert any("fast" in d.message.lower() for d in result.warnings)

    def test_nonstandard_audio_rate_warning(self) -> None:
        source = "AUDIO_RATE 44100"
        result = validate(parse(source))
        assert any("non-standard" in d.message.lower() for d in result.warnings)
