---
name: vrman
description: 用 VRMan 数字人工具生成 3D 头像和说话视频。用户想「按描述捏一个 3D 头像」「用照片生成 3D 头像 / GLB」「让照片或头像说一段话、做成视频」「数字人播报视频」时使用。照片只在本机处理，不上传。
allowed-tools: Bash(python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py *)
---

# VRMan：描述 / 照片 → 3D 头像，文本 → 说话视频

所有操作都通过一个命令行完成，结果以 JSON 打印（出错时是 `{"error": "..."}`，退出码 1）：

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py <命令> ...
```

（不是以插件方式安装时，`${CLAUDE_PLUGIN_ROOT}` 换成 vrman-skill 仓库所在的目录。也可以直接用同名的 MCP 工具，参数一样。）

工具会在本机开一个看不见的 Chrome，打开 VRMan 工作室页面完成组装、导出和逐帧渲染。页面、素材和语音合成来自 VRMan 服务（www.hg.network）。
生成一个头像约 5 秒，第一次要下载素材会慢一些；视频耗时约等于语音时长加几秒。

## 0. 先登录（每台电脑一次）

报「token 无效或还没登录」时，**请用户自己在终端运行**下面的命令，输入 www.hg.network 的账号和密码。
不要替用户输入密码，也不要让用户把密码发到对话里。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py login
```

token 存在 `~/.config/vrman/token`。`vrman.py whoami` 查看当前登录的是谁、用了多少。
所有 www.hg.network 账号都能用（注册免费）；没有账号就请用户先到 www.hg.network 注册。

## 选素材版本

所有命令都可以加 `--library`（MCP 工具是 `library` 参数），搜素材、列标签词、生成头像要用同一个版本：

| 值 | 说明 |
|---|---|
| `original` | 原版（默认）：模型小、最快 |
| `refined-v2` | 精细版：细丝头发、皮肤细节，加了亚洲发型和五官 |
| `refined-v3` | 精细版 v3：再多一批亚洲发型、五官，可以精调五官（`morphs`） |
| `refined-v4` | 精细版 v4：更真实的皮肤，加了手表、手机、皮肤细节，精调项最多 |

用户要「更精细、更像真人」时用 `refined-v4`。精细版模型大，第一次生成要多下载一会儿。

## 1. 按描述生成 3D 头像

1. 先看各部位能用哪些标签词，以及肤色、发色调色板的名字：`vrman.py tags`，或者只看一个部位：`vrman.py tags hair`。
   用精细版时加 `--library refined-v4`，结果里的 `controls` 是这个版本能精调的五官。
2. 把用户的描述（中文也行）换成**英文标签词**，写成清单。拿不准的词先搜一下：`vrman.py assets hair "long wavy" --gender female`。
3. 生成：

   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py avatar \
     --spec '{"gender":"female","hair":"long wavy","hair_color":"栗色","glasses":"round thin_frame","shirt":"casual"}' \
     --out avatar.glb --preview avatar.png
   ```

4. **用 Read 看预览图**，确认像不像描述。不像就改清单重来：换标签词，或直接写 `assets` 搜到的素材名，如 `"hair": "hair-28"`。

清单的键：

| 键 | 值 |
|---|---|
| `gender` | `female` / `male`。决定按哪个性别挑素材；不写眉毛时自动配该性别的眉毛 |
| `region` | `asian` / `western`：五官风格 |
| `skin`、`hair_color` | `#RRGGBB`，或调色板里的名字（如 `象牙`、`栗色`，见 `tags` 的 `colors`） |
| `hair` `eyes` `eyebrow` `beard` `makeup` `glasses` `headwear` `facewear` `facemask` `shirt` `outfit` | 英文标签词或素材名；写 `"none"` 表示不要这个部位 |
| `faceshape` `eyeshape` `noseshape` `lipshape` | 脸形、眼形、鼻形、唇形的标签词 |
| `library` | 素材版本，见上面「选素材版本」；也可以用 `--library` |
| `morphs` | v3、v4 的五官精调：`{"v3_eye_spacing": 0.3, "v2_jaw_width": -0.2}`，键和取值范围见 `tags` 的 `controls` |
| `watch` `handheld` `skin_detail` | v4 才有：手表、手机、皮肤细节。手表、手机挂在手上，要穿全身套装（`outfit`）才看得到 |

