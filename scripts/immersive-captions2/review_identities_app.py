
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon, QKeyEvent, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)


VALID_STATUSES = ["no-name", "named", "ignored"]


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def normalize_status(value: str | None) -> str:
    text = (value or "").strip().lower()
    if text == "candidate":
        return "no-name"
    if text == "ignore":
        return "ignored"
    if text == "ignored":
        return "ignored"
    if text == "named":
        return "named"
    return "no-name"


def denormalize_status(value: str) -> str:
    text = normalize_status(value)
    if text == "ignored":
        return "ignore"
    if text == "named":
        return "named"
    return "candidate"


def try_int(value: str) -> int | None:
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


@dataclass
class PhotoRecord:
    detection_id: int
    identity_id: int | None
    frame_index: int
    face_index: int
    time_seconds: float
    bbox: list[int]
    score: float | None
    crop_path: Path
    identity_ref: dict[str, Any] | None

    @property
    def crop_name(self) -> str:
        return self.crop_path.name

    def effective_name_status(self) -> tuple[str, str]:
        if self.identity_ref is None:
            return "", "no-name"

        base_name = str(self.identity_ref.get("manual_name", "")).strip()
        base_status = normalize_status(self.identity_ref.get("status"))

        overrides = self.identity_ref.get("detection_overrides", {})
        if isinstance(overrides, dict):
            ov = overrides.get(str(self.detection_id))
            if isinstance(ov, dict):
                name = str(ov.get("manual_name", "")).strip()
                status = normalize_status(ov.get("status"))
                return name, status

        return base_name, base_status


