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
    BeatEvent,
    InstrumentDef,
    InstrumentKind,
    LoopBlock,
    Pattern,
    PlayNote,
    PlayPatternRef,
    PlaySequenceRef,
    PlayTogetherBlock,
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

    def __init__(self, program: Program, audio_pin: Optional[int] = None) -> None:
        """Initialize the code generator.

        Args:
            program: A validated Program AST.
            audio_pin: Optional GPIO pin number for PWM audio output (ESP32).
        """
        self.program = program
        self.config = program.config
        self.audio_pin = audio_pin

        # Build ordered list of instruments and channel index mapping
        self._instruments: list[InstrumentDef] = list(program.instruments.values())
        self._inst_index: dict[str, int] = {
            inst.name: i for i, inst in enumerate(self._instruments)
        }

        # Create voice channels for chord support
        self._voice_channels: dict[str, list[int]] = {}
        self._create_voice_channels(program)

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

    def _create_voice_channels(self, program: Program) -> None:
        """Scan for chords and create clone instrument channels for extra voices."""
        max_voices: dict[str, int] = {}
        for seq in program.sequences.values():
            for ev in seq.events:
                if isinstance(ev, PlayNote) and ev.notes:
                    max_voices[ev.instrument] = max(
                        max_voices.get(ev.instrument, 1), len(ev.notes)
                    )
        for pat in program.patterns.values():
            for bev in pat.events:
                if bev.notes:
                    max_voices[bev.instrument] = max(
                        max_voices.get(bev.instrument, 1), len(bev.notes)
                    )
        for inst_name, num_voices in max_voices.items():
            if num_voices <= 1:
                continue
            base_inst = program.instruments[inst_name]
            channels = [self._inst_index[inst_name]]
            for v in range(1, num_voices):
                clone = InstrumentDef(
                    name=f"{inst_name}_v{v}",
                    kind=base_inst.kind,
                    wave=base_inst.wave,
                    adsr=base_inst.adsr,
                    volume=base_inst.volume,
                    freq=base_inst.freq,
                    decay_ms=base_inst.decay_ms,
                )
                new_idx = len(self._instruments)
                self._instruments.append(clone)
                self._inst_index[clone.name] = new_idx
                channels.append(new_idx)
            self._voice_channels[inst_name] = channels

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
            elif isinstance(item, PlayTogetherBlock):
                self._flatten_play_together(item)

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
                if ev.notes:
                    channels = self._voice_channels.get(
                        ev.instrument,
                        [self._inst_index.get(ev.instrument, 0)],
                    )
                    for i, note_name in enumerate(ev.notes):
                        ch = channels[min(i, len(channels) - 1)]
                        is_last = (i == len(ev.notes) - 1)
                        self._events.append(FlatEvent(
                            channel=ch,
                            freq=note_name_to_freq_int(note_name),
                            duration_ms=self._beats_to_ms(ev.duration_beats),
                            is_rest=False,
                            inst_name=ev.instrument,
                            note_name=note_name,
                            simultaneous_with_next=not is_last,
                        ))
                else:
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

            # Expand chords within group into individual items
            expanded: list[tuple[int, str, BeatEvent]] = []
            for bev in group:
                if bev.notes:
                    channels = self._voice_channels.get(
                        bev.instrument,
                        [self._inst_index.get(bev.instrument, 0)],
                    )
                    for i, note_name in enumerate(bev.notes):
                        ch = channels[min(i, len(channels) - 1)]
                        expanded.append((ch, note_name, bev))
                else:
                    ch = self._inst_index.get(bev.instrument, 0)
                    expanded.append((ch, bev.note or "", bev))

            for ev_idx, (ch, note_name, bev) in enumerate(expanded):
                inst = self.program.instruments.get(bev.instrument)

                if note_name:
                    freq = note_name_to_freq_int(note_name)
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

                is_last = (ev_idx == len(expanded) - 1)
                self._events.append(FlatEvent(
                    channel=ch,
                    freq=freq,
                    duration_ms=beat_gap_ms if is_last else dur,
                    is_rest=False,
                    inst_name=bev.instrument,
                    note_name=note_name,
                    simultaneous_with_next=not is_last,
                ))

            current_beat = next_pos

    # ----- play together -----------------------------------------------------

    @staticmethod
    def _events_to_absolute(events: list[FlatEvent]) -> list[tuple[int, FlatEvent]]:
        """Convert sequential FlatEvents to (absolute_time_ms, event) pairs."""
        abs_events: list[tuple[int, FlatEvent]] = []
        t = 0
        for ev in events:
            if ev.is_rest:
                if not ev.simultaneous_with_next:
                    t += ev.duration_ms
            else:
                abs_events.append((t, ev))
                if not ev.simultaneous_with_next:
                    t += ev.duration_ms
        return abs_events

    def _flatten_play_together(self, block: PlayTogetherBlock) -> None:
        """Flatten a PLAY_TOGETHER block by merging child timelines."""
        child_timelines: list[list[FlatEvent]] = []
        for child in block.body:
            saved = len(self._events)
            if isinstance(child, PlaySequenceRef):
                self._flatten_sequence(child.sequence_name)
            elif isinstance(child, PlayPatternRef):
                self._flatten_pattern(child.pattern_name)
            elif isinstance(child, LoopBlock):
                for _ in range(child.count):
                    self._flatten_arrangement(child.body)
            elif isinstance(child, PlayTogetherBlock):
                self._flatten_play_together(child)
            child_events = self._events[saved:]
            self._events = self._events[:saved]
            child_timelines.append(child_events)

        all_abs: list[tuple[int, FlatEvent]] = []
        for child_events in child_timelines:
            all_abs.extend(self._events_to_absolute(child_events))

        all_abs.sort(key=lambda x: x[0])
        if not all_abs:
            return

        from itertools import groupby

        groups: list[tuple[int, list[FlatEvent]]] = []
        for t, grp in groupby(all_abs, key=lambda x: x[0]):
            groups.append((t, [ev for _, ev in grp]))

        for g_idx, (start, group) in enumerate(groups):
            if g_idx == 0 and start > 0:
                self._events.append(FlatEvent(
                    channel=0, freq=0, duration_ms=start, is_rest=True,
                ))
            elif g_idx > 0:
                gap = start - groups[g_idx - 1][0]
                prev_group = groups[g_idx - 1][1]
                prev_duration = prev_group[-1].duration_ms if prev_group else 0
                rest_gap = gap - prev_duration
                if rest_gap > 0:
                    self._events.append(FlatEvent(
                        channel=0, freq=0, duration_ms=rest_gap, is_rest=True,
                    ))

            if g_idx + 1 < len(groups):
                next_start = groups[g_idx + 1][0]
            else:
                next_start = start + max(ev.duration_ms for ev in group)
            beat_gap = max(1, next_start - start)

            for ev_idx, ev in enumerate(group):
                is_last = ev_idx == len(group) - 1
                self._events.append(FlatEvent(
                    channel=ev.channel,
                    freq=ev.freq,
                    duration_ms=beat_gap if is_last else ev.duration_ms,
                    is_rest=False,
                    inst_name=ev.inst_name,
                    note_name=ev.note_name,
                    simultaneous_with_next=not is_last,
                ))

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
        ]
        if self.audio_pin is not None:
            if self.audio_pin in (25, 26):
                lines.append("#define MOZZI_OUTPUT_MODE MOZZI_OUTPUT_I2S_DAC")
            else:
                lines.append("#define MOZZI_OUTPUT_MODE MOZZI_OUTPUT_PWM")
                lines.append(f"#define MOZZI_AUDIO_PIN_1 {self.audio_pin}")
        lines.append("")
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
            "// ----- Hardware pins -----\n"
            "#define BTN_PLAY  18\n"
            "#define BTN_RESTART 19\n"
            "#define POT_VOL   32\n"
            "#define POT_FREQ  34\n"
            "\n"
            "// ----- Button state -----\n"
            "bool playing = false;\n"
            "bool lastBtn1 = HIGH;\n"
            "bool lastBtn2 = HIGH;\n"
            "unsigned long lastDebounce1 = 0;\n"
            "unsigned long lastDebounce2 = 0;\n"
            "uint8_t masterVol = 255;\n"
            "\n"
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
            "    Serial.begin(115200);",
            "    Serial.println(\"JEM sketch booted\");",
            "    pinMode(BTN_PLAY, INPUT_PULLUP);",
            "    pinMode(BTN_RESTART, INPUT_PULLUP);",
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
            "    // Read volume pot (GPIO 32)",
            "    int potRaw = mozziAnalogRead(POT_VOL);",
            "    masterVol = (potRaw < 10) ? 255 : map(potRaw, 0, 4095, 0, 255);",
            "",
            "    // BTN_PLAY (GPIO 18) — toggle play/stop",
            "    bool btn1 = digitalRead(BTN_PLAY);",
            "    if (btn1 == LOW && lastBtn1 == HIGH",
            "        && (millis() - lastDebounce1 > 50)) {",
            "        lastDebounce1 = millis();",
            "        playing = !playing;",
            "        Serial.print(\"BTN_PLAY -> playing=\");",
            "        Serial.println(playing);",
            "        if (playing) {",
            "            currentEvent = 0;",
            "            eventTriggered = false;",
            "            eventStartTime = mozziMicros();",
            "        }",
            "    }",
            "    lastBtn1 = btn1;",
            "",
            "    // BTN_RESTART (GPIO 19) — restart from beginning",
            "    bool btn2 = digitalRead(BTN_RESTART);",
            "    if (btn2 == LOW && lastBtn2 == HIGH",
            "        && (millis() - lastDebounce2 > 50)) {",
            "        lastDebounce2 = millis();",
            "        currentEvent = 0;",
            "        eventTriggered = false;",
            "        eventStartTime = mozziMicros();",
            "        playing = true;",
            "    }",
            "    lastBtn2 = btn2;",
            "",
            "    if (!playing) return;",
            "",
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
            "        playing = false;",
            "        currentEvent = 0;",
            "        eventTriggered = false;",
            "        return;",
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
            "    // Apply master volume from pot",
            "    sample = (sample * (int16_t)masterVol) >> 8;",
            "",
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


def generate(program: Program, audio_pin: Optional[int] = None) -> str:
    """Convenience function: generate C++ from a Program AST.

    Args:
        program: A validated Program AST.
        audio_pin: Optional GPIO pin number for PWM audio output (ESP32).

    Returns:
        Complete Mozzi 2.0 C++ sketch as a string.
    """
    return CodeGenerator(program, audio_pin=audio_pin).generate()
