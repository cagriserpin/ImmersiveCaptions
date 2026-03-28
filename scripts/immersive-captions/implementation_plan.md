# Immersive Captions Implementation Plan

## Goal

Build a working prototype that plays a video and renders immersive captions from a JSON file.

The first version should prioritize:

* reliable video playback
* correct caption timing
* simple visible styling
* minimal implementation risk

Animations and editing tools come after the base pipeline works.

---

## Project Priorities

1. Make the media player work.
2. Convert transcription output into the agreed caption JSON format.
3. Render captions on screen with default styling.
4. Highlight words based on timing.
5. Add smooth color transitions.
6. Add a small set of animations.
7. Only build a caption creator if time remains.

---

## Chosen Stack

### Core UI and playback

* PySide6
* Qt Multimedia for video/audio playback

### Data

* JSON caption format defined in the spec

### Caption generation

* faster-whisper for transcription and word timestamps

### Rendering approach

* transparent caption overlay widget drawn on top of the video

---

## Why this approach

This keeps playback, timing, drawing, and animation in one framework.
That reduces setup complexity and lowers implementation risk for the prototype.

A separate animation framework is not required for the first version.
Qt is sufficient for the planned caption effects.

---

## Folder Usage

### Existing structure

* `json-spec/` → documentation for JSON format and implementation notes
* `media/audio/` → stripped audio files
* `media/video/` → video files
* `media/captions/` → final caption JSON files
* `scripts/caption-creator/` → optional future tool
* `scripts/immersive-captions/` → main prototype application

---

## Suggested Files in `scripts/immersive-captions/`

* `main.py`
* `player_window.py`
* `caption_model.py`
* `caption_overlay.py`

### Responsibilities

#### `main.py`

* start the Qt application
* open the main player window

#### `player_window.py`

* create the media player
* load video
* control playback
* poll current playback time
* pass time updates to the caption overlay

#### `caption_model.py`

* load caption JSON
* expose active groups, sections, and words for a given time
* resolve style inheritance rules

#### `caption_overlay.py`

* draw captions over the video
* show dim inactive text
* show active words with resolved styling
* later apply fade and animation effects

---

## Implementation Stages

## Stage 1 — Basic media player

Build a simple player that:

* opens the video
* plays and pauses
* reports current playback time

### Success condition

A video can be played reliably inside the application.

---

## Stage 2 — Caption JSON conversion

Convert the current transcription output into the agreed JSON format.

At this stage, use:

* defaults
* speakers
* groups
* dialogue sections
* words

SFX can be added manually later if needed.

### Success condition

A valid caption JSON file exists and matches the JSON spec.

---

## Stage 3 — Static caption rendering

Render captions on top of the video with no animation.

At first:

* visible groups are shown
* sections are drawn
* words appear with default/speaker styling
* inactive text is dim

### Success condition

Captions appear at the correct time over the video.

---

## Stage 4 — Word timing highlight

Add word-level timing behavior.

At first:

* words before their start time are dim
* active words use the resolved speaker/default color
* spoken words remain visible after activation

### Success condition

The currently spoken word can be clearly identified during playback.

---

## Stage 5 — Smooth color transition

Replace the instant color switch with a smoother transition.

Example behavior:

* active word fades from dim color to target color
* transition starts when the word becomes active

### Success condition

Word activation feels visually smoother and more expressive.

---

## Stage 6 — Basic animations

Add a very small initial animation set.

Recommended first set:

* `none`
* `pop`
* `shake`
* `stretch`
* `fade`

Implement these only after the timing and rendering pipeline is already stable.

### Success condition

At least 1 to 3 animations work reliably on active words.

---

## Stage 7 — Optional caption creator

Only if time remains, create a small helper tool for editing/managing caption JSON.

This is not required for the prototype.
Manual editing is acceptable for the first version.

### Success condition

Optional convenience tool exists, but only after the player is working.

---

## Rendering Rules to Follow

### Dialogue style priority

1. word field
2. dialogue section field
3. speaker defaults
4. global defaults

### SFX style priority

1. SFX section field
2. global defaults

---

## First Milestone Target

The first major milestone should be:

> The video plays, a caption JSON file is loaded, and the currently spoken word changes from dim to active color at the correct time.

This milestone is more important than building advanced animations early.

---

## Out of Scope for First Version

The following should not be prioritized initially:

* complex editor tools
* syllable-level timing
* letter-level timing
* automatic emotion extraction
* advanced multi-layer animation system
* perfect diarization pipeline

These may be added later if needed.

---

## Current Implementation Order

1. basic player
2. caption JSON conversion
3. static captions
4. active word highlighting
5. smooth color fade
6. basic animations
7. optional caption creator

---

## Current Version

Version: `v1`

This plan reflects the current agreed implementation order for the prototype.
