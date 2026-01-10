import os
import json
import uuid
import time
from datetime import datetime

CONVERSATIONS_DIR = "conversations"

def ensure_conversations_dir():
    if not os.path.exists(CONVERSATIONS_DIR):
        os.makedirs(CONVERSATIONS_DIR)

def create_conversation(title=None):
    ensure_conversations_dir()
    convo_id = str(uuid.uuid4())
    convo_dir = os.path.join(CONVERSATIONS_DIR, convo_id)
    os.makedirs(convo_dir)
    os.makedirs(os.path.join(convo_dir, "images"))
    
    metadata = {
        "id": convo_id,
        "title": title or "New Conversation",
        "created_at": datetime.now().isoformat(),
        "total_cost": 0.0,
        "history": []
    }
    
    with open(os.path.join(convo_dir, "history.json"), "w") as f:
        json.dump(metadata, f, indent=4)
        
    return convo_id

def save_message(convo_id, role, text, image_path=None, cost=0.0):
    convo_dir = os.path.join(CONVERSATIONS_DIR, convo_id)
    history_file = os.path.join(convo_dir, "history.json")
    
    if not os.path.exists(history_file):
        print(f"Error: Conversation {convo_id} not found.")
        return

    with open(history_file, "r") as f:
        metadata = json.load(f)
    
    message = {
        "role": role,
        "text": text,
        "timestamp": datetime.now().isoformat(),
        "image": image_path,
        "cost": cost
    }
    
    metadata["history"].append(message)
    metadata["total_cost"] = metadata.get("total_cost", 0.0) + cost
    # Update title if it's the first user message and title is default
    if role == "user" and len(metadata["history"]) == 1 and metadata["title"] == "New Conversation":
        metadata["title"] = text[:30] + "..." if len(text) > 30 else text

    with open(history_file, "w") as f:
        json.dump(metadata, f, indent=4)

def load_conversations():
    ensure_conversations_dir()
    conversations = []
    for name in os.listdir(CONVERSATIONS_DIR):
        path = os.path.join(CONVERSATIONS_DIR, name)
        if os.path.isdir(path):
            history_file = os.path.join(path, "history.json")
            if os.path.exists(history_file):
                try:
                    with open(history_file, "r") as f:
                        meta = json.load(f)
                        conversations.append(meta)
                except json.JSONDecodeError:
                    pass
    
    # Sort by created_at desc
    conversations.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    return conversations

def load_history(convo_id):
    history_file = os.path.join(CONVERSATIONS_DIR, convo_id, "history.json")
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            return json.load(f)
    return None

def get_image_save_path(convo_id, extension=".png"):
    timestamp = int(time.time() * 1000)
    filename = f"{timestamp}{extension}"
    return os.path.join(CONVERSATIONS_DIR, convo_id, "images", filename)

def get_conversation_dir(convo_id):
    return os.path.join(CONVERSATIONS_DIR, convo_id)
