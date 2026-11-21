---
name: local-voice-narration
description: Generate local English voice narration from an authorized speaker recording on Apple Silicon using MLX Audio and Qwen3-TTS. Launch a local upload, editable sample-text, playback and export interface, or use the bundled CLI for narration, gentle noise cleanup and MP3 export.
---

# Local voice narration

## Safety and privacy

Confirm that the user owns the voice or has the speaker's explicit permission
before processing it. Never infer consent from possession of a recording.
Do not use this workflow for deceptive impersonation. Disclose synthetic audio
when sharing it. Never commit recordings, scripts, embeddings or generated media.

Explain the process first: isolated dependency setup, authorized model download
if needed, local reference conversion, model loading, speech generation, optional
gentle filtering, then listening and export. Local inference does not mean setup
is offline. Ask before substantial downloads; never bypass cached-only mode.

## Interactive workflow (preferred)

Resolve bundled paths relative to this skill directory. Follow the
[setup instructions](README.md) using Python 3.11 in an isolated virtual
environment and ffmpeg on native Apple Silicon macOS.

Run `.venv/bin/python scripts/serve.py` from this directory, then open the printed
`http://127.0.0.1:8765` address. Do not bind to a public interface, forward the
port, or enable public sharing.

Check the page's saved voice status first. Reuse the active reference without
asking for an upload or speaker permission again. Only request a recording when
none is saved or the user explicitly chooses replacement. Never use a reference
if the user withdraws permission; direct them to Delete saved voice.

For a first upload/replacement, explain that the prepared reference is retained at
`~/Library/Application Support/local-voice-narration/authorized-reference.wav`
outside the repository until replaced/deleted, and confirm permission for this
local reuse. Guide the user through selecting an authorized recording, confirming consent,
trying the editable generic sample, explicitly allowing model downloads if
needed, and generating. Selecting audio transfers it to the local loopback
service, not a cloud voice provider. The service shows factual stages and errors,
not invented percentages or estimated times.

Output noise reduction is enabled by default: have the user listen to the
cleaned MP3 first and keep raw WAV for comparison. The cleanup checkbox opts out
if filtering sounds worse. It only affects generated narration, never the
uploaded/saved reference; do not add a new consent prompt or filter that reference.
Then they can replace the sample with their own transcript and generate again.
Download desired outputs before stopping the service; generated session files are
temporary, but the saved voice survives restarts. The UI shows the active reference
and explicit replace/delete controls. New recordings need fresh permission;
the same saved voice does not. Do not run multiple service instances concurrently.
Point out the saved/uploaded voice indicator and AI-generated result label:
they identify the reference used, not verified identity or an original recording.
Never describe a mocked test as actual synthesis or a listening-quality review.

## CLI workflow

Use the venv Python with `scripts/narrate.py`:

1. `prepare --input <reference.m4a> --output <reference-24k.wav> --consent`
2. `generate --reference <reference-24k.wav> --script <script.txt> --output <raw.wav> --consent`
3. Recommended `clean --input <raw.wav> --output <clean.wav>` (skip only if requested)
4. `export --input <chosen.wav> --output <narration.mp3>`

Generation is cached-only by default. Add `--allow-download` only after
authorization. Use individually quoted paths and UTF-8 transcript files, not
shell-interpolated text. Keep personal files outside the repository. Existing
output paths are always refused; choose new filenames instead of deleting originals.

Once a voice has been authorized and saved in the UI, use
`generate --saved-voice --script <script.txt> --output <new.wav>` for later CLI
requests. Do not ask for another recording or redundant consent confirmation.
Explicit `--reference` usage still requires `--consent` and does not save a voice.

## Model contract and limitations

Only `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit` is supported. Reference and
model/output rates are checked against 24 kHz. Direct `model.generate` calls
receive reference samples without a reference transcript (speaker-embedding
mode). Do not substitute the `generate_audio` convenience wrapper, which may
download an additional large STT model when `ref_text` is absent.

English text is split into at most 500-character chunks at paragraph/word
boundaries, with 350 ms silence between chunks and a 1,200-token budget per chunk.
Even these chunks can truncate; listen against the complete script and shorten
paragraphs when words are missing. Waveform checks reject empty, non-finite,
near-silent or out-of-range results but do not prove completeness or quality.

Cleanup uses a 70 Hz high-pass, adaptive spectral denoising at `nr=12:nf=-40`
with noise tracking, and a non-boosting limiter. It targets generated hiss/noise,
not reference processing, and adds no model download. It is not source separation.
It may change the
voice, leave noise, or sound worse; compare raw and cleaned versions. It cannot
reliably repair robotic cadence, pronunciation or similarity. Report actual
failures and output paths, not success-shaped fallbacks.
