# Local voice narration

An Agent Skill for authorized local English voice narration on Apple Silicon:
**choose a recording, try editable sample text, listen, export, then supply your
own transcript**. Includes a loopback-only browser interface and a reusable CLI.

Generation uses MLX Audio and Qwen3-TTS locally. Setup downloads dependencies;
first use may download model files after confirmation. No cloud voice API is
required. Optional gentle filtering preserves the raw audio.

## Listen to the original narration takes

These are the original finished conversions, published with the voice owner's
approval. Each is **AI-generated narration using an authorized voice sample**,
not an original speaker recording. All six read the same transcript:

> The thing about Luffy is that he lives so completely in the moment. Of all the
> characters in any anime, he’s the one who isn’t tortured by his past. He has a
> painful past, but he isn’t tormented by it. And he has a goal for the future,
> but he isn’t so fixated on that goal that he loses sight of what’s right in
> front of him. He’s always living fully in the moment. Sometimes, that makes
> him hilarious, because he does exactly what he wants to do right then. And
> sometimes, it means he’s the only one who sees clearly enough, and has his
> priorities straight enough, to do what needs to be done.

### Conversational

[Download MP3](samples/luffy-conversational.mp3)

https://github.com/user-attachments/assets/cf367aca-2ca0-4825-890d-301a4c9bdc2f

### Reflective — more deliberate pauses

[Download MP3](samples/luffy-reflective.mp3)

https://github.com/user-attachments/assets/3cc76b4b-7fd5-464b-a48a-e9d16b9f16f9

### Lively — brisker delivery

[Download MP3](samples/luffy-lively.mp3)

https://github.com/user-attachments/assets/c57eab7c-c5be-43a8-bf5e-3de80e225910

### Unhurried

[Download MP3](samples/luffy-unhurried.mp3)

https://github.com/user-attachments/assets/2ee7ca04-5871-4f52-adcb-7d3ae6f81307

### Flowing — shorter pauses

[Download MP3](samples/luffy-flowing.mp3)

https://github.com/user-attachments/assets/3e70cc3b-5e61-4465-aec6-eb402843c472

### Measured

[Download MP3](samples/luffy-measured.mp3)

https://github.com/user-attachments/assets/68882a34-3792-4d78-b3f1-f999f78f2e4b

The video players wrap the full original MP3 audio in a static labeled cover
(H.264/AAC) for GitHub playback. They introduce no new speech or voice reference.
If your GitHub client does not render a player, use the MP3 download link.
The [plain-text transcript](samples/luffy-transcript.txt) is available separately.

**Provenance:** generated locally with
`mlx-community/Qwen3-TTS-12Hz-0.6B-Base-8bit` via MLX Audio using an authorized
voice reference. These are independently sampled takes with varied paragraph
pauses and modest post-generation tempo adjustments, then gentle noise cleanup
and MP3 export. They are not an exact transfer of someone else's expression or
proof of speaker identity.

The labels describe these existing exports, **not mode presets currently
implemented in the skill UI**. The interface still starts with its generic
editable sample text; paste this transcript if you want to narrate it yourself.
Outputs will vary rather than reproduce these takes exactly.

Only the six approved finished takes and their playback wrappers are public. The source recording, raw WAVs,
speaker representations, and saved private reference are not included. These
original conversions replace the earlier generic eSpeak export demos.

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
   Approve local saving once. The recording transfers only to the local service
   on your computer; its prepared reference is saved privately for reuse.
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
   aloud and generate another take. Your saved voice is reused automatically,
   including after browser/service restarts; no repeated upload or speaker
   permission prompt is needed for that same reference. Save current outputs first.

The page shows the active saved voice and **Replace saved voice** / **Delete saved
voice** controls. Replacement requires permission for the new recording; deletion
means you must upload and authorize another voice before generating again.
The prepared reference stays at
`~/Library/Application Support/local-voice-narration/authorized-reference.wav`,
outside this repository, until replaced or deleted. Use only on your trusted
local account; deleting a file is not a guarantee of secure erasure or removal
from backups. Generated outputs remain temporary and are not saved with the voice.

The interface explicitly indicates when your saved or newly uploaded voice sample
is used. Results are labeled **AI-generated narration using your voice sample**:
this is an AI recreation from the authorized reference, not an original recording
or verification of the speaker's identity.

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
outside version control. Only the explicitly approved finished narration demos
above are included alongside the tooling and tests; personal references remain
excluded from version control.

Audio selection transfers data to the local loopback service, not a cloud
voice provider. Inference is local, but package/model downloads make external
requests; this is not an absolute no-network guarantee. Cached-only generation
is the default. No extra automatic speech-recognition model is required.

Always listen to the whole result: generation can omit/mispronounce words or
sound synthetic. Filtering is not proof of perceptual quality. Temporary UI
outputs must be downloaded before stopping the server. The saved reference,
unlike generated session audio, remains available for subsequent narration.

## License

**Pending owner selection.** No project license is granted yet. Public visibility
alone does not grant general permission to reuse or redistribute this code.
Choose a license before promoting it as an openly reusable release. Models and
dependencies have their own separate terms.
