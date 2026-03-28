# Immersive Captions Animation Plan

## Goal

Add animation support to the caption system in a way that keeps layout stable and implementation manageable.

Word animations are the first priority.
Section-wide animations will be implemented later, after word animations are working correctly.

---

## Core Rules

### 1. No explicit `none` animation

If a word or section has no `animation` field, it has no animation.

### 2. `animation` is a list

A word or section may have multiple animations.

Examples:

```json
"animation": [
  { "type": "pop", "peak_scale": 1.25 }
]
```

```json
"animation": [
  { "type": "scale", "scale": 1.2 },
  { "type": "weight", "active_weight": 700 }
]
```

### 3. Layout must stay fixed

Word positions are computed once.
Animations must not move neighboring words.
If a word changes size, weight, or rotation, it must animate inside its own reserved layout space.

### 4. Word animations first

Word-level animation support must be correct before section-level animations are added.

### 5. Section animations later

If a section has an `animation` field, that animation applies to the whole section together, not word by word.
Think of this as animating the sentence or caption block as a whole.

---

## Animation Scope

## Phase 1 — Word animations

Implement animation support for words first.

Supported animation types:

* `pop`
* `bounce`
* `scale`
* `weight`
* `jiggle`

Animations may be combined by placing multiple entries in the `animation` list.

Example:

```json
{
  "text": "What?!",
  "start": 4.52,
  "end": 4.88,
  "animation": [
    { "type": "scale", "scale": 1.2 },
    { "type": "jiggle", "angle_deg": 6, "cycles": 3 }
  ]
}
```

---

## Word Animation Parameters

### `pop`

Purpose:

* quick impact burst
* good for laughs or sudden emphasis

Parameters:

* `peak_scale`

Example:

```json
{ "type": "pop", "peak_scale": 1.25 }
```

---

### `bounce`

Purpose:

* vertical up/down motion
* good for surprise, marching, rhythm

Parameters:

* `amplitude_px`
* `cycles`

Example:

```json
{ "type": "bounce", "amplitude_px": 8, "cycles": 2 }
```

---

### `scale`

Purpose:

* sustained enlargement during the word
* good for emphasis

Parameters:

* `scale`

Example:

```json
{ "type": "scale", "scale": 1.2 }
```

---

### `weight`

Purpose:

* heavier text during active word timing

Parameters:

* `active_weight`

Example:

```json
{ "type": "weight", "active_weight": 700 }
```

---

### `jiggle`

Purpose:

* rotational left/right wobble
* good for shouting, panic, comedy, instability

Parameters:

* `angle_deg`
* `cycles`

Example:

```json
{ "type": "jiggle", "angle_deg": 5, "cycles": 3 }
```

---

## Word Animation Timing

Word animations run during the word's own active time range:

* start: `word.start`
* end: `word.end`

Animation progress is derived from the word timing window.
No separate speed parameter is needed.

General rule:

* before `start`: no animation effect
* during `start -> end`: animation active
* after `end`: return to stable final visual state

The final visual state should keep the highlighted color, but temporary motion effects should stop.

---

## Word Animation Implementation Order

### Step 1

Add parsing for `animation` as a list on words.

### Step 2

Support one animation per word reliably.

### Step 3

Support combining multiple animations on the same word.

### Step 4

Ensure all animation transforms happen inside the word's reserved layout box.

### Step 5

Tune defaults visually using the actual video.

---

## Phase 2 — Section animations

Section animations should be added only after word animations are stable.

A section animation applies to the whole sentence/block together.
This means:

* all words in the section move as one unit
* the section background and text block should visually stay together
* the effect is applied to the whole rendered section, not independently per word

Example future usage:

```json
{
  "type": "dialogue",
  "speaker": "zee",
  "animation": [
    { "type": "bounce", "amplitude_px": 6, "cycles": 2 }
  ],
  "words": [
    { "text": "Wake", "start": 62.05, "end": 62.39 },
    { "text": "up!", "start": 62.39, "end": 62.71 }
  ]
}
```

This should animate the entire section together.

---

## Section Animation Timing

For section-wide animation timing, use the section's effective time range:

* dialogue section: earliest word start to latest word end
* sfx section: explicit `start` to `end`

Section timing rules should be added only after word animation timing is fully working.

---

## Recommended Development Order

1. parse word animation lists
2. implement `scale`
3. implement `pop`
4. implement `bounce`
5. implement `jiggle`
6. implement `weight`
7. support multiple animations on one word
8. only then add section-level animation support

---

## Notes

* Keep layout fixed at all times.
* Animations must never push neighboring words.
* Word animation correctness is more important than adding many effects quickly.
* Section animations are explicitly lower priority than word animations.

---

## Current Version

Version: `v1`

This plan reflects the current agreed direction for animation support in the immersive captions prototype.
