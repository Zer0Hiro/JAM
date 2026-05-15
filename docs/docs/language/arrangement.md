---
sidebar_position: 5
---

# Arrangement

The arrangement section controls playback order. It sits at the top level (no indentation).

## PLAY_SEQUENCE

```
PLAY_SEQUENCE melody
```

Plays the named sequence once, start to finish.

## PLAY_PATTERN

```
PLAY_PATTERN basic_beat
```

Plays one bar of the named pattern.

## LOOP

```
LOOP 4:
    PLAY_SEQUENCE verse
    PLAY_PATTERN drums
```

Repeats the indented body N times. Loops can contain `PLAY_SEQUENCE`, `PLAY_PATTERN`, `PLAY_TOGETHER`, and nested `LOOP` blocks.

```
LOOP 2:
    LOOP 4:
        PLAY_SEQUENCE intro
    PLAY_SEQUENCE chorus
```

## PLAY_TOGETHER

Plays multiple sequences and patterns simultaneously — all children start at the same time and their events are merged onto a single timeline.

```
PLAY_TOGETHER:
    PLAY_SEQUENCE bassline
    PLAY_SEQUENCE melody
    PLAY_PATTERN drums
```

Without `PLAY_TOGETHER`, arrangement items play one after another:

```
# Sequential — bass plays first, THEN melody, THEN drums
PLAY_SEQUENCE bassline
PLAY_SEQUENCE melody
PLAY_PATTERN drums
```

With `PLAY_TOGETHER`, they play at the same time — like a real band:

```
# Simultaneous — all three play at once
PLAY_TOGETHER:
    PLAY_SEQUENCE bassline
    PLAY_SEQUENCE melody
    PLAY_PATTERN drums
```

`PLAY_TOGETHER` works inside `LOOP` blocks:

```
LOOP 4:
    PLAY_TOGETHER:
        PLAY_SEQUENCE bassline
        PLAY_SEQUENCE melody
        PLAY_PATTERN drums
```

## FADE_IN / FADE_OUT

Gradually ramp master volume up or down over a number of beats:

```
FADE_IN 4                    # fade from silence to full over 4 beats
LOOP 4:
    PLAY_SEQUENCE melody
FADE_OUT 8                   # fade from current volume to silence over 8 beats
LOOP 2:
    PLAY_SEQUENCE outro
```

| Directive | Range | Description |
|-----------|-------|-------------|
| `FADE_IN` | 1–64 beats | Ramp volume from 0 to current master volume |
| `FADE_OUT` | 1–64 beats | Ramp volume from current level to 0 |

Fades are arrangement-level items — they apply to everything that follows until the fade completes. They work inside `LOOP` and `PLAY_TOGETHER` blocks.

## Dynamic BPM / VOLUME Changes

`BPM` and `VOLUME` can appear as arrangement items to change tempo or master volume mid-song:

```
BPM 100
LOOP 2:
    PLAY_SEQUENCE verse
BPM 140
LOOP 2:
    PLAY_SEQUENCE chorus
```

When `BPM` appears after arrangement items have started, it changes the tempo for all subsequent events. When it appears before any arrangement, it sets the initial tempo.

### Smooth BPM Ramp

`BPM <target> OVER <beats>` gradually ramps from the current tempo to `<target>` over `<beats>` beats:

```
BPM 100
LOOP 4:
    PLAY_SEQUENCE verse
BPM 140 OVER 8                  # ramp from 100 to 140 over 8 beats
LOOP 4:
    PLAY_SEQUENCE chorus
```

| Parameter | Range | Description |
|-----------|-------|-------------|
| `target` | 1–300 | Target BPM |
| `beats` | 1–64 | Number of beats over which the ramp occurs |

- Existing `BPM <value>` (instant change) stays unchanged
- Warning if ramp is very short (< 2 beats) — may sound like a glitch rather than a smooth transition

`VOLUME` sets the master volume (0–255) for everything that follows:

```
PLAY_SEQUENCE intro
VOLUME 255
PLAY_SEQUENCE climax
```
