# Scenes and persistent worlds

## Asset selection and scene creation

Use `search_library(query, kind, era?, profile?, asset_type?, limit?)` for current props, avatar parts, motions and sounds, with metadata and exact stable IDs. `semanticPending` means semantic retrieval is warming; do not interpret it as proof that no asset exists. Distinguish a named character from a generic animal. Use the shared `cocreate_world` resolver for 孙悟空/猪八戒 rather than assembling a generic monkey/pig. Pass its returned `character` ID as `spec={preset:ID}` to `create_avatar_from_description` when a separate GLB is needed.

Choose an operation in `start_creation`:

- `sketch_scene`: `{text, era?}` produces an editable prop arrangement.
- `build_scene_steps`: `{text}` or `image_path` produces inspectable stages (silhouette, structure, form, material/assets). Show the returned progress URL and each newly completed stage, not every internal mesh operation.
- `build_scene`: `{text, mode:"new"|"mix"|"reuse", draw?}` with an optional reference. `refine_scene` accepts the returned `build`.
- `design_world`: `{text}` generates a world; `{world}` validates an edited world against shared rules.
- `auto_world`, `world_from_photo`, `world_from_scene`: use the capability fields. A scene-to-world request needs the studio's scene summary (bounds/spawn/parts): use the `scene` returned by `preview_scene`. After generation set `world.scene.url` to the same uploaded/built GLB URL before saving so reopening retains the original scene.
- `extend_world`: `{world}` continues the existing design. Preserve its seed and prior stretches.
- `review_world`: `{world, image, before?, fix?}` reviews an actual screenshot; the image must be of this result.

`import_scene(path)` uploads a local GLB up to 14 MiB. `preview_scene(url)` renders a PNG; `export_scene(url)` downloads the original GLB. Both use URLs returned by the service. `export_build(identifier OR build)` combines a saved build into GLB with its transforms and spawn marker.

An editable build is `{kind:"vrman-build",version:1,title,pieces:[{asset,name,at:[x,y,z],rot:[x,y,z],scale:[x,y,z]}]}`. A piece may instead use an uploaded `url`, with optional `node`. Metres and radians are used. Save with `manage_project("build","save",payload={build,id?})`. Its preview link opens the same build desk as the website.

## Save and co-create

`manage_project` handles `world`, `build`, `character`, and `performance`. World save payload is `{world, checkpoint?, revision?, client?}`. Get/list first. A design-only save preserves existing game progress; a checkpoint save requires the current revision. World saves include the same position, backpack, gold, defeat/collection claims and co-created objects as the website.

`cocreate_world` takes `{text,era?}` and returns a validated additive plan. It does not mutate a live browser. To retain it in a saved world, append `{id,at:[x,y,z],entities,text}` to `checkpoint.state.creations`, preserve the rest of the checkpoint, and save with the fetched revision. `at` is the absolute anchor; plan x/z positions are relative to it. Respect the existing 48-entity checkpoint limit. Read the saved checkpoint back and open its preview link to verify placement. Do not fabricate a checkpoint when the user already has progress.

For a world with no checkpoint, use the web preview to enter and create its initial game state before applying checkpoint edits. Live game interactions (walking, pickup, attack, trade, quizzes, map, VR clicks) run in that browser. Skill generation does not remotely control an unrelated open browser or grant game rewards by editing counters.

`world_event` accepts era/season/time/place/near/seen. `learning_question` accepts `subject` (english, translation, chinese, math, ai, computer, or the existing Chinese names), `id` such as `learning:2,3`, the world's 64-character hash and seed 1..999999. It returns a reviewed question on encounter, independent of story writing. Reward rules and coin sound remain in the game's existing runtime.

Characters save as `{character:{kind:"vrman-character",version:1,name,appearance},id?}`. `appearance` is the studio's `captureAppearance()` format, not the descriptive avatar spec: keep library/profile, picks, faceProfile, skin/hair and morphs. Do not confuse these two formats. Avatar creation results include `appearance` when available. Reuse it with `spec={appearance:...}`; a `describe_character` result can be assembled with `spec={look:...}`. Photo textures remain in the local GLB unless explicitly saved through the studio.
