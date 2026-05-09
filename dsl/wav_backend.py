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

        # Flatten arrangement
        self._events: list[WavEvent] = []
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
                    cutoff=base_inst.cutoff,
                    resonance=base_inst.resonance,
                    reverb=base_inst.reverb,
                    delay_time_ms=base_inst.delay_time_ms,
                    delay_feedback=base_inst.delay_feedback,
                    glide_ms=base_inst.glide_ms,
                    pan=base_inst.pan,
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
                ))

            current_beat = next_pos

    @staticmethod
    def _events_to_absolute(events: list[WavEvent]) -> list[tuple[float, WavEvent]]:
        """Convert sequential WavEvents to (absolute_time_s, event) pairs."""
        abs_events: list[tuple[float, WavEvent]] = []
        t = 0.0
        for ev in events:
            if ev.is_rest:
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
                gap = start - groups[g_idx - 1][0]
                prev_group = groups[g_idx - 1][1]
                prev_duration = prev_group[-1].duration_s if prev_group else 0.0
                rest_gap = gap - prev_duration
                if rest_gap > 0.001:
                    self._events.append(WavEvent(
                        inst_index=0, freq=0.0, duration_s=rest_gap, is_rest=True,
                    ))

            if g_idx + 1 < len(groups):
                next_start = groups[g_idx + 1][0]
            else:
                next_start = start + max(ev.duration_s for ev in group)
            beat_gap = max(0.001, next_start - start)

            for ev_idx, ev in enumerate(group):
                is_last = ev_idx == len(group) - 1
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

        # LPF state per instrument
        lpf_states: dict[int, float] = {}
        for di, inst in enumerate(self._instruments):
            if inst.cutoff is not None:
                lpf_states[di] = 0.0

        # Glide state: prev freq per instrument channel
        glide_prev_freq: dict[int, float] = {}

        while ev_idx < len(self._events):
            # Collect simultaneous group
            group: list[WavEvent] = [self._events[ev_idx]]
            while group[-1].simultaneous_with_next and ev_idx + 1 < len(self._events):
                ev_idx += 1
                group.append(self._events[ev_idx])
            ev_idx += 1

            # Handle volume change events
            if any(ev.is_volume_change for ev in group):
                for ev in group:
                    if ev.is_volume_change:
                        master_volume = ev.new_volume / 255.0
                continue

            last_event = group[-1]
            num_samples = max(1, int(last_event.duration_s * WAV_SAMPLE_RATE))

            if all(ev.is_rest or ev.freq <= 0 for ev in group) or n_instruments == 0:
                has_active_delay = any(
                    di in delay_bufs and any(abs(v) > 0.001 for v in delay_bufs[di])
                    for di in delay_bufs
                )
                if not has_active_delay:
                    if self._is_stereo:
                        all_samples.extend([0] * (num_samples * 2))
                    else:
                        all_samples.extend([0] * num_samples)
                    continue

                # Process delay tails during REST
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
                        wet = delayed * fb
                        buf[pos] = wet
                        delay_positions[di] = (pos + 1) % len(buf)
                        sample_val = wet
                        if self._is_stereo:
                            pan = self._pans[di]
                            left_gain = max(0.0, 1.0 - pan) if pan > 0 else 1.0
                            right_gain = max(0.0, 1.0 + pan) if pan < 0 else 1.0
                            mixed_l += sample_val * left_gain
                            mixed_r += sample_val * right_gain
                        else:
                            mixed += sample_val
                    if self._is_stereo:
                        mixed_l *= master_volume
                        mixed_r *= master_volume
                        sl = int(mixed_l * 24000)
                        sr = int(mixed_r * 24000)
                        all_samples.append(max(-32768, min(32767, sl)))
                        all_samples.append(max(-32768, min(32767, sr)))
                    else:
                        mixed *= master_volume
                        sv = int(mixed * 24000)
                        all_samples.append(max(-32768, min(32767, sv)))
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

            release_samples = int(max_release_s * WAV_SAMPLE_RATE)
            total = num_samples + release_samples

            phases = [0.0] * len(active_members)
            hp_prev_in = [0.0] * len(active_members)
            hp_prev_out = [0.0] * len(active_members)

            m_is_drum_noise: list[bool] = []
            m_is_drum_tonal: list[bool] = []
            m_hp_alpha: list[float] = []
            m_osc_fn = []

            for ev_m, idx_m in active_members:
                inst_m = self._instruments[idx_m]
                is_drum = inst_m.kind == InstrumentKind.DRUM
                is_noise = inst_m.wave == WaveType.NOISE
                m_is_drum_noise.append(is_drum and is_noise)
                m_is_drum_tonal.append(is_drum and not is_noise)
                m_osc_fn.append(_OSCILLATORS.get(inst_m.wave, _sin_sample))
                if is_drum and is_noise:
                    fc = max(20.0, ev_m.freq)
                    rc = 1.0 / (2.0 * math.pi * fc)
                    dt = 1.0 / WAV_SAMPLE_RATE
                    m_hp_alpha.append(rc / (rc + dt))
                else:
                    m_hp_alpha.append(0.0)

            scale = 1.0 / (len(active_members) ** 0.5) if len(active_members) > 1 else 1.0

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
                    volume = self._volumes[idx] * ev.velocity

                    # Compute current frequency (with glide)
                    cur_freq = ev.freq
                    if m_glide_samples[m_idx] > 0 and s < m_glide_samples[m_idx]:
                        frac = s / m_glide_samples[m_idx]
                        cur_freq = m_glide_from[m_idx] * ((m_glide_to[m_idx] / max(0.1, m_glide_from[m_idx])) ** frac)

                    if m_is_drum_noise[m_idx]:
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
                        osc_val = m_osc_fn[m_idx](phases[m_idx])
                        phases[m_idx] += cur_freq / WAV_SAMPLE_RATE
                        if phases[m_idx] >= 1.0:
                            phases[m_idx] -= 1.0

                    env_val = envelope.amplitude_at(t, ev.duration_s)
                    sample_val = osc_val * env_val * volume

                    # Low-pass filter
                    inst = self._instruments[idx]
                    if idx in lpf_states and inst.cutoff is not None:
                        fc = inst.cutoff
                        alpha_lpf = (2.0 * math.pi * fc / WAV_SAMPLE_RATE) / (1.0 + 2.0 * math.pi * fc / WAV_SAMPLE_RATE)
                        lpf_states[idx] += alpha_lpf * (sample_val - lpf_states[idx])
                        sample_val = lpf_states[idx]

                    # Delay effect
                    if idx in delay_bufs and inst.delay_time_ms > 0:
                        buf = delay_bufs[idx]
                        pos = delay_positions[idx]
                        delayed = buf[pos]
                        fb = inst.delay_feedback / 255.0
                        wet = sample_val + delayed * fb
                        buf[pos] = wet
                        delay_positions[idx] = (pos + 1) % len(buf)
                        dry_wet = inst.reverb / 255.0 if inst.reverb > 0 else 0.5
                        sample_val = sample_val * (1.0 - dry_wet) + wet * dry_wet

                    if self._is_stereo:
                        pan = self._pans[idx]
                        left_gain = max(0.0, 1.0 - pan) if pan > 0 else 1.0
                        right_gain = max(0.0, 1.0 + pan) if pan < 0 else 1.0
                        mixed_l += sample_val * left_gain
                        mixed_r += sample_val * right_gain
                    else:
                        mixed += sample_val

                if self._is_stereo:
                    mixed_l *= scale * master_volume
                    mixed_r *= scale * master_volume
                    sl = int(mixed_l * 24000)
                    sr = int(mixed_r * 24000)
                    all_samples.append(max(-32768, min(32767, sl)))
                    all_samples.append(max(-32768, min(32767, sr)))
                else:
                    mixed *= scale * master_volume
                    sample_i = int(mixed * 24000)
                    sample_i = max(-32768, min(32767, sample_i))
                    all_samples.append(sample_i)

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
        for ev in self._events:
            if ev.simultaneous_with_next:
                continue
            total += ev.duration_s
            if not ev.is_rest and ev.inst_index < len(self._envelopes):
                total += self._envelopes[ev.inst_index].release_s
        return total


def render_wav(program: Program, output_path: str) -> None:
    """Convenience function: render a Program AST to a WAV file.

    Args:
        program: A validated Program AST.
        output_path: Path to write the .wav file.
    """
    WavRenderer(program).render(output_path)
