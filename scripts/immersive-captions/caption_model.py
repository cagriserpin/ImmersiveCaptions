import json
from pathlib import Path


GROUP_SHOW_TIME_MARGIN = 0.20
GROUP_DISAPPEAR_TIME_MARGIN = 1.0
DEFAULT_ANIMATION_TIME_MARGIN = 0.1


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

    def normalize_animation_list(self, animation_value) -> list[dict]:
        if animation_value is None:
            return []

        if isinstance(animation_value, str):
            return [{"type": animation_value}]

        if isinstance(animation_value, dict):
            return [animation_value]

        if isinstance(animation_value, list):
            normalized = []
            for entry in animation_value:
                if isinstance(entry, str):
                    normalized.append({"type": entry})
                elif isinstance(entry, dict) and "type" in entry:
                    normalized.append(entry)
            return normalized

        return []

    def get_animation_time_margins(self, owner: dict) -> tuple[float, float]:
        animations = self.normalize_animation_list(owner.get("animation"))

        if not animations:
            return 0.0, 0.0

        max_begin_margin = 0.0
        max_end_margin = 0.0

        for animation in animations:
            if "time_margin" in animation:
                shared_margin = float(animation.get("time_margin", DEFAULT_ANIMATION_TIME_MARGIN))
                begin_margin = shared_margin
                end_margin = shared_margin
            elif "begin_time_margin" in animation or "end_time_margin" in animation:
                begin_margin = float(animation.get("begin_time_margin", 0.0))
                end_margin = float(animation.get("end_time_margin", 0.0))
            else:
                begin_margin = DEFAULT_ANIMATION_TIME_MARGIN
                end_margin = DEFAULT_ANIMATION_TIME_MARGIN

            max_begin_margin = max(max_begin_margin, begin_margin)
            max_end_margin = max(max_end_margin, end_margin)

        return max_begin_margin, max_end_margin

    def get_owner_effective_time_range(self, owner: dict) -> tuple[float | None, float | None]:
        start = owner.get("start")
        end = owner.get("end")

        if start is None or end is None:
            return None, None

        start = float(start)
        end = float(end)

        begin_margin, end_margin = self.get_animation_time_margins(owner)

        effective_start = start - begin_margin
        effective_end = end + end_margin

        return effective_start, effective_end

    def compute_owner_effective_progress(self, owner: dict, time_seconds: float) -> float:
        start, end = self.get_owner_effective_time_range(owner)

        if start is None and end is None:
            return 0.0

        if start is not None and end is not None:
            if time_seconds <= start:
                return 0.0
            if time_seconds >= end:
                return 1.0

            duration = max(0.001, end - start)
            return (time_seconds - start) / duration

        if start is not None:
            return 1.0 if time_seconds >= start else 0.0

        if end is not None:
            return 1.0 if time_seconds >= end else 0.0

        return 0.0

    def get_dialogue_section_effective_time_range(self, section: dict) -> tuple[float | None, float | None]:
        words = section.get("words", [])
        if not words:
            return None, None

        word_ranges = []

        for word in words:
            start, end = self.get_owner_effective_time_range(word)
            if start is not None and end is not None:
                word_ranges.append((start, end))

        if not word_ranges:
            return None, None

        effective_start = min(start for start, _ in word_ranges)
        effective_end = max(end for _, end in word_ranges)

        section_begin_margin, section_end_margin = self.get_animation_time_margins(section)
        effective_start -= section_begin_margin
        effective_end += section_end_margin

        return effective_start, effective_end

    def get_sfx_section_effective_time_range(self, section: dict) -> tuple[float | None, float | None]:
        return self.get_owner_effective_time_range(section)

    def get_section_time_range(self, section: dict) -> tuple[float | None, float | None]:
        section_type = section.get("type")

        if section_type == "dialogue":
            return self.get_dialogue_section_effective_time_range(section)

        if section_type == "sfx":
            return self.get_sfx_section_effective_time_range(section)

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

        effective_start = natural_start - GROUP_SHOW_TIME_MARGIN
        effective_end = natural_end + GROUP_DISAPPEAR_TIME_MARGIN

        return effective_start, effective_end

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