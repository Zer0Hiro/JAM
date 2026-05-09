"""
Semantic analysis / validation pass for the Mozzi DSL AST.

Checks:
- All referenced instruments are defined.
- All referenced sequences/patterns are defined.
- Note names are valid scientific pitch notation.
- Durations are positive and not suspiciously short.
- ADSR values are within sane ranges for 8-bit AVR.
- Volume is 0-255.
- Warns on excessive polyphony (ATmega328 has only 2KB RAM).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ast_nodes import (
    BPMChange,
    InstrumentKind,
    LoopBlock,
    PlayNote,
    PlayPatternRef,
    PlaySequenceRef,
    PlayTogetherBlock,
    Program,
    VolumeChange,
)
from .notes import is_valid_note, note_name_to_midi


@dataclass
class Diagnostic:
    """A single validation diagnostic (error or warning).

    Attributes:
        level: "error" or "warning".
        message: Human-readable message.
        line: Source line number (0 = unknown).
    """
    level: str
    message: str
    line: int = 0

    def __str__(self) -> str:
        loc = f"line {self.line}: " if self.line else ""
        return f"[{self.level.upper()}] {loc}{self.message}"


@dataclass
class ValidationResult:
    """Collected diagnostics from semantic analysis.

    Attributes:
        diagnostics: List of all diagnostics.
    """
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def errors(self) -> list[Diagnostic]:
        """Return only error-level diagnostics."""
        return [d for d in self.diagnostics if d.level == "error"]

    @property
    def warnings(self) -> list[Diagnostic]:
        """Return only warning-level diagnostics."""
        return [d for d in self.diagnostics if d.level == "warning"]

    @property
    def ok(self) -> bool:
        """True if there are no errors (warnings are acceptable)."""
        return len(self.errors) == 0

    def _add(self, level: str, msg: str, line: int = 0) -> None:
        self.diagnostics.append(Diagnostic(level=level, message=msg, line=line))

    def error(self, msg: str, line: int = 0) -> None:
        """Record an error."""
        self._add("error", msg, line)

    def warn(self, msg: str, line: int = 0) -> None:
        """Record a warning."""
        self._add("warning", msg, line)


# Maximum number of simultaneous synth channels recommended for ATmega328
_MAX_RECOMMENDED_SYNTHS = 4


def validate(program: Program) -> ValidationResult:
    """Run semantic analysis on a parsed Program AST.

    Args:
        program: The Program AST to validate.

    Returns:
        A ValidationResult containing any errors or warnings.
    """
    result = ValidationResult()
    inst_names = set(program.instruments.keys())
    seq_names = set(program.sequences.keys())
    pat_names = set(program.patterns.keys())

    # --- Check instrument definitions ---
    synth_count = 0
    for name, inst in program.instruments.items():
        if inst.volume < 0 or inst.volume > 255:
            result.error(f"Instrument '{name}': volume {inst.volume} out of range 0-255")
        if inst.adsr:
            adsr = inst.adsr
            for param_name, val in [
                ("attack_ms", adsr.attack_ms),
                ("decay_ms", adsr.decay_ms),
                ("sustain_ms", adsr.sustain_ms),
                ("release_ms", adsr.release_ms),
            ]:
                if val < 0:
                    result.error(f"Instrument '{name}': ADSR {param_name} is negative")
                if 0 < val < 5:
                    result.warn(
                        f"Instrument '{name}': ADSR {param_name}={val}ms is very short "
                        "— at 64Hz control rate each step is ~16ms"
                    )
        if inst.kind == InstrumentKind.SYNTH:
            synth_count += 1
        if inst.kind == InstrumentKind.DRUM and inst.freq is not None and inst.freq <= 0:
            result.error(f"Instrument '{name}': drum frequency must be positive")
        if inst.decay_ms is not None and inst.decay_ms < 0:
            result.error(f"Instrument '{name}': decay must be non-negative")
        if inst.cutoff is not None:
            if inst.cutoff < 20 or inst.cutoff > 20000:
                result.error(f"Instrument '{name}': cutoff {inst.cutoff} out of range 20-20000 Hz")
        if inst.resonance < 0 or inst.resonance > 255:
            result.error(f"Instrument '{name}': resonance {inst.resonance} out of range 0-255")
        if inst.reverb < 0 or inst.reverb > 255:
            result.error(f"Instrument '{name}': reverb {inst.reverb} out of range 0-255")
        if inst.delay_time_ms < 0 or inst.delay_time_ms > 2000:
            result.error(f"Instrument '{name}': delay time {inst.delay_time_ms} out of range 0-2000 ms")
        if inst.delay_feedback < 0 or inst.delay_feedback > 255:
            result.error(f"Instrument '{name}': delay feedback {inst.delay_feedback} out of range 0-255")
        if inst.glide_ms < 0:
            result.error(f"Instrument '{name}': glide must be non-negative")
        if inst.glide_ms > 1000:
            result.warn(f"Instrument '{name}': glide {inst.glide_ms}ms is very slow")
        if inst.kind == InstrumentKind.DRUM and inst.glide_ms > 0:
            result.warn(f"Instrument '{name}': glide on a drum instrument may sound unexpected")
        if inst.pan < 0 or inst.pan > 255:
            result.error(f"Instrument '{name}': pan {inst.pan} out of range 0-255")

    if synth_count > _MAX_RECOMMENDED_SYNTHS:
        result.warn(
            f"{synth_count} synth instruments defined — ATmega328 has only 2KB RAM; "
            f"consider using {_MAX_RECOMMENDED_SYNTHS} or fewer"
        )

    # --- Check sequences ---
    for seq_name, seq in program.sequences.items():
        for ev in seq.events:
            if isinstance(ev, PlayNote):
                if ev.instrument not in inst_names:
                    result.error(
                        f"Sequence '{seq_name}': instrument '{ev.instrument}' is not defined",
                        ev.line,
                    )
                if ev.note is not None:
                    if not is_valid_note(ev.note):
                        result.error(
                            f"Sequence '{seq_name}': invalid note '{ev.note}'",
                            ev.line,
                        )
                    else:
                        midi = note_name_to_midi(ev.note)
                        if midi < 21 or midi > 108:
                            result.warn(
                                f"Sequence '{seq_name}': note '{ev.note}' (MIDI {midi}) "
                                "is outside the typical piano range",
                                ev.line,
                            )
                if ev.notes:
                    if len(ev.notes) > 4:
                        result.warn(
                            f"Sequence '{seq_name}': chord with {len(ev.notes)} notes "
                            "— ATmega328 may not have enough RAM for this many voices",
                            ev.line,
                        )
                    for cn in ev.notes:
                        if not is_valid_note(cn):
                            result.error(
                                f"Sequence '{seq_name}': invalid chord note '{cn}'",
                                ev.line,
                            )
                        else:
                            midi = note_name_to_midi(cn)
                            if midi < 21 or midi > 108:
                                result.warn(
                                    f"Sequence '{seq_name}': chord note '{cn}' (MIDI {midi}) "
                                    "is outside the typical piano range",
                                    ev.line,
                                )
                if ev.duration_beats <= 0:
                    result.error(
                        f"Sequence '{seq_name}': duration must be positive",
                        ev.line,
                    )
                if ev.velocity is not None and (ev.velocity < 0 or ev.velocity > 255):
                    result.error(
                        f"Sequence '{seq_name}': velocity {ev.velocity} out of range 0-255",
                        ev.line,
                    )

    # --- Check patterns ---
    for pat_name, pat in program.patterns.items():
        for ev in pat.events:
            if ev.instrument not in inst_names:
                result.error(
                    f"Pattern '{pat_name}': instrument '{ev.instrument}' is not defined",
                    ev.line,
                )
            if ev.note is not None:
                if not is_valid_note(ev.note):
                    result.error(
                        f"Pattern '{pat_name}': invalid note '{ev.note}'",
                        ev.line,
                    )
                else:
                    midi = note_name_to_midi(ev.note)
                    if midi < 21 or midi > 108:
                        result.warn(
                            f"Pattern '{pat_name}': note '{ev.note}' (MIDI {midi}) "
                            "is outside the typical piano range",
                            ev.line,
                        )
            if ev.notes:
                if len(ev.notes) > 4:
                    result.warn(
                        f"Pattern '{pat_name}': chord with {len(ev.notes)} notes "
                        "— ATmega328 may not have enough RAM for this many voices",
                        ev.line,
                    )
                for cn in ev.notes:
                    if not is_valid_note(cn):
                        result.error(
                            f"Pattern '{pat_name}': invalid chord note '{cn}'",
                            ev.line,
                        )
                    else:
                        midi = note_name_to_midi(cn)
                        if midi < 21 or midi > 108:
                            result.warn(
                                f"Pattern '{pat_name}': chord note '{cn}' (MIDI {midi}) "
                                "is outside the typical piano range",
                                ev.line,
                            )
            if ev.duration_beats is not None and ev.duration_beats <= 0:
                result.error(
                    f"Pattern '{pat_name}': beat duration must be positive",
                    ev.line,
                )
            inst = program.instruments.get(ev.instrument)
            if (inst and inst.kind == InstrumentKind.SYNTH
                    and ev.note is None and ev.notes is None and inst.freq is None):
                result.warn(
                    f"Pattern '{pat_name}': synth '{ev.instrument}' has no note or FREQ "
                    "— will use default 60Hz",
                    ev.line,
                )
            if ev.beat_position < 1 or ev.beat_position > pat.beats_per_bar + 1:
                result.warn(
                    f"Pattern '{pat_name}': beat {ev.beat_position} may be outside "
                    f"the {pat.beats_per_bar}-beat bar",
                    ev.line,
                )
            if ev.velocity is not None and (ev.velocity < 0 or ev.velocity > 255):
                result.error(
                    f"Pattern '{pat_name}': velocity {ev.velocity} out of range 0-255",
                    ev.line,
                )

    # --- Check arrangement references ---
    _check_arrangement(program.arrangement, seq_names, pat_names, result)

    # --- Config checks ---
    if program.config.bpm <= 0:
        result.error("BPM must be positive")
    if program.config.bpm > 300:
        result.warn(f"BPM {program.config.bpm} is very fast — may exceed AVR timing budget")
    if program.config.audio_rate not in (16384, 32768):
        result.warn(
            f"AUDIO_RATE {program.config.audio_rate} is non-standard; "
            "Mozzi defaults to 16384 or 32768"
        )

    return result


def _check_arrangement(
    items: list,
    seq_names: set[str],
    pat_names: set[str],
    result: ValidationResult,
) -> None:
    """Recursively validate arrangement items."""
    for item in items:
        if isinstance(item, PlaySequenceRef):
            if item.sequence_name not in seq_names:
                result.error(
                    f"Arrangement references undefined sequence '{item.sequence_name}'",
                    item.line,
                )
        elif isinstance(item, PlayPatternRef):
            if item.pattern_name not in pat_names:
                result.error(
                    f"Arrangement references undefined pattern '{item.pattern_name}'",
                    item.line,
                )
        elif isinstance(item, LoopBlock):
            if item.count <= 0:
                result.error("LOOP count must be positive", item.line)
            _check_arrangement(item.body, seq_names, pat_names, result)
        elif isinstance(item, PlayTogetherBlock):
            if len(item.body) < 2:
                result.warn(
                    "PLAY_TOGETHER with fewer than 2 items — use PLAY_SEQUENCE/PLAY_PATTERN directly",
                    item.line,
                )
            _check_arrangement(item.body, seq_names, pat_names, result)
        elif isinstance(item, BPMChange):
            if item.bpm <= 0:
                result.error("BPM change must be positive", item.line)
            if item.bpm > 300:
                result.warn(f"BPM {item.bpm} is very fast", item.line)
        elif isinstance(item, VolumeChange):
            if item.volume < 0 or item.volume > 255:
                result.error(f"VOLUME {item.volume} out of range 0-255", item.line)
