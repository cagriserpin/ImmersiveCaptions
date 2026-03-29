# Immersive Captions JSON Specification

## Purpose

This document defines the JSON schema for the immersive captions system.
It is the source of truth for how caption data should be structured.
If the JSON format changes, this document should be updated as well.

---

## Design Goals

The format is designed to support:

* global default styling
* group-level default styling
* section-level default styling
* word-level default styling
* per-speaker default styling for dialogue
* grouped simultaneous captions
* optional group overlap during transitions
* dialogue captions
* sound-effect captions (SFX)
* per-word timing
* per-word style overrides
* per-word animation lists
* per-section animation lists
* animation default inheritance
* animation timing margins
* JSON-driven renderer and layout defaults
* restrained typography variation

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

`defaults` contains fallback values.
It may appear at multiple levels:

* root
* group
* section
* word

This means defaults can be inherited and refined as content becomes more specific.

### Normal fields allowed inside `defaults`

* `font`
* `font_size`
* `font_weight`
* `font_style`
* `font_color`
* `dim_opacity`
* `group_show_time_margin`
* `group_disappear_time_margin`
* `default_animation_time_margin`
* `group_gap`
* `section_gap`
* `section_to_bg_padding_x`
* `section_to_bg_padding_y`
* `section_video_bottom_margin`
* `word_gap`
* `reveal_feather_px`
* `animation_defaults`

Example:

```json
"defaults": {
  "font": "Calibri",
  "font_size": 30,
  "font_weight": 400,
  "font_style": "normal",
  "font_color": "#ffffff",
  "dim_opacity": 0.35,
  "group_show_time_margin": 0.0,
  "group_disappear_time_margin": 0.0,
  "default_animation_time_margin": 0.1,
  "group_gap": 8,
  "section_gap": 0,
  "section_to_bg_padding_x": 18,
  "section_to_bg_padding_y": 10,
  "section_video_bottom_margin": 110,
  "word_gap": 10,
  "reveal_feather_px": 12,
  "animation_defaults": {
    "shared": {
      "time_margin": 0.1
    },
    "bounce": {
      "amplitude_px": 15,
      "cycles": 1,
      "direction": "up"
    },
    "pop": {
      "scale": 1.25,
      "cycles": 1
    },
    "scale": {
      "scale": 1.25,
      "cycles": 1
    }
  }
}
```

### Notes

* Word-level `defaults` is valid, even if it is often unnecessary.
* There is no explicit `none` animation.
* If a word or section has no `animation` field, no animation is applied.

---

## 2. `speakers`

`speakers` defines style defaults for spoken dialogue by character or speaker.

Each speaker entry may contain styling fields that override broader defaults.

Example:

```json
"speakers": {
  "john": {
    "font_color": "#CD7F32"
  },
  "zee": {
    "font_color": "#FCBA03"
  },
  "crowd": {
    "font_color": "#FFFFFF"
  }
}
```

### Notes

* Speaker definitions apply only to dialogue sections.
* SFX sections do not use speakers.
* Speaker defaults affect normal style values, not animation defaults.

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

### Allowed fields on a group

* `defaults`
* `sections`

### Important structure rule

At group level, `defaults` and `sections` are sibling fields.

Valid:

```json
{
  "defaults": { ... },
  "sections": [
    { ... },
    { ... }
  ]
}
```

Invalid:

```json
{
  "sections": [
    "defaults": { ... },
    { ... }
  ]
}
```

`sections` must be an array of section objects only.
`defaults` must not appear inside the `sections` array.

### Notes

* Groups do **not** explicitly store `start` or `end`.
* Group timing is derived from the sections inside the group.
* Group visibility is based on:

  * section timing
  * word timing
  * animation timing margins
  * inherited group show/disappear margins
* Only one group is visible by default.
* Two adjacent groups may overlap only when explicitly requested by section overlap flags.

---

## 4. `sections`

Each group contains one or more `sections`.
A section is a visible caption block.

There are currently two section types:

* `dialogue`
* `sfx`

Sections may also contain defaults, overlap flags, and animations.
Section animation is conceptually applied to the whole section together, not word by word.
Word animation support has higher priority and should be implemented first.

### Allowed shared fields on a section

* `defaults`
* `animation`
* `overlap_previous`
* `overlap_next`

### Overlap flags

These flags may appear **only on sections**.

* `overlap_previous: true` means this section’s group may overlap with the previous group if both are active.
* `overlap_next: true` means this section’s group may overlap with the next group if both are active.

If no section requests overlap, only one group is shown.

---

