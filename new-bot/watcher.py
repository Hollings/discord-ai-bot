import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os

class ChangeHandler(FileSystemEventHandler):
    def on_any_event(self, event):
        print(f"Change detected: {event.src_path}")
        if "__pycache__" in event.src_path:
            return  # Ignore changes in __pycache__ directories
        os.system('docker-compose restart discord-bot worker postgres redis')

if __name__ == "__main__":
    path = "./bot"  # path to watch
    event_handler = ChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()