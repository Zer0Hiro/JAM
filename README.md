# JAM DSL

A Python DSL compiler that transforms `.jam` music notation into Mozzi 2.0 C++ sketches for Arduino/ESP32 hardware, with optional WAV preview rendering.

## What it does

Write music in a high-level language:

```
BPM 120

INSTRUMENT bass:
    TYPE SYNTH
    WAVE SAW
    ADSR 5 40 300 120
    VOLUME 200

INSTRUMENT kick:
    TYPE DRUM
    WAVE SIN
    FREQ 55
    DECAY 100

SEQUENCE intro:
    PLAY bass C2 1
    PLAY bass G2 1

PATTERN beat:
    BEAT 1: kick
    BEAT 1: bass C2
    BEAT 3: kick
    BEAT 3: bass G2

LOOP 4:
    PLAY_SEQUENCE intro
    PLAY_PATTERN beat
```

The compiler generates a complete Mozzi 2.0 C++ sketch with event-sequencer, oscillators, ADSR envelopes, and audio mixing -- ready to upload via PlatformIO.

## Pipeline

```
.jam source
    |
    v
  Lexer (lexer.py) --> tokens
    |
    v
  Parser (parser.py) --> AST (ast_nodes.py)
    |
    v
  Semantic Validator (semantic.py) --> diagnostics
    |
    v
  Code Generator (codegen.py) --> Mozzi C++ sketch
    |
    v
  WAV Renderer (wav_backend.py) --> .wav preview (optional)
```

## Usage

### Compile to C++

```bash
python3 -m dsl.compiler my_song.jam -o src/main.cpp
```

### Compile and render WAV preview

```bash
python3 -m dsl.compiler my_song.jam -o src/main.cpp --wav preview.wav
```

### Upload to hardware (PlatformIO)

```bash
python3 -m dsl.compiler my_song.jam -o src/main.cpp
pio run --target upload
```

## Project Structure

```
dsl/
    lexer.py          Tokenizer for .jam syntax
    parser.py         Recursive descent parser -> AST
    ast_nodes.py      AST node definitions (Program, Instrument, Sequence, Pattern, etc.)
    semantic.py       Validation and diagnostics
    codegen.py        Mozzi 2.0 C++ code generator
    wav_backend.py    Software WAV renderer for browser preview
    notes.py          Note name to frequency mapping
    compiler.py       CLI entry point
dsl_examples/         Example .jam files
tests/                Unit tests for each pipeline stage
platformio.ini        PlatformIO config (ESP32 / Arduino Uno)
```

## DSL Features

- **Instruments**: SYNTH (oscillator-based) and DRUM (percussive) types
- **Waveforms**: SIN, SAW, SQUARE, TRIANGLE, NOISE
- **ADSR envelopes**: attack, decay, sustain, release control
- **Sequences**: sequential note playback with durations in beats
- **Patterns**: beat-grid notation with simultaneous multi-instrument playback
- **Chords**: bracket notation `[C4 E4 G4]` for polyphonic voices
- **Loops**: repeat sections with `LOOP N:`
- **Configurable**: BPM, AUDIO_RATE, CONTROL_RATE
- **ESP32 pin selection**: configurable GPIO output pin for PWM audio

## Hardware Targets

- **ESP32** (esp32dev) -- primary target, internal DAC or PWM output
- **Arduino Uno** (ATmega328P) -- PWM output on pin 9

## Tests

```bash
python3 -m pytest tests/
```

## Requirements

- Python 3.10+
- PlatformIO (for hardware upload)
- Mozzi library (installed via PlatformIO)