## 4.1 Dialogue Section

A dialogue section represents spoken text from a speaker.
It contains timed words.

Example:

```json
{
  "type": "dialogue",
  "speaker": "zee",
  "defaults": {
    "animation_defaults": {
      "bounce": {
        "amplitude_px": 15,
        "cycles": 1,
        "direction": "up"
      }
    }
  },
  "words": [
    { "text": "This", "start": 12.2, "end": 12.45 },
    { "text": "is", "start": 12.46, "end": 12.60 },
    {
      "text": "wild",
      "start": 12.61,
      "end": 12.92,
      "animation": [
        { "type": "pop", "scale": 1.25, "cycles": 1 }
      ]
    }
  ]
}
```

### Required fields

* `type`: must be `"dialogue"`
* `speaker`: key referencing an entry in `speakers`
* `words`: array of timed word objects

### Optional explicit style fields

A dialogue section may optionally contain explicit style fields such as:

* `font`
* `font_size`
* `font_weight`
* `font_style`
* `font_color`

These are direct section-level overrides.

### Optional defaults field

A dialogue section may contain a `defaults` object.
Those defaults can be inherited by the words inside that section.

### Optional animation field

A dialogue section may optionally contain:

* `animation`

`animation` must be a list.
Section animation applies to the whole section as one unit.
This is a later-stage feature and should not replace word-level animation.

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
* or fallback values inherited from defaults

Example:

```json
{
  "type": "sfx",
  "text": "[huh huhh]",
  "start": 31.18,
  "end": 32.0,
  "font_color": "#bbbbbb",
  "font_weight": 500,
  "font_style": "italic",
  "animation": [
    { "type": "scale", "scale": 1.2, "cycles": 1 }
  ]
}
```

### Required fields

* `type`: must be `"sfx"`
* `text`: displayed SFX text
* `start`: start time in seconds
* `end`: end time in seconds

### Optional explicit style fields

An SFX section may contain explicit style override fields:

* `font`
* `font_size`
* `font_weight`
* `font_style`
* `font_color`

### Optional defaults field

An SFX section may contain a `defaults` object.
This is valid, even if it is less common than at group or dialogue section level.

### Optional animation field

An SFX section may also contain:

* `animation`

`animation` must be a list.
SFX animation applies to the whole SFX text item.

---

## 5. `words`

`words` is used only inside dialogue sections.
Each word contains timing data and may optionally override style values, defaults, and animations.

Example:

```json
{
  "text": "AI!",
  "start": 89.08,
  "end": 89.46,
  "font_weight": 700,
  "font_style": "italic",
  "animation": [
    { "type": "pop", "scale": 1.25, "cycles": 1 }
  ]
}
```

### Required fields

* `text`: the displayed word
* `start`: word start time in seconds
* `end`: word end time in seconds

### Optional explicit style fields

* `font`
* `font_size`
* `font_weight`
* `font_style`
* `font_color`

### Optional defaults field

A word may contain a `defaults` object.
This is valid, although explicit word fields are usually simpler.

### Optional animation field

* `animation`

`animation` must be a list.
A word may have multiple animations at once.

Example:

```json
"animation": [
  { "type": "scale", "scale": 1.2, "cycles": 1 },
  { "type": "bounce", "amplitude_px": 8, "cycles": 2, "direction": "up" }
]
```

---

## Style Resolution Rules

### Dialogue word style priority

For dialogue words, styling should be resolved in this order:

1. explicit field set on the word
2. values from word `defaults`
3. explicit field set on the section
4. values from section `defaults`
5. speaker defaults
6. values from group `defaults`
7. values from root `defaults`

This applies to:

* `font`
* `font_size`
* `font_weight`
* `font_style`
* `font_color`
* `dim_opacity`

### SFX style priority

For SFX sections, styling should be resolved in this order:

1. explicit field set on the section
2. values from section `defaults`
3. values from group `defaults`
4. values from root `defaults`

SFX does not use speaker-based styling.

---

## Font Style

`font_style` controls whether text is rendered normally or italicized.

Currently supported values:

* `normal`
* `italic`

If omitted, it inherits from `defaults`.
If not specified anywhere, it behaves as `normal`.

This may be used at:

* root `defaults`
* group `defaults`
* section `defaults`
* word `defaults`
* explicit section field
* explicit word field

Use it sparingly for emphasis, quoted-feeling words, reactions, music/SFX labels, or stylistic moments.
Too much variation reduces readability.

---

## JSON-Driven Layout and Renderer Defaults

