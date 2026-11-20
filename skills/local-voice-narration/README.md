# Setup and use

**What will happen:** install tools in an isolated Python environment, start a
local page, choose an authorized voice recording, try editable sample text,
generate locally, listen and download. Later, replace the sample with your own
transcript. The first model use may need a substantial download; later runs
reuse cached files. The interface asks permission before enabling downloads.

## Prerequisites

- Native Apple Silicon macOS for generation, not Intel/Rosetta.
- Python 3.11 and ffmpeg installed through your trusted package manager.
- Free disk space and unified memory for the model. Requirements and speed
  depend on the upstream model/environment; no fixed size or timing is promised.

Check `python3.11 --version`, `uname -m` (should be `arm64`) and
`ffmpeg -version`. The ffmpeg build needs `afftdn`, `alimiter` and `libmp3lame`.
Cleanup/export alone need only Python and ffmpeg.

From this skill directory, after approving dependency installation:

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/serve.py
```

Open **http://127.0.0.1:8765** in your browser. The service binds only to
`127.0.0.1`; do not share/forward this port or expose it through a proxy.
Use `--port 8766` if the default port is busy. No web framework, external web
assets, cloud speech API, or public sharing feature is involved.
Direct dependencies are pinned; this is not a full transitive lock.

## First narration

1. Read the process/privacy explanation in the page.
2. Select a clear, short, single-speaker recording (up to 16 MiB). ffmpeg
   decodes the first audio stream to mono 24 kHz PCM WAV. Avoid music and
   overlapping voices. Confirm it is your voice or explicitly authorized.
3. Try the editable generic sample text. Tick the model-download permission
   only if you authorize fetching missing files. Otherwise cached-only mode
   fails explicitly when the model is unavailable.
4. Generate. Stages show reference preparation, model loading (and possible
   download), chunk generation, optional filtering and MP3 encoding.
   Upstream download tools may show additional details in the terminal.
   No invented download percentage, total size or completion time is shown.
5. Listen through the full result, then download raw WAV, cleaned WAV if
   selected, and MP3. Check missing words, pronunciation and model artifacts.
6. Paste your own narration transcript into the same text area and generate
   another take. Save current outputs first.

The interface is single-user and accepts one job at a time. Each job uses new
filenames. Audio lives in a private OS temporary session directory, not in this
repository. **Download before stopping the server with Ctrl-C**: stopping removes
the session directory. Abnormal process termination can leave temporary files;
disk encryption and local machine access remain your responsibility. No claim
of secure erasure is made. Do not use this service on an untrusted shared machine.

## Downloads versus local uploads

Selecting a recording sends it from your browser to the loopback service on
the same computer. The code does not upload your recording or text to a voice
provider. Speech generation runs locally.

Package setup contacts package indexes. Online model loading contacts Hugging
Face and its download infrastructure for
[`mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit`](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit).
The standard model cache is normally `~/.cache/huggingface/hub`; `HF_HOME`,
`HF_HUB_CACHE` or other upstream settings can change this. Keep caches outside
the repository. Read the upstream model card/license and dependency terms.
Model size has not been independently measured here.

Before ML imports the tool sets `HF_HUB_DISABLE_TELEMETRY=1` and `DO_NOT_TRACK=1`
to reduce optional telemetry where supported. This is not a guarantee about all
dependency requests. Cached-only mode sets `HF_HUB_OFFLINE=1`; use OS network
controls for strict isolation. Speaker-embedding mode calls the model directly
without a reference transcript, avoiding a separate automatic STT download.
The narration transcript is what to read, not a transcript of the reference.

## CLI

From the skill directory, set `WORK` to an existing private directory outside the
repository containing an authorized reference and a UTF-8 `script.txt`:

```sh
WORK="$HOME/Narration" # Select/create this private directory yourself.
.venv/bin/python scripts/narrate.py prepare \
  --input "$WORK/reference.m4a" --output "$WORK/reference-24k.wav" --consent
.venv/bin/python scripts/narrate.py generate \
  --reference "$WORK/reference-24k.wav" --script "$WORK/script.txt" \
  --output "$WORK/raw.wav" --consent
# Add --allow-download to generate only after approving missing model downloads.
.venv/bin/python scripts/narrate.py clean \
  --input "$WORK/raw.wav" --output "$WORK/clean.wav"
.venv/bin/python scripts/narrate.py export \
  --input "$WORK/clean.wav" --output "$WORK/narration.mp3"
```

Existing output paths are never replaced. Raw and cleaned audio remain separate.
CLI outputs are owner-readable/writable on POSIX. English narration uses
paragraph/word chunks up to 500 characters, 350 ms pauses and at most 1,200
generated tokens per chunk. Listen for truncation and shorten paragraphs if
needed; automatic validation cannot prove every word was spoken.

Cleanup is `highpass=f=70,afftdn=nr=8:nf=-45:tn=1:gs=8,alimiter=limit=0.95:level=false`
to PCM 16-bit WAV. MP3 export uses `libmp3lame -q:a 2`. These filters can affect
the voice and do not guarantee better perceived quality or fix model artifacts.

## Troubleshooting

- **Missing dependencies:** use `.venv/bin/python`, not system Python. Install
  requirements into the Python 3.11 venv; generation requires native `arm64`.
- **`uv` says `Socket is not connected` against `files.pythonhosted.org`:**
  check connectivity, VPN/proxy and certificates; use the explicit Python venv
  and pip commands above as an alternative. Do not disable TLS checks or hide
  install errors.
- **Model unavailable offline:** authorize an online run once, then reuse the
  cache. Do not bypass an offline requirement or silently use a cloud provider.
- **ffmpeg/filter/encoder unavailable:** install a build with the named features
  on PATH. The tool surfaces ffmpeg error details.
- **Wrong rate/stereo:** run `prepare`; the default model requires mono 24 kHz.
- **Silent, invalid or clipping waveform:** generation fails explicitly rather
  than silently normalizing corrupt audio. Check reference quality/levels.
- **Missing words/robotic cadence:** use shorter paragraphs and listen again.
  Gentle filtering cannot reliably fix synthesis mistakes.
- **Memory pressure:** close memory-heavy apps and consult the model card.
  No universal speed, memory, or similarity guarantee is made.

## Development

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 skills/local-voice-narration/scripts/narrate.py --help
python3 skills/local-voice-narration/scripts/serve.py --help
```

Default tests require only standard-library Python, use generic synthetic
fixtures, and never download models or use recordings. A real ffmpeg smoke test
can validate conversions separately. Mocked synthesis is not proof of actual
model generation or perceptual quality. A real model run needs an authorized
reference, installed dependencies, and explicit download permission as needed.
