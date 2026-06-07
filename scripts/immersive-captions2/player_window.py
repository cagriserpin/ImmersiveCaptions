from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from detection_renderer import DetectionRenderer
from detection_store import FaceDetectionStore
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
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Immersive Captions 2 — Phase 1")
        self.resize(1280, 820)

        self.video_path: Path | None = None
        self.face_json_path: Path | None = None

        self.face_store = FaceDetectionStore()
        self.renderer: DetectionRenderer | None = None

        self.is_user_scrubbing = False
        self.duration_ms = 0

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

        self.open_video_button = QPushButton("Open Video")
        self.open_detections_button = QPushButton("Open Face JSON")
        self.extract_faces_button = QPushButton("Extract Faces")
        self.toggle_boxes_button = QPushButton("Hide Boxes")
        self.toggle_landmarks_button = QPushButton("Hide Landmarks")
        self.toggle_scores_button = QPushButton("Hide Labels")
        self.play_pause_button = QPushButton("Play")
        self.time_label = QLabel("00:00 / 00:00")

        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.open_video_button)
        controls_layout.addWidget(self.open_detections_button)
        controls_layout.addWidget(self.extract_faces_button)
        controls_layout.addWidget(self.toggle_boxes_button)
        controls_layout.addWidget(self.toggle_landmarks_button)
        controls_layout.addWidget(self.toggle_scores_button)
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.time_label)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.view, stretch=1)
        main_layout.addWidget(self.seek_slider)
        main_layout.addLayout(controls_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.renderer = DetectionRenderer(self.scene)

        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(33)

        self.open_video_button.clicked.connect(self.open_video)
        self.open_detections_button.clicked.connect(self.open_detections)
        self.extract_faces_button.clicked.connect(self.extract_faces_for_current_video)
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

    def format_time(self, ms: int) -> str:
        total_seconds = max(0, ms // 1000)
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        return f"{minutes:02d}:{seconds:02d}"

    def reset_player_state(self):
        self.player.pause()
        self.player.setSource(QUrl())

        self.duration_ms = 0
        self.seek_slider.setRange(0, 0)
        self.seek_slider.setValue(0)
        self.time_label.setText("00:00 / 00:00")
        self.play_pause_button.setText("Play")
        self.is_user_scrubbing = False

        if self.renderer is not None:
            self.renderer.clear()

        self.scene.setSceneRect(0, 0, 1280, 720)
        self.video_item.setSize(self.scene.sceneRect().size())

    def load_video(self, file_path: str):
        self.video_path = Path(file_path)
        self.reset_player_state()
        self.player.setSource(QUrl.fromLocalFile(str(self.video_path)))
        self.player.pause()
        self.update_window_title()
        self.ui_timer.start()

    def load_detections(self, file_path: str):
        self.face_json_path = Path(file_path)
        self.face_store.load(self.face_json_path)
        self.update_overlay()
        self.update_window_title()

    def open_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)",
        )
        if file_path:
            self.load_video(file_path)

    def open_detections(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Face JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if file_path:
            self.load_detections(file_path)

    def extract_faces_for_current_video(self):
        if self.video_path is None:
            QMessageBox.warning(self, "No video", "Open a video first.")
            return

        suggested_json = self.video_path.with_suffix(".faces_raw.json")
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
        except Exception as exc:
            progress_dialog.close()
            QMessageBox.critical(self, "Extraction failed", str(exc))

    def toggle_boxes(self):
        if self.renderer is None:
            return
        self.renderer.show_boxes = not self.renderer.show_boxes
        self.toggle_boxes_button.setText("Hide Boxes" if self.renderer.show_boxes else "Show Boxes")
        self.update_overlay()

    def toggle_landmarks(self):
        if self.renderer is None:
            return
        self.renderer.show_landmarks = not self.renderer.show_landmarks
        self.toggle_landmarks_button.setText("Hide Landmarks" if self.renderer.show_landmarks else "Show Landmarks")
        self.update_overlay()

    def toggle_scores(self):
        if self.renderer is None:
            return
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

    def on_slider_released(self):
        self.is_user_scrubbing = False
        self.player.setPosition(self.seek_slider.value())
        self.update_overlay()

    def on_position_changed(self, position: int):
        if not self.is_user_scrubbing:
            self.seek_slider.setValue(position)
        self.time_label.setText(f"{self.format_time(position)} / {self.format_time(self.duration_ms)}")

    def on_duration_changed(self, duration: int):
        self.duration_ms = duration
        self.seek_slider.setRange(0, duration)
        self.time_label.setText(f"{self.format_time(self.player.position())} / {self.format_time(duration)}")

    def on_playback_state_changed(self, state: QMediaPlayer.PlaybackState):
        self.play_pause_button.setText("Pause" if state == QMediaPlayer.PlaybackState.PlayingState else "Play")
        if state == QMediaPlayer.PlaybackState.PlayingState and not self.ui_timer.isActive():
            self.ui_timer.start()

    def on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        if status in (QMediaPlayer.MediaStatus.LoadedMedia, QMediaPlayer.MediaStatus.BufferedMedia):
            video_size = self.video_item.nativeSize()
            if video_size.width() > 0 and video_size.height() > 0:
                self.scene.setSceneRect(0, 0, video_size.width(), video_size.height())
                self.video_item.setSize(video_size)
                self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def on_player_error(self, error, error_string: str):
        if error_string:
            print("Player error:", error_string)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.scene.sceneRect().isEmpty():
            self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def update_overlay(self):
        if self.renderer is None:
            return
        faces = self.face_store.get_faces(self.player.position() / 1000.0)
        self.renderer.render_faces(faces)

    def update_window_title(self):
        video_name = self.video_path.name if self.video_path else "No Video"
        detections_name = self.face_json_path.name if self.face_json_path else "No Face JSON"
        self.setWindowTitle(f"Immersive Captions 2 — Phase 1 — {video_name} — {detections_name}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
