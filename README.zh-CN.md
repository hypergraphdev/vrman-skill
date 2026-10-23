# Hello Genesis Skill · 世界创作

[English (default)](README.md) · **简体中文**

Skill 和工具说明默认使用英文；回复、剧本与台词仍按用户选择的语言生成。中文版参考：[人物与说话视频](skills/vrman/references/avatars.zh-CN.md)、[剧本 JSON 规范](skills/vrman/references/script-format.zh-CN.md)。

让你的 AI 创作人物、搭建场景、编排演出，探索并保存自己的世界。

- 搜人物、物件、动作和声音，生成形象与说话视频。
- 分阶段搭场景：逐步看模型、对照图和进度，导出 GLB。
- 写剧本、选角、续写、修改布景、保存演出，导出带配音和字幕的整剧 MP4。
- 生成与扩展无限世界、共创物件、按需出题，与网页版共用世界和游戏存档。
- 查看任务进度与阶段预览，管理生成和导出任务。

例如：“搭一座河畔古镇，每搭好一步给我看；编一段店家上菜的戏，保存世界，并把演出导出 MP4。”

## 工作方式

在 AI 客户端里描述想法，逐步预览生成结果，再将作品保存到账号或导出文件。世界、人物、搭建与演出和网页版共用，预览链接可在电脑、手机和 VR 打开。

人物照片匹配在本机完成；场景参考图和生成请求提交到服务端。视频在运行 Skill 的电脑上合成，作品可导出为 GLB、PNG 或 MP4。模型生成需要账号开通相应权限。

接入参数、任务状态与运行限制见 [任务与 CLI 指南](skills/vrman/references/tasks.md)。

## 安装

**1. 准备环境**：Python 3.10+、Chrome（或 Playwright 自带的 Chromium）、ffmpeg。

```bash
git clone https://github.com/hypergraphdev/vrman-skill.git ~/vrman-skill
```

```bash
pip3 install -r ~/vrman-skill/requirements.txt
```

没装 Chrome 时运行下面这条：

```bash
python3 -m playwright install chromium
```

ffmpeg：Mac 上用 `brew install ffmpeg` 安装，Ubuntu 上用 `sudo apt install ffmpeg` 安装。

**2. 登录（每台电脑一次）**：输入 www.hg.network 的账号和密码，换一个 token 存到 `~/.config/vrman/token`（只有你自己能读）。
密码只发给 hg.network 的登录接口，不会保存。

```bash
python3 ~/vrman-skill/vrman.py login
```

用下面这条确认登录成功，也能看到用量：

```bash
python3 ~/vrman-skill/vrman.py whoami
```

**3. 接到你的 Agent**（选一种）：

### Claude Code

装成插件，Skill 和 MCP 工具一起装好：

```bash
claude plugin marketplace add hypergraphdev/vrman-skill
```

```bash
claude plugin install vrman@vrman-skill
```

也可以在 Claude Code 里输入 `/plugin marketplace add hypergraphdev/vrman-skill`，再输入 `/plugin install vrman@vrman-skill`。装完重开会话生效。

### Claude Desktop

打开「设置 → 开发者 → 编辑配置」，在 `claude_desktop_config.json` 里加上下面这段，然后重启 Claude Desktop：

```json
{
  "mcpServers": {
    "vrman": {
      "command": "python3",
      "args": ["/Users/你的用户名/vrman-skill/mcp_server.py"]
    }
  }
}
```

路径要写完整，不能用 `~`。如果提示找不到 `mcp` 模块，把 `python3` 换成装过依赖的那个 Python 的完整路径（用 `which python3` 查）。

### Cursor 及其他支持 MCP 的工具

配置写法相同。Cursor 的配置文件是 `~/.cursor/mcp.json`。

### 其他客户端

需要支持本地 stdio MCP 或本机命令执行。只有云端运行环境的客户端不能直接启动本机 Chromium 和 ffmpeg；可打开已保存作品的浏览器预览链接。

## MCP 工具

| 工具 | 做什么 |
|---|---|
| `tag_vocabulary` / `search_assets` | 各部位能用的标签词和调色板；按标签搜素材 |
| `list_voices` | 可用的发音人（目前开放微软的免费发音人） |
| `create_avatar_from_description` | 清单 → GLB，附一张头肩预览图，Agent 能直接看到效果 |
| `create_avatar_from_photo` | 照片 → GLB（生成相似形象 / 照片直出），附预览图 |
| `render_talking_video` | 文本 → MP4，说话的可以是照片、GLB 头像或现组装的头像；`style` 选口型方式（见下） |