The renderer reads these values from `defaults` instead of hardcoded Python constants.
All of them participate in the normal defaults inheritance chain.

### Group-level / stack-related values

* `group_show_time_margin`
* `group_disappear_time_margin`
* `group_gap`
* `section_video_bottom_margin`

### Section-level values

* `section_gap`
* `section_to_bg_padding_x`
* `section_to_bg_padding_y`

### Word-level values

* `word_gap`
* `reveal_feather_px`

### Fallback behavior

If these values are missing:

* `group_show_time_margin` defaults to `0.0`
* `group_disappear_time_margin` defaults to `0.0`
* `default_animation_time_margin` defaults to `0.0`
* all layout spacing / padding values default to `0.0`

In practice, you usually set them at root `defaults`.

---

## Animation System

### General rules

* There is no explicit `none` animation.
* If `animation` is missing, no animation is applied.
* `animation` must be a list.
* Multiple animations may be combined on the same word or section.
* Animation timing is based on the owner's `start` and `end`, extended by resolved timing margins.

### Supported animation types

Current supported or planned animation names:

* `pop`
* `bounce`
* `scale`
* `weight`
* `jiggle`

### General `cycles` rule

All current animation types may define `cycles`.

If omitted, `cycles` defaults to `1`.

Meaning depends on animation type:

* `bounce`: repeated bounce arcs or oscillations depending on direction
* `jiggle`: repeated rotational oscillations
* `scale`: repeated scale pulses
* `pop`: repeated pop bursts

---

## Animation Defaults

Animation defaults are stored inside `defaults.animation_defaults`.
They may appear at:

* root level
* group level
* section level
* word level

### Structure

`animation_defaults` is a dictionary keyed by animation type.
It may also contain a special `shared` key for values that apply to all animation types.

Example:

```json
"defaults": {
  "animation_defaults": {
    "shared": {
      "time_margin": 0.1
    },
    "bounce": {
      "amplitude_px": 15,
      "cycles": 1,
      "direction": "up"
    },
    "pop": {
      "scale": 1.25,
      "cycles": 1
    },
    "scale": {
      "scale": 1.25,
      "cycles": 1
    },
    "jiggle": {
      "angle_deg": 6,
      "cycles": 3
    }
  }
}
```

### Resolution order for animation parameters

For each animation entry, parameters should be resolved in this order:

1. explicit fields on the animation object
2. word-level `defaults.animation_defaults`
3. section-level `defaults.animation_defaults`
4. group-level `defaults.animation_defaults`
5. root-level `defaults.animation_defaults`

Within each level:

* `shared` values apply first
* type-specific values apply after `shared`
* explicit animation object values override inherited defaults

### Important note

Normal animation parameters use override priority.
Timing margins use special **maximum-based merging** described below.

---

## Animation Timing Margins

Each animation object may optionally contain:

* `time_margin`
* `begin_time_margin`
* `end_time_margin`

### Rules

#### 1. `time_margin`

If `time_margin` is present, it sets both:

* begin margin
* end margin

and overrides `begin_time_margin` and `end_time_margin` for that animation object.

#### 2. Explicit begin/end margins

If `time_margin` is absent:

* `begin_time_margin` applies only to begin
* `end_time_margin` applies only to end

#### 3. Default animation time margin

If an animation exists and no timing margin fields are present at that animation level, the system uses:

* `default_animation_time_margin`

This is read from inherited `defaults`.
If not specified anywhere, it becomes `0.0`.

#### 4. Final owner timing margins

If timing margins are provided at multiple levels, the final owner timing margins are:

* `final_begin_margin = max(all begin contributors)`
* `final_end_margin = max(all end contributors)`

This means timing margins are merged with `max()`, not simple override.

### Meaning

These values extend the effective timing window used by both:

* animation progress
* highlight / reveal progress

For an owner:

* effective start = `start - final_begin_margin`
* effective end = `end + final_end_margin`

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
* `cycles`
* optional timing margin fields

Example:

```json
{ "type": "pop", "scale": 1.25, "cycles": 1 }
```

`cycles` controls how many pop bursts occur during the animation window.
Default: `1`

---

### `bounce`

Purpose:

* vertical motion
* useful for surprise, marching, rhythm, emphasis

Parameters:

* `amplitude_px`
* `cycles`
* `direction`
* optional timing margin fields

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
* For `direction: "up-down"`, `cycles` means the number of full up/down oscillation cycles.

---

### `scale`

Purpose:

* sustained scale pulse across the timing window
* grows and returns smoothly

Parameters:

* `scale`
* `cycles`
* optional timing margin fields

