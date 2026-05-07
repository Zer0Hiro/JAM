"""Tests for dsl.wav_backend — WAV audio rendering."""

import io
import struct
import wave

from dsl.parser import parse
from dsl.wav_backend import WavRenderer, WAV_SAMPLE_RATE


SIMPLE_SOURCE = """
BPM 120

INSTRUMENT tone:
    TYPE SYNTH
    WAVE SIN
    ADSR 10 50 200 100
    VOLUME 200

SEQUENCE melody:
    PLAY tone C4 1
    REST 1

PLAY_SEQUENCE melody
"""

DRUM_SOURCE = """
BPM 120

INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80
    VOLUME 255

PATTERN beat:
    BEAT 1: kick
    BEAT 3: kick

PLAY_PATTERN beat
"""


class TestWavRendererBasic:
    """Test basic WAV rendering."""

    def test_render_produces_bytes(self) -> None:
        program = parse(SIMPLE_SOURCE)
        renderer = WavRenderer(program)
        data = renderer.render_bytes()
        assert len(data) > 44  # WAV header is 44 bytes minimum

    def test_render_valid_wav_header(self) -> None:
        program = parse(SIMPLE_SOURCE)
        renderer = WavRenderer(program)
        data = renderer.render_bytes()
        buf = io.BytesIO(data)
        wf = wave.open(buf, "rb")
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == WAV_SAMPLE_RATE
        assert wf.getnframes() > 0
        wf.close()

    def test_duration_matches_composition(self) -> None:
        program = parse(SIMPLE_SOURCE)
        renderer = WavRenderer(program)
        dur = renderer.total_duration_s()
        # 1 beat at 120 BPM = 0.5s, + rest 0.5s, + release ~0.2s
        assert dur > 0.5
        assert dur < 5.0  # sanity upper bound


class TestWavRendererDrums:
    """Test drum pattern rendering."""

    def test_drum_pattern_renders(self) -> None:
        program = parse(DRUM_SOURCE)
        renderer = WavRenderer(program)
        data = renderer.render_bytes()
        buf = io.BytesIO(data)
        wf = wave.open(buf, "rb")
        assert wf.getnframes() > 0
        wf.close()


class TestWavRendererSamples:
    """Test sample content quality."""

    def test_samples_in_range(self) -> None:
        program = parse(SIMPLE_SOURCE)
        renderer = WavRenderer(program)
        samples = renderer._synthesize()
        for s in samples:
            assert -32768 <= s <= 32767

    def test_non_silent(self) -> None:
        program = parse(SIMPLE_SOURCE)
        renderer = WavRenderer(program)
        samples = renderer._synthesize()
        # At least some samples should be non-zero (we're playing a note)
        nonzero = sum(1 for s in samples if s != 0)
        assert nonzero > len(samples) * 0.1  # at least 10% non-silent

    def test_rest_is_silent(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE quiet:
    REST 1

PLAY_SEQUENCE quiet
"""
        program = parse(source)
        renderer = WavRenderer(program)
        samples = renderer._synthesize()
        # Pure rest should produce all zeros
        assert all(s == 0 for s in samples)
