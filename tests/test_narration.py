import base64
import http.client
import io
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import wave

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/local-voice-narration/scripts"
sys.path.insert(0, str(SCRIPTS))
import narrate
import serve


def reference_bytes(sample=1000):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as file:
        file.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        file.writeframes(struct.pack("<h", sample) * 240)
    return buffer.getvalue()


class PipelineTests(unittest.TestCase):
    def test_chunks_preserve_words_and_paragraphs(self):
        text = "A quiet morning.\n\nClouds pass over the open sky."
        parts = narrate.chunks(text, 18)
        self.assertEqual(parts[0], "A quiet morning.")
        self.assertEqual(" ".join(parts), " ".join(text.split()))
        self.assertTrue(all(0 < len(part) <= 18 for part in parts))

    def test_bad_text(self):
        for text in (" \n ", "a" * 501):
            with self.assertRaises(ValueError):
                narrate.chunks(text)

    def test_output_safeguards_and_race(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "out.wav"
            with self.assertRaises(FileExistsError):
                with narrate.output_file(target, ".wav") as temp:
                    temp.write_bytes(b"synthetic new output")
                    target.write_bytes(b"other writer")
            self.assertEqual(target.read_bytes(), b"other writer")
            with self.assertRaises(ValueError):
                with narrate.output_file(target, ".wav"):
                    pass
            dangling = Path(folder) / "link.wav"
            dangling.symlink_to(Path(folder) / "missing")
            with self.assertRaises(ValueError):
                with narrate.output_file(dangling, ".wav"):
                    pass

    def test_failure_removes_partial_output(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "out.wav"
            with self.assertRaises(RuntimeError):
                with narrate.output_file(target, ".wav") as temp:
                    temp.write_bytes(b"partial")
                    raise RuntimeError("synthetic failure")
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_ffmpeg_arguments_and_no_shell(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "input ; harmless.wav"
            source.write_bytes(b"fixture")
            for operation, suffix, expected in (
                ("prepare", ".wav", ["-ac", "1", "-ar", "24000"]),
                ("clean", ".wav", ["-af", narrate.FILTER]),
                ("export", ".mp3", ["-c:a", "libmp3lame", "-q:a", "2"]),
            ):
                def run(arguments, **kwargs):
                    self.assertIn(str(source.resolve()), arguments)
                    self.assertNotIn("shell", kwargs)
                    self.assertTrue(kwargs["check"])
                    for item in expected:
                        self.assertIn(item, arguments)
                    Path(arguments[-1]).write_bytes(b"result")
                with patch.object(narrate.shutil, "which", return_value="/ffmpeg"):
                    with patch.object(narrate.subprocess, "run", side_effect=run):
                        narrate.transform(source, Path(folder) / (operation + suffix), operation)

    def test_missing_dependencies(self):
        with patch.object(narrate.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "ffmpeg is missing"):
                narrate.ffmpeg([])
        with patch.object(narrate.importlib, "import_module", side_effect=ImportError("absent")):
            with self.assertRaisesRegex(RuntimeError, "requirements.txt"):
                narrate.dependency("numpy")

    def test_consent_required(self):
        with patch("sys.stderr", new_callable=io.StringIO):
            with self.assertRaises(SystemExit):
                narrate.parser().parse_args(["prepare", "--input", "a", "--output", "b.wav"])

    def test_host_guard_before_imports(self):
        with patch.object(narrate.platform, "system", return_value="Linux"):
            with patch.object(narrate, "dependency") as dependencies:
                with self.assertRaisesRegex(RuntimeError, "Apple Silicon"):
                    narrate.generate("unused", "Generic text", "unused.wav")
                dependencies.assert_not_called()

    def test_reference_rate_guard_before_model_download(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "reference.wav"
            source.write_bytes(b"fixture")
            sf = SimpleNamespace(read=lambda *a, **k: (None, 44100))
            modules = {"numpy": object(), "soundfile": sf}
            with patch.object(narrate.platform, "system", return_value="Darwin"):
                with patch.object(narrate.platform, "machine", return_value="arm64"):
                    with patch.object(narrate, "dependency", side_effect=modules.__getitem__):
                        with self.assertRaisesRegex(ValueError, "24000"):
                            narrate.generate(source, "Generic text", Path(folder) / "out.wav")
            self.assertFalse((Path(folder) / "out.wav").exists())

    def test_direct_generation_without_stt_and_with_chunk_pause(self):
        class Audio(list):
            ndim = 1

            @property
            def size(self):
                return len(self)

        np = SimpleNamespace(
            float32="float32",
            asarray=lambda values, **kwargs: Audio(values),
            isfinite=lambda values: SimpleNamespace(all=lambda: all(map(math.isfinite, values))),
            abs=lambda values: [abs(value) for value in values],
            max=max,
            zeros=lambda count, **kwargs: Audio([0] * count),
            concatenate=lambda values: Audio(value for part in values for value in part),
        )
        reference_samples = Audio([.1, -.2])
        calls, written = [], []

        def model_generate(**kwargs):
            calls.append(kwargs)
            yield SimpleNamespace(audio=Audio([.2, -.1]), sample_rate=24000)

        def write(path, audio, rate, subtype):
            written.append((len(audio), rate, subtype))
            Path(path).write_bytes(b"synthetic mocked WAV")

        model = SimpleNamespace(sample_rate=24000, generate=model_generate)
        modules = {
            "numpy": np,
            "soundfile": SimpleNamespace(read=lambda *a, **k: (reference_samples, 24000),
                                         write=write),
            "mlx.core": SimpleNamespace(array=lambda values: values),
            "mlx_audio.tts.utils": SimpleNamespace(load_model=lambda name: model),
        }
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "ref.wav"
            reference.write_bytes(b"synthetic reference placeholder")
            output = Path(folder) / "out.wav"
            with patch.object(narrate.platform, "system", return_value="Darwin"):
                with patch.object(narrate.platform, "machine", return_value="arm64"):
                    with patch.object(narrate, "dependency", side_effect=modules.__getitem__):
                        with patch.dict(narrate.os.environ, {}, clear=False):
                            narrate.generate(reference, "First paragraph.\n\nSecond paragraph.",
                                             output, progress=lambda stage: None)
                            self.assertEqual(narrate.os.environ["HF_HUB_OFFLINE"], "1")
            self.assertTrue(output.exists())
        self.assertEqual(len(calls), 2)
        self.assertTrue(all("ref_text" not in call for call in calls))
        self.assertTrue(all(call["max_tokens"] == 1200 for call in calls))
        self.assertEqual(written, [(8404, 24000, "PCM_16")])
        for audio in (Audio([]), Audio([0]), Audio([float("nan")]), Audio([1.1])):
            with self.assertRaises(ValueError):
                narrate.valid_audio(audio, np, "Test")

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not installed")
    def test_real_ffmpeg_with_synthetic_tone(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "synthetic.wav"
            with wave.open(str(source), "wb") as file:
                file.setparams((2, 2, 44100, 0, "NONE", "not compressed"))
                file.writeframes(b"".join(
                    struct.pack("<hh", sample, sample)
                    for sample in (
                        int(5000 * math.sin(2 * math.pi * 440 * index / 44100))
                        for index in range(11025)
                    )
                ))
            prepared, cleaned, mp3 = root / "prepared.wav", root / "clean.wav", root / "out.mp3"
            narrate.transform(source, prepared, "prepare")
            narrate.transform(prepared, cleaned, "clean")
            narrate.transform(cleaned, mp3, "export")
            for path in (prepared, cleaned):
                with wave.open(str(path), "rb") as file:
                    self.assertEqual((file.getnchannels(), file.getframerate()), (1, 24000))
                    self.assertEqual(file.getsampwidth(), 2)
                    self.assertGreater(file.getnframes(), 0)
            self.assertGreater(mp3.stat().st_size, 0)


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.app = serve.App(self.temporary.name, Path(self.temporary.name) / "saved")
        self.server = serve.ThreadingHTTPServer(("127.0.0.1", 0), serve.handler_for(self.app))
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.app.stop()
        self.temporary.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    def test_page_explains_flow_and_has_editable_sample(self):
        status, content, headers = self.request("GET", "/")
        self.assertEqual(status, 200)
        for text in (b"<textarea", b"Hugging Face", b"loopback", b"Download", b"permission"):
            self.assertIn(text, content)
        self.assertNotIn(b"__TOKEN__", content)
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_local_origin_and_token_guards(self):
        status, _, _ = self.request("GET", "/", headers={"Host": "attacker.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/generate", "{}",
                                   {"Content-Type": "application/json"})
        self.assertEqual(status, 403)
        status, _, _ = self.request("POST", "/generate", "{}",
                                   {"X-Session-Token": self.app.token,
                                    "Origin": "https://attacker.example"})
        self.assertEqual(status, 403)

    def test_validation_and_no_arbitrary_media_read(self):
        headers = {"X-Session-Token": self.app.token, "Content-Type": "application/json"}
        for body in ({}, {"consent": True, "text": "Generic", "audio": "!!!"}, []):
            status, _, _ = self.request("POST", "/generate", json.dumps(body), headers)
            self.assertEqual(status, 400)
        status, _, _ = self.request("GET", f"/media/{self.app.token}/../../README.md")
        self.assertEqual(status, 404)

    def test_sample_then_custom_transcript_export_with_mocked_model(self):
        def transform(source, destination, operation):
            Path(destination).write_bytes(reference_bytes() if operation == "prepare"
                                          else b"synthetic processed audio")

        calls = []

        def generate(reference, text, destination, download):
            calls.append((text, download))
            self.app.update("Generating chunk 1 of 1")
            Path(destination).write_bytes(b"synthetic generated audio")

        headers = {"X-Session-Token": self.app.token, "Content-Type": "application/json"}
        with patch.object(narrate, "transform", side_effect=transform):
            with patch.object(self.app, "synthesize", side_effect=generate):
                for text, download in (("Generic sample text.", False), ("A custom transcript.", True)):
                    done = threading.Event()
                    original = self.app.run

                    def run(*args):
                        try:
                            original(*args)
                        finally:
                            done.set()

                    with patch.object(self.app, "run", side_effect=run):
                        data = {"text": text, "download": download, "clean": True}
                        if not download:
                            data.update(consent=True, audio=base64.b64encode(b"fixture").decode())
                        status, _, _ = self.request("POST", "/generate", json.dumps(data), headers)
                        self.assertEqual(status, 202)
                        self.assertTrue(done.wait(5))
                    status, payload, _ = self.request("GET", "/status", headers=headers)
                    state = json.loads(payload)
                    self.assertFalse(state["busy"])
                    self.assertIsNone(state["error"])
                    self.assertEqual(len(state["files"]), 3)
                    for name in state["files"]:
                        status, payload, _ = self.request("GET", f"/media/{self.app.token}/{name}")
                        self.assertEqual(status, 200)
                        self.assertTrue(payload.startswith(b"synthetic"))
        self.assertEqual(calls, [("Generic sample text.", False), ("A custom transcript.", True)])
        self.assertTrue(self.app.voices.active())

    def test_saved_voice_survives_restart_and_delete_requires_new_upload(self):
        prepared = Path(self.temporary.name) / "prepared.wav"
        prepared.write_bytes(reference_bytes())
        self.app.voices.save(prepared)
        restarted = serve.App(self.temporary.name, self.app.voices.directory)
        self.assertTrue(restarted.voice_status()["saved"])
        with patch.object(restarted, "synthesize") as synthesis:
            synthesis.side_effect = lambda ref, text, output, download: Path(output).write_bytes(
                b"synthetic narration")
            with patch.object(narrate, "transform") as transform:
                transform.side_effect = lambda source, output, operation: Path(output).write_bytes(
                    b"synthetic MP3")
                restarted.start({"text": "Later narration."})
                restarted.worker.join()
                self.assertEqual(synthesis.call_args.args[0], restarted.voices.reference)
                self.assertEqual(transform.call_args.args[2], "export")
                self.assertEqual(transform.call_count, 1)
        self.assertIsNone(restarted.status["error"])
        headers = {"X-Session-Token": self.app.token, "Content-Type": "application/json"}
        status, _, _ = self.request("POST", "/voice/delete", "{}", headers)
        self.assertEqual(status, 200)
        self.assertFalse(restarted.voice_status()["saved"])
        with self.assertRaisesRegex(ValueError, "No saved voice"):
            restarted.start({"text": "Later narration."})

    def test_replacement_requires_explicit_choice_and_fresh_permission(self):
        prepared = Path(self.temporary.name) / "prepared.wav"
        prepared.write_bytes(reference_bytes())
        self.app.voices.save(prepared)
        data = {"text": "Generic text.", "audio": base64.b64encode(b"fixture").decode()}
        for changes in ({"replace": True}, {"consent": True}):
            with self.assertRaises(ValueError):
                self.app.start(dict(data, **changes))
        with patch.object(narrate, "transform") as transform:
            transform.side_effect = lambda source, output, operation: Path(output).write_bytes(
                reference_bytes(2000) if operation == "prepare" else b"synthetic output")
            with patch.object(self.app, "synthesize") as synthesis:
                synthesis.side_effect = lambda ref, text, output, download: Path(output).write_bytes(
                    b"synthetic narration")
                self.app.start(dict(data, consent=True, replace=True))
                self.app.worker.join()
        self.assertIsNone(self.app.status["error"])
        self.assertEqual(self.app.voices.active().read_bytes(), reference_bytes(2000))
        self.assertEqual(self.app.voices.reference.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.app.voices.directory.stat().st_mode & 0o777, 0o700)

    def test_invalid_replacement_preserves_previous_voice(self):
        prepared = Path(self.temporary.name) / "prepared.wav"
        prepared.write_bytes(reference_bytes())
        self.app.voices.save(prepared)
        with patch.object(narrate, "transform") as transform:
            transform.side_effect = lambda source, output, operation: Path(output).write_bytes(b"bad")
            self.app.run(b"fixture", "Generic text.", False, False)
        self.assertIsNotNone(self.app.status["error"])
        self.assertEqual(self.app.voices.active().read_bytes(), reference_bytes())

    def test_delete_and_replace_blocked_during_generation(self):
        self.app.status["busy"] = True
        with self.assertRaisesRegex(ValueError, "current job"):
            self.app.delete_voice()
        with self.assertRaisesRegex(ValueError, "already running"):
            self.app.start({"text": "Generic text."})

    def test_saved_reference_is_not_downloadable(self):
        prepared = Path(self.temporary.name) / "prepared.wav"
        prepared.write_bytes(reference_bytes())
        self.app.voices.save(prepared)
        status, _, _ = self.request("GET", f"/media/{self.app.token}/saved/authorized-reference.wav")
        self.assertEqual(status, 404)

    def test_cli_reuses_saved_voice_without_consent_prompt(self):
        script = Path(self.temporary.name) / "script.txt"
        script.write_text("Generic text.", encoding="utf-8")
        prepared = Path(self.temporary.name) / "prepared.wav"
        prepared.write_bytes(reference_bytes())
        self.app.voices.save(prepared)
        with patch("voice_store.VoiceStore", return_value=self.app.voices):
            with patch.object(narrate, "generate") as generate:
                self.assertEqual(narrate.main([
                    "generate", "--saved-voice", "--script", str(script),
                    "--output", str(script.parent / "out.wav"),
                ]), 0)
                self.assertEqual(generate.call_args.args[0], self.app.voices.reference)
        with patch.object(narrate, "generate") as generate:
            with patch("sys.stderr", new_callable=io.StringIO):
                self.assertEqual(narrate.main([
                    "generate", "--reference", str(prepared), "--script", str(script),
                    "--output", str(script.parent / "out.wav"),
                ]), 1)
            generate.assert_not_called()

    def test_subprocess_isolates_each_runs_download_permission(self):
        reference = Path(self.temporary.name) / "reference.wav"
        reference.write_bytes(b"synthetic fixture")
        for download in (True, False):
            process = SimpleNamespace(stdout=io.StringIO("Generating chunk 1 of 1\n"),
                                      wait=lambda: 0)
            with patch.object(serve.subprocess, "Popen", return_value=process) as popen:
                self.app.synthesize(reference, "Generic script.", reference.parent / "raw.wav",
                                    download)
            arguments = popen.call_args.args[0]
            self.assertEqual("--allow-download" in arguments, download)
            self.assertNotIn("Generic script.", arguments)
            self.assertEqual(popen.call_args.kwargs["env"]["HF_HUB_OFFLINE"],
                             "0" if download else "1")

    def test_worker_failure_is_visible_and_retryable(self):
        with patch.object(narrate, "transform", side_effect=RuntimeError("ffmpeg unavailable")):
            self.app.run(b"fixture", "Generic text", False, False)
        self.assertFalse(self.app.status["busy"])
        self.assertIn("ffmpeg unavailable", self.app.status["error"])
        self.assertEqual(self.app.status["files"], [])


if __name__ == "__main__":
    unittest.main()
