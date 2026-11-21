#!/usr/bin/env python3
"""Local English narration on Apple Silicon; no automatic STT download."""

import argparse
from contextlib import contextmanager
import importlib
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile

MODEL = "mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit"
RATE = 24000
FILTER = "highpass=f=70,afftdn=nr=12:nf=-40:tn=1:gs=8,alimiter=limit=0.95:level=false"


def source_file(value):
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Not a regular input file: {path}")
    return path


@contextmanager
def output_file(value, suffix):
    destination = Path(value).expanduser().absolute()
    if destination.suffix.lower() != suffix:
        raise ValueError(f"Output must end in {suffix}")
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Refusing to overwrite: {destination}")
    if not destination.parent.is_dir():
        raise ValueError("Create the output directory first")
    with tempfile.TemporaryDirectory(prefix=".narration-", dir=destination.parent) as folder:
        temporary = Path(folder) / destination.name
        yield temporary
        temporary.chmod(0o600)
        # Atomic publication also refuses a concurrently created destination.
        os.link(temporary, destination)


def ffmpeg(arguments):
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg is missing; install it and put it on PATH")
    subprocess.run(
        [executable, "-hide_banner", "-nostdin", "-v", "error", "-n", *arguments],
        check=True, capture_output=True, text=True,
    )


def transform(source, destination, operation):
    source = source_file(source)
    options = {
        "prepare": ["-ac", "1", "-ar", str(RATE), "-c:a", "pcm_s16le"],
        "clean": ["-af", FILTER, "-c:a", "pcm_s16le"],
        "export": ["-c:a", "libmp3lame", "-q:a", "2"],
    }
    with output_file(destination, ".mp3" if operation == "export" else ".wav") as temp:
        ffmpeg(["-i", str(source), "-map", "0:a:0", "-vn", *options[operation], str(temp)])


def chunks(text, limit=500):
    result = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        current = ""
        for word in paragraph.split():
            if len(word) > limit:
                raise ValueError(f"A word exceeds the {limit}-character chunk limit")
            candidate = f"{current} {word}" if current else word
            if len(candidate) > limit:
                result.append(current)
                current = word
            else:
                current = candidate
        if current:
            result.append(current)
    if not result:
        raise ValueError("Provide non-empty narration text")
    return result


def dependency(name):
    try:
        return importlib.import_module(name)
    except ImportError as error:
        raise RuntimeError(
            f"Cannot import {name}; use the Python 3.11 venv and install "
            f"requirements.txt. Details: {error}"
        ) from error


def valid_audio(audio, np, label):
    if audio.ndim != 1 or audio.size == 0:
        raise ValueError(f"{label} must be non-empty mono audio")
    if not np.isfinite(audio).all():
        raise ValueError(f"{label} contains non-finite samples")
    peak = float(np.max(np.abs(audio)))
    if peak < 1e-6 or peak > 1:
        raise ValueError(f"{label} is silent/near-silent or outside PCM range")


def generate(reference, text, destination, offline=True, progress=print):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise RuntimeError("Generation requires native Apple Silicon macOS Python")
    reference = source_file(reference)
    parts = chunks(text)
    # Validate the destination before any model download or costly inference.
    with output_file(destination, ".wav") as temporary:
        hub_constants = sys.modules.get("huggingface_hub.constants")
        if hub_constants is not None and hub_constants.HF_HUB_OFFLINE != offline:
            raise RuntimeError("Run generation in a fresh process when changing download mode")
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        os.environ["DO_NOT_TRACK"] = "1"
        os.environ["HF_HUB_OFFLINE"] = "1" if offline else "0"
        np = dependency("numpy")
        sf = dependency("soundfile")
        samples, rate = sf.read(str(reference), dtype="float32")
        if rate != RATE:
            raise ValueError("Reference must be mono 24000 Hz WAV; run prepare")
        valid_audio(samples, np, "Reference")
        mx = dependency("mlx.core")
        progress("Loading model from cache" if offline else
                 "Loading model; downloading missing files from Hugging Face if needed")
        model = dependency("mlx_audio.tts.utils").load_model(MODEL)
        if getattr(model, "sample_rate", None) != RATE:
            raise ValueError("Unsupported model rate; expected 24000 Hz")
        segments = []
        for index, paragraph in enumerate(parts):
            progress(f"Generating chunk {index + 1} of {len(parts)}")
            generated = []
            for result in model.generate(
                text=paragraph, ref_audio=mx.array(samples),
                lang_code="English", max_tokens=1200,
            ):
                if result.sample_rate != RATE:
                    raise ValueError("Generated audio has an unexpected sample rate")
                audio = np.asarray(result.audio, dtype=np.float32)
                valid_audio(audio, np, "Generated audio")
                generated.append(audio)
            if not generated:
                raise RuntimeError("Model produced no audio")
            if segments:
                segments.append(np.zeros(round(RATE * .350), dtype=np.float32))
            segments.append(np.concatenate(generated))
        audio = np.concatenate(segments)
        valid_audio(audio, np, "Narration")
        sf.write(str(temporary), audio, RATE, subtype="PCM_16")
    progress("Raw narration saved; listen for missing words and model artifacts")


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("prepare", "generate", "clean", "export"):
        command = commands.add_parser(name)
        command.add_argument("--output", required=True)
        if name == "generate":
            reference = command.add_mutually_exclusive_group(required=True)
            reference.add_argument("--reference")
            reference.add_argument("--saved-voice", action="store_true",
                                   help="Reuse the voice authorized and saved in the local UI")
            command.add_argument("--script", required=True, help="UTF-8 narration text file")
            command.add_argument("--allow-download", action="store_true")
        else:
            command.add_argument("--input", required=True)
        if name in ("prepare", "generate"):
            command.add_argument(
                "--consent", action="store_true", required=name == "prepare",
                help="Confirm your own voice or the speaker's explicit permission",
            )
    return root


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "generate":
            if args.saved_voice:
                from voice_store import VoiceStore
                reference = VoiceStore().active()
                if reference is None:
                    raise ValueError("No saved voice; authorize and save one in the local UI first")
            else:
                if not args.consent:
                    raise ValueError("--consent is required with an explicit --reference")
                reference = args.reference
            generate(reference, source_file(args.script).read_text(encoding="utf-8"),
                     args.output, offline=not args.allow_download,
                     progress=lambda stage: print(stage, flush=True))
        else:
            transform(args.input, args.output, args.command)
    except subprocess.CalledProcessError as error:
        print(f"ffmpeg failed: {error.stderr}", file=sys.stderr)
        return 1
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
