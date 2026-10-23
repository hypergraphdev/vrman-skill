# Hello Genesis Skill · World creation

**English (default)** · [简体中文](README.zh-CN.md)

Bring world creation to your AI: create characters, build scenes, direct performances and save worlds to explore.

- Search characters, props, motions and sounds; create avatars and talking videos.
- Build scenes in stages, inspect each model and comparison image, and export GLB.
- Write, cast, continue and edit performances; export a complete performance as MP4 with dialogue and subtitles.
- Create and extend worlds, plan additions, generate educational encounters, and share saved projects and game progress with the web studio.
- Follow progress, preview completed stages and manage creation and export tasks.

For example: “Build a riverside town and show me each completed stage. Direct a scene where an innkeeper serves a guest, save the world, and export the performance as MP4.”

## How it works

Describe your idea in your AI client, preview each result, then save your project or export a file. Characters, builds, performances and world checkpoints are shared with the web studio. Open preview links on desktop, mobile or VR using the same account.

Avatar photo matching runs locally; scene references and generation requests go to the authenticated service. Videos are rendered on the computer running the Skill. Export models as GLB, previews as PNG and videos as MP4. Model-backed generation requires the corresponding account access.

For integration parameters, task states and operating limits, see the [task and CLI guide](skills/vrman/references/tasks.md).

Documentation and tool descriptions default to English. Replies and generated content follow the user's language choices; script narration and dialogue languages remain separate options. Some asset tags and API enum values are Chinese and must be used exactly as returned by the service.

## Install

### 1. Prepare the environment

Use Python 3.10+, Chrome or Playwright Chromium, and ffmpeg.

```bash
git clone https://github.com/hypergraphdev/vrman-skill.git ~/vrman-skill
pip3 install -r ~/vrman-skill/requirements.txt
```

If Chrome is unavailable:

```bash
python3 -m playwright install chromium
```

Install ffmpeg with `brew install ffmpeg` on macOS or `sudo apt install ffmpeg` on Ubuntu.

### 2. Sign in on this computer

```bash
python3 ~/vrman-skill/vrman.py login
python3 ~/vrman-skill/vrman.py whoami
```

Enter your hg.network credentials in your own terminal. The password is sent only to the login endpoint and is not saved. The resulting token is stored privately at `~/.config/vrman/token`. `whoami` checks the account and usage; do not share the token.

### 3. Connect your AI client

**Claude Code:** install the plugin to load both the Skill and MCP tools.

```bash
claude plugin marketplace add hypergraphdev/vrman-skill
claude plugin install vrman@vrman-skill
```

The corresponding `/plugin marketplace add` and `/plugin install` commands can also be entered inside Claude Code. Restart the session after installation or an update.

**Claude Desktop:** add the following to `claude_desktop_config.json` through Settings → Developer → Edit Config, then restart the client.

```json
{
  "mcpServers": {
    "vrman": {
      "command": "python3",
      "args": ["/absolute/path/to/vrman-skill/mcp_server.py"]
    }
  }
}
```

Replace the example path with the absolute path on your computer; `~` is not expanded here. If Python cannot find `mcp`, use the absolute path of the Python interpreter where the dependencies were installed.

**Cursor and other MCP clients:** use the same stdio configuration. Cursor reads `~/.cursor/mcp.json`. Clients need local stdio MCP or local command execution. A cloud-only client cannot directly launch Chromium and ffmpeg on your computer; saved projects can still be opened through their browser preview links.

## MCP tools

| Tool | Purpose |
|---|---|
| `get_studio_capabilities` | Discover protocol, permissions, operation fields and limits |
| `tag_vocabulary` / `search_assets` | Inspect avatar tags, color palettes and facial controls; search individual parts |
| `search_library` | Search the current library for usable IDs and metadata |
| `list_voices` | List available voices, languages and descriptions |
| `create_avatar_from_description` | Assemble a GLB from a spec, saved appearance or character preset, with a preview |
| `create_avatar_from_photo` | Create a matched or photo-textured avatar locally, with a preview |
| `render_talking_video` | Render one speaking portrait or avatar as H.264/AAC MP4 |
| `start_creation` | Start 16 types of character, motion, scene, world, story, co-creation and educational operations |
| `list_creation_tasks` / `get_creation_task` / `cancel_creation_task` | Recover task IDs, inspect progress and stage images, retrieve results or cancel |
| `manage_project` | Save, list, read and delete characters, builds, worlds and performances |
| `compile_performance` / `edit_performance` | Compile scripts with staging rules and edit performance sets |
| `import_scene` / `export_scene` / `preview_scene` | Upload or download scene GLB and render a PNG preview |
| `export_build` | Combine an assembled build into a GLB |
| `render_performance_video` | Export all supplied performance segments as H.264/AAC MP4 |

