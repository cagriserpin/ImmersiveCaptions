import json
from pathlib import Path
from typing import Any


class CaptionModel:
    def __init__(self, json_path: Path) -> None:
        self.json_path = Path(json_path)
        self.data = self._load_json(self.json_path)

    def _load_json(self, json_path: Path) -> dict[str, Any]:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_defaults(self) -> dict[str, Any]:
        defaults = self.data.get("defaults", {})
        return defaults if isinstance(defaults, dict) else {}

    def get_speakers(self) -> dict[str, Any]:
        speakers = self.data.get("speakers", {})
        return speakers if isinstance(speakers, dict) else {}

    def get_groups(self) -> list[dict[str, Any]]:
        groups = self.data.get("groups", [])
        return groups if isinstance(groups, list) else []

    def _section_time_range(self, section: dict[str, Any]) -> tuple[float | None, float | None]:
        section_type = section.get("type")
        if section_type == "dialogue":
            words = section.get("words", [])
            if not words:
                return None, None
            starts = [float(w["start"]) for w in words if "start" in w]
            ends = [float(w["end"]) for w in words if "end" in w]
            if not starts or not ends:
                return None, None
            return min(starts), max(ends)

        if section_type == "sfx":
            start = section.get("start")
            end = section.get("end")
            if start is None or end is None:
                return None, None
            return float(start), float(end)

        return None, None

    def _group_time_range(self, group: dict[str, Any]) -> tuple[float | None, float | None]:
        starts: list[float] = []
        ends: list[float] = []
        for section in group.get("sections", []):
            start, end = self._section_time_range(section)
            if start is not None and end is not None:
                starts.append(start)
                ends.append(end)

        if not starts or not ends:
            return None, None

        defaults = self.get_defaults()
        start_margin = float(defaults.get("group_show_time_margin", 0.0))
        end_margin = float(defaults.get("group_disappear_time_margin", 0.0))
        return min(starts) - start_margin, max(ends) + end_margin

    def get_active_sections(self, time_seconds: float) -> list[dict[str, Any]]:
        active_sections: list[dict[str, Any]] = []
        for group in self.get_groups():
            group_start, group_end = self._group_time_range(group)
            if group_start is None or group_end is None:
                continue
            if group_start <= time_seconds <= group_end:
                active_sections.extend(group.get("sections", []))
        return active_sections

    def get_speaker_track_id(self, speaker_name: str | None) -> int | None:
        if not speaker_name:
            return None
        speaker = self.get_speakers().get(speaker_name, {})
        if isinstance(speaker, dict) and "track_id" in speaker:
            try:
                return int(speaker["track_id"])
            except (TypeError, ValueError):
                return None
        return None

    def get_speaker_style(self, speaker_name: str | None) -> dict[str, Any]:
        defaults = self.get_defaults().copy()
        if not speaker_name:
            return defaults
        speaker = self.get_speakers().get(speaker_name, {})
        if isinstance(speaker, dict):
            merged = defaults.copy()
            merged.update(speaker)
            return merged
        return defaults
