#!/usr/bin/env python3
"""
Mozzi DSL Compiler — main entry point.

Reads a .mdsl file, parses it, validates the AST, and generates output:
- Mozzi 2.0 C++ sketch (default)
- WAV audio preview (--wav flag)

Usage:
    python -m dsl.compiler input.mdsl                    # C++ to stdout
    python -m dsl.compiler input.mdsl -o src/sketch.cpp  # C++ to file
    python -m dsl.compiler input.mdsl --wav -o out.wav   # WAV audio preview
    python -m dsl.compiler input.mdsl --verbose           # show AST + diagnostics
    python -m dsl.compiler input.mdsl --dry-run           # parse only, no codegen
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Optional

# Support running both as `python dsl/compiler.py` and `python -m dsl.compiler`
if __name__ == "__main__" and __package__ is None:
    # When run directly as a script, add parent dir to path so relative
    # imports work via the package shim below.
    _parent = str(Path(__file__).resolve().parent.parent)
    if _parent not in sys.path:
        sys.path.insert(0, _parent)
    __package__ = "dsl"

from .parser import Parser, ParseError, parse
from .lexer import LexerError
from .semantic import validate
from .codegen import generate
from .ast_nodes import Program


def compile_file(
    source_path: str,
    output_path: Optional[str] = None,
    verbose: bool = False,
    dry_run: bool = False,
    wav_mode: bool = False,
) -> bool:
    """Compile a .mdsl file to a Mozzi 2.0 C++ sketch or WAV preview.

    Args:
        source_path: Path to the .mdsl input file.
        output_path: Path to write the output. None = stdout (C++ only).
        verbose: If True, print the AST and diagnostics.
        dry_run: If True, parse and validate but skip code generation.
        wav_mode: If True, render to WAV instead of C++.

    Returns:
        True if compilation succeeded, False if there were errors.
    """
    # Read source
    path = Path(source_path)
    if not path.exists():
        print(f"Error: file not found: {source_path}", file=sys.stderr)
        return False

    source = path.read_text(encoding="utf-8")

    if verbose:
        print(f"--- Compiling: {source_path} ---", file=sys.stderr)

    # Parse
    try:
        program = parse(source)
    except LexerError as e:
        print(f"Lexer error: {e}", file=sys.stderr)
        return False
    except ParseError as e:
        print(f"Parse error: {e}", file=sys.stderr)
        return False

    if verbose:
        print("\n--- AST ---", file=sys.stderr)
        _print_ast(program)

    # Validate
    result = validate(program)

    if verbose or result.diagnostics:
        print("\n--- Diagnostics ---", file=sys.stderr)
        for d in result.diagnostics:
            print(f"  {d}", file=sys.stderr)
        if not result.diagnostics:
            print("  (no issues found)", file=sys.stderr)

    if not result.ok:
        print(
            f"\nCompilation failed with {len(result.errors)} error(s).",
            file=sys.stderr,
        )
        return False

    if dry_run:
        print("\n--- Dry run: skipping code generation ---", file=sys.stderr)
        return True

    # Generate output
    if wav_mode:
        return _generate_wav(program, source_path, output_path, verbose)
    else:
        return _generate_cpp(program, output_path)


def _generate_cpp(program: Program, output_path: Optional[str]) -> bool:
    """Generate Mozzi C++ output.

    Args:
        program: Validated Program AST.
        output_path: Output file path, or None for stdout.

    Returns:
        True on success.
    """
    cpp_code = generate(program)

    if output_path:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(cpp_code, encoding="utf-8")
        print(f"Written: {output_path}", file=sys.stderr)
    else:
        print(cpp_code)

    return True


def _generate_wav(
    program: Program,
    source_path: str,
    output_path: Optional[str],
    verbose: bool,
) -> bool:
    """Generate WAV audio preview.

    Args:
        program: Validated Program AST.
        source_path: Original source path (for default output naming).
        output_path: Output .wav path, or None for auto-naming.
        verbose: Show extra info.

    Returns:
        True on success.
    """
    from .wav_backend import WavRenderer

    renderer = WavRenderer(program)

    if not output_path:
        # Default: same name as input but .wav extension
        output_path = str(Path(source_path).with_suffix(".wav"))

    if verbose:
        dur = renderer.total_duration_s()
        print(
            f"\n--- WAV render: {dur:.2f}s at 44100Hz ---",
            file=sys.stderr,
        )

    renderer.render(output_path)
    print(f"WAV written: {output_path}", file=sys.stderr)
    return True


def _print_ast(program: Program) -> None:
    """Pretty-print a Program AST to stderr."""
    d = asdict(program)
    # Convert enum values to strings for JSON serialization
    _enum_to_str(d)
    print(json.dumps(d, indent=2), file=sys.stderr)


def _enum_to_str(obj: object) -> None:
    """Recursively convert enum values in a dict/list to their name strings."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if hasattr(v, "name") and hasattr(v, "value") and isinstance(v.value, int):
                obj[k] = v.name
            else:
                _enum_to_str(v)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            if hasattr(v, "name") and hasattr(v, "value") and isinstance(v.value, int):
                obj[i] = v.name
            else:
                _enum_to_str(v)


def main() -> None:
    """CLI entry point for the Mozzi DSL compiler."""
    parser = argparse.ArgumentParser(
        prog="mozzi-dsl",
        description=(
            "Compile .mdsl files into Mozzi 2.0 C++ sketches for Arduino Uno, "
            "or render to WAV for audio preview."
        ),
    )
    parser.add_argument(
        "input",
        help="Path to the .mdsl source file.",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help=(
            "Output file path. For C++ mode: .cpp file (omit for stdout). "
            "For WAV mode: .wav file (omit for auto-named)."
        ),
    )
    parser.add_argument(
        "--wav",
        action="store_true",
        help="Render to WAV audio preview instead of C++ code.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show AST and validation diagnostics.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate only — do not generate output.",
    )

    args = parser.parse_args()
    ok = compile_file(
        source_path=args.input,
        output_path=args.output,
        verbose=args.verbose,
        dry_run=args.dry_run,
        wav_mode=args.wav,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
