#!/usr/bin/env python3
"""Launch backend (AgentServer) and Streamlit frontend side-by-side.

Backend  →  http://localhost:{BACKEND_PORT}  (default 8001)
Frontend →  http://localhost:{PORT}           (default 8000, exposed by Databricks Apps)
"""

import os
import re
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

BACKEND_READY_PATTERNS = [
    r"Uvicorn running on",
    r"Application startup complete",
    r"Started server process",
]
FRONTEND_READY_PATTERNS = [
    r"You can now view your Streamlit app",
    r"Network URL",
    r"External URL",
]


def _wait_for_port(port: int, timeout: int = 120) -> bool:
    """Block until *port* accepts connections (or *timeout* seconds elapse)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False


class ProcessManager:
    def __init__(self, backend_port: int, frontend_port: int):
        self.backend_port = backend_port
        self.frontend_port = frontend_port
        self.backend_proc = None
        self.frontend_proc = None
        self.backend_ready = False
        self.frontend_ready = False
        self.failed = threading.Event()

    # ------------------------------------------------------------------ #
    def _monitor(self, proc, name: str, patterns: list[str]):
        is_ready = False
        try:
            for line in iter(proc.stdout.readline, ""):
                if not line:
                    break
                line = line.rstrip()
                print(f"[{name}] {line}")
                if not is_ready and any(re.search(p, line, re.IGNORECASE) for p in patterns):
                    is_ready = True
                    if name == "backend":
                        self.backend_ready = True
                    else:
                        self.frontend_ready = True
                    print(f"\u2713 {name.capitalize()} is ready!")
                    if self.backend_ready and self.frontend_ready:
                        print("\n" + "=" * 52)
                        print("\u2713 Both backend and frontend are ready!")
                        print(f"\u2713 Open the app at http://localhost:{self.frontend_port}")
                        print("=" * 52 + "\n")
            proc.wait()
            if proc.returncode != 0:
                print(f"[{name}] exited with code {proc.returncode}")
                self.failed.set()
        except Exception as exc:
            print(f"Error monitoring {name}: {exc}")
            self.failed.set()

    # ------------------------------------------------------------------ #
    def _start(self, cmd, name, patterns, env=None, cwd=None):
        print(f"Starting {name}: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=cwd,
            env=env or os.environ.copy(),
        )
        t = threading.Thread(target=self._monitor, args=(proc, name, patterns), daemon=True)
        t.start()
        return proc

    # ------------------------------------------------------------------ #
    def cleanup(self):
        print("\nShutting down\u2026")
        for proc in [self.frontend_proc, self.backend_proc]:
            if proc and proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=5)
                except Exception:
                    proc.kill()

    # ------------------------------------------------------------------ #
    def run(self):
        # -- Backend (AgentServer) ------------------------------------ #
        backend_env = os.environ.copy()
        backend_env["PORT"] = str(self.backend_port)
        self.backend_proc = self._start(
            ["uv", "run", "start-server"],
            name="backend",
            patterns=BACKEND_READY_PATTERNS,
            env=backend_env,
        )

        # Wait for backend to be reachable before starting frontend
        print(f"Waiting for backend on port {self.backend_port}\u2026")
        if not _wait_for_port(self.backend_port):
            print("ERROR: Backend did not start in time.")
            self.cleanup()
            sys.exit(1)
        print(f"\u2713 Backend reachable on port {self.backend_port}")

        # -- Frontend (Streamlit) ------------------------------------- #
        frontend_env = os.environ.copy()
        frontend_env["BACKEND_URL"] = f"http://localhost:{self.backend_port}"
        self.frontend_proc = self._start(
            [
                "uv", "run", "streamlit", "run", "streamlit_app.py",
                "--server.port", str(self.frontend_port),
                "--server.headless", "true",
                "--server.address", "0.0.0.0",
            ],
            name="frontend",
            patterns=FRONTEND_READY_PATTERNS,
            env=frontend_env,
        )

        # -- Monitor -------------------------------------------------- #
        try:
            while not self.failed.is_set():
                if self.backend_proc.poll() is not None:
                    print(f"Backend exited ({self.backend_proc.returncode})")
                    break
                if self.frontend_proc.poll() is not None:
                    print(f"Frontend exited ({self.frontend_proc.returncode})")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()


def main():
    load_dotenv(dotenv_path=".env", override=True)

    backend_port = int(os.environ.get("BACKEND_PORT", "8001"))
    # Databricks Apps expose port 8000 by default
    frontend_port = int(os.environ.get("PORT", "8000"))

    pm = ProcessManager(backend_port=backend_port, frontend_port=frontend_port)
    pm.run()


if __name__ == "__main__":
    main()
