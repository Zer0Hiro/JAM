---
sidebar_position: 3
---

# Grammar

## Formal Grammar

```
program        := (config | instrument | sequence | pattern | arrangement)* EOF

config         := ("BPM" | "AUDIO_RATE" | "CONTROL_RATE") NUMBER
                 | "KEY" NOTE ("MAJOR"|"MINOR"|"DORIAN"|"PHRYGIAN"|"LYDIAN"|"MIXOLYDIAN"|"PENTATONIC"|"BLUES")
                 | "SWING" NUMBER
                 | "HUMANIZE" NUMBER

instrument     := "INSTRUMENT" IDENT ":"
                      ("TYPE" ("SYNTH" | "DRUM")
                     | "WAVE" ("SIN" | "SAW" | "SQUARE" | "TRIANGLE" | "NOISE" | "PLUCK" | "HANDPAN")
                     | "ADSR" NUMBER NUMBER NUMBER NUMBER
                     | "VOLUME" NUMBER
                     | "FREQ" NUMBER
                     | "DECAY" NUMBER
                     | "CUTOFF" NUMBER
                     | "RESONANCE" NUMBER
                     | "REVERB" NUMBER
                     | "DELAY" NUMBER NUMBER
                     | "GLIDE" NUMBER
                     | "PAN" NUMBER
                     | "LFO" NUMBER NUMBER ("VOLUME" | "PITCH" | "CUTOFF" | "PAN")
                     | "VOICES" NUMBER
                     | "DETUNE" NUMBER
                     | "CHORUS" NUMBER)+

sequence       := "SEQUENCE" IDENT ":"
                      ("PLAY" IDENT NOTE NUMBER [NUMBER] [fx_override]*
                     | "PLAY" IDENT "[" NOTE+ "]" NUMBER [NUMBER] [fx_override]*
                     | "REST" NUMBER
                     | velocity_curve)+

velocity_curve := "VELOCITY_CURVE" ("CRESCENDO" | "DECRESCENDO") NUMBER NUMBER NUMBER
                | "VELOCITY_CURVE" "OFF"

fx_override    := "CUTOFF" ":" NUMBER
                | "REVERB" ":" NUMBER
                | "DELAY" ":" NUMBER ":" NUMBER

pattern        := "PATTERN" IDENT ":"
                      ("BEAT" NUMBER ":" IDENT [NOTE] [NUMBER] [NUMBER] [fx_override]*)+

arrangement    := (loop | play_seq | play_pat | play_together | bpm_change | vol_change | fade)+
bpm_change     := "BPM" NUMBER
vol_change     := "VOLUME" NUMBER
fade           := ("FADE_IN" | "FADE_OUT") NUMBER
loop           := "LOOP" NUMBER ":" INDENT arrangement DEDENT
play_seq       := "PLAY_SEQUENCE" IDENT
play_pat       := "PLAY_PATTERN" IDENT
play_together  := "PLAY_TOGETHER" ":" INDENT arrangement DEDENT
```

## Keywords

All keywords must be UPPERCASE:

`BPM`, `AUDIO_RATE`, `CONTROL_RATE`, `KEY`, `SWING`, `HUMANIZE`, `MAJOR`, `MINOR`, `DORIAN`, `PHRYGIAN`, `LYDIAN`, `MIXOLYDIAN`, `PENTATONIC`, `BLUES`, `INSTRUMENT`, `TYPE`, `SYNTH`, `DRUM`, `WAVE`, `SIN`, `SAW`, `SQUARE`, `TRIANGLE`, `NOISE`, `PLUCK`, `HANDPAN`, `ADSR`, `VOLUME`, `FREQ`, `DECAY`, `CUTOFF`, `RESONANCE`, `REVERB`, `DELAY`, `GLIDE`, `PAN`, `LFO`, `PITCH`, `VOICES`, `DETUNE`, `CHORUS`, `SEQUENCE`, `PATTERN`, `PLAY`, `REST`, `BEAT`, `LOOP`, `PLAY_SEQUENCE`, `PLAY_PATTERN`, `PLAY_TOGETHER`, `FADE_IN`, `FADE_OUT`, `VELOCITY_CURVE`, `CRESCENDO`, `DECRESCENDO`, `OFF`

## Identifiers

Lowercase names for instruments, sequences, and patterns. Can contain letters, digits, and underscores.

## Notes

`C4`, `D#3`, `Bb2`, `Fs5` — case-insensitive letter, optional accidental (`#`, `s`, `b`), octave number.

## Numbers

Integers or floats: `120`, `0.5`, `16384`.

## Comments

Lines starting with `#` are comments. Inline comments: a `#` preceded by whitespace starts a comment (so `D#3` is a note, not a comment).

## Indentation

Uses spaces (tabs converted to 4 spaces). Indented blocks define instrument properties, sequence events, pattern beats, loop bodies, and play-together groups.
