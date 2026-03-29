import copy
import json
from pathlib import Path


class CaptionModel:
    def __init__(self, json_path: Path) -> None:
        self.json_path = json_path
        self.data = self._load_json(json_path)

    def _load_json(self, json_path: Path) -> dict:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _deep_merge_dicts(self, base: dict, override: dict) -> dict:
        result = copy.deepcopy(base)

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge_dicts(result[key], value)
            else:
                result[key] = copy.deepcopy(value)

        return result

    def _object_defaults(self, obj: dict | None) -> dict:
        if not isinstance(obj, dict):
            return {}
        defaults = obj.get("defaults", {})
        return defaults if isinstance(defaults, dict) else {}

    def _strip_animation_defaults(self, defaults_dict: dict) -> dict:
        return {key: value for key, value in defaults_dict.items() if key != "animation_defaults"}

    def get_root_defaults(self) -> dict:
        defaults = self.data.get("defaults", {})
        return defaults if isinstance(defaults, dict) else {}

    def get_speakers(self) -> dict:
        speakers = self.data.get("speakers", {})
        return speakers if isinstance(speakers, dict) else {}

    def get_groups(self) -> list:
        groups = self.data.get("groups", [])
        return groups if isinstance(groups, list) else []

    def get_style_defaults_for_context(
        self,
        group: dict | None = None,
        section: dict | None = None,
        word: dict | None = None,
        speaker_name: str | None = None,
        include_word_defaults: bool = True,
    ) -> dict:
        result = self._strip_animation_defaults(self.get_root_defaults())

        if group is not None:
            result = self._deep_merge_dicts(result, self._strip_animation_defaults(self._object_defaults(group)))

        if speaker_name:
            speaker_defaults = self.get_speakers().get(speaker_name, {})
            if isinstance(speaker_defaults, dict):
                result = self._deep_merge_dicts(result, speaker_defaults)

        if section is not None:
            result = self._deep_merge_dicts(result, self._strip_animation_defaults(self._object_defaults(section)))

        if include_word_defaults and word is not None:
            result = self._deep_merge_dicts(result, self._strip_animation_defaults(self._object_defaults(word)))

        return result

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

    def _animation_defaults_from_defaults(self, defaults_dict: dict) -> dict:
        animation_defaults = defaults_dict.get("animation_defaults", {})
        return animation_defaults if isinstance(animation_defaults, dict) else {}

    def _collect_animation_default_layers(
        self,
        group: dict | None = None,
        section: dict | None = None,
        word: dict | None = None,
    ) -> list[dict]:
        layers = []
        layers.append(self._animation_defaults_from_defaults(self.get_root_defaults()))

        if group is not None:
            layers.append(self._animation_defaults_from_defaults(self._object_defaults(group)))
        if section is not None:
            layers.append(self._animation_defaults_from_defaults(self._object_defaults(section)))
        if word is not None:
            layers.append(self._animation_defaults_from_defaults(self._object_defaults(word)))

        return layers

    def resolve_animation_entry(
        self,
        animation_entry,
        group: dict | None = None,
        section: dict | None = None,
        word: dict | None = None,
    ) -> dict:
        if isinstance(animation_entry, str):
            explicit_entry = {"type": animation_entry}
        elif isinstance(animation_entry, dict):
            explicit_entry = dict(animation_entry)
        else:
            return {}

        animation_type = explicit_entry.get("type")
        if not animation_type:
            return {}

        resolved = {"type": animation_type}

        for layer in self._collect_animation_default_layers(group, section, word):
            shared_defaults = layer.get("shared", {})
            if isinstance(shared_defaults, dict):
                resolved = self._deep_merge_dicts(resolved, shared_defaults)

            type_defaults = layer.get(animation_type, {})
            if isinstance(type_defaults, dict):
                resolved = self._deep_merge_dicts(resolved, type_defaults)

        resolved = self._deep_merge_dicts(resolved, explicit_entry)
        return resolved

    def get_resolved_animation_list(
        self,
        owner: dict,
        group: dict | None = None,
        section: dict | None = None,
        word: dict | None = None,
    ) -> list[dict]:
        animation_list = self.normalize_animation_list(owner.get("animation"))
        return [self.resolve_animation_entry(entry, group=group, section=section, word=word) for entry in animation_list]

    def get_default_animation_time_margin(
        self,
        group: dict | None = None,
        section: dict | None = None,
        word: dict | None = None,
    ) -> float:
        resolved_defaults = self.get_style_defaults_for_context(
            group=group,
            section=section,
            word=word,
            speaker_name=None,
            include_word_defaults=True,
        )
        return float(resolved_defaults.get("default_animation_time_margin", 0.0))

    def get_group_show_time_margin(self, group: dict | None = None) -> float:
        resolved_defaults = self.get_style_defaults_for_context(
            group=group,
            section=None,
            word=None,
            speaker_name=None,
            include_word_defaults=False,
        )
        return float(resolved_defaults.get("group_show_time_margin", 0.0))

    def get_group_disappear_time_margin(self, group: dict | None = None) -> float:
        resolved_defaults = self.get_style_defaults_for_context(
            group=group,
            section=None,
            word=None,
            speaker_name=None,
            include_word_defaults=False,
        )
        return float(resolved_defaults.get("group_disappear_time_margin", 0.0))

    def get_animation_time_margins(
        self,
        owner: dict,
        group: dict | None = None,
        section: dict | None = None,
        word: dict | None = None,
        resolved_animations: list[dict] | None = None,
    ) -> tuple[float, float]:
        animations = resolved_animations
        if animations is None:
            animations = self.get_resolved_animation_list(owner, group=group, section=section, word=word)

        if not animations:
            return 0.0, 0.0

        default_time_margin = self.get_default_animation_time_margin(
            group=group,
            section=section,
            word=word,
        )

        max_begin_margin = 0.0
        max_end_margin = 0.0

        for animation in animations:
            if "time_margin" in animation:
                shared_margin = float(animation.get("time_margin", default_time_margin))
                begin_margin = shared_margin
                end_margin = shared_margin
            elif "begin_time_margin" in animation or "end_time_margin" in animation:
                begin_margin = float(animation.get("begin_time_margin", 0.0))
                end_margin = float(animation.get("end_time_margin", 0.0))
            else:
                begin_margin = default_time_margin
                end_margin = default_time_margin

            max_begin_margin = max(max_begin_margin, begin_margin)
            max_end_margin = max(max_end_margin, end_margin)

        return max_begin_margin, max_end_margin

    def get_owner_effective_time_range(
        self,
        owner: dict,
        group: dict | None = None,
        section: dict | None = None,
        word: dict | None = None,
        resolved_animations: list[dict] | None = None,
    ) -> tuple[float | None, float | None]:
        start = owner.get("start")
        end = owner.get("end")

        if start is None or end is None:
            return None, None

        start = float(start)
        end = float(end)

        begin_margin, end_margin = self.get_animation_time_margins(
            owner,
            group=group,
            section=section,
            word=word,
            resolved_animations=resolved_animations,
        )

        return start - begin_margin, end + end_margin

    def compute_owner_effective_progress(
        self,
        owner: dict,
        time_seconds: float,
        group: dict | None = None,
        section: dict | None = None,
        word: dict | None = None,
        resolved_animations: list[dict] | None = None,
    ) -> float:
        start, end = self.get_owner_effective_time_range(
            owner,
            group=group,
            section=section,
            word=word,
            resolved_animations=resolved_animations,
        )

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

    def resolve_dialogue_style(self, group: dict, section: dict, word: dict) -> dict:
        speaker_name = section.get("speaker")

        resolved = self.get_style_defaults_for_context(
            group=group,
            section=section,
            word=word,
            speaker_name=speaker_name,
            include_word_defaults=True,
        )

        for key in ("font", "font_size", "font_weight", "font_color", "font_style"):
            if key in section:
                resolved[key] = section[key]

        for key in ("font", "font_size", "font_weight", "font_color", "font_style"):
            if key in word:
                resolved[key] = word[key]

        return resolved

    def resolve_sfx_style(self, group: dict, section: dict) -> dict:
        resolved = self.get_style_defaults_for_context(
            group=group,
            section=section,
            speaker_name=None,
            include_word_defaults=False,
        )

        for key in ("font", "font_size", "font_weight", "font_color", "font_style"):
            if key in section:
                resolved[key] = section[key]

        return resolved

    def get_dialogue_section_effective_time_range(self, group: dict, section: dict) -> tuple[float | None, float | None]:
        words = section.get("words", [])
        if not words:
            return None, None

        word_ranges = []

        for word in words:
            resolved_animations = self.get_resolved_animation_list(word, group=group, section=section, word=word)
            start, end = self.get_owner_effective_time_range(
                word,
                group=group,
                section=section,
                word=word,
                resolved_animations=resolved_animations,
            )
            if start is not None and end is not None:
                word_ranges.append((start, end))

        if not word_ranges:
            return None, None

        effective_start = min(start for start, _ in word_ranges)
        effective_end = max(end for _, end in word_ranges)

        section_resolved_animations = self.get_resolved_animation_list(section, group=group, section=section, word=None)
        section_begin_margin, section_end_margin = self.get_animation_time_margins(
            section,
            group=group,
            section=section,
            word=None,
            resolved_animations=section_resolved_animations,
        )

        return effective_start - section_begin_margin, effective_end + section_end_margin

    def get_sfx_section_effective_time_range(self, group: dict, section: dict) -> tuple[float | None, float | None]:
        resolved_animations = self.get_resolved_animation_list(section, group=group, section=section, word=None)
        return self.get_owner_effective_time_range(
            section,
            group=group,
            section=section,
            word=None,
            resolved_animations=resolved_animations,
        )

    def get_section_time_range(self, group: dict, section: dict) -> tuple[float | None, float | None]:
        section_type = section.get("type")

        if section_type == "dialogue":
            return self.get_dialogue_section_effective_time_range(group, section)
        if section_type == "sfx":
            return self.get_sfx_section_effective_time_range(group, section)

        return None, None

    def get_group_natural_time_range(self, group: dict) -> tuple[float | None, float | None]:
        section_ranges = []

        for section in group.get("sections", []):
            start, end = self.get_section_time_range(group, section)
            if start is not None and end is not None:
                section_ranges.append((start, end))

        if not section_ranges:
            return None, None

        return min(start for start, _ in section_ranges), max(end for _, end in section_ranges)

    def get_group_effective_time_range(self, group: dict) -> tuple[float | None, float | None]:
        natural_start, natural_end = self.get_group_natural_time_range(group)
        if natural_start is None or natural_end is None:
            return None, None

        show_margin = self.get_group_show_time_margin(group)
        disappear_margin = self.get_group_disappear_time_margin(group)

        return natural_start - show_margin, natural_end + disappear_margin

    def is_group_active(self, group: dict, time_seconds: float) -> bool:
        start, end = self.get_group_effective_time_range(group)
        if start is None or end is None:
            return False
        return start <= time_seconds <= end

    def group_requests_overlap_previous(self, group: dict) -> bool:
        for section in group.get("sections", []):
            if bool(section.get("overlap_previous", False)):
                return True
        return False

    def group_requests_overlap_next(self, group: dict) -> bool:
        for section in group.get("sections", []):
            if bool(section.get("overlap_next", False)):
                return True
        return False

    def groups_should_overlap(self, older_group: dict, newer_group: dict) -> bool:
        return self.group_requests_overlap_next(older_group) or self.group_requests_overlap_previous(newer_group)

    def get_active_groups(self, time_seconds: float) -> list[dict]:
        active = []

        for index, group in enumerate(self.get_groups()):
            if not self.is_group_active(group, time_seconds):
                continue

            natural_start, natural_end = self.get_group_natural_time_range(group)
            effective_start, effective_end = self.get_group_effective_time_range(group)

            if natural_start is None or natural_end is None:
                continue
            if effective_start is None or effective_end is None:
                continue

            active.append({
                "group": group,
                "index": index,
                "natural_start": natural_start,
                "natural_end": natural_end,
                "effective_start": effective_start,
                "effective_end": effective_end,
            })

        active.sort(key=lambda item: item["natural_start"])

        if not active:
            return []

        if len(active) == 1:
            return [active[0]["group"]]

        older = active[-2]["group"]
        newer = active[-1]["group"]

        if self.groups_should_overlap(older, newer):
            return [older, newer]

        return [newer]

    def get_active_group(self, time_seconds: float) -> dict | None:
        active_groups = self.get_active_groups(time_seconds)
        if not active_groups:
            return None
        return active_groups[-1]

    def get_active_sections(self, time_seconds: float) -> list[dict]:
        active_group = self.get_active_group(time_seconds)
        if active_group is None:
            return []
        return active_group.get("sections", [])

    def section_to_display_text(self, section: dict) -> str:
        section_type = section.get("type")

        if section_type == "dialogue":
            return " ".join(word.get("text", "") for word in section.get("words", [])).strip()
        if section_type == "sfx":
            return section.get("text", "").strip()

        return ""