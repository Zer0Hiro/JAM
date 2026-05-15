---
sidebar_position: 2
---

# Validation & Warnings

The compiler runs semantic analysis after parsing and reports errors and warnings.

## Errors (compilation stops)

| Check | Description |
|-------|-------------|
| Undefined instrument | `PLAY` / `BEAT` references an instrument not defined |
| Undefined sequence | `PLAY_SEQUENCE` references a sequence not defined |
| Undefined pattern | `PLAY_PATTERN` references a pattern not defined |
| Invalid note name | Note doesn't match the expected pattern |
| Negative duration | Beat duration `<= 0` |
| Volume out of range | Volume not 0–255 |
| Velocity out of range | Velocity not 0–255 |
| Negative ADSR | Any ADSR parameter `< 0` |
| LOOP count `<= 0` | Loop must repeat at least once |
| Cutoff out of range | CUTOFF not 20–20000 |
| Resonance out of range | RESONANCE not 0–255 |
| Reverb out of range | REVERB not 0–255 |
| Delay time out of range | DELAY time not 0–2000 |
| Delay feedback out of range | DELAY feedback not 0–255 |
| Pan out of range | PAN not 0–255 |
| BPM change out of range | Dynamic BPM not 1–300 |
| SWING out of range | SWING not 0–100 |
| HUMANIZE out of range | HUMANIZE not 0–50 |
| FADE duration invalid | FADE_IN / FADE_OUT not 1–64 beats |
| PLUCK on DRUM | PLUCK wave cannot be used with DRUM instruments |
| LFO rate out of range | LFO rate not 0.1–20.0 |
| LFO depth out of range | LFO depth not 0–255 |
| VOICES out of range | VOICES not 1–4 |
| DETUNE out of range | DETUNE not 0–100 |
| CHORUS out of range | CHORUS not 0–255 |
| DETUNE without VOICES | DETUNE > 0 requires VOICES > 1 |
| Per-note REVERB out of range | REVERB override not 0–255 |
| Per-note DELAY time out of range | DELAY time override not 0–2000 |
| Per-note DELAY feedback out of range | DELAY feedback override not 0–255 |
| Per-note CUTOFF out of range | CUTOFF override not 20–20000 |
| VELOCITY_CURVE velocity out of range | Start or end velocity not 0–255 |
| VELOCITY_CURVE note_count out of range | Note count not 1–128 |

## Warnings (compilation continues)

| Check | Description |
|-------|-------------|
| Very short ADSR | ADSR `< 5` ms (control rate is ~16 ms/step) |
| Note outside piano range | MIDI `< 21` or `> 108` |
| Too many synths | `> 4` synths (ATmega328 has 2 KB RAM) |
| Fast BPM | BPM `> 300` may exceed AVR timing |
| Non-standard audio rate | Not 16384 or 32768 |
| Beat outside bar | Beat position > bar length |
| PLAY_TOGETHER `< 2` items | Use PLAY_SEQUENCE / PLAY_PATTERN directly |
| GLIDE on DRUM | Portamento has no effect on drum instruments |
| GLIDE `> 1000` | Very long glide may sound unnatural |
| GLIDE on PLUCK | Portamento doesn't apply well to plucked strings |
| LFO rate `> 10` | LFO rate approaches audio range |
| LFO VOLUME on DRUM | Volume LFO on drum has limited effect |
| LFO PITCH on DRUM | Pitch LFO has no effect on drums |
| LFO CUTOFF on DRUM | Cutoff LFO on drum has limited effect |
| LFO PAN on DRUM | Pan LFO on drum has limited effect |
| LFO PAN (AVR target) | LFO PAN requires ESP32 with I2S DAC — won't compile on AVR |
| Per-note CUTOFF without instrument CUTOFF | Override has no effect if instrument lacks CUTOFF |
| VELOCITY_CURVE extends beyond sequence | Note count exceeds remaining PLAY events in sequence |
| `>2` CUTOFF LFOs (AVR) | Multiple filter LFOs may exceed AVR RAM budget |
| VOICES `> 2` | Uses significant RAM on AVR targets |
| VOICES on DRUM | Unison voices have no effect on drums |
| DETUNE `> 50` | Large detune may sound out of tune |
| Note outside KEY | Note pitch class not in declared scale |
| High SWING | SWING `> 75` is extreme, may sound unmusical |
| High HUMANIZE | HUMANIZE `> 30` creates very loose timing |