`outfit` 是整套衣服，有它就不要 `shirt`。默认导出「说话精简版」（约 1 MB，只留口型和眨眼）。要带全部表情和捏脸通道的完整版，加 `--full`。

## 2. 用照片生成 3D 头像

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py avatar --photo me.jpg --gender male --consent --out me.glb --preview me.png
```

- `--gender` 必填，填照片里那个人的性别；`--region asian|western` 选五官风格（默认 asian）。
- `--library refined-v4` 用精细版的发型和五官来配，更细致。
- 默认是「生成相似 3D 形象」：按照片挑最像的发型、肤色、五官比例。
- 加 `--photo-face` 是「照片直出」：按照片捏脸形，并把照片贴到脸上，更像本人。

## 3. 文本 → 说话视频

说话的人三选一：

- `--photo`：照片说话；
- `--avatar`：GLB 头像，比如上面生成的；
- `--spec`：按清单现组装一个 3D 头像。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py talk --text "大家好，欢迎来到发布会。" --avatar avatar.glb --out hello.mp4
python3 ${CLAUDE_PLUGIN_ROOT}/vrman.py talk --text "你好" --photo me.jpg --consent --out hello.mp4
```

参数：

- `--voice`：发音人，`vrman.py voices` 列出全部。默认 `zh-CN-XiaoxiaoNeural`（晓晓，普通话女声），男声可用 `zh-CN-YunxiNeural`（云希）。
- `--rate`：语速，如 `-20%`、`+20%`。
- `--style`：口型播放方式。`default`（默认）复韵母在一个字里滑过去；`simple` 优化精简，每字一个口型、靠字与字之间的过渡；
  `talkinghead` 相邻口型叠加；`natural` 真人平滑，下巴按声母抬落、嘴唇只在 b/p/m/f 时合拢。
- `--width`：画面宽度，默认 720。3D 头像是方形画面，照片按原图比例。
- `--background '#ffffff'`：3D 头像的背景色。

输出 MP4（H.264 + AAC），手机和网页都能直接播放。

## 必须遵守

- **照片对应真人。** 用 `--photo` 之前要先问用户：照片是不是本人，或者已经得到本人授权。用户确认了才加 `--consent`，不能替用户默认同意。没有授权就别做，并说明原因。
- **视频默认在右下角加「AI 生成」角标。** 只有用户明确要求时才加 `--no-watermark`，并提醒对外发布时要标明是 AI 生成的。
- 不要拿网上找来的他人照片去生成头像或视频。
- 结果写到用户指定的位置。用户没说的话，用 `--out` 写到当前工作目录，或者问一句放在哪儿。

## 出错怎么办

| 报错 | 处理 |
|---|---|
| `token 无效或还没登录` | 请用户在终端运行上面的 login 命令 |
| `还没开通 VRMan Agent` | 这个账号被管理员停用了，请用户联系管理员 |
| `素材版本 … 现在用不了` | 服务上还没有这个版本的模型，先换 `original` |
| `xxx 没找到匹配「…」的素材` | 用 `tags <部位>` 或 `assets <部位>` 看看有哪些词，换个说法 |
| `不认识的发色/肤色` | 报错里列出了可用的名字，也可以直接写 `#RRGGBB` |
| `需要 ffmpeg 合成视频` | 请用户自己安装：Mac 上 `brew install ffmpeg`，Ubuntu 上 `sudo apt install ffmpeg` |
| 提示找不到 Chrome 或浏览器 | 请用户运行 `python3 -m playwright install chromium` |
| `语音合成失败` | 多半是网络问题，稍后再试 |
| 照片识别不出人脸 | 换一张正脸、光线好、脸部够大的照片 |
