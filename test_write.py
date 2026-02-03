import sys
import os
import json

path = r"X:\.harborpilot\cache\afb35f627931\runtime\config\llm_config.json"

def try_write():
    print(f"Target: {path}")
    dir_name = os.path.dirname(path)
    if not os.path.exists(dir_name):
        print(f"Creating dir: {dir_name}")
        try:
            os.makedirs(dir_name, exist_ok=True)
            print("Dir created.")
        except Exception as e:
            print(f"Failed to create dir: {e}")
            return

    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(json.dumps({"test": "value"}))
        print("Write success!")
    except Exception as e:
        print(f"Write failed: {e}")

    if os.path.isfile(path):
        print("File verified on disk.")
        try:
            os.remove(path)
            print("Cleanup success.")
        except:
            pass
    else:
        print("File NOT found after write.")

if __name__ == "__main__":
    try_write()
