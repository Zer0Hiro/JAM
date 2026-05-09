"""
Tokenizer for the Mozzi DSL.

Produces a flat list of Token objects from source text.  The lexer is
line-oriented: it strips comments, tracks indentation depth, and emits
INDENT / DEDENT tokens so the parser can handle block structure without
a separate indentation pre-pass.

Token types
-----------
KEYWORD     BPM, AUDIO_RATE, CONTROL_RATE, INSTRUMENT, TYPE, WAVE, ADSR,
            VOLUME, FREQ, DECAY, SEQUENCE, PATTERN, PLAY, REST, BEAT,
            LOOP, PLAY_SEQUENCE, PLAY_PATTERN
NOTE        C4, D#3, Bb2, Fs5, ...
NUMBER      integer or float literal
IDENT       user-defined identifier (instrument/sequence/pattern names)
COLON       ':'
NEWLINE     end of a logical line
INDENT      increase in indentation level
DEDENT      decrease in indentation level
EOF         end of input
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class TokenType(Enum):
    """All token types emitted by the lexer."""
    # Keywords
    KEYWORD = auto()
    # Literals
    NOTE = auto()
    NUMBER = auto()
    # Identifiers
    IDENT = auto()
    # Punctuation
    COLON = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    # Structure
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    EOF = auto()


# Set of keyword strings recognised by the lexer
KEYWORDS: set[str] = {
    "BPM", "AUDIO_RATE", "CONTROL_RATE",
    "INSTRUMENT", "TYPE", "WAVE", "ADSR", "VOLUME", "FREQ", "DECAY",
    "SEQUENCE", "PATTERN", "PLAY", "REST", "BEAT",
    "LOOP", "PLAY_SEQUENCE", "PLAY_PATTERN", "PLAY_TOGETHER",
    # Instrument-kind keywords used as values
    "SYNTH", "DRUM",
    # Waveform keywords used as values
    "SIN", "SAW", "SQUARE", "TRIANGLE", "NOISE",
}

# Regex matching a scientific pitch note (C4, D#3, Bb2, Fs5 ...)
_NOTE_RE = re.compile(r"^[A-Ga-g][#sb]?\d+$")

# Regex matching a number (int or float)
_NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?$")


@dataclass
class Token:
    """A single token produced by the lexer.

    Attributes:
        type: The token type.
        value: The string value of the token.
        line: 1-based source line number.
        col: 1-based column number.
    """
    type: TokenType
    value: str
    line: int = 0
    col: int = 0

    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r}, L{self.line})"


class LexerError(Exception):
    """Raised when the lexer encounters invalid input."""

    def __init__(self, message: str, line: int = 0, col: int = 0) -> None:
        self.line = line
        self.col = col
        super().__init__(f"Line {line}, col {col}: {message}")


def _find_comment_start(line: str) -> int:
    """Find the position of a comment '#' in a line.

    A '#' is treated as a comment only when preceded by whitespace or at
    column 0.  This preserves '#' inside note names (D#3, F#5).

    Args:
        line: The source line (may include leading whitespace).

    Returns:
        Index of the comment '#', or -1 if none found.
    """
    i = 0
    length = len(line)
    while i < length:
        ch = line[i]
        if ch == "#":
            # Comment if at start or preceded by whitespace
            if i == 0 or line[i - 1] in (" ", "\t"):
                return i
        i += 1
    return -1


def tokenize(source: str) -> list[Token]:
    """Tokenize a Mozzi DSL source string.

    Args:
        source: The full DSL source text.

    Returns:
        A list of Token objects, ending with an EOF token.

    Raises:
        LexerError: On unrecognisable input.
    """
    tokens: list[Token] = []
    indent_stack: list[int] = [0]  # current indentation levels in spaces

    lines = source.split("\n")

    for line_num_0, raw_line in enumerate(lines):
        line_num = line_num_0 + 1  # 1-based

        # Strip trailing whitespace / CR
        line = raw_line.rstrip()

        # Skip blank lines and comment-only lines
        if not line or line.lstrip().startswith("#"):
            continue

        # Strip inline comment — a '#' counts as a comment start only if
        # it is preceded by whitespace (or is the first non-space char).
        # This preserves '#' inside note names like D#3 and F#5.
        comment_idx = _find_comment_start(line)
        if comment_idx >= 0:
            line = line[:comment_idx].rstrip()
            if not line:
                continue

        # Measure indentation (spaces only — tabs are 4 spaces)
        stripped = line.lstrip(" \t")
        indent_chars = len(line) - len(stripped)
        # Normalise tabs to 4 spaces for indent counting
        indent = 0
        for ch in line[: indent_chars]:
            if ch == "\t":
                indent += 4
            else:
                indent += 1

        # Emit INDENT / DEDENT tokens
        if indent > indent_stack[-1]:
            indent_stack.append(indent)
            tokens.append(Token(TokenType.INDENT, "<INDENT>", line_num, 1))
        else:
            while indent < indent_stack[-1]:
                indent_stack.pop()
                tokens.append(Token(TokenType.DEDENT, "<DEDENT>", line_num, 1))
            if indent != indent_stack[-1]:
                raise LexerError("Inconsistent indentation", line_num, indent + 1)

        # Tokenize the content of the line
        _tokenize_line(stripped, line_num, indent + 1, tokens)

        # Emit NEWLINE after each logical line
        tokens.append(Token(TokenType.NEWLINE, "\\n", line_num, len(raw_line)))

    # Close any remaining indentation levels
    while len(indent_stack) > 1:
        indent_stack.pop()
        tokens.append(Token(TokenType.DEDENT, "<DEDENT>", len(lines), 1))

    tokens.append(Token(TokenType.EOF, "<EOF>", len(lines) + 1, 1))
    return tokens


def _tokenize_line(line: str, line_num: int, col_offset: int, tokens: list[Token]) -> None:
    """Break a single stripped line into tokens and append them to *tokens*.

    Args:
        line: The line content with leading whitespace already removed.
        line_num: 1-based line number for error reporting.
        col_offset: Column offset for the first character.
        tokens: Accumulator list.
    """
    pos = 0
    length = len(line)

    while pos < length:
        ch = line[pos]

        # Skip whitespace between tokens
        if ch in (" ", "\t"):
            pos += 1
            continue

        # Punctuation
        if ch == ":":
            tokens.append(Token(TokenType.COLON, ":", line_num, col_offset + pos))
            pos += 1
            continue
        if ch == "[":
            tokens.append(Token(TokenType.LBRACKET, "[", line_num, col_offset + pos))
            pos += 1
            continue
        if ch == "]":
            tokens.append(Token(TokenType.RBRACKET, "]", line_num, col_offset + pos))
            pos += 1
            continue

        # Collect a word (letters, digits, #, _, .)
        # '#' is included because inline comments are already stripped;
        # any '#' here is part of a note name like D#3.
        word_start = pos
        while pos < length and line[pos] not in (" ", "\t", ":", "[", "]"):
            pos += 1
        word = line[word_start:pos]
        col = col_offset + word_start

        if not word:
            raise LexerError(f"Unexpected character: {ch!r}", line_num, col)

        # Classify the word.
        # Keywords must be written in UPPERCASE in DSL source — this
        # prevents identifiers like "beat" from being misclassified.
        if word in KEYWORDS:
            tokens.append(Token(TokenType.KEYWORD, word, line_num, col))
        elif _NOTE_RE.match(word):
            # Normalise note: uppercase letter, original accidental, digit
            normalised = word[0].upper() + word[1:]
            tokens.append(Token(TokenType.NOTE, normalised, line_num, col))
        elif _NUMBER_RE.match(word):
            tokens.append(Token(TokenType.NUMBER, word, line_num, col))
        else:
            # Treat as identifier
            tokens.append(Token(TokenType.IDENT, word, line_num, col))
