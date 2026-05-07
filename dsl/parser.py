"""
Recursive-descent parser for the Mozzi DSL.

Consumes tokens from the lexer and produces a Program AST.  The grammar
(informally) is:

    program       := (config_line | instrument_def | sequence_def
                      | pattern_def | arrangement_item)* EOF
    config_line   := ("BPM" | "AUDIO_RATE" | "CONTROL_RATE") NUMBER NEWLINE
    instrument_def:= "INSTRUMENT" IDENT ":" NEWLINE INDENT instr_body+ DEDENT
    instr_body    := ("TYPE" ("SYNTH"|"DRUM")
                      | "WAVE" wave_name
                      | "ADSR" NUMBER NUMBER NUMBER NUMBER
                      | "VOLUME" NUMBER
                      | "FREQ" NUMBER
                      | "DECAY" NUMBER) NEWLINE
    sequence_def  := "SEQUENCE" IDENT ":" NEWLINE INDENT seq_event+ DEDENT
    seq_event     := ("PLAY" IDENT NOTE NUMBER | "REST" NUMBER) NEWLINE
    pattern_def   := "PATTERN" IDENT ":" NEWLINE INDENT beat_event+ DEDENT
    beat_event    := "BEAT" NUMBER ":" IDENT [NOTE] [NUMBER] NEWLINE
    arrangement   := (loop_block | play_seq_ref | play_pat_ref)+
    loop_block    := "LOOP" NUMBER ":" NEWLINE INDENT arrangement DEDENT
    play_seq_ref  := "PLAY_SEQUENCE" IDENT NEWLINE
    play_pat_ref  := "PLAY_PATTERN" IDENT NEWLINE
"""

from __future__ import annotations

from typing import Optional

