"""
WAV output backend for the Mozzi DSL.

Renders a Program AST to a .wav file using pure Python (stdlib only).
This allows previewing the composition on a computer without Arduino hardware.

The renderer mimics the Mozzi sequencer architecture:
- Oscillators produce basic waveforms (sin, saw, square, triangle, noise)
- ADSR envelopes shape amplitude over time
- Events are flattened and sequenced identically to the C++ codegen

Limitations compared to actual Mozzi output:
- Uses 16-bit 44.1kHz audio (not 8-bit 16384Hz like Mozzi)
- Envelope timing is more precise (floating point, not control-rate quantised)
- No analog PWM filtering — output is cleaner than real Arduino
"""

from __future__ import annotations

import math
import random
import struct
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ast_nodes import (
    ADSRParams,
    BeatEvent,
    BPMChange,
    FadeIn,
    FadeOut,
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
    VolumeChange,
    WaveType,
)
from .notes import note_name_to_freq


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WAV_SAMPLE_RATE = 44100
WAV_BIT_DEPTH = 16
WAV_CHANNELS = 1  # mono, matching Mozzi mono output


# ---------------------------------------------------------------------------
# Simple oscillator implementations
# ---------------------------------------------------------------------------

def _sin_sample(phase: float) -> float:
    """Sine oscillator. Phase is 0..1. Returns -1..1."""
    return math.sin(2.0 * math.pi * phase)


def _saw_sample(phase: float) -> float:
    """Sawtooth oscillator. Phase is 0..1. Returns -1..1."""
    return 2.0 * phase - 1.0


def _square_sample(phase: float) -> float:
    """Square wave oscillator. Phase is 0..1. Returns -1 or 1."""
    return 1.0 if phase < 0.5 else -1.0


def _triangle_sample(phase: float) -> float:
    """Triangle wave oscillator. Phase is 0..1. Returns -1..1."""
    if phase < 0.25:
        return 4.0 * phase
    elif phase < 0.75:
        return 2.0 - 4.0 * phase
    else:
        return -4.0 + 4.0 * phase


def _noise_sample(_phase: float) -> float:
    """White noise generator. Phase is ignored. Returns -1..1."""
    return random.uniform(-1.0, 1.0)


_OSCILLATORS = {
    WaveType.SIN: _sin_sample,
    WaveType.SAW: _saw_sample,
    WaveType.SQUARE: _square_sample,
    WaveType.TRIANGLE: _triangle_sample,
    WaveType.NOISE: _noise_sample,
}


class KarplusStrong:
    """Karplus-Strong plucked string synthesis."""

    def __init__(self, freq: float, decay_ms: int = 0):
        buf_len = max(2, int(WAV_SAMPLE_RATE / max(freq, 20.0)))
        self.buffer = [random.uniform(-1.0, 1.0) for _ in range(buf_len)]
        self.length = buf_len
        self.ptr = 0
        self.feedback = min(0.999, 0.9 + (decay_ms or 0) / 10000.0)

    def next_sample(self) -> float:
        out = self.buffer[self.ptr]
        nxt = (self.ptr + 1) % self.length
        self.buffer[self.ptr] = self.feedback * (self.buffer[self.ptr] + self.buffer[nxt]) * 0.5
        self.ptr = nxt
        return out


# ---------------------------------------------------------------------------
# ADSR envelope
# ---------------------------------------------------------------------------

@dataclass
class ADSREnvelope:
    """Simple ADSR envelope generator.

    Levels are 0.0..1.0, times in seconds.
    """
    attack_s: float = 0.01
    decay_s: float = 0.05
    sustain_level: float = 0.8
    release_s: float = 0.1
    attack_level: float = 1.0
    decay_level: float = 0.8

    @staticmethod
    def from_params(params: Optional[ADSRParams]) -> ADSREnvelope:
        """Create an ADSREnvelope from AST ADSRParams.

        Args:
            params: AST ADSR parameters, or None for defaults.

        Returns:
            Configured ADSREnvelope.
        """
        if params is None:
            return ADSREnvelope()
        return ADSREnvelope(
            attack_s=params.attack_ms / 1000.0,
            decay_s=params.decay_ms / 1000.0,
            sustain_level=params.decay_level / 255.0,
            release_s=params.release_ms / 1000.0,
            attack_level=params.attack_level / 255.0,
            decay_level=params.decay_level / 255.0,
        )

    def amplitude_at(self, t: float, note_dur_s: float) -> float:
        """Compute envelope amplitude at time t within a note.

        Args:
            t: Time in seconds since note-on.
            note_dur_s: Total note duration in seconds (note-off at this point).

        Returns:
            Amplitude multiplier 0.0..1.0.
        """
        if t < 0:
            return 0.0

        # Attack phase
        if t < self.attack_s:
            if self.attack_s > 0:
                return self.attack_level * (t / self.attack_s)
            return self.attack_level

        # Decay phase
        t_after_attack = t - self.attack_s
        if t_after_attack < self.decay_s:
            if self.decay_s > 0:
                frac = t_after_attack / self.decay_s
                return self.attack_level + (self.decay_level - self.attack_level) * frac
            return self.decay_level

        # Sustain phase — hold until note-off
        if t < note_dur_s:
            return self.sustain_level

        # Release phase
        t_release = t - note_dur_s
        if t_release < self.release_s:
            if self.release_s > 0:
                return self.sustain_level * (1.0 - t_release / self.release_s)
            return 0.0

        return 0.0


# ---------------------------------------------------------------------------
# Flattened event (reused from codegen concept)
# ---------------------------------------------------------------------------

