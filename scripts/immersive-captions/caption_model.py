import json
from pathlib import Path


GROUP_TIME_MARGIN = 1.0


class CaptionModel:
    def __init__(self, json_path: Path) -> None:
        self.json_path = json_path
        self.data = self._load_json(json_path)

    def _load_json(self, json_path: Path) -> dict:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_defaults(self) -> dict:
        return self.data.get("defaults", {})

    def get_speakers(self) -> dict:
        return self.data.get("speakers", {})

    def get_groups(self) -> list:
        return self.data.get("groups", [])

    def get_section_time_range(self, section: dict) -> tuple[float | None, float | None]:
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

    def get_group_natural_time_range(self, group: dict) -> tuple[float | None, float | None]:
        sections = group.get("sections", [])
        section_ranges = []

        for section in sections:
            start, end = self.get_section_time_range(section)
            if start is not None and end is not None:
                section_ranges.append((start, end))

        if not section_ranges:
            return None, None

        group_start = min(start for start, _ in section_ranges)
        group_end = max(end for _, end in section_ranges)
        return group_start, group_end

    def get_group_effective_time_range(self, group: dict) -> tuple[float | None, float | None]:
        natural_start, natural_end = self.get_group_natural_time_range(group)
        if natural_start is None or natural_end is None:
            return None, None

        return natural_start, natural_end + GROUP_TIME_MARGIN

    def is_group_active(self, group: dict, time_seconds: float) -> bool:
        start, end = self.get_group_effective_time_range(group)
        if start is None or end is None:
            return False
        return start <= time_seconds <= end

    def get_active_group(self, time_seconds: float) -> dict | None:
        active_candidates = []

        for group in self.get_groups():
            if not self.is_group_active(group, time_seconds):
                continue

            natural_start, natural_end = self.get_group_natural_time_range(group)
            effective_start, effective_end = self.get_group_effective_time_range(group)

            if natural_start is None or natural_end is None:
                continue
            if effective_start is None or effective_end is None:
                continue

            active_candidates.append({
                "group": group,
                "natural_start": natural_start,
                "natural_end": natural_end,
                "effective_start": effective_start,
                "effective_end": effective_end,
            })

        if not active_candidates:
            return None

        active_candidates.sort(key=lambda item: item["natural_start"], reverse=True)
        return active_candidates[0]["group"]

    def get_active_sections(self, time_seconds: float) -> list[dict]:
        active_group = self.get_active_group(time_seconds)
        if active_group is None:
            return []

        return active_group.get("sections", [])

    def section_to_display_text(self, section: dict) -> str:
        section_type = section.get("type")

        if section_type == "dialogue":
            words = section.get("words", [])
            return " ".join(word.get("text", "") for word in words).strip()

        if section_type == "sfx":
            return section.get("text", "").strip()

        return ""