# Tasks, files and CLI

Long operations started with `start_creation(operation, payload, image_path?)` return `ai:<id>` immediately. Synchronous operations such as `refine_scene` return their result directly; check the operation's `async` flag and required payload fields in `get_studio_capabilities`. All creation operations run through the same validated studio endpoints. `image_path` uploads that reference to the service.

After reconnecting, use `list_creation_tasks` (`vrman.py tasks`) to recover recent task IDs. Poll `get_creation_task(task, since=0)` about every 3 seconds. Scene stages contain stable GLB URLs, titles, comparison pictures, scores and human preview links. Set `since` to the number of stages already shown to avoid resending pictures. If the result contains `nextTask`, continue with it; the first job only prepared the reference. Use `cancel_creation_task` for that task. Cancelling the original completed reference task also cancels its scene task.

Server AI tasks currently expire 10 minutes after completion and do not resume computation after a server restart. Retrieve and save successful results promptly. Scene stages are checkpointed, so completed stages remain inspectable after interruption; report interruption rather than implying automatic resumption. Retrying creates a new task and may incur generation cost.

Local MP4/GLB/PNG jobs run in a separate worker process, with manifests under `~/vrman-output/.tasks` (`VRMAN_TASK_DIR` overrides). They survive MCP reconnection while their service remains reachable. Progress reports stage, segment and step; cancellation is cooperative and stops at the next boundary. Local jobs have a two-hour limit. Do not delete manifests or partial recordings while a worker is active. Final files are only reported after encoding succeeds. The computer must stay awake.

CLI fallback (JSON arguments may be JSON files; quote inline JSON for the shell):

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py capabilities
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py search '宋代长凳' --kind props --era 宋
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py create build_scene_steps --payload request.json
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py task ai:RETURNED_ID
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py task scene:RETURNED_ID --since 1
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py task scene:RETURNED_ID --cancel
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py project world list
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py project world get --id RETURNED_ID --out world.json
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py project world save --payload save.json
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py compile --script script.json --save
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py render --id RETURNED_ID --out performance.mp4
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py task local:RETURNED_ID
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py scene-import scene.glb
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py scene-export api/scene/file/RETURNED_HASH.glb --out scene.glb
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py preview api/scene/file/RETURNED_HASH.glb --out scene.png
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py export-build --build build.json --out build.glb
```

For local repository development, start `server.py` separately and set `VRMAN_URL` for asynchronous CLI tasks. A temporary service cannot outlive a CLI command. Installed clients default to the hosted service.

Errors: 401 means login expired; 403 means the account lacks this capability; 409 means a save conflict; 429 means concurrency limit. Preserve the existing result on these errors; retry only when the underlying condition has changed. Missing Chrome or ffmpeg is a local dependency error, not a failed scene generation. `queued`, `running`, `failed`, `error`, `cancelled`, and `done` must be distinguished in user updates.
