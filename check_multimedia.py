try:
    from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
    print("QMediaPlayer OK")
except ImportError as e:
    print(f"QMediaPlayer Fail: {e}")

try:
    from PySide6.QtMultimediaWidgets import QVideoWidget
    print("QVideoWidget OK")
except ImportError as e:
    print(f"QVideoWidget Fail: {e}")
