import datetime
import time
import re

def timestamp_now():
    """Returns a formatted string of the current time."""
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def sanitize_text(text):
    """Cleans text for safe display."""
    if not text:
        return ""
    # Remove markdown code blocks if present
    text = text.replace("```json", "").replace("```", "").strip()
    return text

def simulate_progress_bar(st_obj, text, speed=0.05):
    """
    Simulates a process with a progress bar.
    st_obj: The streamlit module or a container.
    """
    progress_bar = st_obj.progress(0, text=text)
    for percent_complete in range(100):
        time.sleep(speed)
        progress_bar.progress(percent_complete + 1, text=text)
    time.sleep(0.2)
    progress_bar.empty()