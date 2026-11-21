"""One consented reference, stored locally outside the skill repository."""

import os
from pathlib import Path
import tempfile
import wave


def default_directory():
    return Path.home() / "Library" / "Application Support" / "local-voice-narration"


class VoiceStore:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else default_directory()
        self.reference = self.directory / "authorized-reference.wav"

    def active(self):
        if self.reference.is_symlink():
            raise ValueError("Saved voice must not be a symbolic link")
        if not self.reference.exists():
            return None
        try:
            with wave.open(str(self.reference), "rb") as audio:
                if (audio.getnchannels(), audio.getframerate(), audio.getsampwidth()) != (1, 24000, 2):
                    raise ValueError("Saved voice must be mono 24 kHz PCM 16-bit WAV")
                if audio.getnframes() == 0:
                    raise ValueError("Saved voice is empty")
        except (wave.Error, EOFError) as error:
            raise ValueError(f"Saved voice is not a valid WAV: {error}") from error
        return self.reference

    def save(self, prepared):
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink():
            raise ValueError("Saved voice directory must not be a symbolic link")
        self.directory.chmod(0o700)
        # Validate before atomic replacement so a failed upload retains the old voice.
        with tempfile.TemporaryDirectory(prefix=".voice-", dir=self.directory) as folder:
            candidate = VoiceStore(folder)
            candidate.reference.write_bytes(Path(prepared).read_bytes())
            candidate.reference.chmod(0o600)
            candidate.active()
            os.replace(candidate.reference, self.reference)
        return self.reference

    def delete(self):
        if self.reference.exists() or self.reference.is_symlink():
            self.reference.unlink()
