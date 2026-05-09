# JAM DSL Compiler

Python compiler that transforms `.jam` music notation into Mozzi 2.0 C++ sketches for ESP32/Arduino hardware, with optional WAV preview rendering.

## Quick Start

```bash
# Generate Mozzi C++ to stdout
python3 -m dsl.compiler my_song.jam

# Generate C++ to file
python3 -m dsl.compiler my_song.jam -o src/main.cpp

# Render WAV audio preview (no hardware needed)
python3 -m dsl.compiler my_song.jam --wav -o my_song.wav

# Parse only (validate syntax, show AST)
python3 -m dsl.compiler my_song.jam --dry-run --verbose
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `-o PATH` | Output file path (omit for stdout in C++ mode) |
| `--wav` | Render to WAV instead of C++ |
| `--verbose`, `-v` | Print AST and diagnostics |
| `--dry-run` | Parse and validate only, no output generated |

## Pipeline

```
.jam source
    |
  Lexer (lexer.py) --> tokens
    |
  Parser (parser.py) --> AST (ast_nodes.py)
    |
  Semantic Validator (semantic.py) --> diagnostics
    |
  Code Generator (codegen.py) --> Mozzi C++ sketch
    |
  WAV Renderer (wav_backend.py) --> .wav preview (optional)
```

## Project Structure

```
dsl/
    lexer.py          Tokenizer for .jam syntax
    parser.py         Recursive descent parser -> AST
    ast_nodes.py      AST node definitions (Program, Instrument, Sequence, Pattern, etc.)
    semantic.py       Validation and diagnostics
    codegen.py        Mozzi 2.0 C++ code generator with ESP32 pin selection
    wav_backend.py    Software WAV renderer for browser preview
    notes.py          Note name to frequency mapping
    compiler.py       CLI entry point
docs/
    SyntaxGuide.md    Full language syntax reference
dsl_examples/         Example .jam files
tests/                Unit tests for each pipeline stage
platformio.ini        PlatformIO config (ESP32 / Arduino Uno)
src/main.cpp          Generated sketch output
```

## Language Overview

JAM files define instruments, sequences, patterns, and an arrangement. For the full syntax reference, see **[docs/SyntaxGuide.md](docs/SyntaxGuide.md)**.

### Instruments

Define synths and drums with waveform, envelope, and volume:

```
INSTRUMENT lead:
    TYPE SYNTH
    WAVE SAW
    ADSR 10 50 200 100
    VOLUME 180

INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 60
    DECAY 80
    VOLUME 255
```

### Sequences

Note-by-note melodies with durations in beats. Supports chords with bracket notation:

```
SEQUENCE melody:
    PLAY lead C4 0.5
    PLAY lead E4 1
    REST 0.5
    PLAY lead [C4 E4 G4] 2    # chord
```

### Patterns

Beat-grid placement for drums and instruments. Multiple instruments on the same beat play simultaneously:

```
PATTERN beat:
    BEAT 1: kick
    BEAT 1: hat
    BEAT 2: snare
    BEAT 3: kick
    BEAT 4: snare
```

### Arrangement

Control playback order with `PLAY_SEQUENCE`, `PLAY_PATTERN`, `LOOP`, and `PLAY_TOGETHER`:

```
LOOP 4:
    PLAY_TOGETHER:
        PLAY_SEQUENCE bassline
        PLAY_SEQUENCE melody
        PLAY_PATTERN beat
```

`PLAY_TOGETHER` plays all children simultaneously — bass, melody, and drums all sound at once instead of one after another.

## Quick Example

```
BPM 120

INSTRUMENT bass:
    TYPE SYNTH
    WAVE SAW
    ADSR 5 40 300 120
    VOLUME 220

INSTRUMENT lead:
    TYPE SYNTH
    WAVE TRIANGLE
    ADSR 10 30 200 100
    VOLUME 180

INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 55
    DECAY 100
    VOLUME 255

SEQUENCE bassline:
    PLAY bass C2 1
    PLAY bass C2 1
    PLAY bass G2 1
    PLAY bass F2 1

SEQUENCE melody:
    PLAY lead E4 0.5
    PLAY lead G4 0.5
    PLAY lead A4 1
    PLAY lead G4 0.5
    PLAY lead E4 0.5
    PLAY lead D4 1

PATTERN beat:
    BEAT 1: kick
    BEAT 3: kick

LOOP 2:
    PLAY_TOGETHER:
        PLAY_SEQUENCE bassline
        PLAY_SEQUENCE melody
        PLAY_PATTERN beat
```

More examples in [`dsl_examples/`](dsl_examples/).

## Hardware Targets

- **ESP32** (esp32dev) — primary target, internal DAC (GPIO 25) or configurable PWM output pin
- **Arduino Uno** (ATmega328P) — PWM output on pin 9

## Tests

```bash
python3 -m pytest tests/
```

## Requirements

- Python 3.10+
- PlatformIO (for hardware upload)
- Mozzi library (installed via PlatformIO)
