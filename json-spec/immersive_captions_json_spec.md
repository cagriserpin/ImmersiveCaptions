# Immersive Captions JSON Specification

## Purpose

This document defines the JSON schema for the immersive captions system.
It is the source of truth for how caption data should be structured.
If the JSON format changes, this document should be updated as well.

---

## Design Goals

The format is designed to support:

* global default styling
* per-speaker default styling
* grouped simultaneous captions
* dialogue captions
* sound-effect captions (SFX)
* per-word timing
* per-word style overrides
* per-word animation lists
* per-section animation lists
* animation timing margins

The format is intentionally hand-editable for rapid prototyping.

---

## Top-Level Structure

The root JSON object contains:

* `defaults`
* `speakers`
* `groups`

Example:

```json
{
  "defaults": {},
  "speakers": {},
  "groups": []
}
```

---

## 1. `defaults`

`defaults` contains global fallback styling values.
These values are used whenever a more specific setting is not provided.

Supported fields:

* `font`
* `font_size`
* `font_weight`
* `font_color`
* `dim_opacity`

Example:

```json
"defaults": {
  "font": "Arial",
  "font_size": 42,
  "font_weight": 400,
  "font_color": "#ffffff",
  "dim_opacity": 0.35
}
```

### Field meanings

* `font`: font family name
* `font_size`: default text size
* `font_weight`: default font weight
* `font_color`: default text color
* `dim_opacity`: opacity/intensity used for inactive or not-yet-highlighted text

### Notes

* There is no default `animation` field.
* If a word or section has no `animation` field, no animation is applied.

---

## 2. `speakers`

`speakers` defines style defaults for spoken dialogue by character/speaker.

Each speaker entry may contain any styling fields that should override `defaults`.

At minimum, speakers will usually define a unique color.

Example:

```json
"speakers": {
  "zee": {
    "font_color": "#66ccff"
  },
  "stranger_1": {
    "font_color": "#ffcc66"
  }
}
```

### Notes

* Speaker definitions apply only to dialogue sections.
* SFX sections do not use speakers.

---

## 3. `groups`

`groups` is an array of caption groups.
A group defines which sections are allowed to appear together.

This is necessary when multiple caption elements must appear at the same time.

For example:

* spoken dialogue + background sound effect
* two simultaneous speakers
* emphasized overlay + dialogue

Example:

```json
"groups": [
  {
    "sections": []
  }
]
```

### Fields

* `sections`: array of section objects that belong to the group

### Notes

* Groups do **not** explicitly store `start` or `end`.
* Group timing is derived from the sections inside the group.
* Group visibility is based on:

  * section timing
  * animation timing margins
  * global group show/disappear margins used by the renderer/model
* Only one group is intended to be visible at a time.
* If groups overlap, the most recently starting active group should win.

---

## 4. `sections`

Each group contains one or more `sections`.
A section is a visible caption block.

There are currently two section types:

* `dialogue`
* `sfx`

Sections may also contain animation lists.
Section animation is conceptually applied to the whole section together, not word by word.
Word animation support has higher priority and should be implemented first.

---

## 4.1 Dialogue Section

A dialogue section represents spoken text from a speaker.
It contains timed words.

Example:

```json
{
  "type": "dialogue",
  "speaker": "zee",
  "words": [
    { "text": "This", "start": 12.2, "end": 12.45 },
    { "text": "is", "start": 12.46, "end": 12.60 },
    {
      "text": "wild",
      "start": 12.61,
      "end": 12.92,
      "animation": [
        { "type": "pop", "scale": 1.25 }
      ]
    }
  ]
}
```

### Required fields

* `type`: must be `"dialogue"`
* `speaker`: key referencing an entry in `speakers`
* `words`: array of timed word objects

### Optional style fields

A dialogue section may optionally contain style fields such as:

* `font`
* `font_size`
* `font_weight`
* `font_color`

These act as section-level overrides.

### Optional animation field

A dialogue section may optionally contain:

* `animation`

`animation` must be a list.
Section animation applies to the whole section as one unit.
This is a later-stage feature and should not replace word-level animation.

Example:

```json
"animation": [
  { "type": "bounce", "amplitude_px": 6, "cycles": 2, "direction": "up" }
]
```

---

## 4.2 SFX Section

An SFX section represents non-dialogue caption text such as:

* `[chattering]`
* `[door slams]`
* `[laughter]`
* `[huh huhh]`

SFX does not belong to a speaker.
It uses either:

