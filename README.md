# Local voice narration

An Agent Skill for authorized local English voice narration on Apple Silicon:
**choose a recording, try editable sample text, listen, export, then supply your
own transcript**. Includes a loopback-only browser interface and a reusable CLI.

Generation uses MLX Audio and Qwen3-TTS locally. Setup downloads dependencies;
first use may download model files after confirmation. No cloud voice API is
required. Optional gentle filtering preserves the raw audio.

## Quick start: try it in your browser

You need **native Apple Silicon macOS, Python 3.11 and ffmpeg** installed.
Check `python3.11 --version`, `uname -m` (should print `arm64`) and
`ffmpeg -version` before starting.

From the repository root:

```sh
cd skills/local-voice-narration
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/serve.py
```

The install command downloads Python dependencies into an isolated environment;
it does not download the speech model yet. Open **http://127.0.0.1:8765** in your
browser once the server prints its address. No agent client is needed to try
the interface directly.

## Your first narration

1. **Choose your recording.** Select a clear, short, single-speaker audio file
   up to 16 MiB and confirm that it is your voice or explicitly authorized.
   The recording transfers only to the local service on your computer.
2. **Try the sample.** The text box already contains a generic sample you can
   edit. You do not need a transcript of the reference recording.
3. **Approve the first model download.** If the model is not cached, select
   the download-permission checkbox. Missing files are fetched from
   [Hugging Face](https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit);
   this downloads model files, not uploads of your voice. Without permission,
   generation stays cached-only and reports missing files explicitly.
4. **Generate and listen.** The service prepares your reference, loads the model,
   generates speech in chunks, optionally applies gentle filtering, and encodes
   MP3. The page shows stages and errors; speed depends on your machine.
5. **Download your audio.** Preview the result and save the raw WAV, optional
   cleaned WAV, and MP3. Listen for missing words and pronunciation problems.
6. **Use your own transcript.** Replace the sample text with what you want read
   aloud and generate another take. Save current outputs before starting again.

Model files normally remain in `~/.cache/huggingface/hub` and are reused on
later runs; environment settings can change this location. Initial dependency
and model downloads need internet and free disk space. Download sizes and
completion times have not been independently measured here.

**Save your downloads before pressing Ctrl-C to stop the server.** UI audio is
stored in a temporary session directory and removed on normal shutdown.
To reopen the interface later, run `.venv/bin/python scripts/serve.py` from the
same skill directory; you do not need to recreate the environment each time.
The interface is single-user and loopback-only: do not expose or forward its port.

## Install for GitHub Copilot

Copy the entire `skills/local-voice-narration` directory into your project's
`.github/skills/local-voice-narration`, or into
`~/.copilot/skills/local-voice-narration` for personal use in compatible clients.
Keep `SKILL.md`, `README.md`, `requirements.txt` and `scripts/` together.
Skill availability/discovery depends on your client/version; see
[GitHub's documentation](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills).
Other Agent Skills clients can use their supported skill install location.

Ask your agent:

> Use local-voice-narration to open the local narration interface. Explain setup
> and downloads before I choose my authorized recording and try the sample.

See the [detailed setup, CLI examples and troubleshooting](skills/local-voice-narration/README.md)
for non-interactive use and installation problems. The local interface and CLI
share the same pipeline.

## Privacy and limitations

Use only your own voice or get the speaker's explicit permission. Do not
impersonate people deceptively; disclose synthetic narration when sharing.
Keep recordings, private scripts, embeddings, generated media and model caches
outside version control. The repository bundles only tooling and generic tests.

Audio selection transfers data to the local loopback service, not a cloud
voice provider. Inference is local, but package/model downloads make external
requests; this is not an absolute no-network guarantee. Cached-only generation
is the default. No extra automatic speech-recognition model is required.

Always listen to the whole result: generation can omit/mispronounce words or
sound synthetic. Filtering is not proof of perceptual quality. Temporary UI
outputs must be downloaded before stopping the server.

## License

**Pending owner selection.** No project license is granted yet. Public visibility
alone does not grant general permission to reuse or redistribute this code.
Choose a license before promoting it as an openly reusable release. Models and
dependencies have their own separate terms.
