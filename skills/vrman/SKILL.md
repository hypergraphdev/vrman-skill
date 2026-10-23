---
name: vrman
description: Use Hello Genesis (VRMan) to create 3D characters, build and inspect scenes step by step, write and perform stories, edit and save explorable worlds, search assets, and export GLB or whole-performance MP4. Use for requests to operate this studio through AI, including 场景搭建、剧情演出、无限世界、共创、数字人和说话视频. This skill operates the existing studio, not arbitrary websites or video editing applications.
---

# Hello Genesis · World creation

Use the MCP tools when available; the CLI is the fallback. The installed repository contains the same client for both. `${CLAUDE_PLUGIN_ROOT}` means that repository's root; outside a Claude plugin, substitute its actual path.

Start with `get_studio_capabilities` (`python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py capabilities`). It reports this account's permissions, operation payloads, time limits and protocol version. Model-backed creation needs the same account entitlement as the web studio. Agent access does not grant administration or voice cloning.

If authentication expires, ask the user to run `vrman.py login` in their own terminal; do not request their password in chat. Never put tokens in links or deliverables. Human preview links use the ordinary studio login and work on desktop, mobile and VR; local rendering runs on the computer hosting MCP.

## Choose the workflow

- **Characters / talking portraits:** read [references/avatars.md](references/avatars.md). Existing tools retain adult/child profiles, local photo processing, GLB previews and H.264/AAC talking videos. `describe_character` resolves natural-language appearances; named characters such as 孙悟空 use the `cocreate_world` resolver and its returned character preset.
- **Scenes, assembled builds, worlds, educational events and saves:** read [references/worlds.md](references/worlds.md). Search first using `search_library`; use stable returned asset IDs. It covers props, characters, motions and sounds. Do not silently substitute unrelated assets.
- **Stories and full performance videos:** read [references/performances.md](references/performances.md). For authored script JSON, read [references/script-format.md](references/script-format.md). Compile with the studio's shared staging rules; do not bypass its physical and social checks by inventing engine coordinates.
- **CLI, progress, cancellation, failure recovery and output files:** read [references/tasks.md](references/tasks.md).

## Completion and continuity

A returned task is not a completed creation. Poll `get_creation_task` at the suggested interval, show new stage images and the progress link, and stop on a terminal state. A `nextTask` means the reference is ready and scene modelling has begun: follow that task. Do not rerun paid generation merely because one poll failed. On an expired/interrupted task, retain completed stages and explain what must be retried.

Use `manage_project` to save work that the user wants to continue in the studio. Keep IDs, world seeds and the full checkpoint: position, gold, items, claims and co-created objects. Read before updating. On revision conflict, fetch the current version and reconcile with the user's intended changes; never silently overwrite another device's progress. Deletion is only for the project the user requested to remove.

For each deliverable, verify the actual image/model/video or saved record. Report material missing assets, skipped actions, unresolved scene warnings and failed audio. A script JSON download is not a video; a preview URL is not a downloadable MP4. Only a completed render's `result.video` is the MP4 file.

Avatar photo matching stays local. Reference images submitted for scene/world generation and saved projects go to the authenticated service. Keep this distinction clear when a user's privacy constraints matter. The current asset library remains `refined-current`; use existing lite delivery and stable URLs, not duplicate asset libraries.
