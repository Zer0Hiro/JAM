---
sidebar_position: 1
---

# Getting Started

Write your first JAM program and hear it play.

## Prerequisites

- Python 3.8+
- Clone the repo:

```bash
git clone https://github.com/zer0hiro/JAM-DSL-Compiler.git
cd JAM-DSL-Compiler
```

:::info
No additional Python packages are required — the compiler uses only the standard library.
:::

## Your First Program

Create a file called `hello.jam`:

```
BPM 120

INSTRUMENT tone:
    TYPE SYNTH
    WAVE SIN
    ADSR 10 50 200 100
    VOLUME 200

SEQUENCE melody:
    PLAY tone C4 1
    PLAY tone E4 1
    PLAY tone G4 2

PLAY_SEQUENCE melody
```

## Compile and Preview

Generate a WAV file to hear your music:

```bash
python3 -m dsl.compiler hello.jam --wav -o hello.wav
```

:::tip
You can pipe the output to stdout by omitting `-o` — useful for piping into other tools or quick testing.
:::

Play it with any audio player, or compile to C++ for hardware:

```bash
python3 -m dsl.compiler hello.jam -o src/main.cpp
```

## Validate Without Compiling

Check for errors without generating output:

```bash
python3 -m dsl.compiler hello.jam --dry-run --verbose
```

:::tip
Run `--dry-run --verbose` frequently while writing. It catches undefined instruments, out-of-range values, and notes outside your key — all without generating files.
:::

## What's Next?

- [Your First Song](./first-song) — build a multi-instrument track step by step
- [Drum Patterns](./drum-patterns) — create beats with the pattern grid
- [Effects and Mixing](./effects-and-mixing) — add reverb, delay, filters, and panning
- [Upload to Hardware](./upload-to-hardware) — flash your music to an ESP32
