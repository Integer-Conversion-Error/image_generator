import json
import os

TASKS_FILE = "/root/Projects/Raindrop-Web/image_generator/tasks.json"

# New tasks to add
new_tasks = [
  {
      "subdir": "",
      "clean_file": "dealership-clean.jpeg",
      "dirty_file": "dealership-dirty.jpeg",
      "clean_prompt": "Car dealership showroom, polished tiles, new cars, bright lighting.",
      "dirty_prompt": "Same dealership showroom but dirty, tire marks on floor, uncleaned. Photorealistic."
  },
  {
      "subdir": "",
      "clean_file": "office-hallway-clean.jpeg",
      "dirty_file": "office-hallway-dirty.jpeg",
      "clean_prompt": "Office hallway, clean carpet, bright lights, professional.",
      "dirty_prompt": "Same hallway but dirty, stained carpet, trash on floor. Photorealistic."
  },
  {
      "subdir": "",
      "clean_file": "industrial-clean.png",
      "dirty_file": "industrial-dirty.png",
      "clean_prompt": "Industrial facility, clean polished concrete floor, machinery.",
      "dirty_prompt": "Same industrial facility but dirty, oil spills, dust, debris. Photorealistic."
  },
  {
      "subdir": "",
      "clean_file": "post-construction-clean.png",
      "dirty_file": "post-construction-dirty.png",
      "clean_prompt": "Newly renovated room, clean, fresh paint, no dust.",
      "dirty_prompt": "Same room during construction, dry wall dust everywhere, debris, tools. Photorealistic."
  },
    {
      "subdir": "",
      "clean_file": "commercial-floor-after.jpeg", 
      "dirty_file": "commercial-floor-dirty.jpeg",
      "clean_prompt": "Commercial floor, shiny stripes, newly waxed.",
      "dirty_prompt": "Same commercial floor but dull, dirty, scuffed, before waxing. Photorealistic."
  }
]

def update_tasks():
    with open(TASKS_FILE, 'r') as f:
        tasks = json.load(f)

    # 1. Add missing tasks (check by clean_file to avoid dupes)
    existing_clean_files = {t['clean_file'] for t in tasks}
    for new_task in new_tasks:
        if new_task['clean_file'] not in existing_clean_files:
            tasks.append(new_task)
            print(f"Added new task for {new_task['clean_file']}")

    # 2. Update all tasks: rename dirty_file to v2 and enforce NO PEOPLE prompt
    for task in tasks:
        # Update filename
        base_name = task['dirty_file'].rsplit('.', 1)[0]
        ext = task['dirty_file'].rsplit('.', 1)[1]
        
        # Remove old -v2 if exists to avoid -v2-v2
        if base_name.endswith("-dirty"):
             task['dirty_file'] = f"{base_name}-v2.{ext}"
        elif "-dirty-" not in base_name: # Handle cases where it might not have -dirty suffix effectively
             task['dirty_file'] = f"{base_name}-dirty-v2.{ext}"
        
        # Enforce NO PEOPLE in prompt
        prompt = task['dirty_prompt']
        if "NO PEOPLE" not in prompt:
            task['dirty_prompt'] = "ABSOLUTELY NO PEOPLE. EMPTY ROOM. " + prompt

    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=4)
    print(f"Updated {len(tasks)} tasks in {TASKS_FILE}")

if __name__ == "__main__":
    update_tasks()