Read the [Skill](skills/vrman/SKILL.md) for workflow routing, [worlds](skills/vrman/references/worlds.md) for creation and persistence, [performances](skills/vrman/references/performances.md) for acting and video, and [tasks and CLI](skills/vrman/references/tasks.md) for progress and recovery.

Explore, collect and trade in the browser. Apply co-created additions to a scene or saved world, and choose which performance segments to export. The workflow guides cover each step.

## Characters and speech

There is one current library, `refined-current`; omit `library` for new requests. Old names such as `original` and `refined-v2` remain compatibility aliases. The library contains detailed heads, hair, clothing, accessories and facial morph controls.

Use `profile="adult"` (default) or `profile="child"`. Keep the same profile when searching and assembling. Children use school-age heads, hair and outfits. They have complete `outfit` assets rather than separate `shirt` parts and do not support beards, makeup, watches or handheld accessories. Many child tags are Chinese: use the actual tags or IDs returned by the tools. See the [avatar guide](skills/vrman/references/avatars.md).

| Lip-sync style | Behavior |
|---|---|
| `default` | Transition through diphthongs within a syllable |
| `simple` | Use one mouth shape per syllable with transitions between syllables |
| `talkinghead` | Blend adjacent mouth shapes |
| `natural` | Smooth jaw movement and lip closure for b/p/m/f sounds |

Installed clients default to `~/vrman-output/`; repository development uses `agent/output/` for MCP output. Explicit output paths override the default.

## CLI examples

Create an avatar and use an English voice for a talking video:

```bash
python3 ~/vrman-skill/vrman.py avatar --spec '{"gender":"female","hair":"long wavy","hair_color":"#6b4423","glasses":"round"}' --out avatar.glb --preview avatar.png
python3 ~/vrman-skill/vrman.py talk --text "Hello, welcome to this new world." --voice en-US-GuyNeural --avatar avatar.glb --out hello.mp4
```

Inspect the creation capabilities and manage saved worlds:

```bash
python3 ~/vrman-skill/vrman.py capabilities
python3 ~/vrman-skill/vrman.py project world list
python3 ~/vrman-skill/vrman.py compile --script script.json --save
python3 ~/vrman-skill/vrman.py render --id RETURNED_ID --out performance.mp4
python3 ~/vrman-skill/vrman.py task local:RETURNED_ID
```

Use the returned IDs, not the example placeholders. See `vrman.py --help` and the [task guide](skills/vrman/references/tasks.md) for all commands. Avatar fields are documented in the [avatar guide](skills/vrman/references/avatars.md); authored performance JSON uses the [script format](skills/vrman/references/script-format.md).

## Photo use and disclosure

- Photo-based avatars and videos require the subject's authorization: supply `--consent` or `consent=true` only after the user confirms it is their photo or they have permission. For a minor, the user must be the guardian or have guardian permission. Reuse authorization already given in the conversation.
- Videos include an AI-generated label by default. Retain it or otherwise disclose AI generation when publishing.

## Troubleshooting

Service error text may still be in Chinese. Common messages:

| Message or symptom | Action |
|---|---|
| `token 无效或还没登录` | Run `vrman.py login` in your terminal |
| `还没开通 VRMan Agent` | Ask the administrator to enable Agent access for the account |
| `统一素材库现在用不了` | The service cannot load the model library; retry later or contact the administrator |
| Chrome not found | Run `python3 -m playwright install chromium` |
| `需要 ffmpeg 合成视频` | Install ffmpeg |
| Slow first run | Allow the initial asset downloads to finish |
| HTTP 409 on save | Read the latest checkpoint and reconcile; do not overwrite another device's progress |
| Interrupted generation | Retain completed stages and inspect task status before starting another paid generation |

## License

Code is MIT licensed. The 3D assets and studio pages belong to the VRMan service and are available through that service.
