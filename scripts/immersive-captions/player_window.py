from pathlib import Path
import sys

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QAction, QKeySequence, QShortcut
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
    QPushButton,
    QSizePolicy,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from caption_model import CaptionModel
from caption_renderer import CaptionRenderer


class ClickableSlider(QSlider):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            value = self.pixelPosToRangeValue(int(event.position().x()))
            self.setValue(value)
            self.sliderMoved.emit(value)
            self.sliderReleased.emit()
            event.accept()
            return
        super().mousePressEvent(event)

    def pixelPosToRangeValue(self, pos: int) -> int:
        if self.orientation() == Qt.Orientation.Horizontal:
            span = self.width()
        else:
            span = self.height()

        if span <= 0:
            return self.minimum()

        ratio = max(0.0, min(1.0, pos / span))
        return int(self.minimum() + ratio * (self.maximum() - self.minimum()))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Immersive Captions Player")
        self.resize(1280, 820)

        self.video_path: Path | None = None
        self.caption_path: Path | None = None

        self.caption_model: CaptionModel | None = None
        self.caption_renderer: CaptionRenderer | None = None

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
        self.view.setRenderHints(self.view.renderHints())
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.open_video_button = QPushButton("Open Video")
        self.open_caption_button = QPushButton("Open Caption")
        self.play_pause_button = QPushButton("Play")

        self.time_label = QLabel("00:00 / 00:00")

        self.seek_slider = ClickableSlider(Qt.Orientation.Horizontal)
        self.seek_slider.setRange(0, 0)

        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.open_video_button)
        controls_layout.addWidget(self.open_caption_button)
        controls_layout.addWidget(self.play_pause_button)
        controls_layout.addWidget(self.time_label)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.view, stretch=1)
        main_layout.addWidget(self.seek_slider)
        main_layout.addLayout(controls_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.caption_renderer = CaptionRenderer(self.scene, None)

        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(16)

        self.open_video_button.clicked.connect(self.open_video)
        self.open_caption_button.clicked.connect(self.open_caption)
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

        if self.caption_renderer is not None:
            self.caption_renderer.clear()

        self.scene.setSceneRect(0, 0, 1280, 720)
        self.video_item.setSize(self.scene.sceneRect().size())

    def load_video(self, file_path: str):
        self.video_path = Path(file_path)
        self.reset_player_state()

        self.player.setSource(QUrl.fromLocalFile(str(self.video_path)))
        self.player.pause()

        self.update_window_title()
        self.ui_timer.start()

    def load_caption(self, file_path: str):
        self.caption_path = Path(file_path)

        self.caption_model = CaptionModel(self.caption_path)

        if self.caption_renderer is None:
            self.caption_renderer = CaptionRenderer(self.scene, self.caption_model)
        else:
            self.caption_renderer.clear()
            self.caption_renderer.caption_model = self.caption_model

        self.update_overlay()
        self.update_window_title()

    def open_video(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video Files (*.mp4 *.mov *.mkv *.avi *.webm);;All Files (*)",
        )
        if not file_path:
            return

        self.load_video(file_path)

    def open_caption(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Caption JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not file_path:
            return

        self.load_caption(file_path)

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
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_button.setText("Pause")
            if not self.ui_timer.isActive():
                self.ui_timer.start()
        else:
            self.play_pause_button.setText("Play")

    def on_media_status_changed(self, status: QMediaPlayer.MediaStatus):
        if status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        ):
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
        if self.caption_renderer is None:
            return

        time_seconds = self.player.position() / 1000.0
        self.caption_renderer.render(time_seconds)

    def update_window_title(self):
        video_name = self.video_path.name if self.video_path else "No Video"
        caption_name = self.caption_path.name if self.caption_path else "No Caption"
        self.setWindowTitle(f"Immersive Captions Player — {video_name} — {caption_name}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()