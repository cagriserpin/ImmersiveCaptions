# Immersive Captions JSON Specification

## Purpose

This document defines the JSON schema for the immersive captions system.
It serves as the source of truth for how caption data should be structured.
If the JSON format changes, this document should be updated as well.

---

## Design Goals

The format is designed to support:

- global default styling
- per-speaker default styling
- per-word timing
- per-word style overrides
- grouped simultaneous captions
- dialogue captions
- sound-effect captions (SFX)

The format is intentionally simple so it can be edited manually during early prototyping.

---

## Top-Level Structure

The root JSON object contains:

- `defaults`
- `speakers`
- `groups`

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

`defaults` contains the global fallback styling values.
These values are used whenever a more specific setting is not provided.

Supported fields:

- `font`
- `font_size`
- `font_weight`
- `font_color`
- `animation`
- `dim_opacity`

Example:

```json
"defaults": {
  "font": "Arial",
  "font_size": 42,
  "font_weight": 400,
  "font_color": "#ffffff",
  "animation": "none",
  "dim_opacity": 0.35
}
```

### Field meanings

- `font`: font family name
- `font_size`: default text size
- `font_weight`: default font weight
- `font_color`: default text color
- `animation`: default animation type
- `dim_opacity`: opacity used for inactive or not-yet-spoken text

---

## 2. `speakers`

`speakers` defines style defaults for spoken dialogue by character/speaker.

Each speaker entry may contain any styling fields that should override `defaults`.

At minimum, speakers will usually define a unique color.

Example:

```json
"speakers": {
  "speaker_a": {
    "font_color": "#66ccff"
  },
  "speaker_b": {
    "font_color": "#ffcc66"
  }
}
```

### Notes

- Speaker definitions apply only to dialogue sections.
- SFX sections do not use speakers.

---

## 3. `groups`

`groups` is an array of time-bounded caption groups.
A group defines which sections are visible during a shared time range.

This is necessary when multiple caption elements must appear at the same time.

For example:

- spoken dialogue + background sound effect
- two simultaneous speakers
- emphasized overlay + dialogue

Example:

```json
"groups": [
  {
    "sections": []
  }
]
```

### Fields

- `start`: group start time in seconds
- `end`: group end time in seconds
- `sections`: array of section objects shown during this time

---

## 4. `sections`

Each group contains one or more `sections`.
A section is a visible caption block.

There are currently two section types:

- `dialogue`
- `sfx`

---

## 4.1 Dialogue Section

A dialogue section represents spoken text from a speaker.
It contains timed words.

Example:

```json
{
  "type": "dialogue",
  "speaker": "speaker_a",
  "words": [
    { "text": "This", "start": 12.2, "end": 12.45 },
    { "text": "is", "start": 12.46, "end": 12.60 },
    { "text": "not", "start": 12.61, "end": 12.92, "animation": "shake" }
  ]
}
```

### Required fields

- `type`: must be `"dialogue"`
- `speaker`: key referencing an entry in `speakers`
- `words`: array of timed word objects

### Optional fields

A dialogue section may optionally contain style fields such as:

- `font`
- `font_size`
- `font_weight`
- `font_color`
- `animation`

These act as section-level overrides.

---

## 4.2 SFX Section

An SFX section represents non-dialogue caption text such as:

- `[chattering]`
- `[door slams]`
- `[laughter]`

SFX does not belong to a speaker.
It uses either:

- values set directly in the SFX section
- or fallback values from `defaults`

Example:

```json
{
  "type": "sfx",
  "text": "[chattering]",
  "start": 12.0,
  "end": 15.5,
  "font_color": "#bbbbbb",
  "font_weight": 500
}
```

### Required fields

- `type`: must be `"sfx"`
- `text`: displayed SFX text
- `start`: start time in seconds
- `end`: end time in seconds

### Optional fields

An SFX section may contain any style override fields:

- `font`
- `font_size`
- `font_weight`
- `font_color`
- `animation`

---

## 5. `words`

`words` is used only inside dialogue sections.
Each word contains timing data and may optionally override style values.

Example:

```json
{
  "text": "right",
  "start": 12.93,
  "end": 13.28,
  "font_weight": 700,
  "animation": "pop"
}
```

### Required fields

- `text`: the displayed word
- `start`: word start time in seconds
- `end`: word end time in seconds

### Optional fields

- `font`
- `font_size`
- `font_weight`
- `font_color`
- `animation`

---

## Style Resolution Rules

### Dialogue word style priority

For dialogue words, styling should be resolved in this order:

1. field set on the word
2. field set on the dialogue section
3. field set on the speaker
4. field set in `defaults`

This applies to:

- `font`
- `font_size`
- `font_weight`
- `font_color`
- `animation`

### SFX style priority

For SFX sections, styling should be resolved in this order:

1. field set on the SFX section
2. field set in `defaults`

SFX does not use speaker-based styling.

---

## Rendering Behavior

### Dialogue sections

- the section is visible during the group time range
- dialogue text starts dim
- as each word becomes active, it is styled and animated according to its timing and resolved style
- spoken words may remain visible after activation depending on renderer behavior

### SFX sections

- SFX is visible during its own `start` to `end` range
- SFX may use default styling or explicit overrides
- SFX may appear simultaneously with dialogue inside the same group

---

## Animation Values

For the initial prototype, `animation` is a string.

Recommended initial values:

- `"none"`
- `"pop"`
- `"shake"`
- `"stretch"`
- `"fade"`

This may be expanded later into a richer object format if needed.

---

## Example Full JSON

```json
{
  "defaults": {
    "font": "Arial",
    "font_size": 42,
    "font_weight": 400,
    "font_color": "#ffffff",
    "animation": "none",
    "dim_opacity": 0.35
  },
  "speakers": {
    "speaker_a": {
      "font_color": "#66ccff"
    },
    "speaker_b": {
      "font_color": "#ffcc66"
    }
  },
  "groups": [
    {
      "start": 12.0,
      "end": 15.5,
      "sections": [
        {
          "type": "sfx",
          "text": "[chattering]",
          "start": 12.0,
          "end": 15.5,
          "font_color": "#bbbbbb",
          "font_weight": 500
        },
        {
          "type": "dialogue",
          "speaker": "speaker_a",
          "words": [
            { "text": "This", "start": 12.2, "end": 12.45 },
            { "text": "is", "start": 12.46, "end": 12.60 },
            { "text": "not", "start": 12.61, "end": 12.92, "animation": "shake" },
            { "text": "right", "start": 12.93, "end": 13.28, "font_weight": 700, "animation": "pop" },
            { "text": "man", "start": 13.29, "end": 13.60 }
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

- section position (`top`, `bottom`, custom coordinates)
- text alignment
- per-section opacity
- animation parameters
- speaker labels
- nested SFX word timing
- letter-level or syllable-level timing
- simultaneous multi-line layout control

These are intentionally excluded from the first version to keep the implementation simple.

---

## Current Version

Version: `v1`

This specification reflects the current agreed JSON structure for the prototype.

