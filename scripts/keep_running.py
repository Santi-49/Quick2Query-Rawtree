"""Keep one Python script running: restart it if it exits, and keep Windows awake meanwhile.

    uv run --with requests python scripts/keep_running.py starter/recommender.py

Closing the laptop lid still suspends the machine; this only blocks idle sleep.
"""
import ctypes
import subprocess
import sys
import time

if sys.platform == "win32":  # ES_CONTINUOUS | ES_SYSTEM_REQUIRED, released when this process exits
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
while True:
    code = subprocess.call([sys.executable, "-u", *sys.argv[1:]])
    print(f"{time.strftime('%H:%M:%S')} exited with code {code}, restarting in 2 s", flush=True)
    time.sleep(2)