Example:

```json
{ "type": "scale", "scale": 1.25, "cycles": 1 }
```

`cycles` controls how many grow-and-return pulses occur during the animation window.
Default: `1`

---

### `weight`

Purpose:

* heavier text during the active timing window

Parameters:

* `active_weight`
* optional timing margin fields

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
* optional timing margin fields

Example:

```json
{ "type": "jiggle", "angle_deg": 5, "cycles": 3 }
```

---

## Group Timing Rules

Groups do not store explicit `start` or `end` values.
Instead, group timing is derived from the sections they contain.

A group's effective time range should account for:

* section timing
* word timing
* animation timing margins on words and/or sections
* inherited `group_show_time_margin`
* inherited `group_disappear_time_margin`

Conceptually:

* earliest effective content start inside the group
* latest effective content end inside the group
* minus `group_show_time_margin`
* plus `group_disappear_time_margin`

If the first word has animation timing that starts early, the group should appear early enough for that animation to be visible.

Example:

* word start = `10.0`
* `group_show_time_margin = 0.1`
* animation `begin_time_margin = 0.1`

Then effective group show time should be:

* `10.0 - 0.1 - 0.1 = 9.8`

---

## Overlap Rules

By default:

* only one active group is displayed

Two adjacent groups are shown together only if overlap is explicitly requested.

### Overlap enable rule

If two groups are active at the same time:

* show both if the older group has any section with `overlap_next: true`
* or if the newer group has any section with `overlap_previous: true`

Otherwise:

* show only the newer active group

### Display order during overlap

When overlap is enabled:

* older active group is shown above
* newer active group is shown below

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
* highlight/reveal progresses using the owner's effective timing window
* animations use the same effective timing window
* already-highlighted words may remain visible after highlight completes depending on renderer behavior

### SFX rendering behavior

* SFX is rendered as its own timed text item
* SFX may also use animations
* SFX highlight/animation timing uses the SFX effective timing window

---

## Example Full JSON

```json
{
  "defaults": {
    "font": "Calibri",
    "font_size": 30,
    "font_weight": 400,
    "font_style": "normal",
    "font_color": "#ffffff",
    "dim_opacity": 0.35,
    "group_show_time_margin": 0.0,
    "group_disappear_time_margin": 0.0,
    "default_animation_time_margin": 0.1,
    "group_gap": 8,
    "section_gap": 0,
    "section_to_bg_padding_x": 18,
    "section_to_bg_padding_y": 10,
    "section_video_bottom_margin": 110,
    "word_gap": 10,
    "reveal_feather_px": 12,
    "animation_defaults": {
      "shared": {
        "time_margin": 0.1
      },
      "bounce": {
        "amplitude_px": 15,
        "cycles": 1,
        "direction": "up"
      },
      "pop": {
        "scale": 1.25,
        "cycles": 1
      },
      "scale": {
        "scale": 1.25,
        "cycles": 1
      },
      "jiggle": {
        "angle_deg": 6,
        "cycles": 3
      }
    }
  },
  "speakers": {
    "john": {
      "font_color": "#CD7F32"
    },
    "zee": {
      "font_color": "#FCBA03"
    },
    "crowd": {
      "font_color": "#FFFFFF"
    }
  },
  "groups": [
    {
      "defaults": {
        "font_weight": 700,
        "animation_defaults": {
          "bounce": { "amplitude_px": 10, "cycles": 1, "time_margin": 0 }
        }
      },
      "sections": [
        {
          "type": "dialogue",
          "speaker": "crowd",
          "words": [
            { "text": "LOOK!", "start": 85.68, "end": 85.94, "animation": [ { "type": "pop", "scale": 1.2, "cycles": 1 } ] }
          ]
        },
        {
          "type": "dialogue",
          "speaker": "crowd",
          "words": [
            { "text": "IT'S", "start": 86.4, "end": 86.62, "animation": [ { "type": "bounce" } ] },
            { "text": "GOT", "start": 86.62, "end": 86.76, "animation": [ { "type": "bounce" } ] },
            { "text": "SIX", "start": 86.76, "end": 87.1, "animation": [ { "type": "bounce" } ] },
            { "text": "FINGERS!", "start": 87.1, "end": 87.72, "font_style": "italic", "animation": [ { "type": "scale", "scale": 1.16, "cycles": 1 }, { "type": "bounce" } ] }
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

Version: `v5`

This specification reflects the current agreed JSON structure, inheritance rules, overlap rules, animation defaults model, typography fields, JSON-driven layout defaults, and timing behavior for the prototype.