* values set directly in the SFX section
* or fallback values from `defaults`

Example:

```json
{
  "type": "sfx",
  "text": "[huh huhh]",
  "start": 31.18,
  "end": 32.0,
  "font_color": "#bbbbbb",
  "font_weight": 500,
  "animation": [
    { "type": "scale", "scale": 1.2 }
  ]
}
```

### Required fields

* `type`: must be `"sfx"`
* `text`: displayed SFX text
* `start`: start time in seconds
* `end`: end time in seconds

### Optional style fields

An SFX section may contain style override fields:

* `font`
* `font_size`
* `font_weight`
* `font_color`

### Optional animation field

An SFX section may also contain:

* `animation`

`animation` must be a list.
SFX animation applies to the whole SFX text item.

---

## 5. `words`

`words` is used only inside dialogue sections.
Each word contains timing data and may optionally override style values and animations.

Example:

```json
{
  "text": "AI!",
  "start": 89.08,
  "end": 89.46,
  "font_weight": 700,
  "animation": [
    { "type": "pop", "scale": 1.25 }
  ]
}
```

### Required fields

* `text`: the displayed word
* `start`: word start time in seconds
* `end`: word end time in seconds

### Optional style fields

* `font`
* `font_size`
* `font_weight`
* `font_color`

### Optional animation field

* `animation`

`animation` must be a list.
A word may have multiple animations at once.

Example:

```json
"animation": [
  { "type": "scale", "scale": 1.2 },
  { "type": "bounce", "amplitude_px": 8, "cycles": 2, "direction": "up" }
]
```

---

## Style Resolution Rules

### Dialogue word style priority

For dialogue words, styling should be resolved in this order:

1. field set on the word
2. field set on the dialogue section
3. field set on the speaker
4. field set in `defaults`

This applies to:

* `font`
* `font_size`
* `font_weight`
* `font_color`

### SFX style priority

For SFX sections, styling should be resolved in this order:

1. field set on the SFX section
2. field set in `defaults`

SFX does not use speaker-based styling.

---

## Animation Format

### General rules

* There is no explicit `none` animation.
* If `animation` is missing, no animation is applied.
* `animation` must be a list.
* Multiple animations may be combined on the same word or section.
* Animation timing is based on the owner's `start` and `end`, extended by optional animation timing margins.

### Supported animation types

Current supported or planned animation names:

* `pop`
* `bounce`
* `scale`
* `weight`
* `jiggle`

---

## Animation Timing Margins

Each animation object may optionally contain:

* `begin_time_margin`
* `end_time_margin`

If omitted, both default to `0.0`.

Example:

```json
{
  "type": "bounce",
  "amplitude_px": 25,
  "cycles": 1,
  "direction": "up",
  "begin_time_margin": 0.1,
  "end_time_margin": 0.1
}
```

### Meaning

These values extend the effective timing window used by animation and highlight timing.

For a word:

* effective start = `start - max(begin_time_margin)`
* effective end = `end + max(end_time_margin)`

The maximum is taken across all animations applied to that owner.

### Important rule

Highlight timing should use the same effective timing window as animation timing.
This ensures that:

* animation does not start while the word remains fully dim
* highlight does not finish before the animation has settled

---

## Animation Parameters

### `pop`

Purpose:

* quick impact burst near the beginning
* expands fast, then settles back

Parameters:

* `scale`
* optional `begin_time_margin`
* optional `end_time_margin`

Example:

```json
{ "type": "pop", "scale": 1.25 }
```

---

### `bounce`

Purpose:

* vertical motion
* useful for surprise, marching, rhythm, emphasis

Parameters:

* `amplitude_px`
* `cycles`
* `direction`
* optional `begin_time_margin`
* optional `end_time_margin`

`direction` allowed values:

* `"up"`
* `"down"`
* `"up-down"`

Default direction:

* `"up"`

Example:

```json
{ "type": "bounce", "amplitude_px": 8, "cycles": 2, "direction": "up" }
```

### `cycles` meaning

* For `direction: "up"`, `cycles` means the number of upward bounce arcs.
* For `direction: "down"`, `cycles` means the number of downward bounce arcs.
* For `direction: "up-down"`, `cycles` means the number of full oscillation cycles.

---

### `scale`

Purpose:

* sustained scale pulse across the word timing
* grows and returns smoothly

Parameters:

* `scale`
* optional `begin_time_margin`
* optional `end_time_margin`

Example:

```json
{ "type": "scale", "scale": 1.25 }
```

