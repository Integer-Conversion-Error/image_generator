import sys
import os
import threading
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QListWidget, QListWidgetItem, QTextEdit, QLabel, QPushButton, 
    QSplitter, QInputDialog, QMessageBox, QScrollArea, QFrame, QDialog, QLineEdit, QDialogButtonBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal, QObject, QSize
from PySide6.QtGui import QPixmap, QImage, QIcon
from PIL import Image
import generate_images
import storage

# --- Cost Settings ---
COST_PER_IMAGE = 0.04 # Approximate cost for Imagen 3 standard

class WorkerSignals(QObject):
    finished = Signal(object, str) # result (PIL Image or None), message
    error = Signal(str)

class GenerationWorker(threading.Thread):
    def __init__(self, prompt, output_path, base_image=None, signals=None):
        super().__init__()
        self.prompt = prompt
        self.output_path = output_path
        self.base_image = base_image
        self.signals = signals

    def run(self):
        try:
            # Check for API KEY
            if not generate_images.client:
                self.signals.error.emit("API Key not configured. Please set it in Settings.")
                return

            result = generate_images.generate_image_content(self.prompt, self.output_path, self.base_image)
            if result:
                self.signals.finished.emit(result, "Success")
            else:
                self.signals.error.emit("Generation failed (no image returned).")
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
        
        # Image
        if image_path and os.path.exists(image_path):
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

        # Input Area
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        
        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText("Enter prompt here...")
        self.prompt_input.setMaximumHeight(100)
        input_layout.addWidget(self.prompt_input)
        
        btn_layout = QVBoxLayout()
        self.gen_btn = QPushButton("Generate")
        self.gen_btn.clicked.connect(self.generate_image)
        btn_layout.addWidget(self.gen_btn)
        
        self.clean_checkbox = QPushButton("Use Last Image as Base") # Toggle behavior
        self.clean_checkbox.setCheckable(True)
        btn_layout.addWidget(self.clean_checkbox)

        input_layout.addLayout(btn_layout)
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

    def generate_image(self):
        prompt = self.prompt_input.toPlainText().strip()
        if not prompt:
            return

        self.gen_btn.setEnabled(False)
        self.prompt_input.setDisabled(True)
        
        # Save User Message
        storage.save_message(self.current_convo_id, "user", prompt)
        self.add_message_to_ui("user", prompt)
        
        # Determine output path
        output_path = storage.get_image_save_path(self.current_convo_id)
        
        # Determine base image (if checked)
        base_image = None
        if self.clean_checkbox.isChecked():
            # Find last image in history
            data = storage.load_history(self.current_convo_id)
            if data and "history" in data:
                for msg in reversed(data["history"]):
                    if msg.get("image"):
                        try:
                            base_image = Image.open(msg["image"])
                            break
                        except:
                            pass
        
        # Clear input
        self.prompt_input.clear()
        
        # Worker Setup
        self.signals = WorkerSignals()
        self.signals.finished.connect(self.on_generation_finished)
        self.signals.error.connect(self.on_generation_error)
        
        self.worker = GenerationWorker(prompt, output_path, base_image, self.signals)
        self.worker.start()

    def on_generation_finished(self, image_obj, message):
        output_path = self.worker.output_path
        
        # Save Assistant Message with Image
        storage.save_message(self.current_convo_id, "assistant", "Image Generated", output_path, cost=COST_PER_IMAGE)
        self.add_message_to_ui("assistant", "Image Generated", output_path)
        
        # Update cost
        data = storage.load_history(self.current_convo_id)
        total_cost = data.get("total_cost", 0.0)
        self.cost_label.setText(f"Total Cost: ${total_cost:.2f}")

        self.gen_btn.setEnabled(True)
        self.prompt_input.setDisabled(False)
        self.refresh_conversation_list() # To update tooltip costs

    def on_generation_error(self, error_msg):
        QMessageBox.critical(self, "Error", error_msg)
        storage.save_message(self.current_convo_id, "assistant", f"Error: {error_msg}")
        self.add_message_to_ui("assistant", f"Error: {error_msg}")
        
        self.gen_btn.setEnabled(True)
        self.prompt_input.setDisabled(False)

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
