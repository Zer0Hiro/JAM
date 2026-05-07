# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a PlatformIO project for Arduino Uno (ATmega328) using the [Mozzi](https://sensorium.github.io/Mozzi/) sound synthesis library. The goal is to produce audio synthesis on bare Arduino hardware via PWM output on pin 9 (and optionally pin 10 for stereo).

## Build & Upload Commands

```bash
# Build the project
pio run

# Upload to connected Arduino Uno
pio run --target upload

# Clean build artifacts
pio run --target clean

# Monitor serial output
pio device monitor
```

PlatformIO must be installed (`pip install platformio` or via the VS Code extension `platformio.platformio-ide`).

## Project Structure

- `src/` — main sketch file(s) (`.cpp` or `.ino`); currently empty — add your sketch here
- `include/` — project-specific headers
- `lib/` — local libraries (currently empty; project-level deps go here)
- `Mozzi/` — bundled Mozzi 2.0 library source
- `FixMath/` — bundled fixed-point math library (used by Mozzi internally and useful for audio code)
- `platformio.ini` — build config targeting `atmelavr` / `board = uno`

## Mozzi 2.0 Sketch Structure

Every sketch must implement these three functions:

```cpp
#include <Mozzi.h>

void setup() {
    startMozzi(); // optional: pass MOZZI_CONTROL_RATE
}

void updateControl() {
    // called at MOZZI_CONTROL_RATE (default 64 Hz) — read sensors, update envelopes, LFOs
}

AudioOutput updateAudio() {
    // called at MOZZI_AUDIO_RATE (default 16384 Hz) — return next audio sample
    return MonoOutput::from8Bit(sample);
}

void loop() {
    audioHook(); // must be the only thing in loop()
}
```

**Include `Mozzi.h`** (not the old `MozziGuts.h`) for Mozzi 2.0 compatibility.

## Key Mozzi Concepts

- **Audio output pin**: pin 9 (mono PWM) on Uno; pin 10 added for stereo
- **Config macros** (define before `#include <Mozzi.h>`):
  - `MOZZI_AUDIO_RATE` — sample rate, typically `16384` or `32768`
  - `MOZZI_CONTROL_RATE` — control loop rate, `64`–`1024` Hz
  - `MOZZI_OUTPUT_MODE` — e.g. `MOZZI_OUTPUT_PWM`, `MOZZI_OUTPUT_2PIN_PWM` (HIFI)
- **`updateAudio()` must be fast** — runs at audio rate on an 8-bit MCU; avoid division, floating point, and anything slow
- **FixMath** (`UFix`, `SFix` templates) provides efficient fixed-point arithmetic to replace floats in audio code
- **`mozziMicros()`** replaces `micros()` for timing; avoid `delay()`/`millis()` inside Mozzi sketches
- **Oscillators**: `Oscil<TABLE_SIZE, AUDIO_RATE>` — pass a wavetable from `Mozzi/tables/`
- **Envelopes**: `ADSR<CONTROL_RATE, AUDIO_RATE>` — update in `updateControl()`, call `.next()` in `updateAudio()`

## Porting from Mozzi 1.x

| Old name | Mozzi 2.0 name |
|---|---|
| `AUDIO_RATE` | `MOZZI_AUDIO_RATE` |
| `CONTROL_RATE` | `MOZZI_CONTROL_RATE` |
| `STANDARD` output mode | `MOZZI_OUTPUT_PWM` |
| `HIFI` output mode | `MOZZI_OUTPUT_2PIN_PWM` |
| `EXTERNAL_AUDIO_OUTPUT` | `MOZZI_OUTPUT_EXTERNAL_TIMED` / `MOZZI_OUTPUT_EXTERNAL_CUSTOM` |
| `MozziGuts.h` | `Mozzi.h` |
