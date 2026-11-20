# Local voice narration

An Agent Skill for authorized local English voice narration on Apple Silicon:
**choose a recording, try editable sample text, listen, export, then supply your
own transcript**. Includes a loopback-only browser interface and a reusable CLI.

Generation uses MLX Audio and Qwen3-TTS locally. Setup downloads dependencies;
first use may download model files after confirmation. No cloud voice API is
required. Optional gentle filtering preserves the raw audio.

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

Or follow the [setup and interactive walkthrough](skills/local-voice-narration/README.md)
directly. Generation requires native Apple Silicon macOS, Python 3.11 and ffmpeg.
The local interface and CLI share the same pipeline.

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
