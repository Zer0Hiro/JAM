"""Tests for dsl.notes — note name to MIDI/frequency conversion."""

import pytest
from dsl.notes import (
    note_name_to_midi,
    note_name_to_freq_int,
    is_valid_note,
    midi_to_freq,
    build_freq_table,
)


class TestNoteNameToMidi:
    """Test scientific pitch notation to MIDI conversion."""

    def test_c4_is_60(self) -> None:
        assert note_name_to_midi("C4") == 60

    def test_a4_is_69(self) -> None:
        assert note_name_to_midi("A4") == 69

    def test_middle_c_alias(self) -> None:
        # C4 is middle C = MIDI 60
        assert note_name_to_midi("C4") == 60

    def test_sharps(self) -> None:
        assert note_name_to_midi("C#4") == 61
        assert note_name_to_midi("F#3") == 54
        assert note_name_to_midi("Fs3") == 54  # 's' is sharp

    def test_flats(self) -> None:
        assert note_name_to_midi("Bb3") == 58
        assert note_name_to_midi("Eb4") == 63

    def test_c0(self) -> None:
        assert note_name_to_midi("C0") == 12

    def test_a0_is_21(self) -> None:
        assert note_name_to_midi("A0") == 21

    def test_c8_is_108(self) -> None:
        assert note_name_to_midi("C8") == 108

    def test_octave_boundaries(self) -> None:
        # B3 to C4 should be one semitone apart
        assert note_name_to_midi("C4") - note_name_to_midi("B3") == 1

    def test_invalid_note_raises(self) -> None:
        with pytest.raises(ValueError):
            note_name_to_midi("X4")
        with pytest.raises(ValueError):
            note_name_to_midi("C")
        with pytest.raises(ValueError):
            note_name_to_midi("")


class TestNoteNameToFreqInt:
    """Test note name to integer frequency conversion."""

    def test_a4_is_440(self) -> None:
        assert note_name_to_freq_int("A4") == 440

    def test_c4_is_262(self) -> None:
        assert note_name_to_freq_int("C4") == 262

    def test_c5_is_double_c4(self) -> None:
        c4 = note_name_to_freq_int("C4")
        c5 = note_name_to_freq_int("C5")
        # Should be approximately double (within rounding)
        assert abs(c5 - 2 * c4) <= 1

    def test_positive_frequency(self) -> None:
        for note in ["C2", "A0", "G7"]:
            assert note_name_to_freq_int(note) > 0


class TestMidiToFreq:
    """Test MIDI number to frequency conversion."""

    def test_a4_440(self) -> None:
        assert abs(midi_to_freq(69) - 440.0) < 0.01

    def test_a3_220(self) -> None:
        assert abs(midi_to_freq(57) - 220.0) < 0.01


class TestIsValidNote:
    """Test note name validation."""

    def test_valid_notes(self) -> None:
        for note in ["C4", "D#3", "Bb2", "Fs5", "A0", "G7", "E4"]:
            assert is_valid_note(note), f"{note} should be valid"

    def test_invalid_notes(self) -> None:
        for note in ["X4", "C", "4C", "", "H3", "CC4"]:
            assert not is_valid_note(note), f"{note} should be invalid"


class TestBuildFreqTable:
    """Test frequency lookup table builder."""

    def test_a4_in_table(self) -> None:
        table = build_freq_table()
        assert table[69] == 440

    def test_table_range(self) -> None:
        table = build_freq_table(60, 72)
        assert 60 in table
        assert 72 in table
        assert 59 not in table
