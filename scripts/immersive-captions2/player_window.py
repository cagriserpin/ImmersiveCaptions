from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

try:
    import imageio_ffmpeg  # type: ignore
except Exception:
    imageio_ffmpeg = None

import cv2
import numpy as np

from PySide6.QtCore import Qt, QSettings, QTimer, QUrl
from PySide6.QtGui import QImage, QKeySequence, QPainter, QPixmap, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from detection_renderer import DetectionRenderer
from detection_store import FaceDetectionStore, FaceIdentityStore, TranscriptStore
from face_tracker import process_video_faces


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            value = self.pixel_pos_to_range_value(int(event.position().x()))
            self.setValue(value)
            self.sliderMoved.emit(value)
            self.sliderReleased.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def pixel_pos_to_range_value(self, pos: int) -> int:
        span = self.width() if self.orientation() == Qt.Orientation.Horizontal else self.height()
        if span <= 0:
            return self.minimum()
        ratio = max(0.0, min(1.0, pos / span))
        return int(self.minimum() + ratio * (self.maximum() - self.minimum()))


class MainWindow(QMainWindow):
    SETTINGS_VIDEO = "session/video_path"
    SETTINGS_DETECTIONS = "session/detections_path"
    SETTINGS_IDENTITIES = "session/identities_path"
    SETTINGS_TRANSCRIPT = "session/transcript_path"

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Immersive Captions 2 — Face + Transcript Preview")
        self.resize(1500, 900)

        self.settings = QSettings("OpenAI", "ImmersiveCaptions2")

        self.video_path: Path | None = None
        self.face_json_path: Path | None = None
        self.face_identities_path: Path | None = None
        self.transcript_json_path: Path | None = None

        self.face_store = FaceDetectionStore()
        self.identity_store = FaceIdentityStore()
        self.transcript_store = TranscriptStore()

        self.is_user_scrubbing = False
        self.duration_ms = 0
        self.last_session_status = "No session restored yet."

        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        self.scene = QGraphicsScene(self)
        self.video_item = QGraphicsVideoItem()
        self.scene.addItem(self.video_item)
        self.player.setVideoOutput(self.video_item)

        self.view = QGraphicsView(self.scene)
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setStyleSheet("background:#0d0f14; border-radius: 12px;")

        self.renderer = DetectionRenderer(self.scene)
        self.renderer.set_identity_store(self.identity_store)

        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(33)

        self.open_video_button = QPushButton("Open Video")
        self.open_detections_button = QPushButton("Open Face JSON")
        self.open_identities_button = QPushButton("Open Identities JSON")
        self.open_transcript_button = QPushButton("Open Transcript JSON")
        self.extract_faces_button = QPushButton("Extract Faces")
        self.export_video_button = QPushButton("Export Captioned MP4")
        self.toggle_boxes_button = QPushButton("Hide Boxes")
        self.toggle_landmarks_button = QPushButton("Hide Landmarks")
        self.toggle_scores_button = QPushButton("Hide Labels")
        self.play_pause_button = QPushButton("Play")

        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)

        self.video_value_label = QLabel("No video loaded")
        self.detections_value_label = QLabel("No face JSON loaded")
        self.identities_value_label = QLabel("No identities JSON loaded")
        self.transcript_value_label = QLabel("No transcript JSON loaded")

        self.playback_state_value_label = QLabel("Stopped")
        self.visible_faces_value_label = QLabel("0")
        self.active_captions_value_label = QLabel("0")
        self.current_frame_value_label = QLabel("-")
        self.scene_size_value_label = QLabel("0 × 0")
        self.sample_step_value_label = QLabel("-")
        self.session_status_value_label = QLabel(self.last_session_status)
        self.session_status_value_label.setWordWrap(True)

        self._build_ui()
        self._apply_style()

        self.open_video_button.clicked.connect(self.open_video)
        self.open_detections_button.clicked.connect(self.open_detections)
        self.open_identities_button.clicked.connect(self.open_identities)
        self.open_transcript_button.clicked.connect(self.open_transcript)
        self.extract_faces_button.clicked.connect(self.extract_faces_for_current_video)
        self.export_video_button.clicked.connect(self.export_captioned_video)
        self.toggle_boxes_button.clicked.connect(self.toggle_boxes)
        self.toggle_landmarks_button.clicked.connect(self.toggle_landmarks)
        self.toggle_scores_button.clicked.connect(self.toggle_scores)
        self.play_pause_button.clicked.connect(self.toggle_play_pause)

        self.seek_slider.sliderPressed.connect(self.on_slider_pressed)
        self.seek_slider.sliderReleased.connect(self.on_slider_released)
        self.seek_slider.sliderMoved.connect(self.on_slider_moved)

        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.player.errorOccurred.connect(self.on_player_error)

        self.ui_timer.timeout.connect(self.update_overlay)

        self.space_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.space_shortcut.activated.connect(self.toggle_play_pause)

        self.update_loaded_file_labels()
        self.update_runtime_info()
        QTimer.singleShot(0, self.restore_last_session)

    def _build_ui(self) -> None:
        video_layout = QVBoxLayout()
        video_layout.setContentsMargins(0, 0, 0, 0)
        video_layout.setSpacing(10)
        video_layout.addWidget(self.view, stretch=1)

        slider_row = QHBoxLayout()
        slider_row.setSpacing(10)
        slider_row.addWidget(self.seek_slider, stretch=1)
        slider_row.addWidget(self.time_label)
        video_layout.addLayout(slider_row)

        video_panel = QWidget()
        video_panel.setLayout(video_layout)

        side_layout = QVBoxLayout()
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(12)

        files_group = QGroupBox("Files")
        files_layout = QVBoxLayout()
        files_layout.setSpacing(8)
        files_layout.addWidget(self.open_video_button)
        files_layout.addWidget(self.open_detections_button)
        files_layout.addWidget(self.open_identities_button)
        files_layout.addWidget(self.open_transcript_button)
        files_layout.addWidget(self.extract_faces_button)
        files_layout.addWidget(self.export_video_button)
        files_group.setLayout(files_layout)

        loaded_group = QGroupBox("Loaded Resources")
        loaded_layout = QVBoxLayout()
        loaded_layout.setSpacing(8)
        loaded_layout.addWidget(self._make_label_pair("Video", self.video_value_label))
        loaded_layout.addWidget(self._make_label_pair("Face JSON", self.detections_value_label))
        loaded_layout.addWidget(self._make_label_pair("Identities", self.identities_value_label))
        loaded_layout.addWidget(self._make_label_pair("Transcript", self.transcript_value_label))
        loaded_group.setLayout(loaded_layout)

        playback_group = QGroupBox("Playback & Overlay")
        playback_layout = QVBoxLayout()
        playback_layout.setSpacing(8)
        playback_layout.addWidget(self.play_pause_button)
        playback_layout.addWidget(self.toggle_boxes_button)
        playback_layout.addWidget(self.toggle_landmarks_button)
        playback_layout.addWidget(self.toggle_scores_button)
        playback_group.setLayout(playback_layout)

        info_group = QGroupBox("Runtime Info")
        info_layout = QVBoxLayout()
        info_layout.setSpacing(8)
        info_layout.addWidget(self._make_label_pair("State", self.playback_state_value_label))
        info_layout.addWidget(self._make_label_pair("Visible Faces", self.visible_faces_value_label))
        info_layout.addWidget(self._make_label_pair("Active Captions", self.active_captions_value_label))
        info_layout.addWidget(self._make_label_pair("Current Frame", self.current_frame_value_label))
        info_layout.addWidget(self._make_label_pair("Video Size", self.scene_size_value_label))
        info_layout.addWidget(self._make_label_pair("Sample Step", self.sample_step_value_label))
        info_group.setLayout(info_layout)

        session_group = QGroupBox("Session Restore")
        session_layout = QVBoxLayout()
        session_layout.addWidget(self.session_status_value_label)
        session_group.setLayout(session_layout)

        side_layout.addWidget(files_group)
        side_layout.addWidget(loaded_group)
        side_layout.addWidget(playback_group)
        side_layout.addWidget(info_group)
        side_layout.addWidget(session_group)
        side_layout.addStretch(1)

        side_panel = QWidget()
        side_panel.setLayout(side_layout)
        side_panel.setObjectName("sidePanel")
        side_panel.setMinimumWidth(320)
        side_panel.setMaximumWidth(390)

        root_layout = QHBoxLayout()
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(14)
        root_layout.addWidget(video_panel, stretch=1)
        root_layout.addWidget(side_panel)

        container = QWidget()
        container.setLayout(root_layout)
        self.setCentralWidget(container)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #12151c;
                color: #e8ecf3;
                font-size: 13px;
            }
            QGroupBox {
                border: 1px solid #2c3342;
                border-radius: 10px;
                margin-top: 10px;
                padding-top: 10px;
                background: #171b24;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 6px 0 6px;
                color: #b7c0d4;
            }
            QPushButton {
                background: #232a36;
                border: 1px solid #364056;
                border-radius: 8px;
                padding: 10px 12px;
                text-align: left;
            }
            QPushButton:hover {
                background: #2b3444;
            }
            QPushButton:pressed {
                background: #1d2430;
            }
            QLabel {
                color: #e8ecf3;
            }
            QSlider::groove:horizontal {
                border: 0px;
                height: 6px;
                background: #293241;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #7bb3ff;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            #sidePanel {
                background: transparent;
            }
            """
        )

    def _make_label_pair(self, title: str, value_label: QLabel) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        title_label = QLabel(f"{title}:")
        title_label.setStyleSheet("color:#9aa6bd;")
        title_label.setMinimumWidth(92)

        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        layout.addWidget(title_label)
        layout.addWidget(value_label, stretch=1)
        return row

    def format_time(self, ms: int) -> str:
        total_seconds = max(0, ms // 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def set_session_status(self, text: str) -> None:
        self.last_session_status = text
        self.session_status_value_label.setText(text)
        self.statusBar().showMessage(text, 4000)

    def remember_path(self, key: str, path: Path | None) -> None:
        if path is None:
            self.settings.remove(key)
            return
        self.settings.setValue(key, str(path.resolve()))

    def _path_from_settings(self, key: str) -> tuple[Path | None, str | None]:
        value = self.settings.value(key)
        if not value:
            return None, None
        path = Path(str(value))
        return (path if path.exists() else None), str(value)

    def restore_last_session(self) -> None:
        restored = []
        missing = []

        video_path, raw_video = self._path_from_settings(self.SETTINGS_VIDEO)
        detections_path, raw_detections = self._path_from_settings(self.SETTINGS_DETECTIONS)
        identities_path, raw_identities = self._path_from_settings(self.SETTINGS_IDENTITIES)
        transcript_path, raw_transcript = self._path_from_settings(self.SETTINGS_TRANSCRIPT)

        for resolved, raw in (
            (video_path, raw_video),
            (detections_path, raw_detections),
            (identities_path, raw_identities),
            (transcript_path, raw_transcript),
        ):
            if raw and resolved is None:
                missing.append(Path(raw).name)

        if video_path is not None:
            self.load_video(str(video_path), remember=False)
            restored.append(video_path.name)
        if detections_path is not None:
            self.load_detections(str(detections_path), remember=False, auto_load_identities=(identities_path is None))
            restored.append(detections_path.name)
        if identities_path is not None:
            self.load_identities(str(identities_path), remember=False, update_overlay=False)
            restored.append(identities_path.name)
        if transcript_path is not None:
            self.load_transcript(str(transcript_path), remember=False, update_overlay=False)
            restored.append(transcript_path.name)

        self.update_overlay()

        if restored:
            msg = f"Restored: {', '.join(restored)}"
            if missing:
                msg += f" | Missing: {', '.join(missing)}"
            self.set_session_status(msg)
        elif missing:
            self.set_session_status(f"Previous files missing: {', '.join(missing)}")
        else:
            self.set_session_status("No saved session found.")

    def reset_player_state(self):
        self.player.pause()
        self.player.setSource(QUrl())

        self.duration_ms = 0
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setValue(0)
        self.time_label.setText("00:00 / 00:00")
        self.play_pause_button.setText("Play")
        self.is_user_scrubbing = False

        self.renderer.clear()
        self.renderer.reset_caption_tracking()

        self.scene.setSceneRect(0, 0, 1280, 720)
        self.video_item.setSize(self.scene.sceneRect().size())
        self.update_runtime_info()

    def load_video(self, file_path: str, remember: bool = True):
        self.video_path = Path(file_path)
        self.reset_player_state()
        self.player.setSource(QUrl.fromLocalFile(str(self.video_path)))
        self.player.pause()
        if remember:
            self.remember_path(self.SETTINGS_VIDEO, self.video_path)
        self.update_loaded_file_labels()
        self.update_runtime_info()
        self.update_window_title()
        self.ui_timer.start()

    def _auto_identity_path_for_detection_json(self, detection_path: Path) -> Path | None:
        candidates = [
            detection_path.with_name(detection_path.stem + '.face_identities.json'),
            detection_path.parent / (detection_path.name + '.face_identities.json'),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def load_detections(self, file_path: str, remember: bool = True, auto_load_identities: bool = True):
        self.face_json_path = Path(file_path)
        self.face_store.load(self.face_json_path)

        if auto_load_identities:
            auto_identities = self._auto_identity_path_for_detection_json(self.face_json_path)
            if auto_identities is not None:
                self.load_identities(str(auto_identities), remember=remember, update_overlay=False)
            else:
                self.face_identities_path = None
                self.identity_store.clear()
                self.renderer.set_identity_store(self.identity_store)

        if remember:
            self.remember_path(self.SETTINGS_DETECTIONS, self.face_json_path)
        self.update_overlay()
        self.update_loaded_file_labels()
        self.update_runtime_info()
        self.update_window_title()

    def load_identities(self, file_path: str, remember: bool = True, update_overlay: bool = True):
        self.face_identities_path = Path(file_path)
        self.identity_store.load(self.face_identities_path)
        self.renderer.set_identity_store(self.identity_store)
        self.renderer.reset_caption_tracking()
        if remember:
            self.remember_path(self.SETTINGS_IDENTITIES, self.face_identities_path)
        self.update_loaded_file_labels()
        if update_overlay:
            self.update_overlay()
            self.update_runtime_info()
            self.update_window_title()

    def load_transcript(self, file_path: str, remember: bool = True, update_overlay: bool = True):
        self.transcript_json_path = Path(file_path)
        self.transcript_store.load(self.transcript_json_path)
        if remember:
            self.remember_path(self.SETTINGS_TRANSCRIPT, self.transcript_json_path)
        self.update_loaded_file_labels()
        if update_overlay:
            self.update_overlay()
            self.update_runtime_info()
            self.update_window_title()

    def open_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            str(self.video_path.parent if self.video_path else ""),
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)",
        )
        if file_path:
            self.load_video(file_path)
            self.set_session_status(f"Loaded video: {Path(file_path).name}")

    def open_detections(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Face JSON",
            str(self.face_json_path.parent if self.face_json_path else ""),
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            self.load_detections(file_path)
            self.set_session_status(f"Loaded face JSON: {Path(file_path).name}")

    def open_identities(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Identities JSON",
            str(self.face_identities_path.parent if self.face_identities_path else ""),
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            self.load_identities(file_path)
            self.set_session_status(f"Loaded identities JSON: {Path(file_path).name}")

    def open_transcript(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Transcript JSON",
            str(self.transcript_json_path.parent if self.transcript_json_path else ""),
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            self.load_transcript(file_path)
            self.set_session_status(f"Loaded transcript JSON: {Path(file_path).name}")

    def extract_faces_for_current_video(self):
        if self.video_path is None:
            QMessageBox.warning(self, "No video", "Open a video first.")
            return

        suggested_json = self.video_path.with_suffix(".face_tracks.json")
        output_json_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Face JSON",
            str(suggested_json),
            "JSON Files (*.json)",
        )
        if not output_json_path:
            return

        output_json = Path(output_json_path)
        crops_dir = output_json.with_suffix("")
        model_path = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"

        QMessageBox.information(
            self,
            "Extraction started",
            "Frame-by-frame face extraction is starting. This may take a while.",
        )
        QApplication.processEvents()

        progress_dialog = QMessageBox(self)
        progress_dialog.setWindowTitle("Processing")
        progress_dialog.setText("Processing frames. Watch the terminal for progress updates.")
        progress_dialog.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress_dialog.show()
        QApplication.processEvents()

        try:
            process_video_faces(
                video_path=self.video_path,
                output_json_path=output_json,
                crops_dir=crops_dir,
                model_path=model_path,
                progress_callback=lambda done, total: print(f"Processed {done}/{total} frames", flush=True) if total and done % 50 == 0 else None,
            )
            progress_dialog.close()
            self.load_detections(str(output_json))
            QMessageBox.information(
                self,
                "Done",
                f"Saved face detections to:\n{output_json}\n\nSaved crops to:\n{crops_dir}",
            )
            self.set_session_status(f"Processed and loaded face JSON: {output_json.name}")
        except Exception as exc:
            progress_dialog.close()
            QMessageBox.critical(self, "Extraction failed", str(exc))


    def _copy_renderer_visual_settings(self, export_renderer: DetectionRenderer) -> None:
        export_renderer.show_boxes = self.renderer.show_boxes
        export_renderer.show_landmarks = self.renderer.show_landmarks
        export_renderer.show_scores = self.renderer.show_scores
        export_renderer.caption_font_point_size = self.renderer.caption_font_point_size

    def _find_ffmpeg_executable(self) -> str | None:
        candidates: list[str] = []

        for name in ("ffmpeg", "ffmpeg.exe"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

        local_candidates = [
            Path(__file__).resolve().parent / "ffmpeg.exe",
            Path(__file__).resolve().parent / "ffmpeg",
            Path.cwd() / "ffmpeg.exe",
            Path.cwd() / "ffmpeg",
        ]
        for candidate in local_candidates:
            if candidate.exists():
                candidates.append(str(candidate))

        if imageio_ffmpeg is not None:
            try:
                exe = imageio_ffmpeg.get_ffmpeg_exe()
                if exe:
                    candidates.append(str(exe))
            except Exception:
                pass

        for candidate in candidates:
            if candidate:
                return candidate
        return None

    def _run_ffmpeg_mux(self, ffmpeg_exe: str, silent_video_path: Path, source_video_path: Path, output_path: Path) -> tuple[bool, str]:
        commands = [
            [
                ffmpeg_exe,
                "-y",
                "-i",
                str(silent_video_path),
                "-i",
                str(source_video_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-shortest",
                str(output_path),
            ],
            [
                ffmpeg_exe,
                "-y",
                "-i",
                str(silent_video_path),
                "-i",
                str(source_video_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a?",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-shortest",
                str(output_path),
            ],
        ]

        last_err = ""
        for cmd in commands:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
                return True, result.stderr
            last_err = result.stderr
            if output_path.exists():
                try:
                    output_path.unlink()
                except Exception:
                    pass

        return False, last_err

    def _mux_original_audio(self, silent_video_path: Path, output_path: Path) -> tuple[bool, str]:
        if self.video_path is None:
            return False, "No source video loaded."

        ffmpeg_exe = self._find_ffmpeg_executable()
        if ffmpeg_exe is None:
            return False, "ffmpeg executable not found. Install ffmpeg or place ffmpeg.exe next to player_window.py."

        return self._run_ffmpeg_mux(ffmpeg_exe, silent_video_path, self.video_path, output_path)

    def export_captioned_video(self):
        if self.video_path is None:
            QMessageBox.warning(self, "No video", "Open a video first.")
            return

        suggested_output = self.video_path.with_name(self.video_path.stem + "_captioned.mp4")
        output_path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Export Captioned MP4",
            str(suggested_output),
            "MP4 Video (*.mp4)",
        )
        if not output_path_str:
            return

        output_path = Path(output_path_str)
        if output_path.suffix.lower() != ".mp4":
            output_path = output_path.with_suffix(".mp4")

        cap = cv2.VideoCapture(str(self.video_path))
        if not cap.isOpened():
            QMessageBox.critical(self, "Export failed", f"Could not open video:\n{self.video_path}")
            return

        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)

        if fps <= 0 or width <= 0 or height <= 0:
            cap.release()
            QMessageBox.critical(self, "Export failed", "Could not read video metadata.")
            return

        progress = QProgressDialog("Exporting captioned video...", "Cancel", 0, max(1, frame_count), self)
        progress.setWindowTitle("Exporting")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        QApplication.processEvents()

        with tempfile.TemporaryDirectory(prefix="ic2_export_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            silent_video_path = temp_dir_path / "captioned_silent.mp4"

            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(silent_video_path), fourcc, fps, (width, height))
            if not writer.isOpened():
                cap.release()
                progress.close()
                QMessageBox.critical(self, "Export failed", "Could not create output video writer.")
                return

            export_scene = QGraphicsScene()
            export_scene.setSceneRect(0, 0, width, height)
            background_item = QGraphicsPixmapItem()
            background_item.setZValue(0)
            export_scene.addItem(background_item)

            export_renderer = DetectionRenderer(export_scene)
            export_renderer.set_identity_store(self.identity_store)
            self._copy_renderer_visual_settings(export_renderer)

            frame_index = 0
            canceled = False

            while True:
                ok, frame_bgr = cap.read()
                if not ok:
                    break

                current_time = frame_index / fps
                faces = self.face_store.get_faces(current_time)
                captions = self.transcript_store.get_active_entries(current_time) if self.transcript_store.is_loaded() else []

                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                qimage = QImage(
                    frame_rgb.data,
                    width,
                    height,
                    frame_rgb.strides[0],
                    QImage.Format.Format_RGB888,
                ).copy()
                background_item.setPixmap(QPixmap.fromImage(qimage))

                export_renderer.render_faces(faces, captions, current_time=current_time)

                canvas = QImage(width, height, QImage.Format.Format_ARGB32)
                canvas.fill(Qt.black)
                painter = QPainter(canvas)
                export_scene.render(painter)
                painter.end()

                ptr = canvas.bits()
                frame_bgra = np.frombuffer(ptr, np.uint8).reshape((height, width, 4))
                frame_out = cv2.cvtColor(frame_bgra, cv2.COLOR_BGRA2BGR)
                writer.write(frame_out)

                frame_index += 1
                progress.setValue(frame_index)
                if frame_index % 10 == 0:
                    QApplication.processEvents()
                    if progress.wasCanceled():
                        canceled = True
                        break

            writer.release()
            cap.release()
            progress.close()

            if canceled:
                QMessageBox.information(self, "Export canceled", "Video export was canceled.")
                return

            if output_path.exists():
                output_path.unlink()

            muxed, mux_message = self._mux_original_audio(silent_video_path, output_path)
            if not muxed:
                shutil.copy2(silent_video_path, output_path)

        self.set_session_status(f"Exported captioned video: {output_path.name}")
        if muxed:
            QMessageBox.information(
                self,
                "Export complete",
                f"Saved captioned video with audio to:\n{output_path}\n\n"
                "Font size setting: detection_renderer.py -> self.caption_font_point_size",
            )
        else:
            QMessageBox.warning(
                self,
                "Export complete (silent video)",
                f"Saved captioned video to:\n{output_path}\n\n"
                "Audio could not be muxed, so the export is silent.\n\n"
                f"Reason:\n{mux_message}\n\n"
                "Install ffmpeg or place ffmpeg.exe next to player_window.py, then export again.\n\n"
                "Font size setting: detection_renderer.py -> self.caption_font_point_size",
            )

    def toggle_boxes(self):
        self.renderer.show_boxes = not self.renderer.show_boxes
        self.toggle_boxes_button.setText("Hide Boxes" if self.renderer.show_boxes else "Show Boxes")
        self.update_overlay()

    def toggle_landmarks(self):
        self.renderer.show_landmarks = not self.renderer.show_landmarks
        self.toggle_landmarks_button.setText("Hide Landmarks" if self.renderer.show_landmarks else "Show Landmarks")
        self.update_overlay()

    def toggle_scores(self):
        self.renderer.show_scores = not self.renderer.show_scores
        self.toggle_scores_button.setText("Hide Labels" if self.renderer.show_scores else "Show Labels")
        self.update_overlay()

    def toggle_play_pause(self):
        if self.player.source().isEmpty():
            return
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def on_slider_pressed(self):
        self.is_user_scrubbing = True

    def on_slider_moved(self, value: int):
        self.time_label.setText(f"{self.format_time(value)} / {self.format_time(self.duration_ms)}")
        self.update_runtime_info(position_override=value)

    def on_slider_released(self):
        self.is_user_scrubbing = False
        self.player.setPosition(self.seek_slider.value())
        self.renderer.reset_caption_tracking()
        self.update_overlay()

    def on_position_changed(self, position: int):
        if not self.is_user_scrubbing:
            self.seek_slider.setValue(position)
        self.time_label.setText(f"{self.format_time(position)} / {self.format_time(self.duration_ms)}")
        self.update_runtime_info(position_override=position)

    def on_duration_changed(self, duration: int):
        self.duration_ms = duration
        self.seek_slider.setRange(0, duration)
        self.time_label.setText(f"{self.format_time(self.player.position())} / {self.format_time(duration)}")
        self.update_runtime_info()

    def on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        self.play_pause_button.setText("Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "Play")
        if state == QMediaPlayer.PlaybackState.PlayingState and not self.ui_timer.isActive():
            self.ui_timer.start()
        self.update_runtime_info()

    def on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            video_size = self.video_item.nativeSize()
            if video_size.width() > 0 and video_size.height() > 0:
                self.scene.setSceneRect(0, 0, video_size.width(), video_size.height())
                self.video_item.setSize(video_size)
                self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.update_runtime_info()

    def on_player_error(self, error, error_string: str):
        if error_string:
            self.set_session_status(f"Player error: {error_string}")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.scene.sceneRect().isEmpty():
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def update_overlay(self):
        current_time = self.player.position() / 1000.0
        faces = self.face_store.get_faces(current_time)
        captions = self.transcript_store.get_active_entries(current_time) if self.transcript_store.is_loaded() else []
        self.renderer.render_faces(faces, captions, current_time=current_time)
        self.update_runtime_info()

    def update_loaded_file_labels(self) -> None:
        self._set_path_label(self.video_value_label, self.video_path, "No video loaded")
        self._set_path_label(self.detections_value_label, self.face_json_path, "No face JSON loaded")
        self._set_path_label(self.identities_value_label, self.face_identities_path, "No identities JSON loaded")
        self._set_path_label(self.transcript_value_label, self.transcript_json_path, "No transcript JSON loaded")

    def _set_path_label(self, label: QLabel, path: Path | None, empty_text: str) -> None:
        if path is None:
            label.setText(empty_text)
            label.setToolTip("")
            return
        label.setText(path.name)
        label.setToolTip(str(path.resolve()))

    def update_runtime_info(self, position_override: int | None = None) -> None:
        position_ms = self.player.position() if position_override is None else position_override
        playback_state = self.player.playbackState()
        if playback_state == QMediaPlayer.PlaybackState.PlayingState:
            state_text = "Playing"
        elif playback_state == QMediaPlayer.PlaybackState.PausedState:
            state_text = "Paused"
        else:
            state_text = "Stopped"
        self.playback_state_value_label.setText(state_text)

        current_time_seconds = position_ms / 1000.0
        faces = self.face_store.get_faces(current_time_seconds)
        captions = self.transcript_store.get_active_entries(current_time_seconds) if self.transcript_store.is_loaded() else []
        frame = self.face_store.get_frame(current_time_seconds)

        current_frame_text = str(frame.get("frame_index", "-")) if frame is not None else "-"
        sample_value = self.face_store.metadata.get("sample_every_n_frames")
        self.visible_faces_value_label.setText(str(len(faces)))
        self.active_captions_value_label.setText(str(len(captions)))
        self.current_frame_value_label.setText(current_frame_text)
        self.sample_step_value_label.setText(str(sample_value) if sample_value is not None else "-")

        scene_rect = self.scene.sceneRect()
        self.scene_size_value_label.setText(f"{int(scene_rect.width())} × {int(scene_rect.height())}")

    def update_window_title(self):
        video_name = self.video_path.name if self.video_path else "No Video"
        detections_name = self.face_json_path.name if self.face_json_path else "No Face JSON"
        identities_name = self.face_identities_path.name if self.face_identities_path else "No Identities JSON"
        transcript_name = self.transcript_json_path.name if self.transcript_json_path else "No Transcript JSON"
        self.setWindowTitle(
            f"Immersive Captions 2 — {video_name} — {detections_name} — {identities_name} — {transcript_name}"
        )


def main():
    app = QApplication(sys.argv)
    app.setOrganizationName("OpenAI")
    app.setApplicationName("ImmersiveCaptions2")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
