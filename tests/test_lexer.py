"""Tests for dsl.lexer — tokenization."""

import pytest
from dsl.lexer import tokenize, TokenType, LexerError


class TestTokenizeBasic:
    """Test basic token recognition."""

    def test_bpm_line(self) -> None:
        tokens = tokenize("BPM 120")
        types = [t.type for t in tokens if t.type not in (TokenType.NEWLINE, TokenType.EOF)]
        assert types == [TokenType.KEYWORD, TokenType.NUMBER]
        assert tokens[0].value == "BPM"
        assert tokens[1].value == "120"

    def test_note_token(self) -> None:
        tokens = tokenize("C4")
        note_tok = [t for t in tokens if t.type == TokenType.NOTE]
        assert len(note_tok) == 1
        assert note_tok[0].value == "C4"

    def test_sharp_note(self) -> None:
        tokens = tokenize("D#3")
        note_tok = [t for t in tokens if t.type == TokenType.NOTE]
        assert len(note_tok) == 1
        assert note_tok[0].value == "D#3"

    def test_flat_note(self) -> None:
        tokens = tokenize("Bb2")
        note_tok = [t for t in tokens if t.type == TokenType.NOTE]
        assert len(note_tok) == 1
        assert note_tok[0].value == "Bb2"

    def test_identifier(self) -> None:
        tokens = tokenize("my_synth")
        ident_tok = [t for t in tokens if t.type == TokenType.IDENT]
        assert len(ident_tok) == 1
        assert ident_tok[0].value == "my_synth"

    def test_colon(self) -> None:
        tokens = tokenize("INSTRUMENT foo:")
        colon = [t for t in tokens if t.type == TokenType.COLON]
        assert len(colon) == 1

    def test_float_number(self) -> None:
        tokens = tokenize("0.5")
        nums = [t for t in tokens if t.type == TokenType.NUMBER]
        assert len(nums) == 1
        assert nums[0].value == "0.5"


class TestTokenizeComments:
    """Test comment handling."""

    def test_line_comment(self) -> None:
        tokens = tokenize("# this is a comment\nBPM 120")
        kw = [t for t in tokens if t.type == TokenType.KEYWORD]
        assert len(kw) == 1
        assert kw[0].value == "BPM"

    def test_inline_comment(self) -> None:
        tokens = tokenize("BPM 120  # tempo")
        kw = [t for t in tokens if t.type == TokenType.KEYWORD]
        assert len(kw) == 1


class TestTokenizeIndentation:
    """Test indentation tracking."""

    def test_indent_dedent(self) -> None:
        source = "INSTRUMENT foo:\n    TYPE SYNTH\n"
        tokens = tokenize(source)
        types = [t.type for t in tokens]
        assert TokenType.INDENT in types
        assert TokenType.DEDENT in types

    def test_nested_indent(self) -> None:
        source = "LOOP 2:\n    PLAY_SEQUENCE foo\n"
        tokens = tokenize(source)
        types = [t.type for t in tokens]
        assert types.count(TokenType.INDENT) == 1
        assert types.count(TokenType.DEDENT) == 1


class TestTokenizeCaseSensitivity:
    """Test that keywords must be uppercase."""

    def test_lowercase_keyword_is_ident(self) -> None:
        tokens = tokenize("beat")
        ident_tok = [t for t in tokens if t.type == TokenType.IDENT]
        assert len(ident_tok) == 1
        assert ident_tok[0].value == "beat"

    def test_uppercase_keyword_is_keyword(self) -> None:
        tokens = tokenize("BEAT")
        kw = [t for t in tokens if t.type == TokenType.KEYWORD]
        assert len(kw) == 1
        assert kw[0].value == "BEAT"

    def test_mixed_case_is_ident(self) -> None:
        tokens = tokenize("Play")
        ident_tok = [t for t in tokens if t.type == TokenType.IDENT]
        assert len(ident_tok) == 1


class TestTokenizeErrors:
    """Test error handling."""

    def test_eof_token(self) -> None:
        tokens = tokenize("")
        assert tokens[-1].type == TokenType.EOF

    def test_inconsistent_indent_raises(self) -> None:
        source = "LOOP 2:\n        PLAY_SEQUENCE foo\n    PLAY_SEQUENCE bar\n"
        # The dedent from 8 to 4 should fail if 4 was never on the stack
        # Actually this depends on the indent stack; 8->4 may work if base is 0
        # Let's test a real inconsistency
        source = "LOOP 2:\n    PLAY_SEQUENCE foo\n  PLAY_SEQUENCE bar\n"
        with pytest.raises(LexerError):
            tokenize(source)