---

### `weight`

Purpose:

* heavier text during the active timing window

Parameters:

* `active_weight`
* optional `begin_time_margin`
* optional `end_time_margin`

Example:

```json
{ "type": "weight", "active_weight": 700 }
```

---

### `jiggle`

Purpose:

* rotational left/right wobble
* useful for shouting, panic, comedy, instability

Parameters:

* `angle_deg`
* `cycles`
* optional `begin_time_margin`
* optional `end_time_margin`

Example:

```json
{ "type": "jiggle", "angle_deg": 5, "cycles": 3 }
```

---

## Group Timing Rules

Groups do not store explicit `start` or `end` values.
Instead, group timing is derived from the sections they contain.

A group's effective time range should account for:

* raw section timing
* animation timing margins on words and/or sections
* global group show/disappear margins

Conceptually:

* earliest effective content start inside the group
* latest effective content end inside the group
* minus `GROUP_SHOW_TIME_MARGIN`
* plus `GROUP_DISAPPEAR_TIME_MARGIN`

If the first word has an animation with `begin_time_margin`, the group should appear early enough for that animation to be visible.

Example:

* word start = `10.0`
* `GROUP_SHOW_TIME_MARGIN = 0.1`
* animation `begin_time_margin = 0.1`

Then effective group show time should be:

* `10.0 - 0.1 - 0.1 = 9.8`

---

## Rendering Rules

### Fixed layout rule

Words are laid out once inside reserved slots.
Animations must not push neighboring words around.

This means:

* word positions are stable
* animations happen inside reserved space
* section stacking remains stable

### Background behavior

Current preferred rendering behavior:

* backgrounds remain fixed during animation
* animations affect the word inside its reserved slot
* dynamic background resizing may be revisited later

### Dialogue rendering behavior

* words start dim
* highlight/reveal progresses using the word's effective timing window
* animations use the same effective timing window
* already-highlighted words may remain visible after highlight completes depending on the renderer

### SFX rendering behavior

* SFX is rendered as its own timed text item
* SFX may also use animations
* SFX highlight/animation timing uses the SFX effective timing window

---

## Example Full JSON

```json
{
  "defaults": {
    "font": "Arial",
    "font_size": 42,
    "font_weight": 400,
    "font_color": "#ffffff",
    "dim_opacity": 0.35
  },
  "speakers": {
    "zee": {
      "font_color": "#66ccff"
    },
    "stranger_3": {
      "font_color": "#ffcc66"
    }
  },
  "groups": [
    {
      "sections": [
        {
          "type": "dialogue",
          "speaker": "stranger_3",
          "words": [
            { "text": "That's", "start": 27.38, "end": 27.94 },
            { "text": "AI", "start": 27.94, "end": 28.32 },
            {
              "text": "generated!",
              "start": 28.32,
              "end": 28.86,
              "animation": [
                { "type": "pop", "scale": 1.25 }
              ]
            }
          ]
        }
      ]
    },
    {
      "sections": [
        {
          "type": "dialogue",
          "speaker": "zee",
          "words": [
            {
              "text": "And",
              "start": 10.92,
              "end": 13.08,
              "animation": [
                {
                  "type": "bounce",
                  "amplitude_px": 25,
                  "cycles": 1,
                  "direction": "up",
                  "begin_time_margin": 0.1,
                  "end_time_margin": 0.1
                }
              ]
            },
            { "text": "I", "start": 11.08, "end": 11.28 },
            { "text": "said,", "start": 11.28, "end": 11.8 },
            { "text": "that's", "start": 12.26, "end": 12.5 },
            { "text": "AI,", "start": 12.5, "end": 12.82 },
            { "text": "man.", "start": 13.06, "end": 13.14 }
          ]
        },
        {
          "type": "sfx",
          "text": "[huh huhh]",
          "start": 31.18,
          "end": 32.0,
          "font_color": "#bbbbbb",
          "animation": [
            { "type": "scale", "scale": 1.2 }
          ]
        }
      ]
    }
  ]
}
```

---

## Future Extensions

Possible future additions:

* section position (`top`, `bottom`, custom coordinates)
* text alignment
* per-section opacity
* richer section-wide animation controls
* speaker labels
* syllable-level timing
* letter-level timing
* dynamic background sizing after animation system stabilizes
* simultaneous multi-line layout control

---

## Current Version

Version: `v2`

This specification reflects the current agreed JSON structure and animation behavior for the prototype.
