"""Tests for dsl.parser — parsing DSL source into AST."""

import pytest
from dsl.parser import parse, ParseError
from dsl.ast_nodes import (
    InstrumentKind,
    WaveType,
    PlayNote,
    RestEvent,
    PlaySequenceRef,
    PlayPatternRef,
    PlayTogetherBlock,
    LoopBlock,
)


class TestParseConfig:
    """Test parsing of configuration lines."""

    def test_bpm(self) -> None:
        prog = parse("BPM 140")
        assert prog.config.bpm == 140

    def test_audio_rate(self) -> None:
        prog = parse("AUDIO_RATE 32768")
        assert prog.config.audio_rate == 32768

    def test_control_rate(self) -> None:
        prog = parse("CONTROL_RATE 128")
        assert prog.config.control_rate == 128

    def test_defaults(self) -> None:
        prog = parse("")
        assert prog.config.bpm == 120
        assert prog.config.audio_rate == 16384
        assert prog.config.control_rate == 64


class TestParseInstrument:
    """Test parsing of INSTRUMENT blocks."""

    def test_synth_instrument(self) -> None:
        source = """
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    ADSR 10 50 200 100
    VOLUME 180
"""
        prog = parse(source)
        assert "lead" in prog.instruments
        inst = prog.instruments["lead"]
        assert inst.kind == InstrumentKind.SYNTH
        assert inst.wave == WaveType.SAW
        assert inst.adsr is not None
        assert inst.adsr.attack_ms == 10
        assert inst.adsr.decay_ms == 50
        assert inst.adsr.sustain_ms == 200
        assert inst.adsr.release_ms == 100
        assert inst.volume == 180

    def test_drum_instrument(self) -> None:
        source = """
INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80
    VOLUME 255
"""
        prog = parse(source)
        inst = prog.instruments["kick"]
        assert inst.kind == InstrumentKind.DRUM
        assert inst.freq == 60
        assert inst.decay_ms == 80


class TestParseSequence:
    """Test parsing of SEQUENCE blocks."""

    def test_simple_sequence(self) -> None:
        source = """
INSTRUMENT synth:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE melody:
    PLAY synth C4 1
    REST 0.5
    PLAY synth E4 2
"""
        prog = parse(source)
        assert "melody" in prog.sequences
        seq = prog.sequences["melody"]
        assert len(seq.events) == 3
        assert isinstance(seq.events[0], PlayNote)
        assert seq.events[0].note == "C4"
        assert seq.events[0].duration_beats == 1.0
        assert isinstance(seq.events[1], RestEvent)
        assert seq.events[1].duration_beats == 0.5
        assert isinstance(seq.events[2], PlayNote)
        assert seq.events[2].note == "E4"

    def test_drum_play_no_note(self) -> None:
        source = """
INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80

SEQUENCE beats:
    PLAY kick 1
"""
        prog = parse(source)
        ev = prog.sequences["beats"].events[0]
        assert isinstance(ev, PlayNote)
        assert ev.note is None
        assert ev.duration_beats == 1.0


class TestParsePattern:
    """Test parsing of PATTERN blocks."""

    def test_simple_pattern(self) -> None:
        source = """
INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80

PATTERN groove:
    BEAT 1: kick
    BEAT 3: kick
"""
        prog = parse(source)
        assert "groove" in prog.patterns
        pat = prog.patterns["groove"]
        assert len(pat.events) == 2
        assert pat.events[0].beat_position == 1.0
        assert pat.events[1].beat_position == 3.0


class TestParseArrangement:
    """Test parsing of arrangement items."""

    def test_play_sequence_ref(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE main:
    PLAY s C4 1

PLAY_SEQUENCE main
"""
        prog = parse(source)
        assert len(prog.arrangement) == 1
        assert isinstance(prog.arrangement[0], PlaySequenceRef)
        assert prog.arrangement[0].sequence_name == "main"

    def test_loop_block(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE main:
    PLAY s C4 1

LOOP 3:
    PLAY_SEQUENCE main
"""
        prog = parse(source)
        assert len(prog.arrangement) == 1
        loop = prog.arrangement[0]
        assert isinstance(loop, LoopBlock)
        assert loop.count == 3
        assert len(loop.body) == 1


class TestParsePlayTogether:
    """Test parsing of PLAY_TOGETHER blocks."""

    def test_play_together_basic(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE a:
    PLAY s C4 1

SEQUENCE b:
    PLAY s E4 1

PLAY_TOGETHER:
    PLAY_SEQUENCE a
    PLAY_SEQUENCE b
"""
        prog = parse(source)
        assert len(prog.arrangement) == 1
        block = prog.arrangement[0]
        assert isinstance(block, PlayTogetherBlock)
        assert len(block.body) == 2
        assert isinstance(block.body[0], PlaySequenceRef)
        assert isinstance(block.body[1], PlaySequenceRef)
        assert block.body[0].sequence_name == "a"
        assert block.body[1].sequence_name == "b"

    def test_play_together_with_pattern(self) -> None:
        source = """
INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80

INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE melody:
    PLAY s C4 1

PATTERN beat:
    BEAT 1: kick

PLAY_TOGETHER:
    PLAY_SEQUENCE melody
    PLAY_PATTERN beat
"""
        prog = parse(source)
        block = prog.arrangement[0]
        assert isinstance(block, PlayTogetherBlock)
        assert isinstance(block.body[0], PlaySequenceRef)
        assert isinstance(block.body[1], PlayPatternRef)

    def test_play_together_inside_loop(self) -> None:
        source = """
INSTRUMENT s:
    TYPE SYNTH
    WAVE SIN
    VOLUME 200

SEQUENCE a:
    PLAY s C4 1

SEQUENCE b:
    PLAY s E4 1

LOOP 3:
    PLAY_TOGETHER:
        PLAY_SEQUENCE a
        PLAY_SEQUENCE b
"""
        prog = parse(source)
        assert len(prog.arrangement) == 1
        loop = prog.arrangement[0]
        assert isinstance(loop, LoopBlock)
        assert loop.count == 3
        assert len(loop.body) == 1
        assert isinstance(loop.body[0], PlayTogetherBlock)


class TestParseErrors:
    """Test parse error handling."""

    def test_unknown_keyword_at_top(self) -> None:
        with pytest.raises(ParseError):
            parse("UNKNOWN_THING 42")

    def test_missing_colon_in_instrument(self) -> None:
        with pytest.raises(ParseError):
            parse("INSTRUMENT foo\n    TYPE SYNTH\n")

    def test_missing_indent(self) -> None:
        with pytest.raises(ParseError):
            parse("INSTRUMENT foo:\nTYPE SYNTH\n")