新增创作工具：

| 工具 | 能力 |
|---|---|
| `get_studio_capabilities` | 协议、权限、操作参数与限额 |
| `search_library` | 全库语义检索，返回可使用的 ID 与元数据 |
| `start_creation` | 16 类创作操作：人物、动作、场景、世界、剧情、共创和教育 |
| `list_creation_tasks` / `get_creation_task` / `cancel_creation_task` | 找回任务、查询进度、分步图片、结果与取消 |
| `manage_project` | 角色、搭建、世界和演出的保存、读取、删除 |
| `compile_performance` / `edit_performance` | 剧本编译、布景调整及规则检查 |
| `import_scene` / `export_scene` / `preview_scene` | GLB 上传、下载与 PNG 预览 |
| `export_build` | 搭建作品合并导出 GLB |
| `render_performance_video` | 多场景整剧导出 H.264/AAC MP4 |

详细流程见 [Skill](skills/vrman/SKILL.md) 与 [任务和 CLI](skills/vrman/references/tasks.md)。无限世界中的即时行走、拾取、交易和 VR 点击仍在浏览器运行；共创返回计划，需要应用到场景或存档，不会自动控制另一个已打开的页面。

**素材库**：只有一个统一素材库（`refined-current`），不用选。它有精细头模、细丝头发、亚洲发型和五官、
能精调的五官（清单里写 `morphs`），还有手表、手机、皮肤细节。
以前的版本名（命令行 `--library`、MCP 的 `library` 写 `original`、`refined-v2` 等）还认，旧命令照样能跑。

**成人和儿童**（命令行 `--profile`、MCP 的 `profile`）：默认 `adult` 成人；`child` 儿童，用学龄儿童的头模、发型、衣服和五官。
儿童只有整套衣服（`outfit`），没有上衣、胡子、妆容、手表手机；第一次用要再下载一百多 MB 的儿童头模。

**口型方式**（命令行 `--style`、MCP 的 `style`）：

| 值 | 名字 | 特点 |
|---|---|---|
| `default` | 默认 | 复韵母在一个字里滑过去（好 = a→o） |
| `simple` | 优化精简 | 每个字一个口型，靠字与字之间的过渡 |
| `talkinghead` | TalkingHead | 相邻口型叠加过渡 |
| `natural` | 真人平滑 | 平滑衔接口型与下巴动作，按发音调整嘴唇开合 |

不指定输出路径时，结果写到 `~/vrman-output/`。

## 命令行

```bash
python3 ~/vrman-skill/vrman.py avatar --spec '{"gender":"female","hair":"long wavy","hair_color":"栗色","glasses":"round"}' --out a.glb --preview a.png
```

```bash
python3 ~/vrman-skill/vrman.py talk --text "大家好" --avatar a.glb --out hello.mp4
```

```bash
python3 ~/vrman-skill/vrman.py avatar --spec '{"gender":"male","hair":"v4-hair-03","morphs":{"v3_eye_spacing":0.3}}' --out m.glb --preview m.png
```

```bash
python3 ~/vrman-skill/vrman.py avatar --profile child --spec '{"gender":"female","hair":"高马尾","outfit":"卫衣"}' --out kid.glb --preview kid.png
```

还有 `tags`、`assets`、`voices`、`login`、`whoami` 几个命令，`--help` 可以看全部参数。
头像清单的写法见 [skills/vrman/SKILL.md](skills/vrman/SKILL.md)。

## 使用规则

- 用照片生成头像或视频，必须是**本人照片或已获本人授权**（命令行加 `--consent`，MCP 传 `consent=true`），否则直接报错。
  照片里是未成年人时，要由监护人使用或得到监护人同意。
- 视频右下角默认带「AI 生成」角标。对外发布时请保留，或用其他方式标明是 AI 生成的。

## 常见问题

| 现象 | 处理 |
|---|---|
| `token 无效或还没登录` | 运行 `vrman.py login` |
| `还没开通 VRMan Agent` | 请联系管理员开通 Agent 访问 |
| `统一素材库现在用不了` | 服务上的模型文件出了问题，稍后再试或联系管理员 |
| 找不到 Chrome | 运行 `python3 -m playwright install chromium` |
| `需要 ffmpeg 合成视频` | 安装 ffmpeg |
| 第一次很慢 | 在下载素材，第二次起会快很多 |

## 许可

代码采用 MIT 许可证。3D 素材和页面属于 VRMan 服务，只能通过服务使用。
