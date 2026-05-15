---
sidebar_position: 3
---

# Sequences

Named lists of `PLAY` and `REST` events. Durations are in beats (relative to BPM). Events play one after another (sequentially).

```
SEQUENCE melody:
    PLAY lead C4 0.5      # play instrument "lead", note C4, half a beat
    PLAY lead D#4 0.5     # sharps with #
    PLAY lead E4 1        # one beat
    REST 0.5              # silence for half a beat
    PLAY lead G4 2        # two beats
```

## PLAY Syntax

```
PLAY <instrument> <note> <duration> [velocity] [CUTOFF:<value>] [REVERB:<value>] [DELAY:<time>:<feedback>]
PLAY <instrument> [C4 E4 G4] <duration> [velocity] [CUTOFF:<value>] [REVERB:<value>] [DELAY:<time>:<feedback>]
```

- **instrument** — must match a defined `INSTRUMENT` name
- **note** — scientific pitch notation (e.g. `C4`, `D#3`, `Bb2`)
- **chord** — bracket notation `[note note note]` for polyphonic playback (min 2 notes)
- **duration** — float, in beats relative to BPM (e.g. `0.25` = sixteenth note at 4/4)
- **velocity** — optional, `0`–`255`. Per-note volume scaling. Omit for full instrument volume
- **CUTOFF:value** — optional per-note filter override (20–20000 Hz). Instrument must have `CUTOFF` set. Reverts after note ends
- **REVERB:value** — optional per-note reverb override (0–255)
- **DELAY:time:feedback** — optional per-note delay override (time 0–2000ms, feedback 0–255)

For drums without a melodic pitch, omit the note:

```
PLAY kick 1             # drum hit, 1 beat duration
```

:::note
Drum instruments ignore the note parameter entirely — their pitch is set by the `FREQ` property in the instrument definition.
:::

## REST Syntax

```
REST <duration>
```

Silent pause for the given number of beats.

## Per-note Effect Overrides

Override an instrument's settings for individual notes:

```
SEQUENCE melody:
    PLAY lead C4 1 200 CUTOFF:800          # darker filter on this note
    PLAY lead E4 1                          # normal instrument settings
    PLAY lead G4 1 180 DELAY:500:120       # longer delay on this note
    PLAY lead C5 1 200 REVERB:180 DELAY:400:100   # multiple overrides
    PLAY lead D5 1 180 CUTOFF:3000 REVERB:200      # bright + wet
```

Overrides require velocity to be specified first. `CUTOFF` override only works on instruments that have `CUTOFF` set — the filter reverts to the instrument's base value after the note ends.

## VELOCITY_CURVE

Automatically spread velocities across a series of notes — creates crescendo or decrescendo without writing each velocity by hand.

```
VELOCITY_CURVE CRESCENDO <start_vel> <end_vel> <note_count>
VELOCITY_CURVE DECRESCENDO <start_vel> <end_vel> <note_count>
VELOCITY_CURVE OFF
```

| Parameter | Range | Description |
|-----------|-------|-------------|
| `start_vel` | 0–255 | Starting velocity |
| `end_vel` | 0–255 | Ending velocity |
| `note_count` | 1–128 | How many subsequent PLAY notes the curve spans |

### Crescendo Example

```
SEQUENCE buildup:
    VELOCITY_CURVE CRESCENDO 40 230 6
    PLAY lead C4 0.5       # vel ~40
    PLAY lead D4 0.5       # vel ~78
    PLAY lead E4 0.5       # vel ~116
    PLAY lead F4 0.5       # vel ~154
    PLAY lead G4 0.5       # vel ~192
    PLAY lead A4 1         # vel ~230
```

### Decrescendo Example

```
SEQUENCE fadeout:
    VELOCITY_CURVE DECRESCENDO 200 60 4
    PLAY lead G4 1         # vel ~200
    PLAY lead E4 1         # vel ~153
    PLAY lead C4 1         # vel ~107
    PLAY lead C3 2         # vel ~60
```

### Notes

- VELOCITY_CURVE is **compile-time only** — zero MCU runtime cost. Velocities are baked into the event table
- A note with an explicit velocity override still uses it, but the curve position advances
- `VELOCITY_CURVE OFF` cancels an active curve before it finishes
- REST events do not consume curve positions
- Multiple VELOCITY_CURVEs in the same sequence: each replaces the previous

:::tip
VELOCITY_CURVE is resolved at compile time — it adds zero overhead on the microcontroller. Use it freely for musical expression.
:::

## Chords

Play multiple notes simultaneously with bracket notation:

```
SEQUENCE progression:
    PLAY pad [C4 E4 G4] 2       # C major chord, 2 beats
    PLAY pad [A3 C4 E4] 2       # A minor chord
    PLAY pad [F3 A3 C4] 2       # F major chord
    PLAY pad [G3 B3 D4] 2       # G major chord
```
