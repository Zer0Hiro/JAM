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
    InstrumentDef,
    InstrumentKind,
    LoopBlock,
    Pattern,
    PlayNote,
    PlayPatternRef,
    PlaySequenceRef,
    Program,
    RestEvent,
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

        # Build envelopes for each instrument
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

        # Flatten arrangement
        self._events: list[WavEvent] = []
        self._flatten_arrangement(program.arrangement)

    def _beats_to_s(self, beats: float) -> float:
        """Convert beats to seconds."""
        return beats * 60.0 / self.config.bpm

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

            for ev_idx, bev in enumerate(group):
                idx = self._inst_index.get(bev.instrument, 0)
                inst = self.program.instruments.get(bev.instrument)

                if bev.note:
                    freq = note_name_to_freq(bev.note)
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

                is_last = (ev_idx == len(group) - 1)
                self._events.append(WavEvent(
                    inst_index=idx,
                    freq=freq,
                    duration_s=beat_gap_s if is_last else dur,
                    is_rest=False,
                    simultaneous_with_next=not is_last,
                ))

            current_beat = next_pos

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
            List of int16 sample values.
        """
        all_samples: list[int] = []
        n_instruments = len(self._instruments)
        i = 0

        while i < len(self._events):
            # Collect simultaneous group
            group: list[WavEvent] = [self._events[i]]
            while group[-1].simultaneous_with_next and i + 1 < len(self._events):
                i += 1
                group.append(self._events[i])
            i += 1

            last_event = group[-1]
            num_samples = max(1, int(last_event.duration_s * WAV_SAMPLE_RATE))

            # All rests or no instruments
            if all(ev.is_rest or ev.freq <= 0 for ev in group) or n_instruments == 0:
                all_samples.extend([0] * num_samples)
                continue

            # Find max release tail across active group members
            max_release_s = 0.0
            active_members: list[tuple[WavEvent, int]] = []
            for ev in group:
                if ev.is_rest or ev.freq <= 0 or ev.inst_index >= n_instruments:
                    continue
                active_members.append((ev, ev.inst_index))
                max_release_s = max(max_release_s, self._envelopes[ev.inst_index].release_s)

            if not active_members:
                all_samples.extend([0] * num_samples)
                continue

            release_samples = int(max_release_s * WAV_SAMPLE_RATE)
            total = num_samples + release_samples

            # Per-member synthesis state
            phases = [0.0] * len(active_members)
            hp_prev_in = [0.0] * len(active_members)
            hp_prev_out = [0.0] * len(active_members)

            # Precompute per-member drum synthesis parameters
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

            for s in range(total):
                t = s / WAV_SAMPLE_RATE
                mixed = 0.0

                for m_idx, (ev, idx) in enumerate(active_members):
                    envelope = self._envelopes[idx]
                    volume = self._volumes[idx]

                    if m_is_drum_noise[m_idx]:
                        # High-pass filtered noise — freq controls cutoff
                        # Higher freq = brighter (hat), lower = fuller (snare)
                        raw_noise = random.uniform(-1.0, 1.0)
                        alpha = m_hp_alpha[m_idx]
                        hp_prev_out[m_idx] = alpha * (
                            hp_prev_out[m_idx] + raw_noise - hp_prev_in[m_idx]
                        )
                        hp_prev_in[m_idx] = raw_noise
                        osc_val = hp_prev_out[m_idx]
                    elif m_is_drum_tonal[m_idx]:
                        # Pitch sweep for tonal drums (kick, toms)
                        # Start at 5x base freq, exponential decay to base
                        sweep_freq = ev.freq * (1.0 + 4.0 * math.exp(-t * 80.0))
                        osc_val = m_osc_fn[m_idx](phases[m_idx])
                        phases[m_idx] += sweep_freq / WAV_SAMPLE_RATE
                        while phases[m_idx] >= 1.0:
                            phases[m_idx] -= 1.0
                    else:
                        osc_val = m_osc_fn[m_idx](phases[m_idx])
                        phases[m_idx] += ev.freq / WAV_SAMPLE_RATE
                        if phases[m_idx] >= 1.0:
                            phases[m_idx] -= 1.0

                    env_val = envelope.amplitude_at(t, ev.duration_s)
                    mixed += osc_val * env_val * volume

                mixed *= scale
                sample_i = int(mixed * 24000)
                sample_i = max(-32768, min(32767, sample_i))
                all_samples.append(sample_i)

        return all_samples

    def _write_wav(self, path: str, samples: list[int]) -> None:
        """Write samples to a WAV file on disk.

        Args:
            path: Output file path.
            samples: List of int16 sample values.
        """
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(out), "wb") as wf:
            wf.setnchannels(WAV_CHANNELS)
            wf.setsampwidth(WAV_BIT_DEPTH // 8)
            wf.setframerate(WAV_SAMPLE_RATE)
            data = struct.pack(f"<{len(samples)}h", *samples)
            wf.writeframes(data)

    def _write_wav_to(self, fp, samples: list[int]) -> None:
        """Write samples to a file-like object.

        Args:
            fp: File-like object supporting write().
            samples: List of int16 sample values.
        """
        with wave.open(fp, "wb") as wf:
            wf.setnchannels(WAV_CHANNELS)
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
