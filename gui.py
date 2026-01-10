import sys
import os
import time
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QListWidget, QListWidgetItem, QTextEdit, QLabel, QPushButton, 
    QSplitter, QInputDialog, QMessageBox, QScrollArea, QFrame, QDialog, QLineEdit, QDialogButtonBox, QFormLayout, QGroupBox, QFileDialog, QComboBox, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QObject, QSize, QUrl
from PySide6.QtGui import QPixmap, QImage, QIcon
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PIL import Image
import generate_images
import storage

# --- Cost Settings ---
COST_PER_IMAGE = 0.04 # Approximate cost for Imagen 3 standard

class WorkerSignals(QObject):
    finished = Signal(object, str) # result (PIL Image or None), message
    error = Signal(str)

class VideoPlayer(QWidget):
    def __init__(self, video_path, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 340)
        # self.setMaximumSize(512, 512)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        
        self.video_widget = QVideoWidget()
        layout.addWidget(self.video_widget)
        
        self.audio_output = QAudioOutput()
        self.player = QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)
        self.player.setVideoOutput(self.video_widget)
        self.player.setSource(QUrl.fromLocalFile(os.path.abspath(video_path)))
        self.audio_output.setVolume(1.0) 
        
        # Controls
        controls_layout = QHBoxLayout()
        self.play_btn = QPushButton("Play")
        self.play_btn.clicked.connect(self.toggle_playback)
        controls_layout.addWidget(self.play_btn)
        
        layout.addLayout(controls_layout)
        
    def toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            self.play_btn.setText("Play")
        else:
            self.player.play()
            self.play_btn.setText("Pause")

class GenerationWorker(threading.Thread):
    def __init__(self, prompt, output_path, base_images=None, video_mode=None, signals=None):
        super().__init__()
        self.prompt = prompt
        self.output_path = output_path
        self.base_images = base_images or []
        self.video_mode = video_mode # None for image, or 'text_to_video', 'bring_to_life', 'reference'
        self.signals = signals

    def run(self):
        try:
            # Check for API KEY
            if not generate_images.client:
                self.signals.error.emit("API Key not configured. Please set it in Settings.")
                return

            result = None
            if self.video_mode:
                result = generate_images.generate_video_content(self.prompt, self.output_path, self.base_images, self.video_mode)
            else:
                result = generate_images.generate_image_content(self.prompt, self.output_path, self.base_images)

            if result:
                self.signals.finished.emit(result, "Success")
            else:
                self.signals.error.emit("Generation failed (no output returned).")
        except Exception as e:
            self.signals.error.emit(str(e))

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.resize(400, 150)
        
        layout = QFormLayout(self)
        
        self.api_key_input = QLineEdit()
        current_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or ""
        self.api_key_input.setText(current_key)
        self.api_key_input.setEchoMode(QLineEdit.Password)
        
        layout.addRow("Google/Gemini API Key:", self.api_key_input)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_api_key(self):
        return self.api_key_input.text()

