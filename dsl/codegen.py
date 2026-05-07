"""
C++ code generator for the Mozzi DSL.

Transforms a validated Program AST into a complete Mozzi 2.0 sketch (.cpp)
that compiles for Arduino Uno via PlatformIO.

Architecture
------------
The generated sketch uses an event-list sequencer:

- A flat array of ``NoteEvent`` structs holds every note/rest in the
  arrangement (loops are unrolled at compile time in Python).
- ``updateControl()`` advances a step counter based on elapsed time
  (converted from beats via BPM) and triggers note-on / note-off on the
  appropriate oscillator + ADSR channel.
- ``updateAudio()`` sums all active oscillator outputs (scaled by their
  ADSR envelope) and returns a mono sample via ``MonoOutput::from8Bit()``.

Constraints honoured
--------------------
- No floats or division in ``updateAudio()``
- ``loop()`` contains only ``audioHook()``
- All timing via ``mozziMicros()``
- Integer arithmetic throughout audio path
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .ast_nodes import (
    ADSRParams,
    InstrumentDef,
    InstrumentKind,
    LoopBlock,
    Pattern,
    PlayNote,
    PlayPatternRef,
    PlaySequenceRef,
    Program,
    RestEvent,
    Sequence,
    WaveType,
)
from .notes import note_name_to_freq_int


# ---------------------------------------------------------------------------
# Wavetable mapping
# ---------------------------------------------------------------------------

@dataclass
class WaveTableInfo:
    """Mapping from a WaveType to Mozzi header, data array, and table size."""
    header: str
    data_name: str
    table_size: int


_WAVE_TABLE: dict[WaveType, WaveTableInfo] = {
    WaveType.SIN: WaveTableInfo(
        header="tables/sin2048_int8.h",
        data_name="SIN2048_DATA",
        table_size=2048,
    ),
    WaveType.SAW: WaveTableInfo(
        header="tables/saw2048_int8.h",
        data_name="SAW2048_DATA",
        table_size=2048,
    ),
    WaveType.SQUARE: WaveTableInfo(
        header="tables/square_no_alias_2048_int8.h",
        data_name="SQUARE_NO_ALIAS_2048_DATA",
        table_size=2048,
    ),
    WaveType.TRIANGLE: WaveTableInfo(
        header="tables/triangle2048_int8.h",
        data_name="TRIANGLE2048_DATA",
        table_size=2048,
    ),
    WaveType.NOISE: WaveTableInfo(
        header="tables/whitenoise8192_int8.h",
        data_name="WHITENOISE8192_DATA",
        table_size=8192,
    ),
}


# ---------------------------------------------------------------------------
# Flattened event for the sequencer
# ---------------------------------------------------------------------------

@dataclass
class FlatEvent:
    """A single event in the flattened sequencer timeline.

    Attributes:
        channel: Index into the instrument/oscillator arrays.
        freq: Frequency in Hz (0 for rest / drum with fixed freq).
        duration_ms: Duration in milliseconds.
        is_rest: True if this is a silence event.
        inst_name: Name of instrument (for comments).
        note_name: Original note name (for comments).
        simultaneous_with_next: If True, sequencer triggers next event
            immediately without waiting for duration to expire.
    """
    channel: int
    freq: int
    duration_ms: int
    is_rest: bool = False
    inst_name: str = ""
    note_name: str = ""
    simultaneous_with_next: bool = False


# ---------------------------------------------------------------------------
# Code generator
# ---------------------------------------------------------------------------

class CodeGenerator:
    """Generates a Mozzi 2.0 C++ sketch from a Program AST.

    Usage::

        code = CodeGenerator(program).generate()
    """

    def __init__(self, program: Program) -> None:
        """Initialize the code generator.

        Args:
            program: A validated Program AST.
        """
        self.program = program
        self.config = program.config

        # Build ordered list of instruments and channel index mapping
        self._instruments: list[InstrumentDef] = list(program.instruments.values())
        self._inst_index: dict[str, int] = {
            inst.name: i for i, inst in enumerate(self._instruments)
        }

        # Collect which wavetable types are needed
        self._needed_waves: set[WaveType] = set()
        for inst in self._instruments:
            self._needed_waves.add(inst.wave)

        # Identify drum channels with tonal waves (need pitch sweep)
        self._drum_tonal: list[bool] = [
            inst.kind == InstrumentKind.DRUM and inst.wave != WaveType.NOISE
            for inst in self._instruments
        ]
        self._has_drum_tonal = any(self._drum_tonal)

        # Flatten arrangement into a linear event list
        self._events: list[FlatEvent] = []
        self._flatten_arrangement(program.arrangement)

    # ----- flatten arrangement -----------------------------------------------

    def _beats_to_ms(self, beats: float) -> int:
        """Convert beats to milliseconds using the configured BPM.

        Args:
            beats: Duration in beats.

        Returns:
            Duration in milliseconds (integer).
        """
        ms_per_beat = 60000.0 / self.program.config.bpm
        return max(1, round(beats * ms_per_beat))

    def _flatten_arrangement(self, items: list) -> None:
        """Recursively flatten arrangement items into self._events."""
        for item in items:
            if isinstance(item, PlaySequenceRef):
                self._flatten_sequence(item.sequence_name)
            elif isinstance(item, PlayPatternRef):
                self._flatten_pattern(item.pattern_name)
            elif isinstance(item, LoopBlock):
                for _ in range(item.count):
                    self._flatten_arrangement(item.body)

    def _flatten_sequence(self, name: str) -> None:
        """Flatten a named sequence into events."""
        seq = self.program.sequences.get(name)
        if seq is None:
            return
        for ev in seq.events:
            if isinstance(ev, RestEvent):
                self._events.append(FlatEvent(
                    channel=0,
                    freq=0,
                    duration_ms=self._beats_to_ms(ev.duration_beats),
                    is_rest=True,
                ))
            elif isinstance(ev, PlayNote):
                ch = self._inst_index.get(ev.instrument, 0)
                inst = self.program.instruments.get(ev.instrument)
                freq = 0
                note = ev.note or ""

                if ev.note:
                    freq = note_name_to_freq_int(ev.note)
                elif inst is not None and inst.freq is not None:
                    freq = inst.freq

                self._events.append(FlatEvent(
                    channel=ch,
                    freq=freq,
                    duration_ms=self._beats_to_ms(ev.duration_beats),
                    is_rest=False,
                    inst_name=ev.instrument,
                    note_name=note,
                ))

    def _flatten_pattern(self, name: str) -> None:
        """Flatten a pattern into events, grouping simultaneous beats.

        Events at the same beat position are marked simultaneous so the
        sequencer triggers them all at once (true mixing).
        """
        from itertools import groupby

        pat = self.program.patterns.get(name)
        if pat is None:
            return
        sorted_events = sorted(pat.events, key=lambda e: e.beat_position)
        if not sorted_events:
            return

        groups = []
        for pos, grp in groupby(sorted_events, key=lambda e: round(e.beat_position, 3)):
            groups.append((pos, list(grp)))

        current_beat = 1.0
        for g_idx, (pos, group) in enumerate(groups):
            gap = pos - current_beat
            if gap > 0.01:
                self._events.append(FlatEvent(
                    channel=0, freq=0,
                    duration_ms=self._beats_to_ms(gap),
                    is_rest=True,
                ))

            if g_idx + 1 < len(groups):
                next_pos = groups[g_idx + 1][0]
            else:
                next_pos = pat.beats_per_bar + 1.0
            beat_gap_ms = self._beats_to_ms(next_pos - pos)

            for ev_idx, bev in enumerate(group):
                ch = self._inst_index.get(bev.instrument, 0)
                inst = self.program.instruments.get(bev.instrument)

                if bev.note:
                    freq = note_name_to_freq_int(bev.note)
                elif inst and inst.freq:
                    freq = inst.freq
                else:
                    freq = 60

                if bev.duration_beats is not None:
                    dur = self._beats_to_ms(bev.duration_beats)
                elif inst and inst.decay_ms:
                    dur = inst.decay_ms
                else:
                    dur = 80

                is_last = (ev_idx == len(group) - 1)
                self._events.append(FlatEvent(
                    channel=ch,
                    freq=freq,
                    duration_ms=beat_gap_ms if is_last else dur,
                    is_rest=False,
                    inst_name=bev.instrument,
                    note_name=bev.note or "",
                    simultaneous_with_next=not is_last,
                ))

            current_beat = next_pos

    # ----- C++ emission ------------------------------------------------------

    def generate(self) -> str:
        """Generate the full Mozzi 2.0 C++ sketch.

        Returns:
            Complete C++ source code as a string.
        """
        parts: list[str] = []
        parts.append(self._emit_header())
        parts.append(self._emit_config_macros())
        parts.append(self._emit_includes())
        parts.append(self._emit_globals())
        parts.append(self._emit_event_table())
        parts.append(self._emit_sequencer_state())
        parts.append(self._emit_trigger_helpers())
        parts.append(self._emit_setup())
        parts.append(self._emit_update_control())
        parts.append(self._emit_update_audio())
        parts.append(self._emit_loop())
        return "\n".join(parts)

    def _emit_header(self) -> str:
        """Emit the file header comment."""
        return (
            "// ============================================================\n"
            "// Auto-generated Mozzi 2.0 sketch\n"
            "// Produced by Mozzi DSL Compiler v0.1.0\n"
            "// Target: Arduino Uno (ATmega328P)\n"
            "// ============================================================\n"
        )

    def _emit_config_macros(self) -> str:
        """Emit Mozzi config macros (must come before #include <Mozzi.h>)."""
        lines = [
            f"#define MOZZI_AUDIO_RATE {self.config.audio_rate}",
            f"#define MOZZI_CONTROL_RATE {self.config.control_rate}",
            "",
        ]
        return "\n".join(lines)

    def _emit_includes(self) -> str:
        """Emit #include directives."""
        lines = ["#include <Mozzi.h>"]
        lines.append("#include <Oscil.h>")
        lines.append("#include <ADSR.h>")
        lines.append("")

        # Wavetable includes
        for wt in sorted(self._needed_waves, key=lambda w: w.name):
            info = _WAVE_TABLE[wt]
            lines.append(f"#include <{info.header}>")

        lines.append("")
        return "\n".join(lines)

    def _emit_globals(self) -> str:
        """Emit oscillator, ADSR, and volume declarations for each instrument."""
        n = len(self._instruments)
        lines = [
            "// ----- Instrument channels -----",
            f"#define NUM_CHANNELS {n}",
            "",
        ]

        for i, inst in enumerate(self._instruments):
            info = _WAVE_TABLE[inst.wave]
            lines.append(f"// Channel {i}: {inst.name} ({inst.kind.name})")
            lines.append(
                f"Oscil<{info.table_size}, MOZZI_AUDIO_RATE> osc{i}({info.data_name});"
            )
            lines.append(
                f"ADSR<MOZZI_CONTROL_RATE, MOZZI_AUDIO_RATE> env{i};"
            )
            lines.append("")

        lines.append("// Per-channel volume (0-255)")
        if n > 0:
            volumes = ", ".join(str(inst.volume) for inst in self._instruments)
            lines.append(f"const uint8_t channelVol[NUM_CHANNELS] = {{{volumes}}};")
        else:
            lines.append("const uint8_t channelVol[1] = {0};")
        lines.append("")

        # Track active state per channel
        lines.append("// Per-channel active flag")
        if n > 0:
            lines.append("bool channelActive[NUM_CHANNELS];")
        else:
            lines.append("bool channelActive[1];")
        lines.append("")

        # Frequency tracking for drum pitch sweep
        if self._has_drum_tonal and n > 0:
            lines.append("// Drum pitch sweep state")
            lines.append("uint16_t chanFreq[NUM_CHANNELS];")
            lines.append("uint16_t chanBaseFreq[NUM_CHANNELS];")
            lines.append("")

        return "\n".join(lines)

    def _emit_event_table(self) -> str:
        """Emit the flat event table as a PROGMEM struct array."""
        num = len(self._events)
        lines = [
            "// ----- Sequencer event table -----",
            "struct NoteEvent {",
            "    uint8_t channel;    // instrument channel index",
            "    uint16_t freq;      // frequency in Hz (0 = rest)",
            "    uint16_t duration;  // duration in ms",
            "    uint8_t isRest;     // 1 = rest, 0 = note",
            "    uint8_t simNext;    // 1 = trigger next event simultaneously",
            "};",
            "",
        ]

        if num == 0:
            lines.append("#define NUM_EVENTS 1")
            lines.append("")
            lines.append("const NoteEvent events[1] PROGMEM = {")
            lines.append("    {0, 0, 1000, 1, 0},  // empty — 1s of silence")
            lines.append("};")
        else:
            lines.append(f"#define NUM_EVENTS {num}")
            lines.append("")
            lines.append(f"const NoteEvent events[NUM_EVENTS] PROGMEM = {{")

            for ev in self._events:
                comment = ""
                if ev.is_rest:
                    comment = f"  // rest {ev.duration_ms}ms"
                elif ev.note_name:
                    comment = (
                        f"  // {ev.inst_name} {ev.note_name}"
                        f" ({ev.freq}Hz) {ev.duration_ms}ms"
                    )
                else:
                    comment = f"  // {ev.inst_name} {ev.freq}Hz {ev.duration_ms}ms"

                if ev.simultaneous_with_next:
                    comment += " [SIM]"

                rest_flag = 1 if ev.is_rest else 0
                sim_flag = 1 if ev.simultaneous_with_next else 0
                lines.append(
                    f"    {{{ev.channel}, {ev.freq}, {ev.duration_ms},"
                    f" {rest_flag}, {sim_flag}}},{comment}"
                )

            lines.append("};")

        lines.append("")
        return "\n".join(lines)

    def _emit_sequencer_state(self) -> str:
        """Emit sequencer state variables."""
        return (
            "// ----- Sequencer state -----\n"
            "uint16_t currentEvent = 0;\n"
            "uint16_t groupStart = 0;\n"
            "unsigned long eventStartTime = 0;\n"
            "bool eventTriggered = false;\n"
            "\n"
            "// Read event from PROGMEM\n"
            "NoteEvent readEvent(uint16_t idx) {\n"
            "    NoteEvent ev;\n"
            "    memcpy_P(&ev, &events[idx], sizeof(NoteEvent));\n"
            "    return ev;\n"
            "}\n"
            "\n"
        )

    def _emit_setup(self) -> str:
        """Emit setup() function."""
        lines = [
            "void setup() {",
            f"    startMozzi(MOZZI_CONTROL_RATE);",
            "",
        ]

        # Configure ADSR envelopes for each instrument
        for i, inst in enumerate(self._instruments):
            adsr = inst.adsr
            if adsr:
                lines.append(f"    // {inst.name} envelope")
                lines.append(
                    f"    env{i}.setADLevels({adsr.attack_level},"
                    f" {adsr.decay_level});"
                )
                lines.append(
                    f"    env{i}.setTimes({adsr.attack_ms}, {adsr.decay_ms},"
                    f" {adsr.sustain_ms}, {adsr.release_ms});"
                )
            else:
                # Default envelope for instruments without explicit ADSR
                if inst.kind == InstrumentKind.DRUM:
                    decay = inst.decay_ms if inst.decay_ms else 80
                    lines.append(f"    // {inst.name} drum envelope")
                    lines.append(f"    env{i}.setADLevels(255, 200);")
                    lines.append(
                        f"    env{i}.setTimes(4, {decay}, 0, {decay});"
                    )
                else:
                    lines.append(f"    // {inst.name} default envelope")
                    lines.append(f"    env{i}.setADLevels(255, 200);")
                    lines.append(f"    env{i}.setTimes(10, 50, 200, 100);")
            lines.append("")

        # Initialize channel active flags
        n = len(self._instruments)
        if n > 0:
            lines.append("    // Initialize channel state")
            lines.append("    for (uint8_t i = 0; i < NUM_CHANNELS; i++) {")
            lines.append("        channelActive[i] = false;")
            lines.append("    }")
            lines.append("")

        lines.append("    eventStartTime = mozziMicros();")
        lines.append("}")
        lines.append("")
        return "\n".join(lines)

    def _emit_trigger_helpers(self) -> str:
        """Emit triggerNoteOn/triggerNoteOff helper functions."""
        n = len(self._instruments)
        lines = [
            "// ----- Channel trigger helpers -----",
            "void triggerNoteOn(uint8_t ch, uint16_t freq) {",
        ]
        if n == 0:
            lines.append("    (void)ch; (void)freq;")
        elif n == 1:
            if self._drum_tonal[0]:
                lines += [
                    "    chanBaseFreq[0] = freq;",
                    "    chanFreq[0] = freq * 5;",
                    "    osc0.setFreq((int)chanFreq[0]);",
                    "    env0.noteOn(true);",
                    "    channelActive[0] = true;",
                ]
            else:
                lines += [
                    "    osc0.setFreq((int)freq);",
                    "    env0.noteOn(true);",
                    "    channelActive[0] = true;",
                ]
        else:
            for i in range(n):
                prefix = "if" if i == 0 else "} else if"
                lines.append(f"    {prefix} (ch == {i}) {{")
                if self._drum_tonal[i]:
                    lines.append(f"        chanBaseFreq[{i}] = freq;")
                    lines.append(f"        chanFreq[{i}] = freq * 5;")
                    lines.append(f"        osc{i}.setFreq((int)chanFreq[{i}]);")
                else:
                    lines.append(f"        osc{i}.setFreq((int)freq);")
                lines.append(f"        env{i}.noteOn(true);")
                lines.append(f"        channelActive[{i}] = true;")
            lines.append("    }")
        lines += ["}", ""]

        lines += [
            "void triggerNoteOff(uint8_t ch) {",
        ]
        if n == 0:
            lines.append("    (void)ch;")
        elif n == 1:
            lines += [
                "    env0.noteOff();",
                "    channelActive[0] = false;",
            ]
        else:
            for i in range(n):
                prefix = "if" if i == 0 else "} else if"
                lines.append(f"    {prefix} (ch == {i}) {{")
                lines.append(f"        env{i}.noteOff();")
                lines.append(f"        channelActive[{i}] = false;")
            lines.append("    }")
        lines += ["}", ""]

        return "\n".join(lines)

    def _emit_update_control(self) -> str:
        """Emit updateControl() -- sequencer logic with simultaneous group support."""
        n = len(self._instruments)

        lines = [
            "void updateControl() {",
            "    // Update all active envelopes",
        ]
        for i in range(n):
            lines.append(f"    env{i}.update();")
        lines.append("")

        # Drum pitch sweep — halve distance to base freq each control tick
        if self._has_drum_tonal:
            lines.append("    // Drum pitch sweep")
            for i in range(n):
                if self._drum_tonal[i]:
                    lines.append(f"    if (channelActive[{i}] && chanFreq[{i}] > chanBaseFreq[{i}]) {{")
                    lines.append(f"        chanFreq[{i}] = chanBaseFreq[{i}] + ((chanFreq[{i}] - chanBaseFreq[{i}]) >> 1);")
                    lines.append(f"        osc{i}.setFreq((int)chanFreq[{i}]);")
                    lines.append(f"    }}")
            lines.append("")

        lines += [
            "    if (currentEvent >= NUM_EVENTS) {",
            "        currentEvent = 0;",
            "        eventTriggered = false;",
            "        eventStartTime = mozziMicros();",
            "    }",
            "",
            "    NoteEvent ev = readEvent(currentEvent);",
            "    unsigned long now = mozziMicros();",
            "    unsigned long elapsed = now - eventStartTime;",
            "    unsigned long durationUs = (unsigned long)ev.duration * 1000UL;",
            "",
            "    if (!eventTriggered) {",
            "        groupStart = currentEvent;",
            "",
            "        // Trigger all simultaneous events in the group",
            "        do {",
            "            ev = readEvent(currentEvent);",
            "            if (!ev.isRest) {",
            "                triggerNoteOn(ev.channel, ev.freq);",
            "            }",
            "            if (!ev.simNext) break;",
            "            currentEvent++;",
            "        } while (currentEvent < NUM_EVENTS);",
            "",
            "        eventTriggered = true;",
            "        // Timing is based on the last event in the group",
            "        ev = readEvent(currentEvent);",
            "        durationUs = (unsigned long)ev.duration * 1000UL;",
            "    }",
            "",
            "    if (elapsed >= durationUs) {",
            "        // Note-off for all channels in the group",
            "        for (uint16_t i = groupStart; i <= currentEvent; i++) {",
            "            NoteEvent ge = readEvent(i);",
            "            if (!ge.isRest) {",
            "                triggerNoteOff(ge.channel);",
            "            }",
            "        }",
            "        currentEvent++;",
            "        eventTriggered = false;",
            "        eventStartTime = now;",
            "    }",
            "}",
            "",
        ]

        return "\n".join(lines)

    def _emit_update_audio(self) -> str:
        """Emit updateAudio() -- sum oscillator outputs with envelope scaling."""
        n = len(self._instruments)
        lines = [
            "AudioOutput updateAudio() {",
            "    int16_t sample = 0;",
            "",
        ]

        for i in range(n):
            lines.append(f"    if (channelActive[{i}]) {{")
            # Multiply oscillator sample (-128..127) by envelope (0..255),
            # then right-shift by 8 to get back to ~8-bit range.
            # Both multiplications use only integer arithmetic.
            lines.append(
                f"        int16_t s{i} ="
                f" ((int16_t)osc{i}.next()"
                f" * (int16_t)env{i}.next()) >> 8;"
            )
            # Apply volume scaling with bit shift instead of division
            lines.append(
                f"        s{i} = (s{i}"
                f" * (int16_t)channelVol[{i}]) >> 8;"
            )
            lines.append(f"        sample += s{i};")
            lines.append(f"    }}")
            lines.append("")

        # Clamp to int8_t range
        if n > 1:
            # Scale down to prevent clipping when multiple channels are active
            # Use right-shift by 1 for every doubling of channels
            shift = 0
            ch = n
            while ch > 1:
                shift += 1
                ch = (ch + 1) >> 1
            if shift > 0:
                lines.append(
                    f"    // Scale down to prevent clipping"
                    f" with {n} channels"
                )
                lines.append(f"    sample >>= {shift};")
                lines.append("")

        lines += [
            "    // Clamp to 8-bit signed range",
            "    if (sample > 127) sample = 127;",
            "    if (sample < -128) sample = -128;",
            "",
            "    return MonoOutput::from8Bit(sample);",
            "}",
            "",
        ]

        return "\n".join(lines)

    def _emit_loop(self) -> str:
        """Emit loop() -- must contain only audioHook()."""
        return (
            "void loop() {\n"
            "    audioHook();\n"
            "}\n"
        )


def generate(program: Program) -> str:
    """Convenience function: generate C++ from a Program AST.

    Args:
        program: A validated Program AST.

    Returns:
        Complete Mozzi 2.0 C++ sketch as a string.
    """
    return CodeGenerator(program).generate()
