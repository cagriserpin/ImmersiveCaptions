# Immersive Captions 2 — Brief Plan

## Goal
Build a new pipeline for subtitle placement that first understands who is on screen.

## Order
1. detect faces on every frame
2. collect all detections
3. cluster repeated faces into unique identities
4. manually assign names
5. build stable character-following
6. only then add subtitles