class ChatMessage(QFrame):
    def __init__(self, role, text, image_path=None, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.StyledPanel)
        self.layout = QVBoxLayout(self)
        
        # Role Label
        role_label = QLabel(f"<b>{role.capitalize()}</b>")
        self.layout.addWidget(role_label)
        
        # Text
        if text:
            text_label = QLabel(text)
            text_label.setWordWrap(True)
            self.layout.addWidget(text_label)
        
        # Image or Video
        if image_path and os.path.exists(image_path):
            if image_path.endswith('.mp4'):
                # Video Player
                try:
                    player = VideoPlayer(image_path)
                    self.layout.addWidget(player)
                except Exception as e:
                    self.layout.addWidget(QLabel(f"Error loading video: {e}"))
            else:
                img_label = QLabel()
                pixmap = QPixmap(image_path)
                # Scale if too large
                if pixmap.width() > 512:
                    pixmap = pixmap.scaledToWidth(512, Qt.SmoothTransformation)
                img_label.setPixmap(pixmap)
                self.layout.addWidget(img_label)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Image Generator")
        self.resize(1000, 800)
        
        self.current_convo_id = None
        self.worker = None
        # self.uploaded_base_images removed in favor of UI list source of truth

        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # --- Left Panel: Sidebar ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        
        # Buttons
        new_chat_btn = QPushButton("New Conversation")
        new_chat_btn.clicked.connect(self.start_new_conversation)
        left_layout.addWidget(new_chat_btn)
        
        settings_btn = QPushButton("Settings")
        settings_btn.clicked.connect(self.open_settings)
        left_layout.addWidget(settings_btn)

        # Conversation List
        self.convo_list = QListWidget()
        self.convo_list.itemClicked.connect(self.load_conversation)
        left_layout.addWidget(self.convo_list)
        
        splitter.addWidget(left_panel)
        
        # --- Right Panel: Chat Area ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Chat History Scroll Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.chat_widget = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_widget)
        self.chat_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.chat_widget)
        right_layout.addWidget(self.scroll_area)
        
        # Cost Display
        self.cost_label = QLabel("Cost: $0.00")
        self.cost_label.setAlignment(Qt.AlignRight)
        right_layout.addWidget(self.cost_label)

        # Input Area (Reorganized)
        input_container = QGroupBox("Input")
        input_layout = QVBoxLayout(input_container)
        
        # Mode Selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Type:"))
        self.type_combo = QComboBox()
        self.type_combo.addItems(["Image", "Video"])
        self.type_combo.currentIndexChanged.connect(self.update_ui_state)
        mode_layout.addWidget(self.type_combo)
        
        mode_layout.addWidget(QLabel("Video Mode:"))
        self.video_mode_combo = QComboBox()
        self.video_mode_combo.addItems(["Text-to-Video", "Bring to Life", "Reference"])
        self.video_mode_combo.setEnabled(False) # Default to Image mode
        self.video_mode_combo.currentIndexChanged.connect(self.update_ui_state)
        mode_layout.addWidget(self.video_mode_combo)
        
        mode_layout.addStretch()
        input_layout.addLayout(mode_layout)
        
        # Text Input
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Enter image prompt here...")
        self.prompt_input.setMinimumHeight(80)
        self.prompt_input.setMaximumHeight(120)
        input_layout.addWidget(self.prompt_input)
        
        # Controls Row
        controls_layout = QHBoxLayout()
        
        self.use_base_checkbox = QPushButton("Use Last Image as Base") 
        self.use_base_checkbox.setCheckable(True)
        self.use_base_checkbox.setToolTip("Use the last generated image as a visual reference for the new one.")
        controls_layout.addWidget(self.use_base_checkbox)
        
        self.upload_base_btn = QPushButton("Upload Base Image")
        self.upload_base_btn.setToolTip("Upload an image file to use as base for generation/editing.")
        self.upload_base_btn.clicked.connect(self.upload_base_image)
        controls_layout.addWidget(self.upload_base_btn)
        
        self.remove_base_btn = QPushButton("Remove Selected")
        self.remove_base_btn.setToolTip("Remove selected images from the reference list.")
        self.remove_base_btn.clicked.connect(self.remove_base_image)
        controls_layout.addWidget(self.remove_base_btn)
        
        self.base_image_list = QListWidget()
        self.base_image_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.base_image_list.setIconSize(QSize(64, 64))
        self.base_image_list.setFixedHeight(100) # Give it some height
        self.base_image_list.setViewMode(QListWidget.IconMode)
        self.base_image_list.setResizeMode(QListWidget.Adjust)
        self.base_image_list.setSpacing(5)
        # We put the list *above* the controls row or *in* the controls row?
        # The design plan said replace the label. 
        # Putting a list widget inside a horizontal layout with buttons might be cramped.
        # Let's add it to input_layout *before* the controls row, or make a new row.
        
        controls_layout.addStretch()
        
        self.gen_btn = QPushButton("Generate Image")
        self.gen_btn.setMinimumHeight(40)
        self.gen_btn.setMinimumWidth(120)
        self.gen_btn.setStyleSheet("font-weight: bold;")
        self.gen_btn.clicked.connect(self.generate_image)
        controls_layout.addWidget(self.gen_btn)
        
        input_layout.addWidget(self.base_image_list) # Add list above buttons
        input_layout.addLayout(controls_layout)
        
        right_layout.addWidget(input_container)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([200, 800])
        
        # Initialize
        self.refresh_conversation_list()
        
        # Try to select first convo
        if self.convo_list.count() > 0:
            self.convo_list.setCurrentRow(0)
            self.load_conversation(self.convo_list.item(0))
        else:
            self.start_new_conversation()

    def update_ui_state(self):
        is_video = self.type_combo.currentText() == "Video"
        self.video_mode_combo.setEnabled(is_video)
        
        if is_video:
            v_mode = self.video_mode_combo.currentText()
            if v_mode == "Text-to-Video":
                self.use_base_checkbox.setEnabled(False)
                self.upload_base_btn.setEnabled(False)
            else:
                self.use_base_checkbox.setEnabled(True)
                self.upload_base_btn.setEnabled(True)
        else:
            # Image Mode
            self.use_base_checkbox.setEnabled(True)
            self.upload_base_btn.setEnabled(True)

    def refresh_conversation_list(self):
        self.convo_list.clear()
        conversations = storage.load_conversations()
        for convo in conversations:
            item = QListWidgetItem(convo.get("title", "Untitled"))
            item.setData(Qt.UserRole, convo["id"])
            item.setToolTip(f"Created: {convo.get('created_at')} \nCost: ${convo.get('total_cost', 0.0):.2f}")
            self.convo_list.addItem(item)

    def start_new_conversation(self):
        self.current_convo_id = storage.create_conversation()
        self.refresh_conversation_list()
        # Find and select the new item
        for i in range(self.convo_list.count()):
            item = self.convo_list.item(i)
            if item.data(Qt.UserRole) == self.current_convo_id:
                self.convo_list.setCurrentItem(item)
                self.load_conversation(item)
                break

    def load_conversation(self, item):
        convo_id = item.data(Qt.UserRole)
        self.current_convo_id = convo_id
        
        # Clear chat area
        for i in reversed(range(self.chat_layout.count())): 
            self.chat_layout.itemAt(i).widget().setParent(None)
            
        data = storage.load_history(convo_id)
        if not data:
            return

        # Update running cost label
        total_cost = data.get("total_cost", 0.0)
        self.cost_label.setText(f"Total Cost: ${total_cost:.2f}")

        for msg in data.get("history", []):
            self.add_message_to_ui(msg["role"], msg.get("text"), msg.get("image"))

    def add_message_to_ui(self, role, text, image_path=None):
        msg_widget = ChatMessage(role, text, image_path)
        self.chat_layout.addWidget(msg_widget)
        # Scroll to bottom
        QApplication.processEvents()
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def upload_base_image(self):
        # Allow multiple selection
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Select Base Images", "", "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)")
        if file_paths:
            for file_path in file_paths:
                try:
                    # Verify we can open it
                    img = Image.open(file_path)
                    # Create Item
                    item = QListWidgetItem(os.path.basename(file_path))
                    item.setData(Qt.UserRole, file_path)
                    item.setToolTip(file_path)
                    
                    # Create Thumbnail
                    pixmap = QPixmap(file_path)
                    if not pixmap.isNull():
                         pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                         item.setIcon(QIcon(pixmap))
                    
                    self.base_image_list.addItem(item)
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to load {file_path}: {e}")

    def remove_base_image(self):
        selected_items = self.base_image_list.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            # remove from list
            row = self.base_image_list.row(item)
            self.base_image_list.takeItem(row)

    def generate_image(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            return

        is_video = self.type_combo.currentText() == "Video"
        video_mode_ui = self.video_mode_combo.currentText()
        
        video_mode_key = None
        if is_video:
            if video_mode_ui == "Text-to-Video": video_mode_key = 'text_to_video'
            elif video_mode_ui == "Bring to Life": video_mode_key = 'bring_to_life'
            elif video_mode_ui == "Reference": video_mode_key = 'reference'

        self.gen_btn.setEnabled(False)
        self.prompt_input.setDisabled(True)
        self.use_base_checkbox.setDisabled(True)
        self.upload_base_btn.setDisabled(True)
        self.remove_base_btn.setDisabled(True)
        self.base_image_list.setDisabled(True)
        # UI state for buttons handled by update_ui_state generally, but disable during gen
        
        # Save User Message
        storage.save_message(self.current_convo_id, "user", prompt)
        self.add_message_to_ui("user", prompt)
        
        # Determine output path
        if is_video:
             # Basic timestamp filename for video
             output_path = os.path.join(storage.get_conversation_dir(self.current_convo_id), f"vid_{int(time.time())}.mp4")
        else:
             output_path = storage.get_image_save_path(self.current_convo_id)
        
        # Determine base images from ListWidget
        base_images = []
        
        # 1. From List Widget
        for i in range(self.base_image_list.count()):
            item = self.base_image_list.item(i)
            file_path = item.data(Qt.UserRole)
            try:
                img = Image.open(file_path)
                base_images.append(img)
            except Exception as e:
                print(f"Failed to load base image {file_path}: {e}")

        # 2. Logic for "Use Last Image" (Append to list if checked)
        if self.use_base_checkbox.isChecked() and self.use_base_checkbox.isEnabled():
             data = storage.load_history(self.current_convo_id)
             if data and "history" in data:
                 for msg in reversed(data["history"]):
                     if msg.get("image") and msg["image"].endswith(('.png', '.jpg', '.jpeg')):
                         try:
                             base_images.append(Image.open(msg["image"]))
                             # Note: This doesn't add it to the visual list, just for this generation.
                             # If we wanted to be explicit, we could add it to the list, but "use last" feels ephemeral.
                             # Keeping it ephemeral for now as per previous logic.
                             break
                         except:
                             pass
        
        # Worker Setup
        self.signals = WorkerSignals()
        self.signals.finished.connect(self.on_generation_finished)
        self.signals.error.connect(self.on_generation_error)
        
        self.worker = GenerationWorker(prompt, output_path, base_images, video_mode_key, self.signals)
        self.worker.start()

    def on_generation_finished(self, output_path, message):
        # output_path comes from worker (image_obj or path)
        # If it's a string path, assume it's saved.
        # If it's an image object (legacy code returned result as PIL image sometimes? No, generate_image_content returned path in previous code? 
        # Wait, previous generate_image_content returned image object OR None. 
        # I changed generate_video_content to return path.
        # I should check generate_images.generate_image_content behavior. 
        # It returns saved_img (PIL Image).
        # So I need to handle both.
        
        is_video = isinstance(output_path, str) and output_path.endswith(".mp4")
        
        if is_video:
            msg_text = "Video Generated"
            cost = COST_PER_IMAGE * 10
            # output_path is the path
        else:
             # Logic for image object
             # The old code was: 
             # self.worker.output_path was used. 
             # generate_image_content returned result (PIL Image) if success.
             # But on_generation_finished(self, image_obj, message).
             # It ignored image_obj and used self.worker.output_path for saving message.
             # So I can just use self.worker.output_path.
             
             msg_text = "Image Generated"
             cost = COST_PER_IMAGE
        
        saved_path = self.worker.output_path
        
        # Save Assistant Message with Image/Video
        storage.save_message(self.current_convo_id, "assistant", msg_text, saved_path, cost=cost)
        self.add_message_to_ui("assistant", msg_text, saved_path)
        
        # Update cost
        data = storage.load_history(self.current_convo_id)
        total_cost = data.get("total_cost", 0.0)
        self.cost_label.setText(f"Total Cost: ${total_cost:.2f}")

        self.gen_btn.setEnabled(True)
        self.prompt_input.setDisabled(False)
        self.use_base_checkbox.setDisabled(False)
        self.upload_base_btn.setDisabled(False)
        self.remove_base_btn.setDisabled(False)
        self.base_image_list.setDisabled(False)
        self.refresh_conversation_list() # To update tooltip costs

    def on_generation_error(self, error_msg):
        QMessageBox.critical(self, "Error", error_msg)
        storage.save_message(self.current_convo_id, "assistant", f"Error: {error_msg}")
        self.add_message_to_ui("assistant", f"Error: {error_msg}")
        
        self.gen_btn.setEnabled(True)
        self.prompt_input.setDisabled(False)
        self.use_base_checkbox.setDisabled(False)
        self.upload_base_btn.setDisabled(False)
        self.remove_base_btn.setDisabled(False)
        self.base_image_list.setDisabled(False)

    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_():
            new_key = dialog.get_api_key()
            # Update .env
            try:
                env_path = os.path.join(os.getcwd(), ".env")
                lines = []
                if os.path.exists(env_path):
                    with open(env_path, "r") as f:
                        lines = f.readlines()
                
                key_found = False
                for i, line in enumerate(lines):
                    if line.startswith("GOOGLE_API_KEY=") or line.startswith("GEMINI_API_KEY="):
                        lines[i] = f"GOOGLE_API_KEY={new_key}\n"
                        key_found = True
                        break
                
                if not key_found:
                    lines.append(f"\nGOOGLE_API_KEY={new_key}\n")
                
                with open(env_path, "w") as f:
                    f.writelines(lines)
                
                # Reload module (hacky but works for simple case) or just re-init client
                os.environ["GOOGLE_API_KEY"] = new_key
                import importlib
                importlib.reload(generate_images)
                
            except Exception as e:
                QMessageBox.warning(self, "Error Saving Settings", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
