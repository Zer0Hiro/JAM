"""
AST node definitions for the Mozzi DSL.

Every node is a frozen dataclass for immutability and easy serialization.
The AST is produced by the parser and consumed by the code generator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class WaveType(Enum):
    """Supported oscillator waveform types."""
    SIN = auto()
    SAW = auto()
    SQUARE = auto()
    TRIANGLE = auto()
    NOISE = auto()
    PLUCK = auto()


class ScaleType(Enum):
    """Musical scale types for KEY declaration."""
    MAJOR = auto()
    MINOR = auto()
    DORIAN = auto()
    PHRYGIAN = auto()
    LYDIAN = auto()
    MIXOLYDIAN = auto()
    PENTATONIC = auto()
    BLUES = auto()


SCALE_INTERVALS: dict[ScaleType, tuple[int, ...]] = {
    ScaleType.MAJOR: (0, 2, 4, 5, 7, 9, 11),
    ScaleType.MINOR: (0, 2, 3, 5, 7, 8, 10),
    ScaleType.DORIAN: (0, 2, 3, 5, 7, 9, 10),
    ScaleType.PHRYGIAN: (0, 1, 3, 5, 7, 8, 10),
    ScaleType.LYDIAN: (0, 2, 4, 6, 7, 9, 11),
    ScaleType.MIXOLYDIAN: (0, 2, 4, 5, 7, 9, 10),
    ScaleType.PENTATONIC: (0, 2, 4, 7, 9),
    ScaleType.BLUES: (0, 3, 5, 6, 7, 10),
}


@dataclass
class LfoParams:
    """LFO modulation parameters."""
    rate: float = 1.0
    depth: int = 0


class InstrumentKind(Enum):
    """Whether an instrument is a melodic synth or a drum."""
    SYNTH = auto()
    DRUM = auto()


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------

@dataclass
class Config:
    """Global configuration extracted from BPM, AUDIO_RATE, etc."""
    bpm: int = 120
    audio_rate: int = 16384
    control_rate: int = 64
    swing: int = 0
    humanize: int = 0
    key_root: Optional[str] = None
    key_scale: Optional[ScaleType] = None


# ---------------------------------------------------------------------------
# ADSR envelope parameters
# ---------------------------------------------------------------------------

@dataclass
class ADSRParams:
    """ADSR envelope timing in milliseconds and levels (0-255)."""
    attack_ms: int = 10
    decay_ms: int = 50
    sustain_ms: int = 200
    release_ms: int = 100
    attack_level: int = 255
    decay_level: int = 200


# ---------------------------------------------------------------------------
# Instrument definition
# ---------------------------------------------------------------------------

@dataclass
class InstrumentDef:
    """An instrument definition block.

    Attributes:
        name: User-chosen identifier (e.g. "bass_synth", "kick").
        kind: SYNTH or DRUM.
        wave: Waveform type.
        adsr: Envelope parameters (None for drums that use a simple decay).
        volume: Master volume 0-255.
        freq: Fixed frequency override (used for drums).
        decay_ms: Shorthand decay for drums.
    """
    name: str
    kind: InstrumentKind = InstrumentKind.SYNTH
    wave: WaveType = WaveType.SIN
    adsr: Optional[ADSRParams] = None
    volume: int = 200
    freq: Optional[int] = None
    decay_ms: Optional[int] = None
    cutoff: Optional[int] = None
    resonance: int = 0
    reverb: int = 0
    delay_time_ms: int = 0
    delay_feedback: int = 0
    glide_ms: int = 0
    pan: int = 127
    lfo_volume: Optional[LfoParams] = None
    lfo_pitch: Optional[LfoParams] = None
    voices: int = 1
    detune: int = 0
    chorus: int = 0


# ---------------------------------------------------------------------------
# Sequence / pattern events
# ---------------------------------------------------------------------------

@dataclass
class PlayNote:
    """A PLAY event: trigger an instrument with a note/chord and duration.

    Attributes:
        instrument: Name of the instrument to play.
        note: Note name in scientific notation (e.g. "C3") or None for drums.
        notes: List of notes for a chord (e.g. ["C4", "E4", "G4"]).
        duration_beats: Duration in beats (relative to BPM).
        line: Source line number for error reporting.
    """
    instrument: str
    note: Optional[str] = None
    notes: Optional[list[str]] = None
    duration_beats: float = 1.0
    velocity: Optional[int] = None
    reverb_override: Optional[int] = None
    delay_time_override: Optional[int] = None
    delay_feedback_override: Optional[int] = None
    line: int = 0


@dataclass
class RestEvent:
    """A REST event: silence for a given number of beats.

    Attributes:
        duration_beats: Duration of silence in beats.
        line: Source line number.
    """
    duration_beats: float = 1.0
    line: int = 0


@dataclass
class BeatEvent:
    """A single beat trigger within a PATTERN.

    Attributes:
        beat_position: Float beat position (1-based, e.g. 1, 2.5, 3).
        instrument: Instrument name to trigger.
        note: Note name for melodic instruments (None = use instrument's fixed freq).
        notes: List of notes for a chord (e.g. ["C4", "E4", "G4"]).
        duration_beats: Duration in beats (None = use instrument's decay_ms or default).
        line: Source line number.
    """
    beat_position: float = 1.0
    instrument: str = ""
    note: Optional[str] = None
    notes: Optional[list[str]] = None
    duration_beats: Optional[float] = None
    velocity: Optional[int] = None
    reverb_override: Optional[int] = None
    delay_time_override: Optional[int] = None
    delay_feedback_override: Optional[int] = None
    line: int = 0


# ---------------------------------------------------------------------------
# Containers
# ---------------------------------------------------------------------------

@dataclass
class Sequence:
    """A named sequence of PlayNote and RestEvent items.

    Attributes:
        name: Identifier for this sequence.
        events: Ordered list of PlayNote / RestEvent.
    """
    name: str
    events: list[PlayNote | RestEvent] = field(default_factory=list)


@dataclass
class Pattern:
    """A named drum pattern — a collection of BeatEvents within one bar.

    Attributes:
        name: Identifier for this pattern.
        beats_per_bar: How many beats in one bar (default 4 for 4/4 time).
        events: Unordered list of BeatEvents.
    """
    name: str
    beats_per_bar: int = 4
    events: list[BeatEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Arrangement
# ---------------------------------------------------------------------------

@dataclass
class PlaySequenceRef:
    """Reference to a named sequence in the arrangement.

    Attributes:
        sequence_name: Name of the sequence to play.
        line: Source line number.
    """
    sequence_name: str
    line: int = 0


@dataclass
class PlayPatternRef:
    """Reference to a named pattern in the arrangement.

    Attributes:
        pattern_name: Name of the pattern to play.
        line: Source line number.
    """
    pattern_name: str
    line: int = 0


@dataclass
class BPMChange:
    """A tempo change within the arrangement."""
    bpm: int = 120
    line: int = 0


@dataclass
class VolumeChange:
    """A master volume change within the arrangement."""
    volume: int = 200
    line: int = 0


@dataclass
class FadeIn:
    """Gradually ramp master volume from 0 to current over duration_beats."""
    duration_beats: float = 4.0
    line: int = 0


@dataclass
class FadeOut:
    """Gradually ramp master volume from current to 0 over duration_beats."""
    duration_beats: float = 4.0
    line: int = 0


@dataclass
class LoopBlock:
    """A LOOP N: ... block in the arrangement.

    Attributes:
        count: Number of repetitions (0 = infinite).
        body: List of arrangement items.
        line: Source line number.
    """
    count: int = 1
    body: list[PlaySequenceRef | PlayPatternRef | LoopBlock | PlayTogetherBlock | BPMChange | VolumeChange | FadeIn | FadeOut] = field(default_factory=list)
    line: int = 0


@dataclass
class PlayTogetherBlock:
    """A PLAY_TOGETHER: ... block — plays all children simultaneously.

    Attributes:
        body: List of arrangement items to play at the same time.
        line: Source line number.
    """
    body: list[PlaySequenceRef | PlayPatternRef | LoopBlock | BPMChange | VolumeChange] = field(default_factory=list)
    line: int = 0


# ---------------------------------------------------------------------------
# Program (root node)
# ---------------------------------------------------------------------------

@dataclass
class Program:
    """Root AST node representing the entire .mozzi file.

    Attributes:
        config: Global configuration.
        instruments: Dict of instrument name -> InstrumentDef.
        sequences: Dict of sequence name -> Sequence.
        patterns: Dict of pattern name -> Pattern.
        arrangement: List of top-level arrangement items.
    """
    config: Config = field(default_factory=Config)
    instruments: dict[str, InstrumentDef] = field(default_factory=dict)
    sequences: dict[str, Sequence] = field(default_factory=dict)
    patterns: dict[str, Pattern] = field(default_factory=dict)
    arrangement: list[PlaySequenceRef | PlayPatternRef | LoopBlock | PlayTogetherBlock | BPMChange | VolumeChange | FadeIn | FadeOut] = field(default_factory=list)
