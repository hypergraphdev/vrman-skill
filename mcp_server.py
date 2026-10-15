#!/usr/bin/env python3
"""VRMan 的 MCP 服务（stdio）：让 Agent 直接调用「照片或描述 → 3D 头像」「文本 → 说话视频」

注册到 Claude Code（或装 GitHub 上的 vrman-skill 插件，自动注册）：
    claude mcp add vrman -- python3 <本目录>/mcp_server.py
每次调用会连 VRMan 服务（单独安装时连线上，要先 vrman.py login；在 vrman 项目里则用本地服务），
开一个无界面浏览器，用完关掉。结果文件默认写到 ~/vrman-output/（在 vrman 项目里是 agent/output/）。
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vrman_agent import VRMan, catalog  # noqa: E402
from vrman_agent.remote import in_project  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / 'output' if in_project() else Path.home() / 'vrman-output'

mcp = FastMCP('vrman', instructions="""VRMan 数字人工具：
- 描述 → 3D 头像：先用 tag_vocabulary / search_assets 了解各部位能用的英文标签词，
  再把描述写成清单交给 create_avatar_from_description，例如
  {"gender": "female", "hair": "long wavy", "hair_color": "栗色", "glasses": "round thin_frame", "outfit": "formal shirt white"}
- 照片 → 3D 头像：create_avatar_from_photo（需要用户确认照片是本人或已获授权，consent=true）
- 文本 → 说话视频：render_talking_video，说话的可以是照片、GLB 头像或现组装的清单头像；视频默认带「AI 生成」角标
- 结果文件默认在 ~/vrman-output/，返回里有路径；头像会附一张预览图，看了不满意可以改清单重来
- 报「token 无效或还没登录」时，请用户在终端按提示运行 vrman.py login（用 www.hg.network 账号）""")


def output_path(path, suffix):
    if path:
        return str(Path(path).expanduser().resolve())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    return str(OUTPUT / f'vrman-{time.strftime("%Y%m%d-%H%M%S")}{suffix}')


async def run(work):
    """Playwright 的同步接口不能在事件循环里用，放到线程里跑"""
    return await asyncio.to_thread(work)


def with_preview(result):
    """返回 JSON 结果，再附上预览图，Agent 能直接看到头像长什么样"""
    content = [json.dumps(result, ensure_ascii=False, indent=2)]
    if result.get('preview'):
        content.append(Image(path=result['preview']))
    return content


@mcp.tool()
def tag_vocabulary(part: str | None = None) -> dict:
    """各部位（hair、eyes、eyebrow、beard、makeup、glasses、headwear、facewear、facemask、shirt、outfit、
    faceshape、eyeshape、noseshape、lipshape）常用的英文标签词，以及肤色、发色调色板的名字。
    写头像清单前先看看描述该用哪些词。"""
    return {'tags': catalog.tag_vocabulary(part), 'colors': catalog.palettes()}


@mcp.tool()
def search_assets(part: str, query: str = '', gender: str | None = None, limit: int = 8) -> list:
    """按英文标签词搜某个部位的素材，如 part="glasses", query="round thin_frame gold"。
    gender 填 female / male 时只返回该性别和通用款。返回素材名、风格、标签，清单里可以直接写素材名。"""
    return catalog.search_assets(part, query, gender, limit)


@mcp.tool()
async def list_voices() -> list:
    """可用的发音人（voice 值、名字、说明、语言）。默认 zh-CN-XiaoxiaoNeural（晓晓，普通话女声）。"""
    def work():
        with VRMan() as vrman:
            return vrman.voices()
    return await run(work)


@mcp.tool()
async def create_avatar_from_description(spec: dict, out_path: str | None = None, full: bool = False) -> list:
    """按清单组装 3D 头像，导出 GLB，并附一张头肩预览图。
    spec 的键：gender（female/male）、region（asian/western）、skin、hair_color（#RRGGBB 或调色板名），
    以及部位名（hair、eyes、glasses、outfit……）→ 英文标签词或素材名，写 "none" 表示不要。
    full=false 导出说话精简版（约 1 MB，只留口型和眨眼）；true 导出完整版（带全部表情和捏脸通道）。"""
    glb = output_path(out_path, '.glb')
    preview = str(Path(glb).with_suffix('.png'))

    def work():
        with VRMan() as vrman:
            return vrman.avatar_from_spec(spec, glb, slim=not full, preview=preview)
    return with_preview(await run(work))


@mcp.tool()
async def create_avatar_from_photo(photo_path: str, gender: str, consent: bool, region: str = 'asian',
                                   photo_face: bool = False, out_path: str | None = None, full: bool = False) -> list:
    """照片 → 3D 头像 GLB（附预览图）。照片在本机处理、不上传。
    consent 必须为 true：表示用户确认照片是本人或已获授权。gender 是照片里的性别（female/male），region 是五官风格。
    photo_face=false：按照片挑最像的素材（发型、肤色、五官比例）；true：照片直出，按照片捏脸形并把照片贴到脸上，更像本人。"""
    glb = output_path(out_path, '.glb')
    preview = str(Path(glb).with_suffix('.png'))

    def work():
        with VRMan() as vrman:
            return vrman.avatar_from_photo(photo_path, glb, gender, region, photo_face, slim=not full,
                                           preview=preview, consent=consent)
    return with_preview(await run(work))


@mcp.tool()
async def render_talking_video(text: str, out_path: str | None = None, photo_path: str | None = None,
                               avatar_path: str | None = None, spec: dict | None = None,
                               voice: str = 'zh-CN-XiaoxiaoNeural', rate: str = '+0%', style: str = 'default',
                               width: int = 720, background: str = '#1a1d29', watermark: bool = True,
                               consent: bool = False) -> dict:
    """文本 → 说话视频 MP4（H.264 + AAC）。说话的三选一：photo_path（照片说话，需 consent=true）、
    avatar_path（GLB 头像，可用 create_avatar_* 的结果）、spec（按清单现组装 3D 头像）。
    style：default（复韵母在一个字里滑过去）、simple（优化精简：每字一个口型，靠字与字之间的过渡）或
    talkinghead（相邻口型叠加）；rate 如 "-20%"、"+20%"；watermark 默认在右下角加「AI 生成」。"""
    video = output_path(out_path, '.mp4')

    def work():
        with VRMan() as vrman:
            return vrman.talking_video(text, video, photo=photo_path, avatar=avatar_path, spec=spec, voice=voice,
                                       rate=rate, style=style, width=width, background=background,
                                       watermark=watermark, consent=consent)
    return await run(work)


if __name__ == '__main__':
    mcp.run()
