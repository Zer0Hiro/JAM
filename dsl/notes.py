"""
Note name to MIDI number and frequency conversion utilities.

Supports scientific pitch notation: C4, D#3, Bb2, Fs5, etc.
MIDI note 69 = A4 = 440 Hz.
"""

from __future__ import annotations

import math
import re
from typing import Optional

# Semitone offsets within an octave (C=0)
_NOTE_BASES: dict[str, int] = {
    "C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11,
}

# Accidental modifiers
_ACCIDENTALS: dict[str, int] = {
    "#": 1, "s": 1,   # sharp
    "b": -1,           # flat
}

# Regex for parsing a note name like "C4", "D#3", "Bb2", "Fs5"
_NOTE_RE = re.compile(
    r"^([A-Ga-g])"        # letter name
    r"([#sb]?)"           # optional accidental
    r"(-?\d+)$"           # octave number (allow negative for sub-bass)
)


def note_name_to_midi(name: str) -> int:
    """Convert a scientific pitch notation string to a MIDI note number.

    Examples:
        >>> note_name_to_midi("C4")
        60
        >>> note_name_to_midi("A4")
        69
        >>> note_name_to_midi("D#3")
        51

    Args:
        name: Note name in scientific pitch notation (e.g. "C4", "Bb2", "F#5").

    Returns:
        MIDI note number (0-127 typical range).

    Raises:
        ValueError: If the note name cannot be parsed.
    """
    m = _NOTE_RE.match(name)
    if not m:
        raise ValueError(f"Invalid note name: {name!r}")

    letter = m.group(1).upper()
    accidental = m.group(2)
    octave = int(m.group(3))

    base = _NOTE_BASES[letter]
    modifier = _ACCIDENTALS.get(accidental, 0)

    # MIDI: C4 = 60, which means octave 4 starts at MIDI 60
    # Formula: (octave + 1) * 12 + semitone
    midi = (octave + 1) * 12 + base + modifier
    return midi


def midi_to_freq(midi: int) -> float:
    """Convert a MIDI note number to frequency in Hz.

    Uses equal temperament: f = 440 * 2^((midi - 69) / 12)

    Args:
        midi: MIDI note number.

    Returns:
        Frequency in Hz.
    """
    return 440.0 * math.pow(2.0, (midi - 69) / 12.0)


def note_name_to_freq(name: str) -> float:
    """Convert a note name directly to frequency in Hz.

    Args:
        name: Note name in scientific pitch notation.

    Returns:
        Frequency in Hz.
    """
    return midi_to_freq(note_name_to_midi(name))


def note_name_to_freq_int(name: str) -> int:
    """Convert a note name to an integer frequency suitable for Mozzi setFreq().

    Args:
        name: Note name in scientific pitch notation.

    Returns:
        Rounded integer frequency in Hz.
    """
    return round(note_name_to_freq(name))


def is_valid_note(name: str) -> bool:
    """Check whether a string is a valid scientific pitch notation note name.

    Args:
        name: Candidate note name.

    Returns:
        True if valid.
    """
    return _NOTE_RE.match(name) is not None


# Pre-computed frequency table for common MIDI range (21=A0 through 108=C8)
def build_freq_table(midi_low: int = 21, midi_high: int = 108) -> dict[int, int]:
    """Build a MIDI-to-integer-frequency lookup table.

    Args:
        midi_low: Lowest MIDI note to include.
        midi_high: Highest MIDI note to include.

    Returns:
        Dict mapping MIDI note number to integer frequency.
    """
    return {m: round(midi_to_freq(m)) for m in range(midi_low, midi_high + 1)}