@dataclass
class WavEvent:
    """A single event for the WAV renderer.

    Attributes:
        inst_index: Index into the instrument list.
        freq: Frequency in Hz (0 for rest).
        duration_s: Duration in seconds.
        is_rest: True if this is a silence event.
        simultaneous_with_next: If True, this event plays at the same
            time as the next event (grouped for mixing).
    """
    inst_index: int
    freq: float
    duration_s: float
    is_rest: bool = False
    simultaneous_with_next: bool = False
    velocity: float = 1.0
    is_bpm_change: bool = False
    new_bpm: int = 0
    is_volume_change: bool = False
    new_volume: int = 0
    is_fade: bool = False
    fade_direction: int = 0  # 1 = fade in, -1 = fade out
    fade_duration_s: float = 0.0
    reverb_override: Optional[int] = None
    delay_time_override: Optional[int] = None
    delay_feedback_override: Optional[int] = None


# ---------------------------------------------------------------------------
# WAV renderer
# ---------------------------------------------------------------------------

class WavRenderer:
    """Renders a Program AST to a WAV file.

    Usage::

        renderer = WavRenderer(program)
        renderer.render("output.wav")
    """

    def __init__(self, program: Program) -> None:
        """Initialize the renderer.

        Args:
            program: A validated Program AST.
        """
        self.program = program
        self.config = program.config

        self._instruments: list[InstrumentDef] = list(program.instruments.values())
        self._inst_index: dict[str, int] = {
            inst.name: i for i, inst in enumerate(self._instruments)
        }

        # Create voice channels for chord support
        self._voice_channels: dict[str, list[int]] = {}
        self._create_voice_channels(program)

        # Build envelopes for each instrument (including chord voice clones)
        self._envelopes: list[ADSREnvelope] = []
        for inst in self._instruments:
            if inst.adsr:
                self._envelopes.append(ADSREnvelope.from_params(inst.adsr))
            elif inst.kind == InstrumentKind.DRUM:
                decay = (inst.decay_ms or 80) / 1000.0
                self._envelopes.append(ADSREnvelope(
                    attack_s=0.004,
                    decay_s=decay,
                    sustain_level=0.0,
                    release_s=decay,
                    attack_level=1.0,
                    decay_level=0.8,
                ))
            else:
                self._envelopes.append(ADSREnvelope())

        # Build volume scaling (0.0..1.0) per instrument
        self._volumes: list[float] = [inst.volume / 255.0 for inst in self._instruments]

        # Stereo mode
        self._is_stereo = any(inst.pan != 127 for inst in self._instruments)
        self._pans: list[float] = [(inst.pan - 127) / 128.0 for inst in self._instruments]

        # Current BPM (mutable for dynamic automation)
        self._current_bpm = program.config.bpm

        # Swing & humanize
        self._swing = program.config.swing
        self._humanize = program.config.humanize
        self._humanize_rng = random.Random(hash(str(program.config.bpm)))

        # Flatten arrangement
        self._events: list[WavEvent] = []
        self._flatten_arrangement(program.arrangement)

        # Apply swing and humanize to event timings
        if self._swing > 0 or self._humanize > 0:
            self._apply_swing_humanize()

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
                    cutoff=base_inst.cutoff,
                    resonance=base_inst.resonance,
                    reverb=base_inst.reverb,
                    delay_time_ms=base_inst.delay_time_ms,
                    delay_feedback=base_inst.delay_feedback,
                    glide_ms=base_inst.glide_ms,
                    pan=base_inst.pan,
                    lfo_volume=base_inst.lfo_volume,
                    lfo_pitch=base_inst.lfo_pitch,
                    voices=base_inst.voices,
                    detune=base_inst.detune,
                    chorus=base_inst.chorus,
                )
                new_idx = len(self._instruments)
                self._instruments.append(clone)
                self._inst_index[clone.name] = new_idx
                channels.append(new_idx)
            self._voice_channels[inst_name] = channels

    def _beats_to_s(self, beats: float) -> float:
        """Convert beats to seconds using current BPM."""
        return beats * 60.0 / self._current_bpm

    def _flatten_arrangement(self, items: list) -> None:
        """Recursively flatten arrangement into WavEvents."""
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
            elif isinstance(item, BPMChange):
                self._current_bpm = item.bpm
            elif isinstance(item, VolumeChange):
                self._events.append(WavEvent(
                    inst_index=0, freq=0.0, duration_s=0.0,
                    is_rest=True, is_volume_change=True, new_volume=item.volume,
                ))
            elif isinstance(item, (FadeIn, FadeOut)):
                direction = 1 if isinstance(item, FadeIn) else -1
                dur_s = self._beats_to_s(item.duration_beats)
                self._events.append(WavEvent(
                    inst_index=0, freq=0.0, duration_s=0.0,
                    is_rest=True, is_fade=True,
                    fade_direction=direction, fade_duration_s=dur_s,
                ))

    def _apply_swing_humanize(self) -> None:
        """Adjust event durations in-place for swing and humanize."""
        if not self._events:
            return
        swing_ratio = 0.5 + (self._swing / 200.0)
        beat_s = 60.0 / self._current_bpm
        half_beat_s = beat_s / 2.0
        accumulated = 0.0
        is_offbeat = False
        for ev in self._events:
            if ev.is_volume_change or ev.is_fade or ev.is_bpm_change:
                continue
            if self._swing > 0 and not ev.simultaneous_with_next:
                if abs(ev.duration_s - half_beat_s) < 0.01:
                    if is_offbeat:
                        ev.duration_s = beat_s * (1.0 - swing_ratio)
                    else:
                        ev.duration_s = beat_s * swing_ratio
                    is_offbeat = not is_offbeat
            if self._humanize > 0 and not ev.is_rest and not ev.simultaneous_with_next:
                offset_s = self._humanize_rng.uniform(
                    -self._humanize / 1000.0, self._humanize / 1000.0
                )
                ev.duration_s = max(0.01, ev.duration_s + offset_s)

    def _flatten_sequence(self, name: str) -> None:
        """Flatten a named sequence into WavEvents."""
        seq = self.program.sequences.get(name)
        if seq is None:
            return
        for ev in seq.events:
            if isinstance(ev, RestEvent):
                self._events.append(WavEvent(
                    inst_index=0,
                    freq=0.0,
                    duration_s=self._beats_to_s(ev.duration_beats),
                    is_rest=True,
                ))
            elif isinstance(ev, PlayNote):
                vel = (ev.velocity / 255.0) if ev.velocity is not None else 1.0
                if ev.notes:
                    channels = self._voice_channels.get(
                        ev.instrument,
                        [self._inst_index.get(ev.instrument, 0)],
                    )
                    for i, note_name in enumerate(ev.notes):
                        ch = channels[min(i, len(channels) - 1)]
                        is_last = (i == len(ev.notes) - 1)
                        self._events.append(WavEvent(
                            inst_index=ch,
                            freq=note_name_to_freq(note_name),
                            duration_s=self._beats_to_s(ev.duration_beats),
                            is_rest=False,
                            simultaneous_with_next=not is_last,
                            velocity=vel,
                            reverb_override=ev.reverb_override,
                            delay_time_override=ev.delay_time_override,
                            delay_feedback_override=ev.delay_feedback_override,
                        ))
                else:
                    idx = self._inst_index.get(ev.instrument, 0)
                    inst = self.program.instruments.get(ev.instrument)
                    freq = 0.0
                    if ev.note:
                        freq = note_name_to_freq(ev.note)
                    elif inst is not None and inst.freq is not None:
                        freq = float(inst.freq)

                    self._events.append(WavEvent(
                        inst_index=idx,
                        freq=freq,
                        duration_s=self._beats_to_s(ev.duration_beats),
                        is_rest=False,
                        velocity=vel,
                        reverb_override=ev.reverb_override,
                        delay_time_override=ev.delay_time_override,
                        delay_feedback_override=ev.delay_feedback_override,
                    ))

    def _flatten_pattern(self, name: str) -> None:
        """Flatten a pattern into WavEvents, grouping simultaneous beats."""
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
                self._events.append(WavEvent(
                    inst_index=0, freq=0.0,
                    duration_s=self._beats_to_s(gap),
                    is_rest=True,
                ))

            if g_idx + 1 < len(groups):
                next_pos = groups[g_idx + 1][0]
            else:
                next_pos = pat.beats_per_bar + 1.0
            beat_gap_s = self._beats_to_s(next_pos - pos)

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

            for ev_idx, (idx, note_name, bev) in enumerate(expanded):
                inst = self.program.instruments.get(bev.instrument)

                if note_name:
                    freq = note_name_to_freq(note_name)
                elif inst and inst.freq:
                    freq = float(inst.freq)
                else:
                    freq = 60.0

                if bev.duration_beats is not None:
                    dur = self._beats_to_s(bev.duration_beats)
                elif inst and inst.decay_ms:
                    dur = inst.decay_ms / 1000.0
                else:
                    dur = 0.08

                vel = (bev.velocity / 255.0) if bev.velocity is not None else 1.0
                is_last = (ev_idx == len(expanded) - 1)
                self._events.append(WavEvent(
                    inst_index=idx,
                    freq=freq,
                    duration_s=beat_gap_s if is_last else dur,
                    is_rest=False,
                    simultaneous_with_next=not is_last,
                    velocity=vel,
                    reverb_override=bev.reverb_override,
                    delay_time_override=bev.delay_time_override,
                    delay_feedback_override=bev.delay_feedback_override,
                ))

            current_beat = next_pos

    @staticmethod
    def _events_to_absolute(events: list[WavEvent]) -> list[tuple[float, WavEvent]]:
        """Convert sequential WavEvents to (absolute_time_s, event) pairs."""
        abs_events: list[tuple[float, WavEvent]] = []
        t = 0.0
        for ev in events:
            if ev.is_volume_change:
                abs_events.append((t, ev))
            elif ev.is_rest:
                if not ev.simultaneous_with_next:
                    t += ev.duration_s
            else:
                abs_events.append((t, ev))
                if not ev.simultaneous_with_next:
                    t += ev.duration_s
        return abs_events

    def _flatten_play_together(self, block: PlayTogetherBlock) -> None:
        """Flatten a PLAY_TOGETHER block by merging child timelines."""
        child_timelines: list[list[WavEvent]] = []
        for child in block.body:
            saved = list(self._events)
            self._events = []
            if isinstance(child, PlaySequenceRef):
                self._flatten_sequence(child.sequence_name)
            elif isinstance(child, PlayPatternRef):
                self._flatten_pattern(child.pattern_name)
            elif isinstance(child, LoopBlock):
                for _ in range(child.count):
                    self._flatten_arrangement(child.body)
            elif isinstance(child, PlayTogetherBlock):
                self._flatten_play_together(child)
            elif isinstance(child, BPMChange):
                self._current_bpm = child.bpm
            elif isinstance(child, VolumeChange):
                self._events.append(WavEvent(
                    inst_index=0, freq=0.0, duration_s=0.0,
                    is_rest=True, is_volume_change=True, new_volume=child.volume,
                ))
            elif isinstance(child, (FadeIn, FadeOut)):
                direction = 1 if isinstance(child, FadeIn) else -1
                dur_s = self._beats_to_s(child.duration_beats)
                self._events.append(WavEvent(
                    inst_index=0, freq=0.0, duration_s=0.0,
                    is_rest=True, is_fade=True,
                    fade_direction=direction, fade_duration_s=dur_s,
                ))
            child_timelines.append(self._events)
            self._events = saved

        all_abs: list[tuple[float, WavEvent]] = []
        for child_events in child_timelines:
            all_abs.extend(self._events_to_absolute(child_events))

        all_abs.sort(key=lambda x: x[0])
        if not all_abs:
            return

        from itertools import groupby

        groups: list[tuple[float, list[WavEvent]]] = []
        for t, grp in groupby(all_abs, key=lambda x: round(x[0], 6)):
            groups.append((t, [ev for _, ev in grp]))

        for g_idx, (start, group) in enumerate(groups):
            if g_idx == 0 and start > 0.001:
                self._events.append(WavEvent(
                    inst_index=0, freq=0.0, duration_s=start, is_rest=True,
                ))
            elif g_idx > 0:
                prev_start = groups[g_idx - 1][0]
                prev_group = groups[g_idx - 1][1]
                prev_max_dur = max(ev.duration_s for ev in prev_group)
                prev_end = prev_start + prev_max_dur
                rest_gap = start - prev_end
                if rest_gap > 0.001:
                    self._events.append(WavEvent(
                        inst_index=0, freq=0.0, duration_s=rest_gap, is_rest=True,
                    ))

            control_evs = [ev for ev in group if ev.is_volume_change]
            note_evs = [ev for ev in group if not ev.is_volume_change]

            for cev in control_evs:
                self._events.append(cev)

            if g_idx + 1 < len(groups):
                next_start = groups[g_idx + 1][0]
            else:
                next_start = start + max((ev.duration_s for ev in note_evs), default=0.0)
            beat_gap = max(0.001, next_start - start)

            for ev_idx, ev in enumerate(note_evs):
                is_last = ev_idx == len(note_evs) - 1
                self._events.append(WavEvent(
                    inst_index=ev.inst_index,
                    freq=ev.freq,
                    duration_s=beat_gap if is_last else ev.duration_s,
                    is_rest=False,
                    simultaneous_with_next=not is_last,
                ))

    def render(self, output_path: str) -> None:
        """Render the composition to a WAV file.

        Args:
            output_path: Path to write the .wav file.
        """
        samples = self._synthesize()
        self._write_wav(output_path, samples)

    def render_bytes(self) -> bytes:
        """Render the composition to WAV data in memory.

        Returns:
            Raw WAV file bytes.
        """
        import io
        samples = self._synthesize()
        buf = io.BytesIO()
        self._write_wav_to(buf, samples)
        return buf.getvalue()

    def _synthesize(self) -> list[int]:
        """Synthesize all events into a list of 16-bit signed samples.

        Handles simultaneous groups by mixing multiple instruments together.

        Returns:
            List of int16 sample values (interleaved L/R if stereo).
        """
        all_samples: list[int] = []
        n_instruments = len(self._instruments)
        ev_idx = 0
        master_volume = 1.0

        # Delay buffers per instrument
        delay_bufs: dict[int, list[float]] = {}
        delay_positions: dict[int, int] = {}
        for di, inst in enumerate(self._instruments):
            if inst.delay_time_ms > 0:
                buf_len = max(1, int(inst.delay_time_ms / 1000.0 * WAV_SAMPLE_RATE))
                delay_bufs[di] = [0.0] * buf_len
                delay_positions[di] = 0

        # Reverb buffers per instrument (multi-tap comb filter)
        _REVERB_TAPS_MS = [30, 50, 80, 113]
        reverb_bufs: dict[int, list[list[float]]] = {}
        reverb_positions: dict[int, list[int]] = {}
        for di, inst in enumerate(self._instruments):
            if inst.reverb > 0:
                bufs = []
                for tap_ms in _REVERB_TAPS_MS:
                    tap_len = max(1, int(tap_ms / 1000.0 * WAV_SAMPLE_RATE))
                    bufs.append([0.0] * tap_len)
                reverb_bufs[di] = bufs
                reverb_positions[di] = [0] * len(_REVERB_TAPS_MS)

        # LPF state per instrument
        lpf_states: dict[int, float] = {}
        for di, inst in enumerate(self._instruments):
            if inst.cutoff is not None:
                lpf_states[di] = 0.0

        # Glide state: prev freq per instrument channel
        glide_prev_freq: dict[int, float] = {}

        # Karplus-Strong state per instrument (for PLUCK waveform)
        ks_engines: dict[int, KarplusStrong] = {}

        # Chorus buffers per instrument (short modulated delay)
        _CHORUS_BASE_MS = 20
        _CHORUS_LFO_HZ = 0.5
        _CHORUS_DEPTH_MS = 5
        chorus_bufs: dict[int, list[float]] = {}
        chorus_write_pos: dict[int, int] = {}
        for di, inst in enumerate(self._instruments):
            if inst.chorus > 0:
                buf_len = max(1, int((_CHORUS_BASE_MS + _CHORUS_DEPTH_MS + 2) / 1000.0 * WAV_SAMPLE_RATE))
                chorus_bufs[di] = [0.0] * buf_len
                chorus_write_pos[di] = 0

        # LFO phase accumulators per instrument
        lfo_vol_phases: dict[int, float] = {}
        lfo_pitch_phases: dict[int, float] = {}
        for di, inst in enumerate(self._instruments):
            if inst.lfo_volume:
                lfo_vol_phases[di] = 0.0
            if inst.lfo_pitch:
                lfo_pitch_phases[di] = 0.0

        # Global sample counter for LFO/chorus time tracking
        global_sample_count = 0

        # Fade state
        fade_volume = 1.0
        fade_step_per_sample = 0.0
        fade_target = 1.0

        # Sustained notes: [ev, inst_idx, total_dur_s, elapsed_s, phase, osc_fn]
        sustained: list[list] = []

        # Track cumulative time for fade progress
        cumulative_samples = 0

        while ev_idx < len(self._events):
            # Collect simultaneous group
            group: list[WavEvent] = [self._events[ev_idx]]
            while group[-1].simultaneous_with_next and ev_idx + 1 < len(self._events):
                ev_idx += 1
                group.append(self._events[ev_idx])
            ev_idx += 1

            # Handle volume change and fade events
            if any(ev.is_volume_change or ev.is_fade for ev in group):
                for ev in group:
                    if ev.is_volume_change:
                        master_volume = ev.new_volume / 255.0
                    if ev.is_fade:
                        fade_samples = max(1, int(ev.fade_duration_s * WAV_SAMPLE_RATE))
                        if ev.fade_direction > 0:  # fade in
                            fade_volume = 0.0
                            fade_target = 1.0
                            fade_step_per_sample = 1.0 / fade_samples
                        else:  # fade out
                            fade_target = 0.0
                            fade_step_per_sample = -fade_volume / fade_samples
                continue

            last_event = group[-1]
            num_samples = max(1, int(last_event.duration_s * WAV_SAMPLE_RATE))

            if all(ev.is_rest or ev.freq <= 0 for ev in group) or n_instruments == 0:
                has_active_delay = any(
                    di in delay_bufs and any(abs(v) > 0.001 for v in delay_bufs[di])
                    for di in delay_bufs
                )
                has_active_reverb = any(
                    di in reverb_bufs and any(
                        abs(v) > 0.001 for tap_buf in reverb_bufs[di] for v in tap_buf
                    )
                    for di in reverb_bufs
                )
                if not has_active_delay and not has_active_reverb and not sustained:
                    if self._is_stereo:
                        all_samples.extend([0] * (num_samples * 2))
                    else:
                        all_samples.extend([0] * num_samples)
                    advance_s = last_event.duration_s
                    sustained = [sn for sn in sustained if sn[3] + advance_s < sn[2] + self._envelopes[sn[1]].release_s]
                    for sn in sustained:
                        sn[3] += advance_s
                    continue

                # Process delay/reverb tails and sustained notes during REST
                for s in range(num_samples):
                    mixed_l = 0.0
                    mixed_r = 0.0
                    mixed = 0.0
                    for di in delay_bufs:
                        inst = self._instruments[di]
                        buf = delay_bufs[di]
                        pos = delay_positions[di]
                        delayed = buf[pos]
                        fb = inst.delay_feedback / 255.0
                        buf[pos] = delayed * fb
                        delay_positions[di] = (pos + 1) % len(buf)
                        sample_val = delayed * 0.5
                        if self._is_stereo:
                            pan = self._pans[di]
                            left_gain = max(0.0, 1.0 - pan) if pan > 0 else 1.0
                            right_gain = max(0.0, 1.0 + pan) if pan < 0 else 1.0
                            mixed_l += sample_val * left_gain
                            mixed_r += sample_val * right_gain
                        else:
                            mixed += sample_val
                    for di in reverb_bufs:
                        rev_sum = 0.0
                        for tap_i, tap_buf in enumerate(reverb_bufs[di]):
                            tap_pos = reverb_positions[di][tap_i]
                            rev_sum += tap_buf[tap_pos]
                            tap_buf[tap_pos] = tap_buf[tap_pos] * 0.4
                            reverb_positions[di][tap_i] = (tap_pos + 1) % len(tap_buf)
                        sample_val = rev_sum / len(reverb_bufs[di])
                        if self._is_stereo:
                            pan = self._pans[di]
                            left_gain = max(0.0, 1.0 - pan) if pan > 0 else 1.0
                            right_gain = max(0.0, 1.0 + pan) if pan < 0 else 1.0
                            mixed_l += sample_val * left_gain
                            mixed_r += sample_val * right_gain
                        else:
                            mixed += sample_val
                    for sn in sustained:
                        st = sn[3] + s / WAV_SAMPLE_RATE
                        env_val = self._envelopes[sn[1]].amplitude_at(st, sn[2])
                        if env_val < 0.0001:
                            continue
                        vol = self._volumes[sn[1]] * sn[0].velocity
                        osc_val = sn[5](sn[4])
                        sn[4] += sn[0].freq / WAV_SAMPLE_RATE
                        if sn[4] >= 1.0:
                            sn[4] -= 1.0
                        sv = osc_val * env_val * vol
                        if self._is_stereo:
                            pan = self._pans[sn[1]]
                            left_gain = max(0.0, 1.0 - pan) if pan > 0 else 1.0
                            right_gain = max(0.0, 1.0 + pan) if pan < 0 else 1.0
                            mixed_l += sv * left_gain
                            mixed_r += sv * right_gain
                        else:
                            mixed += sv
                    vol_mult = master_volume * fade_volume
                    if fade_step_per_sample != 0.0:
                        fade_volume += fade_step_per_sample
                        fade_volume = max(0.0, min(1.0, fade_volume))
                        if (fade_step_per_sample > 0 and fade_volume >= fade_target) or \
                           (fade_step_per_sample < 0 and fade_volume <= fade_target):
                            fade_volume = fade_target
                            fade_step_per_sample = 0.0
                    if self._is_stereo:
                        mixed_l *= vol_mult
                        mixed_r *= vol_mult
                        sl = int(mixed_l * 24000)
                        sr = int(mixed_r * 24000)
                        all_samples.append(max(-32768, min(32767, sl)))
                        all_samples.append(max(-32768, min(32767, sr)))
                    else:
                        mixed *= vol_mult
                        sv = int(mixed * 24000)
                        all_samples.append(max(-32768, min(32767, sv)))
                advance_s = last_event.duration_s
                sustained = [sn for sn in sustained if sn[3] + advance_s < sn[2] + self._envelopes[sn[1]].release_s]
                for sn in sustained:
                    sn[3] += advance_s
                continue

            max_release_s = 0.0
            active_members: list[tuple[WavEvent, int]] = []
            for ev in group:
                if ev.is_rest or ev.freq <= 0 or ev.inst_index >= n_instruments:
                    continue
                active_members.append((ev, ev.inst_index))
                max_release_s = max(max_release_s, self._envelopes[ev.inst_index].release_s)

            if not active_members:
                if self._is_stereo:
                    all_samples.extend([0] * (num_samples * 2))
                else:
                    all_samples.extend([0] * num_samples)
                continue

            advance_s = last_event.duration_s
            is_last_group = ev_idx >= len(self._events)
            has_sustaining = sustained or any(
                ev.duration_s > advance_s + 0.001 for ev, _ in active_members
            )
            release_samples = int(max_release_s * WAV_SAMPLE_RATE)
            total = num_samples + release_samples if is_last_group else num_samples

            phases = [0.0] * len(active_members)
            hp_prev_in = [0.0] * len(active_members)
            hp_prev_out = [0.0] * len(active_members)

            m_is_drum_noise: list[bool] = []
            m_is_drum_tonal: list[bool] = []
            m_is_pluck: list[bool] = []
            m_ks: list[Optional[KarplusStrong]] = []
            m_hp_alpha: list[float] = []
            m_osc_fn = []

            for ev_m, idx_m in active_members:
                inst_m = self._instruments[idx_m]
                is_drum = inst_m.kind == InstrumentKind.DRUM
                is_noise = inst_m.wave == WaveType.NOISE
                is_pluck = inst_m.wave == WaveType.PLUCK and not is_drum
                m_is_drum_noise.append(is_drum and is_noise)
                m_is_drum_tonal.append(is_drum and not is_noise)
                m_is_pluck.append(is_pluck)
                if is_pluck:
                    m_ks.append(KarplusStrong(ev_m.freq, inst_m.decay_ms or 0))
                else:
                    m_ks.append(None)
                m_osc_fn.append(_OSCILLATORS.get(inst_m.wave, _sin_sample))
                if is_drum and is_noise:
                    fc = max(20.0, ev_m.freq)
                    rc = 1.0 / (2.0 * math.pi * fc)
                    dt = 1.0 / WAV_SAMPLE_RATE
                    m_hp_alpha.append(rc / (rc + dt))
                else:
                    m_hp_alpha.append(0.0)

            # Multi-voice detuned phase arrays
            m_voice_phases: list[list[float]] = []
            m_voice_freq_mults: list[list[float]] = []
            for ev_mv, idx_mv in active_members:
                inst_mv = self._instruments[idx_mv]
                nv = inst_mv.voices if inst_mv.kind != InstrumentKind.DRUM else 1
                if nv > 1 and inst_mv.detune > 0:
                    offsets = []
                    for vi in range(nv):
                        cents = inst_mv.detune * (2.0 * vi / (nv - 1) - 1.0)
                        offsets.append(2.0 ** (cents / 1200.0))
                    m_voice_phases.append([0.0] * nv)
                    m_voice_freq_mults.append(offsets)
                else:
                    m_voice_phases.append([0.0])
                    m_voice_freq_mults.append([1.0])

            total_voices = len(active_members) + len(sustained)
            scale = 1.0 / (total_voices ** 0.5) if total_voices > 1 else 1.0

            # Precompute glide targets
            m_glide_from: list[float] = []
            m_glide_to: list[float] = []
            m_glide_samples: list[int] = []
            for ev, idx in active_members:
                inst = self._instruments[idx]
                if inst.glide_ms > 0 and idx in glide_prev_freq:
                    m_glide_from.append(glide_prev_freq[idx])
                    m_glide_to.append(ev.freq)
                    m_glide_samples.append(max(1, int(inst.glide_ms / 1000.0 * WAV_SAMPLE_RATE)))
                else:
                    m_glide_from.append(ev.freq)
                    m_glide_to.append(ev.freq)
                    m_glide_samples.append(0)
                glide_prev_freq[idx] = ev.freq

            for s in range(total):
                t = s / WAV_SAMPLE_RATE
                mixed_l = 0.0
                mixed_r = 0.0
                mixed = 0.0

                for m_idx, (ev, idx) in enumerate(active_members):
                    envelope = self._envelopes[idx]
                    inst = self._instruments[idx]
                    volume = self._volumes[idx] * ev.velocity

                    # LFO volume modulation
                    if idx in lfo_vol_phases and inst.lfo_volume:
                        lfo_v = math.sin(2.0 * math.pi * lfo_vol_phases[idx])
                        volume *= max(0.0, 1.0 + lfo_v * inst.lfo_volume.depth / 255.0)

                    # Compute current frequency (with glide)
                    cur_freq = ev.freq
                    if m_glide_samples[m_idx] > 0 and s < m_glide_samples[m_idx]:
                        frac = s / m_glide_samples[m_idx]
                        cur_freq = m_glide_from[m_idx] * ((m_glide_to[m_idx] / max(0.1, m_glide_from[m_idx])) ** frac)

                    # LFO pitch modulation (depth in cents)
                    if idx in lfo_pitch_phases and inst.lfo_pitch:
                        lfo_p = math.sin(2.0 * math.pi * lfo_pitch_phases[idx])
                        cur_freq *= 2.0 ** (lfo_p * inst.lfo_pitch.depth / 1200.0)

                    if m_is_pluck[m_idx]:
                        ks = m_ks[m_idx]
                        osc_val = ks.next_sample()
                    elif m_is_drum_noise[m_idx]:
                        raw_noise = random.uniform(-1.0, 1.0)
                        alpha = m_hp_alpha[m_idx]
                        hp_prev_out[m_idx] = alpha * (
                            hp_prev_out[m_idx] + raw_noise - hp_prev_in[m_idx]
                        )
                        hp_prev_in[m_idx] = raw_noise
                        osc_val = hp_prev_out[m_idx]
                    elif m_is_drum_tonal[m_idx]:
                        sweep_freq = cur_freq * (1.0 + 4.0 * math.exp(-t * 80.0))
                        osc_val = m_osc_fn[m_idx](phases[m_idx])
                        phases[m_idx] += sweep_freq / WAV_SAMPLE_RATE
                        while phases[m_idx] >= 1.0:
                            phases[m_idx] -= 1.0
                    else:
                        # Multi-voice detuned oscillator
                        nv = len(m_voice_freq_mults[m_idx])
                        if nv > 1:
                            osc_sum = 0.0
                            for vi in range(nv):
                                osc_sum += m_osc_fn[m_idx](m_voice_phases[m_idx][vi])
                                vf = cur_freq * m_voice_freq_mults[m_idx][vi]
                                m_voice_phases[m_idx][vi] += vf / WAV_SAMPLE_RATE
                                if m_voice_phases[m_idx][vi] >= 1.0:
                                    m_voice_phases[m_idx][vi] -= 1.0
                            osc_val = osc_sum / nv
                        else:
                            osc_val = m_osc_fn[m_idx](phases[m_idx])
                            phases[m_idx] += cur_freq / WAV_SAMPLE_RATE
                            if phases[m_idx] >= 1.0:
                                phases[m_idx] -= 1.0

                    env_val = envelope.amplitude_at(t, ev.duration_s)
                    sample_val = osc_val * env_val * volume

                    # Low-pass filter
                    if idx in lpf_states and inst.cutoff is not None:
                        fc = inst.cutoff
                        alpha_lpf = (2.0 * math.pi * fc / WAV_SAMPLE_RATE) / (1.0 + 2.0 * math.pi * fc / WAV_SAMPLE_RATE)
                        lpf_states[idx] += alpha_lpf * (sample_val - lpf_states[idx])
                        sample_val = lpf_states[idx]

                    # Delay effect with per-note overrides
                    eff_delay_ms = ev.delay_time_override if ev.delay_time_override is not None else inst.delay_time_ms
                    eff_delay_fb = ev.delay_feedback_override if ev.delay_feedback_override is not None else inst.delay_feedback
                    if idx in delay_bufs and eff_delay_ms > 0:
                        buf = delay_bufs[idx]
                        pos = delay_positions[idx]
                        if ev.delay_time_override is not None:
                            rd = max(1, int(eff_delay_ms / 1000.0 * WAV_SAMPLE_RATE))
                            rd = min(rd, len(buf))
                            rpos = (pos + len(buf) - rd) % len(buf)
                            delayed = buf[rpos]
                        else:
                            delayed = buf[pos]
                        fb = eff_delay_fb / 255.0
                        buf[pos] = sample_val + delayed * fb
                        delay_positions[idx] = (pos + 1) % len(buf)
                        sample_val = sample_val + delayed * 0.5

                    # Reverb effect with per-note override
                    eff_reverb = ev.reverb_override if ev.reverb_override is not None else inst.reverb
                    if idx in reverb_bufs and eff_reverb > 0:
                        rev_mix = eff_reverb / 255.0 * 0.5
                        rev_sum = 0.0
                        for tap_i, tap_buf in enumerate(reverb_bufs[idx]):
                            tap_pos = reverb_positions[idx][tap_i]
                            rev_sum += tap_buf[tap_pos]
                            tap_buf[tap_pos] = sample_val * 0.3 + tap_buf[tap_pos] * 0.4
                            reverb_positions[idx][tap_i] = (tap_pos + 1) % len(tap_buf)
                        sample_val = sample_val * (1.0 - rev_mix) + rev_sum * rev_mix / len(reverb_bufs[idx])

                    # Chorus effect (short modulated delay)
                    if idx in chorus_bufs and inst.chorus > 0:
                        cbuf = chorus_bufs[idx]
                        cwpos = chorus_write_pos[idx]
                        cbuf[cwpos] = sample_val
                        g_t = global_sample_count / WAV_SAMPLE_RATE
                        mod = math.sin(2.0 * math.pi * _CHORUS_LFO_HZ * g_t)
                        d_ms = _CHORUS_BASE_MS + mod * _CHORUS_DEPTH_MS
                        d_samps = max(1, int(d_ms / 1000.0 * WAV_SAMPLE_RATE))
                        d_samps = min(d_samps, len(cbuf) - 1)
                        crpos = (cwpos - d_samps) % len(cbuf)
                        wet = cbuf[crpos]
                        cmix = inst.chorus / 255.0
                        sample_val = sample_val * (1.0 - cmix * 0.5) + wet * cmix * 0.5
                        chorus_write_pos[idx] = (cwpos + 1) % len(cbuf)

                    if self._is_stereo:
                        pan = self._pans[idx]
                        left_gain = max(0.0, 1.0 - pan) if pan > 0 else 1.0
                        right_gain = max(0.0, 1.0 + pan) if pan < 0 else 1.0
                        mixed_l += sample_val * left_gain
                        mixed_r += sample_val * right_gain
                    else:
                        mixed += sample_val

                # Advance LFO phases
                for _ev_lfo, idx_lfo in active_members:
                    inst_lfo = self._instruments[idx_lfo]
                    if idx_lfo in lfo_vol_phases and inst_lfo.lfo_volume:
                        lfo_vol_phases[idx_lfo] += inst_lfo.lfo_volume.rate / WAV_SAMPLE_RATE
                        if lfo_vol_phases[idx_lfo] >= 1.0:
                            lfo_vol_phases[idx_lfo] -= 1.0
                    if idx_lfo in lfo_pitch_phases and inst_lfo.lfo_pitch:
                        lfo_pitch_phases[idx_lfo] += inst_lfo.lfo_pitch.rate / WAV_SAMPLE_RATE
                        if lfo_pitch_phases[idx_lfo] >= 1.0:
                            lfo_pitch_phases[idx_lfo] -= 1.0
                global_sample_count += 1

                # Mix in sustained notes from previous groups
                for sn in sustained:
                    st = sn[3] + t
                    env_val = self._envelopes[sn[1]].amplitude_at(st, sn[2])
                    if env_val < 0.0001:
                        continue
                    vol = self._volumes[sn[1]] * sn[0].velocity
                    osc_val = sn[5](sn[4])
                    sn[4] += sn[0].freq / WAV_SAMPLE_RATE
                    if sn[4] >= 1.0:
                        sn[4] -= 1.0
                    sv = osc_val * env_val * vol
                    if self._is_stereo:
                        pan = self._pans[sn[1]]
                        left_gain = max(0.0, 1.0 - pan) if pan > 0 else 1.0
                        right_gain = max(0.0, 1.0 + pan) if pan < 0 else 1.0
                        mixed_l += sv * left_gain
                        mixed_r += sv * right_gain
                    else:
                        mixed += sv

                vol_mult = scale * master_volume * fade_volume
                if fade_step_per_sample != 0.0:
                    fade_volume += fade_step_per_sample
                    fade_volume = max(0.0, min(1.0, fade_volume))
                    if (fade_step_per_sample > 0 and fade_volume >= fade_target) or \
                       (fade_step_per_sample < 0 and fade_volume <= fade_target):
                        fade_volume = fade_target
                        fade_step_per_sample = 0.0
                if self._is_stereo:
                    mixed_l *= vol_mult
                    mixed_r *= vol_mult
                    sl = int(mixed_l * 24000)
                    sr = int(mixed_r * 24000)
                    all_samples.append(max(-32768, min(32767, sl)))
                    all_samples.append(max(-32768, min(32767, sr)))
                else:
                    mixed *= vol_mult
                    sample_i = int(mixed * 24000)
                    sample_i = max(-32768, min(32767, sample_i))
                    all_samples.append(sample_i)

            # Update sustained notes: advance elapsed, remove finished, add new
            new_sustained = []
            for sn in sustained:
                sn[3] += advance_s
                total_note_s = sn[2] + self._envelopes[sn[1]].release_s
                if sn[3] < total_note_s:
                    new_sustained.append(sn)
            for m_idx, (ev, idx) in enumerate(active_members):
                total_with_release = ev.duration_s + self._envelopes[idx].release_s
                if total_with_release > advance_s + 0.001:
                    osc_fn = _OSCILLATORS.get(self._instruments[idx].wave, _sin_sample)
                    new_sustained.append([ev, idx, ev.duration_s, advance_s, phases[m_idx], osc_fn])
            sustained = new_sustained

        return all_samples

    def _write_wav(self, path: str, samples: list[int]) -> None:
        """Write samples to a WAV file on disk."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        channels = 2 if self._is_stereo else WAV_CHANNELS
        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(WAV_BIT_DEPTH // 8)
            wf.setframerate(WAV_SAMPLE_RATE)
            data = struct.pack(f"<{len(samples)}h", *samples)
            wf.writeframes(data)

    def _write_wav_to(self, fp, samples: list[int]) -> None:
        """Write samples to a file-like object."""
        channels = 2 if self._is_stereo else WAV_CHANNELS
        with wave.open(fp, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(WAV_BIT_DEPTH // 8)
            wf.setframerate(WAV_SAMPLE_RATE)
            data = struct.pack(f"<{len(samples)}h", *samples)
            wf.writeframes(data)

    def total_duration_s(self) -> float:
        """Calculate the total duration of the composition in seconds.

        Returns:
            Total duration in seconds.
        """
        total = 0.0
        last_release = 0.0
        for ev in self._events:
            if ev.simultaneous_with_next:
                continue
            total += ev.duration_s
            if not ev.is_rest and ev.inst_index < len(self._envelopes):
                last_release = self._envelopes[ev.inst_index].release_s
            else:
                last_release = 0.0
        total += last_release
        return total


def render_wav(program: Program, output_path: str) -> None:
    """Convenience function: render a Program AST to a WAV file.

    Args:
        program: A validated Program AST.
        output_path: Path to write the .wav file.
    """
    WavRenderer(program).render(output_path)
