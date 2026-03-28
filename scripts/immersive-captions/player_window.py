from pathlib import Path

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


def ms_to_time(ms: int) -> str:
    total_seconds = max(0, ms // 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    return f"{minutes:02}:{seconds:02}"


class PlayerWindow(QMainWindow):
    def __init__(self, video_path: Path | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Immersive Captions - Stage 1")

        self.video_path = video_path

        # Media objects
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)
        self.audio_output.setVolume(0.7)

        # Video widget
        self.video_widget = QVideoWidget(self)
        self.player.setVideoOutput(self.video_widget)

        # Controls
        self.open_button = QPushButton("Open Video")
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")

        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.position_slider.setRange(0, 0)

        self.time_label = QLabel("00:00 / 00:00")
        self.status_label = QLabel("No media loaded")
        self.is_seeking = False

        # Layout
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(self.open_button)
        controls_layout.addWidget(self.play_button)
        controls_layout.addWidget(self.pause_button)

        bottom_layout = QVBoxLayout()
        bottom_layout.addLayout(controls_layout)
        bottom_layout.addWidget(self.position_slider)
        bottom_layout.addWidget(self.time_label)
        bottom_layout.addWidget(self.status_label)

        central_layout = QVBoxLayout()
        central_layout.addWidget(self.video_widget, stretch=1)
        central_layout.addLayout(bottom_layout)

        central_widget = QWidget()
        central_widget.setLayout(central_layout)
        self.setCentralWidget(central_widget)

        # Timer for UI refresh
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(100)
        self.ui_timer.timeout.connect(self.update_time_ui)
        self.ui_timer.start()

        # Signals
        self.open_button.clicked.connect(self.open_video)
        self.play_button.clicked.connect(self.player.play)
        self.pause_button.clicked.connect(self.player.pause)

        self.position_slider.sliderPressed.connect(self.on_slider_pressed)
        self.position_slider.sliderReleased.connect(self.on_slider_released)
        self.position_slider.sliderMoved.connect(self.on_slider_moved)
        self.player.positionChanged.connect(self.on_position_changed)
        self.player.durationChanged.connect(self.on_duration_changed)
        self.player.errorChanged.connect(self.on_error_changed)
        self.player.mediaStatusChanged.connect(self.on_media_status_changed)
        self.player.playbackStateChanged.connect(self.on_playback_state_changed)

        # Auto-load initial file if it exists
        if self.video_path is not None and self.video_path.exists():
            self.load_video(self.video_path)

    def open_video(self) -> None:
        file_name, _ = QFileDialog.getOpenFileName(
            self,
            "Open Video",
            "",
            "Video Files (*.mp4 *.mkv *.avi *.mov *.webm);;All Files (*)",
        )
        if file_name:
            self.load_video(Path(file_name))

    def load_video(self, path: Path) -> None:
        self.video_path = path
        self.player.setSource(QUrl.fromLocalFile(str(path.resolve())))
        self.status_label.setText(f"Loaded: {path.name}")

    def on_slider_pressed(self) -> None:
        self.is_seeking = True

    def on_slider_moved(self, value: int) -> None:
        duration = self.player.duration()
        self.time_label.setText(f"{ms_to_time(value)} / {ms_to_time(duration)}")

    def on_slider_released(self) -> None:
        value = self.position_slider.value()
        self.player.setPosition(value)
        self.is_seeking = False

    def on_position_changed(self, position: int) -> None:
        if not self.is_seeking:
            self.position_slider.setValue(position)

    def on_duration_changed(self, duration: int) -> None:
        self.position_slider.setRange(0, duration)
        self.update_time_ui()

    def on_error_changed(self) -> None:
        if self.player.error():
            self.status_label.setText(f"Error: {self.player.errorString()}")

    def on_media_status_changed(self, status) -> None:
        self.status_label.setText(f"Media status: {status}")

    def on_playback_state_changed(self, state) -> None:
        self.status_label.setText(f"Playback state: {state}")

    def update_time_ui(self) -> None:
        position = self.player.position()
        duration = self.player.duration()
        self.time_label.setText(f"{ms_to_time(position)} / {ms_to_time(duration)}")