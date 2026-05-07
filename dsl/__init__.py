"""
Mozzi DSL Compiler — transforms a high-level music DSL into Mozzi 2.0 C++ sketches
for Arduino Uno (ATmega328P), or renders to WAV for audio preview.

Modules:
    ast_nodes    - AST node definitions (dataclasses)
    lexer        - tokenizer for the .mdsl DSL
    parser       - recursive-descent parser producing an AST
    semantic     - validation pass on the AST
    codegen      - AST -> Mozzi 2.0 C++ code generator
    wav_backend  - AST -> WAV audio file renderer
    notes        - note name / MIDI / frequency conversion
    compiler     - end-to-end pipeline (CLI entry point)
"""

__version__ = "0.1.0"
