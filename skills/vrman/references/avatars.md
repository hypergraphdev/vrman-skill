# Characters and talking videos

[简体中文](avatars.zh-CN.md)

## Current library

Use the single current library, `refined-current`; new commands can omit `--library`. Legacy names such as `original` and `refined-v2` are compatibility aliases. Adult and child assets are profiles of the same library, not separate versions. It includes detailed heads, hair, clothing, facial controls, watches, phones and skin details.

## Create a character from a description

1. Inspect available tags, palette names and morph ranges with `tag_vocabulary` or `vrman.py tags`. Narrow to a part with `vrman.py tags hair`; `controls` lists valid `morphs` keys and ranges.
2. Convert the description into tags from the library. Most adult tags are English. Search uncertain terms, for example `vrman.py assets hair "long wavy" --gender female`.
3. Assemble and preview:

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py avatar \
     --spec '{"gender":"female","hair":"long wavy","hair_color":"#6b4423","glasses":"round thin_frame","shirt":"casual"}' \
     --out avatar.glb --preview avatar.png
   ```

4. Inspect the actual preview image. If it misses the description, adjust tags or use the exact asset ID returned by search.

| Spec field | Value |
|---|---|
| `gender` | `female` or `male`; filters assets and supplies matching eyebrows when omitted |
| `profile` | `adult` (default) or `child`; also available as `--profile` |
| `region` | `asian` or `western` facial style |
| `skin`, `hair_color` | `#RRGGBB` or an exact palette name from `tags.colors`, including names such as `象牙` (ivory) and `栗色` (chestnut) |
| `hair`, `eyes`, `eyebrow`, `beard`, `makeup`, `glasses`, `headwear`, `facewear`, `facemask`, `shirt`, `outfit` | Library tags or an asset ID; `"none"` omits that part |
| `faceshape`, `eyeshape`, `noseshape`, `lipshape` | Tags for facial shape presets |
| `morphs` | Facial adjustments such as `{"v3_eye_spacing":0.3,"v2_jaw_width":-0.2}`; use ranges from `tags.controls` |
| `watch`, `handheld`, `skin_detail` | Accessories and skin details; hand accessories require a full-body `outfit` to be visible |

An `outfit` replaces a separate `shirt`. The default compact export retains speech and blink morphs; file size depends on the chosen assets. `--full` retains all expression and facial adjustment channels.

MCP also accepts `spec={appearance:...}` to restore a saved appearance, `spec={look:...}` for a `describe_character` result, or `spec={preset:...}` for a character ID returned by `cocreate_world`. Returned `appearance` can be saved as a character project; see [worlds.md](worlds.md).

### Children

Pass `--profile child` or `profile="child"` consistently to tag search, asset search and assembly:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py assets outfit 卫衣 --profile child --gender female
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py avatar --profile child \
  --spec '{"gender":"female","hair":"高马尾","outfit":"卫衣"}' --out child.glb --preview child.png
```

Here `高马尾` means a high ponytail and `卫衣` means a sweatshirt. Many child tags are Chinese; retain the actual library tags even when the request is in English.

Children use school-age heads, hair, clothing and facial features. They have complete `outfit` assets, without `shirt`, `beard`, `makeup`, `facemask`, `watch`, `handheld` or `skin_detail`. Morph ranges are narrower than for adults; read `tags --profile child`. First use also downloads the child head model.

## Create a character from a photo

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py avatar --photo me.jpg --gender male --consent --out me.glb --preview me.png
```

- `--gender` is required for photo matching. `--region asian|western` selects facial style; default is `asian`.
- Default mode chooses library parts and facial proportions resembling the photo.
- `--photo-face` shapes and textures the face from the photo for closer resemblance.
- Use `--profile child` for a child's photo.
- Original avatar photos are processed locally. Uploading references for scene or world generation is a separate workflow.

## Render a talking video

Choose one speaker source: `--photo`, `--avatar` (GLB), or `--spec` (assemble a character). Use `--profile child` for a child spec.

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py talk --text "Welcome to our new world." --voice en-US-GuyNeural --avatar avatar.glb --out hello.mp4
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py talk --text "Hello." --voice en-US-GuyNeural --photo me.jpg --consent --out portrait.mp4
```

Options:

- `--voice`: choose a voice from `vrman.py voices` matching the requested dialogue language. The API default remains `zh-CN-XiaoxiaoNeural` (Mandarin female); English documentation does not change that default.
- `--rate`: speech rate, such as `-20%` or `+20%`.
- `--style`: `default` transitions through diphthongs; `simple` uses one mouth shape per syllable; `talkinghead` blends adjacent shapes; `natural` smooths jaw movement and closes lips for b/p/m/f.
- `--width`: output width, default 720 pixels. A 3D avatar uses a square frame; a photo keeps its aspect ratio.
- `--background '#ffffff'`: background color for a 3D avatar.

Output is MP4 with H.264 video and AAC audio. To render a multi-character, multi-scene play, use `render_performance_video`; see [performances.md](performances.md).

## Photo authorization and output

Reuse a user's existing confirmation that a photo is theirs or that they have permission. If missing, ask before supplying `--consent` or `consent=true`; never invent authorization. For a minor, confirm the user is the guardian or has guardian permission. Do not source another person's photo from the web for this workflow.

Videos include an AI-generated label by default. Remove it only on the user's explicit request and retain disclosure when publishing. Save files to the requested location, or use the MCP default output directory when none is specified.

## Troubleshooting

| Message or symptom | Action |
|---|---|
| `token 无效或还没登录` | Ask the user to run `vrman.py login` in their terminal |
| `还没开通 VRMan Agent` | Ask the administrator to enable account access |
| `统一素材库现在用不了` | The service cannot load model files; retry later or contact the administrator |
| `没找到匹配` | Inspect tags and search again; retain `profile="child"` for child assets |
| `这类人物没有` | The part is unsupported for this profile; use a child's `outfit` instead of `shirt` |
| `不认识的发色/肤色` | Use a listed palette name or `#RRGGBB` |
| `需要 ffmpeg 合成视频` | Install ffmpeg locally |
| Chrome/browser not found | Run `python3 -m playwright install chromium` |
| `语音合成失败` | Speech synthesis failed; inspect the network/service error before retrying |
| No face detected | Use a clear, well-lit frontal photo with a sufficiently large face |
