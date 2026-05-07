---
name: Mozzi DSL design decisions
description: Key architecture and grammar decisions for the .jam compiler — sequencer model, keyword casing, sharp-note handling, WAV backend
type: project
---

The DSL compiler uses an event-list sequencer architecture: loops are unrolled in Python at compile time into a flat PROGMEM array of NoteEvent structs. updateControl() walks this array with mozziMicros() timing. This was chosen over a state-machine approach for simplicity and predictable SRAM usage on ATmega328.

**Why:** The Arduino Uno has only 2KB RAM. A flat event array in PROGMEM uses flash (32KB) instead of SRAM, and the sequencer state is just 3 variables (currentEvent, eventStartTime, eventTriggered).

**How to apply:** When adding new DSL features that expand events (e.g., nested loops, conditionals), always unroll in Python -- never generate recursive C++ structures that consume stack on AVR.

Key resolved decisions:
- Keywords must be UPPERCASE in source (prevents "beat" identifier from colliding with BEAT keyword)
- Sharp notes (D#3, F#5) require context-aware comment stripping: # is only a comment when preceded by whitespace
- Oscillators are template-typed in Mozzi (Oscil<TABLE_SIZE, AUDIO_RATE>) so channel dispatch uses if/else chains, not array indexing
- WAV backend added as a pure-stdlib (wave, struct, math) renderer at 44.1kHz 16-bit mono for computer-side preview
- Max recommended synth channels: 4 (due to 2KB SRAM constraint)
