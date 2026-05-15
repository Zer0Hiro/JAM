---
sidebar_position: 4
---

# Patterns

Beat-grid notation for placing instruments at specific positions in a bar. Multiple instruments on the same beat play simultaneously.

```
PATTERN basic_beat:
    BEAT 1: kick        # beat 1 (downbeat)
    BEAT 1: hat         # same beat = simultaneous with kick
    BEAT 1.5: hat       # offbeat (fractional positions OK)
    BEAT 2: snare
    BEAT 2: hat
    BEAT 3: kick
    BEAT 3: hat
    BEAT 4: snare
    BEAT 4: hat
```

## BEAT Syntax

```
BEAT <position>: <instrument> [note] [duration] [velocity] [CUTOFF:<value>] [REVERB:<value>] [DELAY:<time>:<feedback>]
BEAT <position>: <instrument> [C4 E4 G4] [duration] [velocity] [CUTOFF:<value>] [REVERB:<value>] [DELAY:<time>:<feedback>]
```

- **position** — float, 1-based (1 = first beat of bar). Fractional = offbeats (e.g. `1.5`, `2.5`)
- **instrument** — must match a defined `INSTRUMENT`
- **note** — optional pitch for synth instruments in patterns
- **duration** — optional, in beats
- **velocity** — optional, `0`–`255`. Per-hit volume scaling
- **CUTOFF:value** / **REVERB:value** / **DELAY:time:feedback** — optional per-note effect overrides (same as PLAY)
- Default bar length: 4 beats (4/4 time)

## Simultaneous Playback

Place different instruments on the same beat number to play them at the same time:

```
PATTERN band:
    BEAT 1: bass C2     # bass and lead play together on beat 1
    BEAT 1: lead E4
    BEAT 1: kick
    BEAT 2: bass C2
    BEAT 2: lead G4
```