from .ast_nodes import (
    ADSRParams,
    BeatEvent,
    Config,
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
from .lexer import Token, TokenType, tokenize


class ParseError(Exception):
    """Raised when the parser encounters unexpected tokens."""

    def __init__(self, message: str, token: Optional[Token] = None) -> None:
        self.token = token
        loc = f" at line {token.line}" if token else ""
        super().__init__(f"Parse error{loc}: {message}")


class Parser:
    """Recursive-descent parser for the Mozzi DSL.

    Usage::

        ast = Parser(source_text).parse()
    """

    def __init__(self, source: str) -> None:
        """Initialize the parser with DSL source text.

        Args:
            source: Full DSL source string.
        """
        self.tokens = tokenize(source)
        self.pos = 0

    # ----- helpers -----------------------------------------------------------

    def _current(self) -> Token:
        """Return the current token without consuming it."""
        return self.tokens[self.pos]

    def _peek_type(self) -> TokenType:
        """Return the type of the current token."""
        return self.tokens[self.pos].type

    def _peek_value(self) -> str:
        """Return the value of the current token."""
        return self.tokens[self.pos].value

    def _advance(self) -> Token:
        """Consume and return the current token."""
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, ttype: TokenType, value: Optional[str] = None) -> Token:
        """Consume a token, asserting its type and optionally its value.

        Args:
            ttype: Expected token type.
            value: If given, expected token value.

        Returns:
            The consumed token.

        Raises:
            ParseError: If the expectation is not met.
        """
        tok = self._current()
        if tok.type != ttype:
            raise ParseError(
                f"Expected {ttype.name} but got {tok.type.name} ({tok.value!r})", tok
            )
        if value is not None and tok.value != value:
            raise ParseError(
                f"Expected {value!r} but got {tok.value!r}", tok
            )
        return self._advance()

    def _match_keyword(self, *values: str) -> Optional[Token]:
        """If the current token is a KEYWORD with one of *values*, consume it.

        Returns:
            The consumed token, or None if no match.
        """
        tok = self._current()
        if tok.type == TokenType.KEYWORD and tok.value in values:
            return self._advance()
        return None

    def _skip_newlines(self) -> None:
        """Consume consecutive NEWLINE tokens."""
        while self._peek_type() == TokenType.NEWLINE:
            self._advance()

    # ----- top-level ---------------------------------------------------------

    def parse(self) -> Program:
        """Parse the full token stream and return a Program AST.

        Returns:
            The root Program node.

        Raises:
            ParseError: On syntax errors.
        """
        program = Program()

        while self._peek_type() != TokenType.EOF:
            self._skip_newlines()
            if self._peek_type() == TokenType.EOF:
                break

            tok = self._current()

            if tok.type == TokenType.KEYWORD:
                kw = tok.value
                if kw in ("BPM", "AUDIO_RATE", "CONTROL_RATE"):
                    self._parse_config(program.config)
                elif kw == "INSTRUMENT":
                    inst = self._parse_instrument()
                    program.instruments[inst.name] = inst
                elif kw == "SEQUENCE":
                    seq = self._parse_sequence()
                    program.sequences[seq.name] = seq
                elif kw == "PATTERN":
                    pat = self._parse_pattern()
                    program.patterns[pat.name] = pat
                elif kw in ("LOOP", "PLAY_SEQUENCE", "PLAY_PATTERN"):
                    item = self._parse_arrangement_item()
                    program.arrangement.append(item)
                else:
                    raise ParseError(f"Unexpected keyword {kw!r} at top level", tok)
            else:
                raise ParseError(f"Unexpected token {tok.value!r} at top level", tok)

        return program

    # ----- config ------------------------------------------------------------

    def _parse_config(self, config: Config) -> None:
        """Parse a config line like ``BPM 120``."""
        kw = self._advance()  # consume keyword
        num_tok = self._expect(TokenType.NUMBER)
        value = int(num_tok.value)

        if kw.value == "BPM":
            config.bpm = value
        elif kw.value == "AUDIO_RATE":
            config.audio_rate = value
        elif kw.value == "CONTROL_RATE":
            config.control_rate = value

        self._expect(TokenType.NEWLINE)

    # ----- instrument --------------------------------------------------------

    _WAVE_MAP: dict[str, WaveType] = {
        "SIN": WaveType.SIN,
        "SAW": WaveType.SAW,
        "SQUARE": WaveType.SQUARE,
        "TRIANGLE": WaveType.TRIANGLE,
        "NOISE": WaveType.NOISE,
    }

    _KIND_MAP: dict[str, InstrumentKind] = {
        "SYNTH": InstrumentKind.SYNTH,
        "DRUM": InstrumentKind.DRUM,
    }

    def _parse_instrument(self) -> InstrumentDef:
        """Parse an INSTRUMENT block.

        ::

            INSTRUMENT name:
                TYPE SYNTH
                WAVE SAW
                ADSR 10 50 200 100
                VOLUME 200
        """
        self._expect(TokenType.KEYWORD, "INSTRUMENT")
        name_tok = self._expect(TokenType.IDENT)
        self._expect(TokenType.COLON)
        self._expect(TokenType.NEWLINE)
        self._expect(TokenType.INDENT)

        inst = InstrumentDef(name=name_tok.value)

        while self._peek_type() != TokenType.DEDENT:
            self._skip_newlines()
            if self._peek_type() == TokenType.DEDENT:
                break

            kw = self._current()
            if kw.type != TokenType.KEYWORD:
                raise ParseError(f"Expected instrument property, got {kw.value!r}", kw)

            if kw.value == "TYPE":
                self._advance()
                kind_tok = self._expect(TokenType.KEYWORD)
                if kind_tok.value not in self._KIND_MAP:
                    raise ParseError(f"Unknown instrument type: {kind_tok.value!r}", kind_tok)
                inst.kind = self._KIND_MAP[kind_tok.value]
            elif kw.value == "WAVE":
                self._advance()
                wave_tok = self._expect(TokenType.KEYWORD)
                if wave_tok.value not in self._WAVE_MAP:
                    raise ParseError(f"Unknown waveform: {wave_tok.value!r}", wave_tok)
                inst.wave = self._WAVE_MAP[wave_tok.value]
            elif kw.value == "ADSR":
                self._advance()
                a = int(self._expect(TokenType.NUMBER).value)
                d = int(self._expect(TokenType.NUMBER).value)
                s = int(self._expect(TokenType.NUMBER).value)
                r = int(self._expect(TokenType.NUMBER).value)
                inst.adsr = ADSRParams(attack_ms=a, decay_ms=d, sustain_ms=s, release_ms=r)
            elif kw.value == "VOLUME":
                self._advance()
                inst.volume = int(self._expect(TokenType.NUMBER).value)
            elif kw.value == "FREQ":
                self._advance()
                inst.freq = int(self._expect(TokenType.NUMBER).value)
            elif kw.value == "DECAY":
                self._advance()
                inst.decay_ms = int(self._expect(TokenType.NUMBER).value)
            else:
                raise ParseError(f"Unknown instrument property: {kw.value!r}", kw)

            self._expect(TokenType.NEWLINE)

        self._expect(TokenType.DEDENT)
        return inst

    # ----- sequence ----------------------------------------------------------

    def _parse_sequence(self) -> Sequence:
        """Parse a SEQUENCE block.

        ::

            SEQUENCE name:
                PLAY instrument note beats
                REST beats
        """
        self._expect(TokenType.KEYWORD, "SEQUENCE")
        name_tok = self._expect(TokenType.IDENT)
        self._expect(TokenType.COLON)
        self._expect(TokenType.NEWLINE)
        self._expect(TokenType.INDENT)

        seq = Sequence(name=name_tok.value)

        while self._peek_type() != TokenType.DEDENT:
            self._skip_newlines()
            if self._peek_type() == TokenType.DEDENT:
                break

            kw = self._current()
            if kw.type == TokenType.KEYWORD and kw.value == "PLAY":
                self._advance()
                line = kw.line
                inst_tok = self._expect(TokenType.IDENT)

                # Note is optional for drums
                note: Optional[str] = None
                if self._peek_type() == TokenType.NOTE:
                    note = self._advance().value

                dur = float(self._expect(TokenType.NUMBER).value)
                seq.events.append(PlayNote(
                    instrument=inst_tok.value,
                    note=note,
                    duration_beats=dur,
                    line=line,
                ))
                self._expect(TokenType.NEWLINE)

            elif kw.type == TokenType.KEYWORD and kw.value == "REST":
                self._advance()
                dur = float(self._expect(TokenType.NUMBER).value)
                seq.events.append(RestEvent(duration_beats=dur, line=kw.line))
                self._expect(TokenType.NEWLINE)
            else:
                raise ParseError(
                    f"Expected PLAY or REST inside SEQUENCE, got {kw.value!r}", kw
                )

        self._expect(TokenType.DEDENT)
        return seq

    # ----- pattern -----------------------------------------------------------

    def _parse_pattern(self) -> Pattern:
        """Parse a PATTERN block.

        ::

            PATTERN name:
                BEAT 1: kick
                BEAT 2.5: snare
        """
        self._expect(TokenType.KEYWORD, "PATTERN")
        name_tok = self._expect(TokenType.IDENT)
        self._expect(TokenType.COLON)
        self._expect(TokenType.NEWLINE)
        self._expect(TokenType.INDENT)

        pat = Pattern(name=name_tok.value)

        while self._peek_type() != TokenType.DEDENT:
            self._skip_newlines()
            if self._peek_type() == TokenType.DEDENT:
                break

            kw = self._current()
            if kw.type == TokenType.KEYWORD and kw.value == "BEAT":
                self._advance()
                pos = float(self._expect(TokenType.NUMBER).value)
                self._expect(TokenType.COLON)
                inst_tok = self._expect(TokenType.IDENT)

                note: Optional[str] = None
                if self._peek_type() == TokenType.NOTE:
                    note = self._advance().value

                duration_beats: Optional[float] = None
                if self._peek_type() == TokenType.NUMBER:
                    duration_beats = float(self._advance().value)

                pat.events.append(BeatEvent(
                    beat_position=pos,
                    instrument=inst_tok.value,
                    note=note,
                    duration_beats=duration_beats,
                    line=kw.line,
                ))
                self._expect(TokenType.NEWLINE)
            else:
                raise ParseError(
                    f"Expected BEAT inside PATTERN, got {kw.value!r}", kw
                )

        self._expect(TokenType.DEDENT)
        return pat

    # ----- arrangement -------------------------------------------------------

    def _parse_arrangement_item(self) -> PlaySequenceRef | PlayPatternRef | LoopBlock:
        """Parse one arrangement item (LOOP block, PLAY_SEQUENCE, or PLAY_PATTERN)."""
        tok = self._current()

        if tok.type == TokenType.KEYWORD and tok.value == "LOOP":
            return self._parse_loop_block()
        elif tok.type == TokenType.KEYWORD and tok.value == "PLAY_SEQUENCE":
            self._advance()
            name = self._expect(TokenType.IDENT).value
            self._expect(TokenType.NEWLINE)
            return PlaySequenceRef(sequence_name=name, line=tok.line)
        elif tok.type == TokenType.KEYWORD and tok.value == "PLAY_PATTERN":
            self._advance()
            name = self._expect(TokenType.IDENT).value
            self._expect(TokenType.NEWLINE)
            return PlayPatternRef(pattern_name=name, line=tok.line)
        else:
            raise ParseError(f"Expected arrangement item, got {tok.value!r}", tok)

    def _parse_loop_block(self) -> LoopBlock:
        """Parse a LOOP block.

        ::

            LOOP 4:
                PLAY_SEQUENCE main
                PLAY_PATTERN drums
        """
        tok = self._expect(TokenType.KEYWORD, "LOOP")
        count = int(self._expect(TokenType.NUMBER).value)
        self._expect(TokenType.COLON)
        self._expect(TokenType.NEWLINE)
        self._expect(TokenType.INDENT)

        loop = LoopBlock(count=count, line=tok.line)

        while self._peek_type() != TokenType.DEDENT:
            self._skip_newlines()
            if self._peek_type() == TokenType.DEDENT:
                break
            item = self._parse_arrangement_item()
            loop.body.append(item)

        self._expect(TokenType.DEDENT)
        return loop


def parse(source: str) -> Program:
    """Convenience function: parse source text into a Program AST.

    Args:
        source: Full .mozzi file content.

    Returns:
        Program AST.
    """
    return Parser(source).parse()
