"""Push the models to the VM whenever training rewrites them, and fetch what the dashboard shows of the VM.
Run on the laptop next to `q2q train2`."""
import pathlib
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
GIT_BASH = pathlib.Path("C:/Program Files/Git/bin/bash.exe")  # plain "bash" is WSL on this laptop
BASH = str(GIT_BASH) if GIT_BASH.exists() else "bash"
seen = None
while True:
    now = tuple(sorted((p.name, p.stat().st_mtime) for p in (ROOT / "models").glob("*.*")))
    if now != seen:
        code = subprocess.call([BASH, "scripts/vm.sh", "models"], cwd=ROOT)
        print(time.strftime("%H:%M:%S"), "pushed" if code == 0 else f"push failed ({code})", flush=True)
        seen = now if code == 0 else seen
    subprocess.call([BASH, "scripts/vm.sh", "sync"], cwd=ROOT)
    time.sleep(30)