class SampleCard(QWidget):
    def __init__(self, detection_id: int, crop_path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.detection_id = int(detection_id)
        self.crop_path = crop_path
        self.selected = False

        self.setStyleSheet("background: #181818; border: 1px solid #555; border-radius: 8px;")
        self.setMinimumWidth(220)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(200, 150)
        self.image_label.setStyleSheet("border: 1px solid #444; background: #111; border-radius: 4px;")

        self.meta_label = QLabel()
        self.meta_label.setWordWrap(True)
        self.meta_label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.image_label)
        layout.addWidget(self.meta_label)

        self.set_image(crop_path)
        self.update_text("")

    def set_image(self, path: Path) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_label.setText(f"Image not found\n{path}")
            self.image_label.setPixmap(QPixmap())
            return
        self.image_label.setPixmap(
            pixmap.scaled(220, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        )
        self.image_label.setText("")

    def update_text(self, text: str) -> None:
        self.meta_label.setText(text)

    def set_selected(self, selected: bool) -> None:
        self.selected = bool(selected)
        if self.selected:
            self.setStyleSheet(
                "background: #202020; border: 2px solid #4ea8ff; border-radius: 8px;"
            )
        else:
            self.setStyleSheet(
                "background: #181818; border: 1px solid #555; border-radius: 8px;"
            )

    def mousePressEvent(self, event) -> None:
        parent = self.parent()
        while parent is not None and not hasattr(parent, "on_sample_card_clicked"):
            parent = parent.parent()
        if parent is not None:
            parent.on_sample_card_clicked(self)
        super().mousePressEvent(event)


class IdentityReviewWindow(QMainWindow):
    def __init__(self, json_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Identity Review Tool - Group + Photo Browser")
        self.resize(1850, 1040)

        self.json_path: Path | None = None
        self.data: dict[str, Any] | None = None
        self.identities: list[dict[str, Any]] = []
        self.identities_by_id: dict[int, dict[str, Any]] = {}
        self.current_index: int = -1
        self.current_sample_detection_id: int | None = None
        self.sample_cards: list[SampleCard] = []
        self._updating_ui = False

        self.source_faces_raw_path: Path | None = None
        self.raw_faces_data: dict[str, Any] | None = None
        self.detection_index: dict[int, dict[str, Any]] = {}
        self.source_crops_dir: Path | None = None
        self.photo_records: list[PhotoRecord] = []
        self.filtered_detection_ids: list[int] = []

        self.tabs = QTabWidget()

        self._build_cluster_tab()
        self._build_browser_tab()
        self.setCentralWidget(self.tabs)

        self._build_toolbar()
        self.setStatusBar(QStatusBar())

        if json_path is not None:
            self.open_json(json_path)

    # ---------- schema and loading ----------

    def ensure_schema(self, data: dict[str, Any]) -> None:
        label_options = data.get("label_options")
        if not isinstance(label_options, list):
            data["label_options"] = []

        for identity in data.get("identities", []):
            if not isinstance(identity.get("manual_name"), str):
                identity["manual_name"] = str(identity.get("manual_name", "") or "")
            identity["status"] = normalize_status(identity.get("status"))

            detection_ids = identity.get("detection_ids", [])
            if not isinstance(detection_ids, list):
                identity["detection_ids"] = []

            sample_crops = identity.get("sample_crops", [])
            if not isinstance(sample_crops, list):
                identity["sample_crops"] = []

            overrides = identity.get("detection_overrides")
            if not isinstance(overrides, dict):
                identity["detection_overrides"] = {}

            cleaned_overrides: dict[str, dict[str, Any]] = {}
            for key, value in identity["detection_overrides"].items():
                if not isinstance(value, dict):
                    continue
                cleaned_overrides[str(key)] = {
                    "manual_name": str(value.get("manual_name", "") or ""),
                    "status": normalize_status(value.get("status")),
                }
            identity["detection_overrides"] = cleaned_overrides

    def try_load_source_faces_raw(self) -> None:
        self.raw_faces_data = None
        self.source_faces_raw_path = None
        self.source_crops_dir = None
        self.detection_index = {}

        if self.data is None or self.json_path is None:
            return

        source_value = str(self.data.get("source_faces_raw_json", "")).strip()
        crops_value = str(self.data.get("source_crops_dir", "")).strip()

        candidates: list[Path] = []
        if source_value:
            source_path = Path(source_value)
            candidates.extend([
                source_path,
                self.json_path.parent / source_path.name,
                self.json_path.with_name(source_path.name),
            ])

        if not candidates:
            guessed = self.json_path.with_name(self.json_path.name.replace(".face_identities", ""))
            candidates.append(guessed)

        loaded_path: Path | None = None
        for candidate in candidates:
            try:
                if candidate.exists():
                    loaded_path = candidate.resolve()
                    break
            except Exception:
                continue

        if crops_value:
            candidate_crops = Path(crops_value)
            if candidate_crops.exists():
                self.source_crops_dir = candidate_crops.resolve()

        if loaded_path is None:
            return

        try:
            self.raw_faces_data = load_json(loaded_path)
            self.source_faces_raw_path = loaded_path

            raw_crops_dir = str(self.raw_faces_data.get("crops_dir", "")).strip()
            if raw_crops_dir:
                raw_crops = Path(raw_crops_dir)
                if raw_crops.exists():
                    self.source_crops_dir = raw_crops.resolve()

            if self.source_crops_dir is None:
                self.source_crops_dir = loaded_path.with_suffix("").resolve()

            self.build_detection_index()
        except Exception:
            self.raw_faces_data = None
            self.source_faces_raw_path = None
            self.source_crops_dir = None
            self.detection_index = {}

    def build_detection_index(self) -> None:
        self.detection_index = {}
        if self.raw_faces_data is None:
            return

        frames = self.raw_faces_data.get("frames", [])
        if not isinstance(frames, list):
            return

        for frame in frames:
            frame_index = int(frame.get("frame_index", 0))
            time_seconds = float(frame.get("time_seconds", 0.0))
            faces = frame.get("faces", [])
            if not isinstance(faces, list):
                continue

            for face_idx, face in enumerate(faces):
                detection_id = face.get("detection_id")
                if detection_id is None:
                    continue

                crop_path_value = str(face.get("crop_path", "")).strip()
                crop_path = Path(crop_path_value) if crop_path_value else Path()
                if (not crop_path.exists()) and self.source_crops_dir is not None:
                    guessed = self.source_crops_dir / crop_path.name if crop_path_value else self.source_crops_dir / f"frame_{frame_index:06d}_face_{face_idx:02d}.jpg"
                    crop_path = guessed

                if (not crop_path.exists()) and self.source_crops_dir is not None:
                    crop_path = self.source_crops_dir / f"frame_{frame_index:06d}_face_{face_idx:02d}.jpg"

                self.detection_index[int(detection_id)] = {
                    "frame_index": frame_index,
                    "face_index": face_idx,
                    "time_seconds": time_seconds,
                    "bbox": face.get("bbox", []),
                    "score": face.get("score"),
                    "crop_path": crop_path,
                }

    def rebuild_identity_maps(self) -> None:
        self.identities_by_id = {}
        for identity in self.identities:
            identity_id = int(identity.get("identity_id", -1))
            if identity_id >= 0:
                self.identities_by_id[identity_id] = identity

    def rebuild_photo_records(self) -> None:
        self.photo_records = []
        if self.data is None:
            return

        det_to_identity = self.data.get("detection_to_identity", {})
        if not isinstance(det_to_identity, dict):
            det_to_identity = {}

        for detection_id, info in sorted(self.detection_index.items(), key=lambda item: (int(item[1].get("frame_index", 0)), int(item[1].get("face_index", 0)))):
            identity_id = det_to_identity.get(str(detection_id))
            identity_ref = self.identities_by_id.get(int(identity_id)) if identity_id is not None else None

            self.photo_records.append(
                PhotoRecord(
                    detection_id=int(detection_id),
                    identity_id=int(identity_id) if identity_id is not None else None,
                    frame_index=int(info.get("frame_index", 0)),
                    face_index=int(info.get("face_index", 0)),
                    time_seconds=float(info.get("time_seconds", 0.0)),
                    bbox=list(info.get("bbox", [])),
                    score=float(info["score"]) if isinstance(info.get("score"), (int, float)) else None,
                    crop_path=Path(info.get("crop_path", "")),
                    identity_ref=identity_ref,
                )
            )

    # ---------- name / status helpers ----------

    def get_label_options(self) -> list[str]:
        if self.data is None:
            return []

        raw = self.data.get("label_options", [])
        names = [str(x).strip() for x in raw if str(x).strip()]

        for identity in self.identities:
            base_name = str(identity.get("manual_name", "")).strip()
            if base_name:
                names.append(base_name)

            overrides = identity.get("detection_overrides", {})
            if isinstance(overrides, dict):
                for item in overrides.values():
                    if isinstance(item, dict):
                        name = str(item.get("manual_name", "")).strip()
                        if name:
                            names.append(name)

        unique: list[str] = []
        seen = set()
        for name in names:
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(name)
        unique.sort(key=lambda x: x.lower())
        return unique

    def refresh_name_combos(self) -> None:
        names = self.get_label_options()

        def refill(combo: QComboBox, current_text: str, include_any: bool = False) -> None:
            combo.blockSignals(True)
            combo.clear()
            if include_any:
                combo.addItem("Any")
            combo.addItem("")
            for name in names:
                combo.addItem(name)
            idx = combo.findText(current_text)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(0)
            combo.blockSignals(False)

        refill(self.bulk_name_combo, self.bulk_name_combo.currentText())
        refill(self.sample_name_combo, self.sample_name_combo.currentText())
        refill(self.search_name_combo, self.search_name_combo.currentText(), include_any=True)

    def add_name_option(self, name: str) -> None:
        clean = name.strip()
        if not clean or self.data is None:
            return
        options = self.data.setdefault("label_options", [])
        if not any(str(existing).strip().lower() == clean.lower() for existing in options):
            options.append(clean)
        self.refresh_name_combos()

    def get_current_identity(self) -> dict[str, Any] | None:
        if self.current_index < 0 or self.current_index >= len(self.identities):
            return None
        return self.identities[self.current_index]

    def get_effective_sample_assignment(self, identity: dict[str, Any], detection_id: int) -> tuple[str, str]:
        overrides = identity.get("detection_overrides", {})
        override = overrides.get(str(detection_id), {}) if isinstance(overrides, dict) else {}
        status = normalize_status(override.get("status") if override else identity.get("status"))
        name = str(override.get("manual_name") if override else identity.get("manual_name", "")).strip()
        return name, status

    def set_sample_override(self, identity: dict[str, Any], detection_id: int, name: str, status: str) -> None:
        overrides = identity.setdefault("detection_overrides", {})
        overrides[str(detection_id)] = {
            "manual_name": name.strip(),
            "status": normalize_status(status),
        }

    def commit_backwards_compatible_fields(self) -> None:
        for identity in self.identities:
            detection_ids = [int(x) for x in identity.get("detection_ids", [])]
            if not detection_ids:
                continue
            values = [self.get_effective_sample_assignment(identity, det_id) for det_id in detection_ids]
            unique_values = {(name, status) for name, status in values}
            if len(unique_values) == 1:
                name, status = values[0]
                identity["manual_name"] = name
                identity["status"] = normalize_status(status)
            else:
                identity["manual_name"] = ""
                identity["status"] = "no-name"

    # ---------- UI build ----------

    def _build_cluster_tab(self) -> None:
        self.cluster_tab = QWidget()
        cluster_root = QSplitter()

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(QLabel("Clusters"))
        self.identity_list = QListWidget()
        self.identity_list.currentRowChanged.connect(self.on_identity_selected)
        left_layout.addWidget(self.identity_list)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)

        meta_group = QGroupBox("Cluster Info")
        meta_form = QFormLayout(meta_group)
        self.id_label = QLabel("-")
        self.count_label = QLabel("-")
        self.best_score_label = QLabel("-")
        self.time_range_label = QLabel("-")
        self.loaded_source_label = QLabel("-")
        self.loaded_crops_label = QLabel("-")
        meta_form.addRow("Identity ID", self.id_label)
        meta_form.addRow("Detections", self.count_label)
        meta_form.addRow("Best score", self.best_score_label)
        meta_form.addRow("Time range", self.time_range_label)
        meta_form.addRow("Loaded source faces", self.loaded_source_label)
        meta_form.addRow("Loaded crops dir", self.loaded_crops_label)
        right_layout.addWidget(meta_group)

        bulk_group = QGroupBox("Cluster Default Assignment")
        bulk_form = QFormLayout(bulk_group)
        self.bulk_name_combo = QComboBox()
        self.bulk_name_combo.currentIndexChanged.connect(self.on_bulk_fields_changed)
        self.bulk_new_name_edit = QLineEdit()
        self.bulk_new_name_edit.setPlaceholderText("New name")
        self.bulk_new_name_edit.textEdited.connect(self.on_bulk_fields_changed)
        self.bulk_status_combo = QComboBox()
        self.bulk_status_combo.addItems(VALID_STATUSES)
        self.bulk_status_combo.currentIndexChanged.connect(self.on_bulk_fields_changed)
        self.apply_identity_button = QPushButton("Apply to Entire Cluster")
        self.apply_identity_button.clicked.connect(self.apply_bulk_to_identity)
        bulk_form.addRow("Existing names", self.bulk_name_combo)
        bulk_form.addRow("New name", self.bulk_new_name_edit)
        bulk_form.addRow("Status", self.bulk_status_combo)
        bulk_form.addRow("", self.apply_identity_button)
        right_layout.addWidget(bulk_group)

        rep_group = QGroupBox("Representative Crop")
        rep_layout = QVBoxLayout(rep_group)
        self.representative_label = QLabel("No image")
        self.representative_label.setAlignment(Qt.AlignCenter)
        self.representative_label.setMinimumSize(420, 320)
        self.representative_label.setStyleSheet("border: 1px solid #666; background: #111; color: #ccc;")
        rep_layout.addWidget(self.representative_label)
        right_layout.addWidget(rep_group)

        sample_editor_group = QGroupBox("Selected Photo Assignment")
        sample_form = QFormLayout(sample_editor_group)
        self.selected_detection_label = QLabel("-")
        self.sample_name_combo = QComboBox()
        self.sample_name_combo.currentIndexChanged.connect(self.on_sample_fields_changed)
        self.sample_new_name_edit = QLineEdit()
        self.sample_new_name_edit.setPlaceholderText("New name")
        self.sample_new_name_edit.textEdited.connect(self.on_sample_fields_changed)
        self.sample_status_combo = QComboBox()
        self.sample_status_combo.addItems(VALID_STATUSES)
        self.sample_status_combo.currentIndexChanged.connect(self.on_sample_fields_changed)
        self.apply_sample_button = QPushButton("Apply to Selected Photo")
        self.apply_sample_button.clicked.connect(self.apply_to_selected_sample)
        sample_form.addRow("Detection ID", self.selected_detection_label)
        sample_form.addRow("Existing names", self.sample_name_combo)
        sample_form.addRow("New name", self.sample_new_name_edit)
        sample_form.addRow("Status", self.sample_status_combo)
        sample_form.addRow("", self.apply_sample_button)
        right_layout.addWidget(sample_editor_group)

        samples_group = QGroupBox("Cluster Photos")
        samples_group_layout = QVBoxLayout(samples_group)
        self.samples_container = QWidget()
        self.samples_layout = QGridLayout(self.samples_container)
        self.samples_layout.setContentsMargins(0, 0, 0, 0)
        self.samples_layout.setHorizontalSpacing(10)
        self.samples_layout.setVerticalSpacing(10)
        self.samples_scroll = QScrollArea()
        self.samples_scroll.setWidgetResizable(True)
        self.samples_scroll.setWidget(self.samples_container)
        samples_group_layout.addWidget(self.samples_scroll)
        right_layout.addWidget(samples_group, stretch=1)

        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("Previous Cluster")
        self.prev_button.clicked.connect(self.go_previous)
        self.next_button = QPushButton("Next Cluster")
        self.next_button.clicked.connect(self.go_next)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_current_file)
        self.save_next_button = QPushButton("Save + Next")
        self.save_next_button.clicked.connect(self.save_and_next)
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.save_button)
        nav_layout.addWidget(self.save_next_button)
        right_layout.addLayout(nav_layout)

        cluster_root.addWidget(left_panel)
        cluster_root.addWidget(right_panel)
        cluster_root.setSizes([380, 1280])

        layout = QVBoxLayout(self.cluster_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(cluster_root)
        self.tabs.addTab(self.cluster_tab, "Group View")

    def _build_browser_tab(self) -> None:
        self.browser_tab = QWidget()

        main_splitter = QSplitter()

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(8, 8, 8, 8)

        search_group = QGroupBox("Photo Search")
        search_layout = QGridLayout(search_group)

        self.search_query_edit = QLineEdit()
        self.search_query_edit.setPlaceholderText("Search: saban, det:9269, id:0, frame:2283, named ...")

        self.search_name_combo = QComboBox()
        self.search_status_combo = QComboBox()
        self.search_status_combo.addItems(["Any"] + VALID_STATUSES)

        self.search_identity_edit = QLineEdit()
        self.search_identity_edit.setPlaceholderText("Identity ID")
        self.search_detection_edit = QLineEdit()
        self.search_detection_edit.setPlaceholderText("Detection ID")
        self.search_frame_edit = QLineEdit()
        self.search_frame_edit.setPlaceholderText("Frame index")

        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.apply_photo_search)
        self.search_query_edit.returnPressed.connect(self.apply_photo_search)
        self.search_identity_edit.returnPressed.connect(self.apply_photo_search)
        self.search_detection_edit.returnPressed.connect(self.apply_photo_search)
        self.search_frame_edit.returnPressed.connect(self.apply_photo_search)
        self.reset_search_button = QPushButton("Reset")
        self.reset_search_button.clicked.connect(self.reset_photo_search)

        self.search_count_label = QLabel("0 photos")

        search_layout.addWidget(QLabel("Query"), 0, 0)
        search_layout.addWidget(self.search_query_edit, 0, 1, 1, 3)
        search_layout.addWidget(QLabel("Name"), 1, 0)
        search_layout.addWidget(self.search_name_combo, 1, 1)
        search_layout.addWidget(QLabel("Status"), 1, 2)
        search_layout.addWidget(self.search_status_combo, 1, 3)
        search_layout.addWidget(QLabel("Identity"), 2, 0)
        search_layout.addWidget(self.search_identity_edit, 2, 1)
        search_layout.addWidget(QLabel("Detection"), 2, 2)
        search_layout.addWidget(self.search_detection_edit, 2, 3)
        search_layout.addWidget(QLabel("Frame"), 3, 0)
        search_layout.addWidget(self.search_frame_edit, 3, 1)
        search_layout.addWidget(self.search_button, 3, 2)
        search_layout.addWidget(self.reset_search_button, 3, 3)
        search_layout.addWidget(self.search_count_label, 4, 0, 1, 4)

        left_layout.addWidget(search_group)

        results_group = QGroupBox("Folder View")
        results_layout = QVBoxLayout(results_group)
        self.folder_list = QListWidget()
        self.folder_list.setViewMode(QListWidget.IconMode)
        self.folder_list.setMovement(QListWidget.Static)
        self.folder_list.setResizeMode(QListWidget.Adjust)
        self.folder_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.folder_list.setIconSize(QSize(120, 96))
        self.folder_list.setGridSize(QSize(165, 150))
        self.folder_list.setSpacing(8)
        self.folder_list.currentItemChanged.connect(self.on_browser_item_changed)
        self.folder_list.itemSelectionChanged.connect(self.on_browser_selection_changed)
        self.folder_list.itemDoubleClicked.connect(self.open_selected_in_group_view)
        results_layout.addWidget(self.folder_list)
        left_layout.addWidget(results_group, stretch=1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 8, 8, 8)

        preview_group = QGroupBox("Single Photo View")
        preview_layout = QVBoxLayout(preview_group)
        self.browser_image_label = QLabel("No image")
        self.browser_image_label.setAlignment(Qt.AlignCenter)
        self.browser_image_label.setMinimumSize(640, 480)
        self.browser_image_label.setStyleSheet("border: 1px solid #666; background: #111; color: #ccc;")
        preview_layout.addWidget(self.browser_image_label)
        right_layout.addWidget(preview_group, stretch=3)

        meta_group = QGroupBox("Photo Metadata")
        meta_layout = QVBoxLayout(meta_group)
        self.browser_meta_text = QTextEdit()
        self.browser_meta_text.setReadOnly(True)
        meta_layout.addWidget(self.browser_meta_text)
        right_layout.addWidget(meta_group, stretch=2)

        assign_group = QGroupBox("Selected Photo Assignment")
        assign_form = QFormLayout(assign_group)
        self.browser_selected_detection_label = QLabel("-")
        self.browser_selected_identity_label = QLabel("-")
        self.browser_name_combo = QComboBox()
        self.browser_new_name_edit = QLineEdit()
        self.browser_new_name_edit.setPlaceholderText("New name")
        self.browser_status_combo = QComboBox()
        self.browser_status_combo.addItems(VALID_STATUSES)
        self.browser_apply_button = QPushButton("Apply to This Photo")
        self.browser_apply_button.clicked.connect(self.apply_browser_assignment)
        self.browser_open_group_button = QPushButton("Open Selected in Group View")
        self.browser_open_group_button.clicked.connect(self.open_selected_in_group_view)
        assign_form.addRow("Detection ID", self.browser_selected_detection_label)
        assign_form.addRow("Identity ID", self.browser_selected_identity_label)
        assign_form.addRow("Existing names", self.browser_name_combo)
        assign_form.addRow("New name", self.browser_new_name_edit)
        assign_form.addRow("Status", self.browser_status_combo)
        assign_form.addRow("", self.browser_apply_button)
        assign_form.addRow("", self.browser_open_group_button)
        right_layout.addWidget(assign_group, stretch=1)

        batch_group = QGroupBox("Batch Assignment for Selected Search Results")
        batch_form = QFormLayout(batch_group)
        self.browser_batch_count_label = QLabel("0 selected")
        self.browser_batch_name_combo = QComboBox()
        self.browser_batch_new_name_edit = QLineEdit()
        self.browser_batch_new_name_edit.setPlaceholderText("New name")
        self.browser_batch_status_combo = QComboBox()
        self.browser_batch_status_combo.addItems(VALID_STATUSES)
        self.browser_batch_apply_button = QPushButton("Apply to Selected Photos")
        self.browser_batch_apply_button.clicked.connect(self.apply_browser_batch_assignment)
        self.browser_select_all_button = QPushButton("Select All Results")
        self.browser_select_all_button.clicked.connect(self.select_all_browser_results)
        self.browser_clear_selection_button = QPushButton("Clear Selection")
        self.browser_clear_selection_button.clicked.connect(self.clear_browser_selection)
        batch_form.addRow("Selection", self.browser_batch_count_label)
        batch_form.addRow("Existing names", self.browser_batch_name_combo)
        batch_form.addRow("New name", self.browser_batch_new_name_edit)
        batch_form.addRow("Status", self.browser_batch_status_combo)
        batch_form.addRow("", self.browser_batch_apply_button)
        batch_form.addRow("", self.browser_select_all_button)
        batch_form.addRow("", self.browser_clear_selection_button)
        right_layout.addWidget(batch_group, stretch=1)

        main_splitter.addWidget(left_panel)
        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([900, 900])

        layout = QVBoxLayout(self.browser_tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(main_splitter)
        self.tabs.addTab(self.browser_tab, "Photo Browser")

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open JSON", self)
        open_action.triggered.connect(self.choose_json)
        toolbar.addAction(open_action)

        save_action = QAction("Save", self)
        save_action.triggered.connect(self.save_current_file)
        toolbar.addAction(save_action)

        search_action = QAction("Apply Search", self)
        search_action.triggered.connect(self.apply_photo_search)
        toolbar.addAction(search_action)

    # ---------- open / save ----------

    def choose_json(self) -> None:
        start_dir = str(self.json_path.parent) if self.json_path else ""
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open face_identities.json",
            start_dir,
            "JSON files (*.json)",
        )
        if path_str:
            self.open_json(Path(path_str))

    def open_json(self, path: Path) -> None:
        try:
            data = load_json(path)
        except Exception as exc:
            QMessageBox.critical(self, "Open failed", f"Could not open JSON:\n{exc}")
            return

        identities = data.get("identities", [])
        if not isinstance(identities, list):
            QMessageBox.critical(self, "Invalid file", "This JSON has no valid 'identities' list.")
            return

        self.ensure_schema(data)
        self.json_path = path.resolve()
        self.data = data
        self.identities = data["identities"]
        self.current_index = -1
        self.current_sample_detection_id = None

        self.rebuild_identity_maps()
        self.try_load_source_faces_raw()
        self.rebuild_photo_records()

        self.loaded_source_label.setText(str(self.source_faces_raw_path) if self.source_faces_raw_path else "Not loaded")
        self.loaded_crops_label.setText(str(self.source_crops_dir) if self.source_crops_dir else "Not loaded")

        self.refresh_name_combos()
        self.refresh_browser_name_combo()
        self.rebuild_identity_list()
        self.reset_photo_search()
        self.on_browser_selection_changed()
        self.tabs.setCurrentWidget(self.browser_tab)

        self.statusBar().showMessage(f"Opened {path}")
        if self.identities:
            self.identity_list.setCurrentRow(0)
        else:
            self.clear_details()

    def save_current_file(self) -> None:
        if self.data is None or self.json_path is None:
            return

        self.commit_backwards_compatible_fields()
        try:
            cloned = json.loads(json.dumps(self.data))
            cloned["identity_json_path"] = str(self.json_path.resolve())
            if self.source_faces_raw_path is not None:
                cloned["source_faces_raw_json"] = str(self.source_faces_raw_path.resolve())
            if self.source_crops_dir is not None:
                cloned["source_crops_dir"] = str(self.source_crops_dir.resolve())

            for identity in cloned.get("identities", []):
                identity["status"] = denormalize_status(identity.get("status"))
                overrides = identity.get("detection_overrides", {})
                if isinstance(overrides, dict):
                    for item in overrides.values():
                        if isinstance(item, dict):
                            item["status"] = denormalize_status(item.get("status"))
            save_json(self.json_path, cloned)
        except Exception as exc:
            QMessageBox.critical(self, "Save failed", f"Could not save JSON:\n{exc}")
            return

        self.statusBar().showMessage(f"Saved {self.json_path}", 3000)

    # ---------- cluster view ----------

    def rebuild_identity_list(self) -> None:
        self.identity_list.clear()

        def sort_key(identity: dict[str, Any]) -> tuple[int, int]:
            return (-int(identity.get("num_detections", 0)), int(identity.get("identity_id", 0)))

        self.identities.sort(key=sort_key)

        for identity in self.identities:
            item = QListWidgetItem(self._list_text(identity))
            item.setData(Qt.UserRole, int(identity.get("identity_id", 0)))
            self.identity_list.addItem(item)

    def _list_text(self, identity: dict[str, Any]) -> str:
        identity_id = int(identity.get("identity_id", 0))
        num = int(identity.get("num_detections", 0))
        base_status = normalize_status(identity.get("status"))
        base_name = str(identity.get("manual_name", "")).strip()
        overrides = identity.get("detection_overrides", {})
        override_count = len(overrides) if isinstance(overrides, dict) else 0
        name_part = f" | {base_name}" if base_name else ""
        mixed_part = f" | mixed:{override_count}" if override_count else ""
        return f"#{identity_id:02d} | {num:4d} | {base_status}{name_part}{mixed_part}"

    def clear_layout(self, layout: QGridLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def clear_details(self) -> None:
        self.id_label.setText("-")
        self.count_label.setText("-")
        self.best_score_label.setText("-")
        self.time_range_label.setText("-")
        self.selected_detection_label.setText("-")
        self.loaded_source_label.setText("-")
        self.loaded_crops_label.setText("-")

        self.bulk_name_combo.setCurrentIndex(0)
        self.bulk_new_name_edit.setText("")
        self.bulk_status_combo.setCurrentText("no-name")

        self.sample_name_combo.setCurrentIndex(0)
        self.sample_new_name_edit.setText("")
        self.sample_status_combo.setCurrentText("no-name")

        self.representative_label.setText("No image")
        self.representative_label.setPixmap(QPixmap())
        self.clear_layout(self.samples_layout)
        self.sample_cards = []
        self.current_sample_detection_id = None

    def on_identity_selected(self, row: int) -> None:
        self.current_index = row
        self.current_sample_detection_id = None

        if row < 0 or row >= len(self.identities):
            self.clear_details()
            return

        identity = self.identities[row]
        self._updating_ui = True
        try:
            self.id_label.setText(str(identity.get("identity_id", "")))
            self.count_label.setText(str(identity.get("num_detections", "")))
            best_score = identity.get("best_score")
            self.best_score_label.setText(f"{best_score:.4f}" if isinstance(best_score, (int, float)) else "-")

            time_range = identity.get("time_range", [])
            if isinstance(time_range, list) and len(time_range) == 2:
                self.time_range_label.setText(f"{time_range[0]:.2f}s - {time_range[1]:.2f}s")
            else:
                self.time_range_label.setText("-")

            self.loaded_source_label.setText(str(self.source_faces_raw_path) if self.source_faces_raw_path else "Not loaded")
            self.loaded_crops_label.setText(str(self.source_crops_dir) if self.source_crops_dir else "Not loaded")

            base_name = str(identity.get("manual_name", "")).strip()
            base_status = normalize_status(identity.get("status"))

            self.set_combo_text(self.bulk_name_combo, base_name)
            self.bulk_new_name_edit.setText("")
            self.bulk_status_combo.setCurrentText(base_status)

            self.selected_detection_label.setText("-")
            self.set_combo_text(self.sample_name_combo, "")
            self.sample_new_name_edit.setText("")
            self.sample_status_combo.setCurrentText("no-name")

            self.set_representative_image(Path(str(identity.get("representative_crop", ""))))
            self.populate_sample_grid(identity)
        finally:
            self._updating_ui = False

    def on_sample_card_clicked(self, card: SampleCard) -> None:
        for sample_card in self.sample_cards:
            sample_card.set_selected(sample_card is card)

        self.current_sample_detection_id = card.detection_id
        self.selected_detection_label.setText(str(card.detection_id))

        identity = self.get_current_identity()
        if identity is None:
            return

        name, status = self.get_effective_sample_assignment(identity, card.detection_id)

        self._updating_ui = True
        try:
            self.set_combo_text(self.sample_name_combo, name)
            self.sample_new_name_edit.setText("")
            self.sample_status_combo.setCurrentText(status)
        finally:
            self._updating_ui = False

    def scaled_pixmap(self, path: Path, width: int, height: int) -> QPixmap:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return QPixmap()
        return pixmap.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)

    def set_representative_image(self, path: Path) -> None:
        display_path = path
        if (not display_path.exists()) and self.source_crops_dir is not None and display_path.name:
            guess = self.source_crops_dir / display_path.name
            if guess.exists():
                display_path = guess

        pixmap = self.scaled_pixmap(display_path, 700, 420)
        if pixmap.isNull():
            self.representative_label.setText(f"Could not load image:\n{display_path}")
            self.representative_label.setPixmap(QPixmap())
        else:
            self.representative_label.setText("")
            self.representative_label.setPixmap(pixmap)

    def populate_sample_grid(self, identity: dict[str, Any]) -> None:
        self.clear_layout(self.samples_layout)
        self.sample_cards = []

        detection_ids = identity.get("detection_ids", [])
        if not isinstance(detection_ids, list) or not detection_ids:
            placeholder = QLabel("No detections in cluster")
            self.samples_layout.addWidget(placeholder, 0, 0)
            return

        columns = 4
        for idx, det_id in enumerate(detection_ids):
            det_id = int(det_id)
            record = self.photo_record_by_detection(det_id)
            path = record.crop_path if record is not None else Path()
            card = SampleCard(det_id, path, self.samples_container)

            if record is not None:
                name, status = record.effective_name_status()
                preview = name if name else "-"
                score_text = f"{record.score:.2f}" if record.score is not None else "-"
                card.update_text(f"det: {det_id}\nframe: {record.frame_index}\nstatus: {status}\nname: {preview}\nscore: {score_text}")
            else:
                card.update_text(f"det: {det_id}\nmissing")

            row = idx // columns
            col = idx % columns
            self.samples_layout.addWidget(card, row, col)
            self.sample_cards.append(card)

        self.samples_layout.setRowStretch((len(self.sample_cards) // columns) + 1, 1)

    # ---------- browser view ----------

    def refresh_browser_name_combo(self) -> None:
        names = self.get_label_options()
        current = self.browser_name_combo.currentText() if hasattr(self, "browser_name_combo") else "Any"
        self.browser_name_combo.blockSignals(True)
        self.browser_name_combo.clear()
        self.browser_name_combo.addItem("Any")
        self.browser_name_combo.addItem("")
        for name in names:
            self.browser_name_combo.addItem(name)
        idx = self.browser_name_combo.findText(current)
        self.browser_name_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.browser_name_combo.blockSignals(False)

        self.browser_name_combo.blockSignals(True)
        self.browser_name_combo.clear()
        self.browser_name_combo.addItem("")
        for name in names:
            self.browser_name_combo.addItem(name)
        self.browser_name_combo.blockSignals(False)

    def photo_record_by_detection(self, detection_id: int) -> PhotoRecord | None:
        for rec in self.photo_records:
            if rec.detection_id == detection_id:
                return rec
        return None


    def get_selected_browser_detection_ids(self) -> list[int]:
        ids: list[int] = []
        for item in self.folder_list.selectedItems():
            try:
                ids.append(int(item.data(Qt.UserRole)))
            except Exception:
                continue
        return ids

    def on_browser_selection_changed(self) -> None:
        selected_ids = self.get_selected_browser_detection_ids()
        self.browser_batch_count_label.setText(f"{len(selected_ids)} selected")

    def select_all_browser_results(self) -> None:
        self.folder_list.selectAll()
        self.on_browser_selection_changed()

    def clear_browser_selection(self) -> None:
        self.folder_list.clearSelection()
        self.on_browser_selection_changed()

    def find_identity_by_name(self, name: str) -> dict[str, Any] | None:
        clean = name.strip().lower()
        if not clean:
            return None
        for identity in self.identities:
            if str(identity.get("manual_name", "")).strip().lower() == clean:
                return identity
        return None

    def next_identity_id(self) -> int:
        ids = [int(identity.get("identity_id", -1)) for identity in self.identities]
        return (max(ids) + 1) if ids else 0

    def update_identity_metadata(self, identity: dict[str, Any]) -> None:
        detection_ids = [int(x) for x in identity.get("detection_ids", [])]
        identity["detection_ids"] = detection_ids
        identity["num_detections"] = len(detection_ids)

        frame_indices: list[int] = []
        time_values: list[float] = []
        sample_crops: list[str] = []
        best_score = None
        representative_crop = ""

        for det_id in detection_ids:
            record = self.photo_record_by_detection(det_id)
            if record is None:
                continue
            frame_indices.append(int(record.frame_index))
            time_values.append(float(record.time_seconds))
            if len(sample_crops) < 12:
                sample_crops.append(str(record.crop_path))
            if representative_crop == "":
                representative_crop = str(record.crop_path)
            if record.score is not None:
                if best_score is None or float(record.score) > float(best_score):
                    best_score = float(record.score)
                    representative_crop = str(record.crop_path)

        identity["sample_crops"] = sample_crops
        identity["representative_crop"] = representative_crop
        identity["frame_indices"] = sorted(set(frame_indices))
        identity["time_range"] = [min(time_values), max(time_values)] if time_values else [0.0, 0.0]
        identity["best_score"] = float(best_score) if best_score is not None else 0.0

    def create_identity_for_assignment(self, name: str, status: str, seed_detection_id: int | None = None) -> dict[str, Any]:
        identity_id = self.next_identity_id()
        identity = {
            "identity_id": identity_id,
            "manual_name": name.strip(),
            "status": normalize_status(status),
            "num_detections": 0,
            "best_score": 0.0,
            "representative_crop": "",
            "sample_crops": [],
            "detection_ids": [],
            "frame_indices": [],
            "time_range": [0.0, 0.0],
            "detection_overrides": {},
        }
        self.identities.append(identity)
        self.identities_by_id[identity_id] = identity
        return identity

    def remove_detection_from_identity(self, detection_id: int, identity: dict[str, Any] | None) -> None:
        if identity is None:
            return
        identity["detection_ids"] = [int(x) for x in identity.get("detection_ids", []) if int(x) != int(detection_id)]
        overrides = identity.get("detection_overrides", {})
        if isinstance(overrides, dict):
            overrides.pop(str(detection_id), None)

        if not identity["detection_ids"]:
            identity_id = int(identity.get("identity_id", -1))
            if identity in self.identities:
                self.identities.remove(identity)
            self.identities_by_id.pop(identity_id, None)
        else:
            self.update_identity_metadata(identity)

    def attach_detection_to_identity(self, detection_id: int, target_identity: dict[str, Any]) -> None:
        if self.data is None:
            return

        mapping = self.data.setdefault("detection_to_identity", {})
        current_identity_id = mapping.get(str(detection_id))
        if current_identity_id is not None and int(current_identity_id) != int(target_identity.get("identity_id", -1)):
            old_identity = self.identities_by_id.get(int(current_identity_id))
            self.remove_detection_from_identity(detection_id, old_identity)

        mapping[str(detection_id)] = int(target_identity.get("identity_id", -1))
        detection_ids = [int(x) for x in target_identity.get("detection_ids", [])]
        if int(detection_id) not in detection_ids:
            detection_ids.append(int(detection_id))
        target_identity["detection_ids"] = detection_ids

    def assign_detections_to_name_status(self, detection_ids: list[int], name: str, status: str) -> tuple[int, int]:
        clean_name = name.strip()
        norm_status = normalize_status(status)

        target_identity = self.find_identity_by_name(clean_name) if clean_name else None
        if target_identity is None:
            target_identity = self.create_identity_for_assignment(clean_name, norm_status, detection_ids[0] if detection_ids else None)

        target_identity["manual_name"] = clean_name
        target_identity["status"] = norm_status

        changed = 0
        for detection_id in detection_ids:
            self.attach_detection_to_identity(int(detection_id), target_identity)
            overrides = target_identity.setdefault("detection_overrides", {})
            if isinstance(overrides, dict):
                overrides.pop(str(int(detection_id)), None)
            changed += 1

        self.rebuild_identity_maps()
        self.rebuild_photo_records()
        target_identity = self.identities_by_id.get(int(target_identity["identity_id"]), target_identity)
        self.update_identity_metadata(target_identity)
        self.commit_backwards_compatible_fields()
        self.rebuild_identity_maps()
        self.rebuild_photo_records()
        return changed, int(target_identity.get("identity_id", -1))

    def reset_photo_search(self) -> None:
        self.search_query_edit.setText("")
        self.search_name_combo.setCurrentText("Any")
        self.search_status_combo.setCurrentText("Any")
        self.search_identity_edit.setText("")
        self.search_detection_edit.setText("")
        self.search_frame_edit.setText("")
        self.browser_batch_name_combo.setCurrentIndex(0)
        self.browser_batch_new_name_edit.setText("")
        self.browser_batch_status_combo.setCurrentText("named")
        self.apply_photo_search()

    def record_matches(self, record: PhotoRecord) -> bool:
        query = self.search_query_edit.text().strip().lower()
        exact_identity = try_int(self.search_identity_edit.text())
        exact_detection = try_int(self.search_detection_edit.text())
        exact_frame = try_int(self.search_frame_edit.text())
        selected_name = self.search_name_combo.currentText()
        selected_status = self.search_status_combo.currentText()

        eff_name, eff_status = record.effective_name_status()

        if exact_identity is not None and record.identity_id != exact_identity:
            return False
        if exact_detection is not None and record.detection_id != exact_detection:
            return False
        if exact_frame is not None and record.frame_index != exact_frame:
            return False
        if selected_name not in ("Any", "") and eff_name.lower() != selected_name.strip().lower():
            return False
        if selected_status != "Any" and eff_status != selected_status:
            return False

        if query:
            haystack = " ".join([
                eff_name.lower(),
                eff_status.lower(),
                f"id {record.identity_id}" if record.identity_id is not None else "",
                f"identity {record.identity_id}" if record.identity_id is not None else "",
                f"det {record.detection_id}",
                f"detection {record.detection_id}",
                f"frame {record.frame_index}",
                record.crop_name.lower(),
            ])

            for token in query.split():
                if token.startswith("det:") or token.startswith("detection:"):
                    value = token.split(":", 1)[1]
                    if value != str(record.detection_id):
                        return False
                    continue
                if token.startswith("id:") or token.startswith("identity:"):
                    value = token.split(":", 1)[1]
                    if str(record.identity_id) != value:
                        return False
                    continue
                if token.startswith("frame:"):
                    value = token.split(":", 1)[1]
                    if value != str(record.frame_index):
                        return False
                    continue
                if token.startswith("name:"):
                    value = token.split(":", 1)[1]
                    if value not in eff_name.lower():
                        return False
                    continue
                if token.startswith("status:"):
                    value = token.split(":", 1)[1]
                    if value != eff_status.lower():
                        return False
                    continue
                if token not in haystack:
                    return False

        return True

    def apply_photo_search(self) -> None:
        matches = [rec for rec in self.photo_records if self.record_matches(rec)]
        self.filtered_detection_ids = [rec.detection_id for rec in matches]
        self.rebuild_folder_view(matches)

    def rebuild_folder_view(self, matches: list[PhotoRecord]) -> None:
        self.folder_list.clear()

        for rec in matches:
            name, status = rec.effective_name_status()
            title = name if name else "(no-name)"
            score_text = f"{rec.score:.2f}" if rec.score is not None else "-"
            text = f"{title}\ndet:{rec.detection_id} id:{rec.identity_id if rec.identity_id is not None else '-'}\nframe:{rec.frame_index} score:{score_text}\n{status}"

            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, rec.detection_id)

            pixmap = QPixmap(str(rec.crop_path))
            if not pixmap.isNull():
                item.setIcon(QIcon(pixmap.scaled(120, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation)))

            self.folder_list.addItem(item)

        self.search_count_label.setText(f"{len(matches)} photos")
        if matches:
            self.folder_list.setCurrentRow(0)
        else:
            self.browser_image_label.setText("No photo selected")
            self.browser_image_label.setPixmap(QPixmap())
            self.browser_meta_text.setPlainText("")
            self.browser_selected_detection_label.setText("-")
            self.browser_selected_identity_label.setText("-")
        self.on_browser_selection_changed()

    def on_browser_item_changed(self, current: QListWidgetItem | None, previous: QListWidgetItem | None = None) -> None:
        if current is None:
            return
        detection_id = int(current.data(Qt.UserRole))
        record = self.photo_record_by_detection(detection_id)
        if record is None:
            return
        self.show_browser_record(record)

    def show_browser_record(self, record: PhotoRecord) -> None:
        pixmap = QPixmap(str(record.crop_path))
        if pixmap.isNull():
            self.browser_image_label.setText(f"Image not found\n{record.crop_path}")
            self.browser_image_label.setPixmap(QPixmap())
        else:
            self.browser_image_label.setText("")
            self.browser_image_label.setPixmap(
                pixmap.scaled(820, 620, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )

        name, status = record.effective_name_status()
        identity = record.identity_ref
        meta = {
            "detection_id": record.detection_id,
            "identity_id": record.identity_id,
            "effective_name": name,
            "effective_status": status,
            "frame_index": record.frame_index,
            "face_index": record.face_index,
            "time_seconds": record.time_seconds,
            "score": record.score,
            "bbox": record.bbox,
            "crop_path": str(record.crop_path),
            "cluster_manual_name": str(identity.get("manual_name", "")).strip() if identity else "",
            "cluster_status": normalize_status(identity.get("status")) if identity else "no-name",
        }
        self.browser_meta_text.setPlainText(json.dumps(meta, ensure_ascii=False, indent=2))

        self.browser_selected_detection_label.setText(str(record.detection_id))
        self.browser_selected_identity_label.setText(str(record.identity_id) if record.identity_id is not None else "-")
        self.set_combo_text(self.browser_name_combo, name)
        self.browser_new_name_edit.setText("")
        self.browser_status_combo.setCurrentText(status)

    def open_selected_in_group_view(self, *args) -> None:
        current_item = self.folder_list.currentItem()
        if current_item is None:
            return

        detection_id = int(current_item.data(Qt.UserRole))
        record = self.photo_record_by_detection(detection_id)
        if record is None or record.identity_id is None:
            return

        # Switch to group view and select the matching cluster.
        self.tabs.setCurrentWidget(self.cluster_tab)
        for row, identity in enumerate(self.identities):
            if int(identity.get("identity_id", -1)) == int(record.identity_id):
                self.identity_list.setCurrentRow(row)
                break

        # highlight matching photo card in cluster view if visible
        for card in self.sample_cards:
            card.set_selected(card.detection_id == detection_id)
            if card.detection_id == detection_id:
                self.current_sample_detection_id = detection_id
                self.selected_detection_label.setText(str(detection_id))


    def apply_browser_assignment(self) -> None:
        current_item = self.folder_list.currentItem()
        if current_item is None:
            QMessageBox.information(self, "No photo selected", "Select a photo first.")
            return

        detection_id = int(current_item.data(Qt.UserRole))
        record = self.photo_record_by_detection(detection_id)
        if record is None or record.identity_ref is None:
            QMessageBox.information(self, "No cluster", "This photo is not mapped to a cluster.")
            return

        typed = self.browser_new_name_edit.text().strip()
        name = typed if typed else self.browser_name_combo.currentText().strip()
        status = self.browser_status_combo.currentText()

        if name:
            self.add_name_option(name)

        self.set_sample_override(record.identity_ref, detection_id, name, status)
        self.commit_backwards_compatible_fields()
        self.refresh_name_combos()
        self.refresh_browser_name_combo()
        self.refresh_identity_list_row()
        self.apply_photo_search()

        # restore selection
        for row in range(self.folder_list.count()):
            item = self.folder_list.item(row)
            if int(item.data(Qt.UserRole)) == detection_id:
                self.folder_list.setCurrentRow(row)
                break

        # refresh cluster view if same cluster visible
        current_identity = self.get_current_identity()
        if current_identity is not None and record.identity_id == int(current_identity.get("identity_id", -1)):
            self.populate_sample_grid(current_identity)

        self.statusBar().showMessage("Applied to selected photo", 2000)


    def apply_browser_batch_assignment(self) -> None:
        detection_ids = self.get_selected_browser_detection_ids()
        if not detection_ids:
            QMessageBox.information(self, "No selection", "Select one or more photos in the search results first.")
            return

        typed = self.browser_batch_new_name_edit.text().strip()
        name = typed if typed else self.browser_batch_name_combo.currentText().strip()
        status = self.browser_batch_status_combo.currentText()

        if not name and normalize_status(status) == "named":
            QMessageBox.information(self, "Name required", "Choose or type a name when assigning named photos.")
            return

        if name:
            self.add_name_option(name)

        changed, target_identity_id = self.assign_detections_to_name_status(detection_ids, name, status)

        self.refresh_name_combos()
        self.refresh_browser_name_combo()
        self.rebuild_identity_list()
        self.apply_photo_search()

        wanted = set(int(x) for x in detection_ids)
        self.folder_list.clearSelection()
        for row in range(self.folder_list.count()):
            item = self.folder_list.item(row)
            if int(item.data(Qt.UserRole)) in wanted:
                item.setSelected(True)
                if self.folder_list.currentRow() < 0:
                    self.folder_list.setCurrentItem(item)
        self.on_browser_selection_changed()

        current_identity = self.get_current_identity()
        if current_identity is not None:
            self.populate_sample_grid(current_identity)

        self.statusBar().showMessage(
            f"Applied to {changed} photo(s) in identity #{target_identity_id}.",
            4000,
        )

    # ---------- shared field helpers ----------

    def set_combo_text(self, combo: QComboBox, text: str) -> None:
        idx = combo.findText(text)
        combo.setCurrentIndex(idx if idx >= 0 else 0)

    def on_bulk_fields_changed(self) -> None:
        if self._updating_ui:
            return
        self.statusBar().showMessage("Unsaved changes", 2000)

    def on_sample_fields_changed(self) -> None:
        if self._updating_ui:
            return
        self.statusBar().showMessage("Unsaved changes", 2000)

    def apply_bulk_to_identity(self) -> None:
        identity = self.get_current_identity()
        if identity is None:
            return

        typed = self.bulk_new_name_edit.text().strip()
        name = typed if typed else self.bulk_name_combo.currentText().strip()
        status = self.bulk_status_combo.currentText()

        if name:
            self.add_name_option(name)

        identity["manual_name"] = name
        identity["status"] = normalize_status(status)

        detection_ids = [int(x) for x in identity.get("detection_ids", [])]
        overrides = identity.setdefault("detection_overrides", {})
        overrides.clear()
        for det_id in detection_ids:
            overrides[str(det_id)] = {
                "manual_name": name,
                "status": normalize_status(status),
            }

        self.commit_backwards_compatible_fields()
        self.refresh_name_combos()
        self.refresh_browser_name_combo()
        self.populate_sample_grid(identity)
        self.refresh_identity_list_row()
        self.apply_photo_search()
        self.statusBar().showMessage("Applied to entire cluster", 2000)

    def apply_to_selected_sample(self) -> None:
        identity = self.get_current_identity()
        if identity is None or self.current_sample_detection_id is None:
            QMessageBox.information(self, "No photo selected", "Select a cluster photo first.")
            return

        typed = self.sample_new_name_edit.text().strip()
        name = typed if typed else self.sample_name_combo.currentText().strip()
        status = self.sample_status_combo.currentText()

        if name:
            self.add_name_option(name)

        self.set_sample_override(identity, self.current_sample_detection_id, name, status)
        self.commit_backwards_compatible_fields()
        self.refresh_name_combos()
        self.refresh_browser_name_combo()
        self.populate_sample_grid(identity)
        self.refresh_identity_list_row()
        self.apply_photo_search()
        self.statusBar().showMessage("Applied to selected photo", 2000)

    def refresh_identity_list_row(self) -> None:
        if self.current_index < 0 or self.current_index >= len(self.identities):
            return
        item = self.identity_list.item(self.current_index)
        if item is not None:
            item.setText(self._list_text(self.identities[self.current_index]))

    def save_and_next(self) -> None:
        self.save_current_file()
        self.go_next()

    def go_next(self) -> None:
        row = self.identity_list.currentRow()
        if row < self.identity_list.count() - 1:
            self.identity_list.setCurrentRow(row + 1)

    def go_previous(self) -> None:
        row = self.identity_list.currentRow()
        if row > 0:
            self.identity_list.setCurrentRow(row - 1)

    # ---------- keyboard navigation ----------

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if self.tabs.currentWidget() is self.browser_tab and self.folder_list.count() > 0:
            current_row = self.folder_list.currentRow()
            if event.key() in (Qt.Key_Right, Qt.Key_Down):
                if current_row < self.folder_list.count() - 1:
                    self.folder_list.setCurrentRow(current_row + 1)
                    return
            if event.key() in (Qt.Key_Left, Qt.Key_Up):
                if current_row > 0:
                    self.folder_list.setCurrentRow(current_row - 1)
                    return
        super().keyPressEvent(event)


def main() -> int:
    app = QApplication(sys.argv)
    json_path: Path | None = None
    if len(sys.argv) > 1:
        json_path = Path(sys.argv[1]).expanduser().resolve()
    window = IdentityReviewWindow(json_path)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
