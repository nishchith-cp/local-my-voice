#!/usr/bin/env python3
"""Single-user, loopback-only narration UI. No external web assets."""

import argparse
import base64
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading

import narrate

MAX_BODY = 24 * 1024 * 1024
MAX_AUDIO = 16 * 1024 * 1024


def prerequisites():
    missing = [name for name in ("numpy", "soundfile", "mlx", "mlx_audio")
               if importlib.util.find_spec(name) is None]
    return {
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "native_mac": platform.system() == "Darwin" and platform.machine() == "arm64",
        "python": platform.python_version(),
        "supported_python": sys.version_info >= (3, 11),
        "missing": missing,
    }


class App:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.worker = None
        self.process = None
        self.stopping = False
        self.status = {"stage": "Ready. Choose a voice reference and review consent.", "busy": False,
                       "files": [], "error": None}

    def update(self, stage):
        with self.lock:
            self.status["stage"] = stage

    def start(self, data):
        if data.get("consent") is not True:
            raise ValueError("Confirm voice ownership or explicit speaker permission")
        text = data.get("text")
        encoded = data.get("audio")
        if not isinstance(text, str) or len(text) > 20000:
            raise ValueError("Text must contain 1 to 20000 characters")
        narrate.chunks(text)
        if not isinstance(encoded, str):
            raise ValueError("Select an audio recording")
        try:
            audio = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as error:
            raise ValueError("Invalid audio upload encoding") from error
        if not audio or len(audio) > MAX_AUDIO:
            raise ValueError("Audio must be non-empty and at most 16 MiB")
        with self.lock:
            if self.stopping:
                raise ValueError("Service is stopping")
            if self.status["busy"]:
                raise ValueError("A narration job is already running")
            self.status = {"stage": "Preparing your reference locally", "busy": True,
                           "files": [], "error": None}
            self.worker = threading.Thread(
                target=self.run, args=(audio, text, data.get("download") is True,
                                      data.get("clean") is True),
            )
            self.worker.start()

    def synthesize(self, reference, text, destination, download):
        script = reference.parent / "script.txt"
        script.write_text(text, encoding="utf-8")
        arguments = [
            sys.executable, "-u", str(Path(narrate.__file__).resolve()), "generate",
            "--reference", str(reference), "--script", str(script),
            "--output", str(destination), "--consent",
        ]
        if download:
            arguments.append("--allow-download")
        environment = dict(os.environ, HF_HUB_OFFLINE="0" if download else "1",
                           HF_HUB_DISABLE_TELEMETRY="1", DO_NOT_TRACK="1")
        # Hugging Face caches offline settings on import; isolate every run so
        # switching the checkbox cannot accidentally reuse an earlier online mode.
        with self.lock:
            if self.stopping:
                raise RuntimeError("Service is stopping")
            process = subprocess.Popen(
                arguments, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, env=environment,
            )
            self.process = process
        try:
            last_line = ""
            for line in process.stdout:
                last_line = line.strip()[-2000:]
                if last_line:
                    self.update(last_line)
            if process.wait() != 0:
                raise RuntimeError(f"Generation subprocess failed: {last_line}")
        finally:
            process.stdout.close()
            with self.lock:
                self.process = None

    def stop(self):
        with self.lock:
            self.stopping = True
            process = self.process
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if self.worker is not None:
            self.worker.join()

    def run(self, audio, text, download, cleanup):
        try:
            folder = Path(tempfile.mkdtemp(prefix="take-", dir=self.directory))
            reference = folder / "reference-upload"
            reference.write_bytes(audio)
            prepared = folder / "reference.wav"
            narrate.transform(reference, prepared, "prepare")
            raw = folder / "raw.wav"
            self.synthesize(prepared, text, raw, download)
            files = [raw]
            with self.lock:
                self.status["files"] = [str(raw.relative_to(self.directory))]
            chosen = raw
            if cleanup:
                self.update("Applying gentle noise filtering; preserving raw audio")
                chosen = folder / "clean.wav"
                narrate.transform(raw, chosen, "clean")
                files.append(chosen)
                with self.lock:
                    self.status["files"] = [str(file.relative_to(self.directory)) for file in files]
            self.update("Encoding MP3 for playback and export")
            mp3 = folder / "narration.mp3"
            narrate.transform(chosen, mp3, "export")
            files.append(mp3)
            with self.lock:
                self.status["files"] = [str(file.relative_to(self.directory)) for file in files]
                self.status["stage"] = "Ready to preview/export. Listen through for missing words and artifacts."
        except Exception as error:
            # Worker exceptions must become explicit UI failures, never success-shaped results.
            detail = error.stderr if isinstance(error, subprocess.CalledProcessError) else str(error)
            with self.lock:
                self.status["error"] = f"{type(error).__name__}: {detail}"
                self.status["stage"] = "Failed. Correct the error and try again."
        finally:
            with self.lock:
                self.status["busy"] = False


def handler_for(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass  # Avoid logging tokens, media URLs, or user inputs.

        def reply(self, status, content, mime="application/json"):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                f"default-src 'none'; script-src 'nonce-{app.token}'; "
                "style-src 'unsafe-inline'; connect-src 'self'; media-src 'self'; "
                "base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(content)

        def local_request(self):
            expected = f"127.0.0.1:{self.server.server_port}"
            return (self.headers.get("Host") == expected and
                    self.headers.get("Origin") in (None, f"http://{expected}"))

        def authorized(self):
            return self.local_request() and secrets.compare_digest(
                self.headers.get("X-Session-Token", ""), app.token
            )

        def do_GET(self):
            if not self.local_request():
                self.reply(403, b'{"error":"Loopback origin required"}')
                return
            if self.path == "/":
                page = Path(__file__).with_name("ui.html").read_text(encoding="utf-8")
                self.reply(200, page.replace("__TOKEN__", app.token).encode(), "text/html; charset=utf-8")
            elif self.path == "/status" and self.authorized():
                with app.lock:
                    status = dict(app.status)
                status["prerequisites"] = prerequisites()
                self.reply(200, json.dumps(status).encode())
            elif self.path.startswith(f"/media/{app.token}/"):
                name = self.path[len(f"/media/{app.token}/"):]
                with app.lock:
                    allowed = list(app.status["files"])
                if name not in allowed:
                    self.reply(404, b'{"error":"Unknown output"}')
                    return
                file = app.directory / name
                self.reply(200, file.read_bytes(),
                           "audio/mpeg" if file.suffix == ".mp3" else "audio/wav")
            else:
                self.reply(404, b'{"error":"Not found"}')

        def do_POST(self):
            if self.path != "/generate" or not self.authorized():
                self.reply(403, b'{"error":"Invalid local session"}')
                return
            try:
                if self.headers.get("Content-Type") != "application/json":
                    raise ValueError("Expected application/json")
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= MAX_BODY:
                    raise ValueError("Request too large or empty")
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected an object")
                app.start(data)
                self.reply(202, b'{"accepted":true}')
            except (ValueError, UnicodeError) as error:
                self.reply(400, json.dumps({"error": str(error)}).encode())

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="local-voice-narration-") as directory:
        app = App(directory)
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(app))
        server.daemon_threads = True
        print(f"Open http://127.0.0.1:{server.server_port} (Ctrl-C stops and removes session audio)",
              flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
            app.stop()


if __name__ == "__main__":
    main()
