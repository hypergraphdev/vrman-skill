#!/usr/bin/env python3
"""Hello Genesis MCP (stdio): shared creative APIs, saved worlds and local GLB/MP4 exports.
Install the vrman-skill plugin or register this file as a local MCP server.
"""
import asyncio
import json
import sys
import time
import atexit
import base64
import uuid
import threading
from typing import Literal
from pathlib import Path

from mcp.server.fastmcp import FastMCP, Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vrman_agent import VRMan, catalog  # noqa: E402
from vrman_agent.remote import in_project  # noqa: E402
from vrman_agent.server import Service  # noqa: E402
from vrman_agent.creation import Creation, image_payload  # noqa: E402
from vrman_agent import local_tasks  # noqa: E402

OUTPUT = Path(__file__).resolve().parent / 'output' if in_project() else Path.home() / 'vrman-output'

mcp = FastMCP('vrman', instructions="""Hello Genesis 世界创作工具。先 get_studio_capabilities 查看账号可用能力。
- start_creation 接通场景、人物、动作、剧情、无限世界、共创和教育事件。长任务立即返回 task；用 get_creation_task 查询，cancel_creation_task 取消。
- build_scene_steps 的第一项任务准备参考图，完成后返回 nextTask；继续查询它可逐步看 GLB 和对照图，previewUrl 可在网页、手机和 VR 打开（需要同一账号登录）。
- manage_project 管理自己的角色、搭建、世界存档和演出。先读再改，世界 checkpoint 必须带当前 revision，冲突不能自动覆盖。
- compile_performance 将 vrman-script 编译为可演记录；render_performance_video 导出整剧 H.264/AAC MP4（本机后台任务）。
- 返回 queued/running 不等于完成；只有 done.result 指向的文件才是交付物。任务失效不能盲目重做付费生成。素材缺失、配音失败必须说明。
原有数字人工具：
- 描述 → 3D 头像：先用 tag_vocabulary / search_assets 了解各部位能用的英文标签词，
  再把描述写成清单交给 create_avatar_from_description，例如
  {"gender": "female", "hair": "long wavy", "hair_color": "栗色", "glasses": "round thin_frame", "outfit": "formal shirt white"}
- 照片 → 3D 头像：create_avatar_from_photo（需要用户确认照片是本人或已获授权，consent=true）
- 文本 → 说话视频：render_talking_video，说话的可以是照片、GLB 头像或现组装的清单头像；视频默认带「AI 生成」角标
- 只有一个统一素材库，library 不用传；清单里可以写 morphs 精调五官（键和取值范围见 tag_vocabulary 的 controls）。
  第一次要下载两百多 MB 的头模，要等几分钟
- 做小孩：各工具传 profile="child"（儿童只有整套衣服 outfit，没有 shirt、胡子、妆容、手表手机）；
  儿童素材的标签多是中文名，search_assets 可以直接搜中文词，如 query="卫衣"。搜素材和生成头像用同一个 profile
- 结果文件默认在 ~/vrman-output/，返回里有路径；头像会附一张预览图，看了不满意可以改清单重来
- 报「token 无效或还没登录」时，请用户在终端按提示运行 vrman.py login（用 www.hg.network 账号）""")


def output_path(path, suffix):
    if path:
        return str(Path(path).expanduser().resolve())
    OUTPUT.mkdir(parents=True, exist_ok=True)
    return str(OUTPUT / f'vrman-{time.strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:10]}{suffix}')


async def run(work):
    """Playwright 的同步接口不能在事件循环里用，放到线程里跑"""
    return await asyncio.to_thread(work)


def with_preview(result):
    """返回 JSON 结果，再附上预览图，Agent 能直接看到头像长什么样"""
    content = [json.dumps(result, ensure_ascii=False, indent=2)]
    if result.get('preview'):
        content.append(Image(path=result['preview']))
    return content


_creative_service = None
_service_lock = threading.Lock()


def creation():
    global _creative_service
    with _service_lock:
        if _creative_service is None:
            _creative_service = Service().__enter__()
            atexit.register(_creative_service.close)
    return Creation(_creative_service)


@mcp.tool()
async def get_studio_capabilities() -> dict:
    """Discover supported operations, payload fields, project types, account permissions and limits. No browser needed."""
    return await run(lambda: creation().capabilities())


@mcp.tool()
async def list_creation_tasks() -> dict:
    """Recover recent task IDs after reconnecting. Includes this account's server jobs and this computer's local exports."""
    def work():
        local = local_tasks.listing()
        try:
            return {'tasks': creation().service.get('/api/agent/tasks')['tasks'] + local}
        except RuntimeError as error:
            return {'tasks': local, 'serverError': str(error)}
    return await run(work)


@mcp.tool()
async def search_library(query: str, kind: Literal['props', 'avatars', 'motions', 'sounds'] = 'props',
                         era: str | None = None, profile: str | None = None, asset_type: str | None = None,
                         limit: int = 12) -> dict:
    """Semantic search across the current library; returns stable IDs, URLs, dimensions, tags and source metadata.
    Use these IDs in scenes/scripts; do not invent IDs. semanticPending means semantic indexing is still warming."""
    return await run(lambda: creation().search(query, kind, limit, era=era, profile=profile, asset_type=asset_type))


Operation = Literal['describe_character', 'compose_motion', 'sketch_scene', 'build_scene', 'refine_scene',
                    'build_scene_steps', 'design_world', 'extend_world', 'world_from_scene', 'world_from_photo',
                    'auto_world', 'review_world', 'cocreate_world', 'world_event', 'learning_question', 'write_story']


@mcp.tool()
async def start_creation(operation: Operation, payload: dict, image_path: str | None = None) -> dict:
    """Start a creative task using the same engine as the studio. See capabilities for operation payload fields.
    image_path attaches a local reference image (uploads it to the service). For a stepped scene use build_scene_steps.
    write_story: action outline/cast/segment; scriptLanguage zh/en controls narration, language controls dialogue.
    cocreate_world returns an additive plan; it is not applied until saved in a world checkpoint or used by the browser."""
    def work():
        data = {**payload, **({'image': image_payload(image_path)} if image_path else {})}
        return creation().start(operation, data)
    return await run(work)


@mcp.tool()
async def get_creation_task(task: str, since: int = 0, include_images: bool = True) -> list:
    """Read ai:/scene:/local: progress, errors and final artifacts. since is the number of scene stages already seen.
    If nextTask is returned, follow it: preparing a reference is not the completed scene. New stages include previews."""
    state = await run(lambda: local_tasks.status(task[6:]) if task.startswith('local:') else creation().task(task, since))
    pictures = []
    for stage in state.get('stages', []):
        compare = stage.pop('compare', '')
        if include_images and compare.startswith('data:image/'):
            pictures.append((stage['title'], compare))
    content = [json.dumps(state, ensure_ascii=False)]
    for title, data in pictures[-4:]:
        content += [title, Image(data=base64.b64decode(data.split(',')[1]), format='jpeg')]
    preview = state.get('result', {}).get('preview')
    if include_images and preview and Path(preview).is_file():
        content.append(Image(path=preview))
    return content


@mcp.tool()
async def cancel_creation_task(task: str) -> dict:
    """Cancel the selected task. Completed stages/files remain available. This never cancels another user's tasks."""
    return await run(lambda: local_tasks.cancel(task[6:]) if task.startswith('local:') else creation().task(task, cancel=True))


@mcp.tool()
async def manage_project(kind: Literal['world', 'build', 'character', 'performance'],
                         action: Literal['list', 'get', 'save', 'delete'] = 'list',
                         identifier: str | None = None, payload: dict | None = None) -> dict:
    """Account projects shared with the web. Save world as {world, checkpoint?, revision?, client?};
    build as {build, id?}; character as {character, id?}; performance as a compiled record or vrman-script (private copy).
    Keep world seed, items, gold, claims and creations; stale revision returns 409, never force-overwrite it.
    get/list before editing. delete removes only the specified saved project; use only when requested."""
    return await run(lambda: creation().project(kind, action, identifier, payload))


@mcp.tool()
async def compile_performance(script: dict, save: bool = False) -> dict:
    """Compile vrman-script v1 with the studio's casting, staging, motion and physical/common-sense checks.
    Returns a replayable record plus gaps/notes. save=true also stores a private copy and a browser replay link.
    Read the skill's references/script-format.md for the script schema."""
    return await run(lambda: creation().compile(script, save))


@mcp.tool()
async def edit_performance(payload: dict) -> dict:
    """Edit a performance's set: {id OR record, scene, props, things?, save?}. Actors and held objects move with furniture.
    Occupied seats cannot be deleted. save=true creates a new private performance."""
    return await run(lambda: creation().edit_performance(payload))


@mcp.tool()
async def import_scene(path: str) -> dict:
    """Upload a local GLB (max 14 MiB) for scene preview, editing and world generation. Returns a stable relative URL."""
    return await run(lambda: creation().upload_scene(path))


@mcp.tool()
async def export_scene(url: str, out_path: str | None = None) -> dict:
    """Download the original GLB from a scene build/upload URL, preserving the existing stable URL and lite delivery policy."""
    return await run(lambda: creation().download_scene(url, output_path(out_path, '.glb')))


@mcp.tool()
async def preview_scene(url: str, out_path: str | None = None) -> dict:
    """Render a PNG of any completed scene stage. Returns a local task; poll get_creation_task for the image."""
    return await run(lambda: local_tasks.start('scene_preview', {'url': url, 'out': output_path(out_path, '.png')}, creation().service))


@mcp.tool()
async def render_performance_video(identifier: str | None = None, record: dict | None = None,
                                    out_path: str | None = None, width: int = 1280, watermark: bool = True) -> dict:
    """Render a WHOLE performance (all scenes, dialogue, sounds, subtitles) into actual H.264/AAC MP4.
    Supply identifier OR record (compiled vrman-theater or vrman-script). Uses local Chromium and ffmpeg.
    Returns a persistent local task immediately; poll get_creation_task or cancel it. No silent success if dialogue fails."""
    if (identifier is None) == (record is None):
        raise ValueError('Supply identifier OR record')
    payload = {'id': identifier, 'record': record, 'out': output_path(out_path, '.mp4'), 'width': width, 'watermark': watermark}
    return await run(lambda: local_tasks.start('performance', payload, creation().service))


@mcp.tool()
async def export_build(identifier: str | None = None, build: dict | None = None, out_path: str | None = None) -> dict:
    """Export an assembled vrman-build project to a combined GLB, preserving transforms and spawn marker.
    Supply identifier OR build. Returns a local task, poll until done."""
    if (identifier is None) == (build is None):
        raise ValueError('Supply identifier OR build')
    return await run(lambda: local_tasks.start('build_export', {'id': identifier, 'build': build, 'out': output_path(out_path, '.glb')}, creation().service))


@mcp.tool()
def tag_vocabulary(part: str | None = None, library: str = catalog.DEFAULT_LIBRARY, profile: str | None = None) -> dict:
    """各部位（hair、eyes、eyebrow、beard、makeup、glasses、headwear、facewear、facemask、shirt、outfit、
    faceshape、eyeshape、noseshape、lipshape 等）常用的标签词，以及肤色、发色调色板的名字。
    写头像清单前先看看描述该用哪些词。controls 是能精调的五官（清单 morphs 的键和取值范围）。
    profile：adult 成人（默认）、child 儿童。library 不用传（只有统一素材库，旧版本名还认）。"""
    return {'tags': catalog.tag_vocabulary(part, library=library, profile=profile), 'colors': catalog.palettes(),
            'controls': catalog.controls(library, profile)}


@mcp.tool()
def search_assets(part: str, query: str = '', gender: str | None = None, limit: int = 8,
                  library: str = catalog.DEFAULT_LIBRARY, profile: str | None = None) -> list:
    """按标签词搜某个部位的素材，如 part="glasses", query="round thin_frame gold"。
    gender 填 female / male 时只返回该性别和通用款。返回素材名、风格、标签，清单里可以直接写素材名。
    profile="child" 搜儿童素材（标签多是中文名，可以搜中文词）。"""
    return catalog.search_assets(part, query, gender, limit, library=library, profile=profile)


@mcp.tool()
async def list_voices() -> list:
    """可用的发音人（voice 值、名字、说明、语言）。默认 zh-CN-XiaoxiaoNeural（晓晓，普通话女声）。"""
    def work():
        with VRMan() as vrman:
            return vrman.voices()
    return await run(work)


@mcp.tool()
async def create_avatar_from_description(spec: dict, out_path: str | None = None, full: bool = False,
                                         library: str = catalog.DEFAULT_LIBRARY, profile: str | None = None) -> list:
    """按清单组装 3D 头像，导出 GLB，并附一张头肩预览图。
    spec 的键：gender（female/male）、region（asian/western）、skin、hair_color（#RRGGBB 或调色板名），
    以及部位名（hair、eyes、glasses、outfit……）→ 标签词或素材名，写 "none" 表示不要；
    可加 morphs（精调值，如 {"v3_eye_spacing": 0.3}）。profile="child" 做儿童头像（spec 里写了 profile 时以 spec 为准）。
    也可传 {appearance: 已保存搭配}、{look: describe_character 的结果}，或 {preset: 共创人物返回的 character ID}。
    结果的 appearance 可存入 manage_project 的 character。照片贴图默认只在本机 GLB 中。
    full=false 导出说话精简版（只留口型和眨眼）；true 导出完整版（带全部表情和捏脸通道）。"""
    glb = output_path(out_path, '.glb')
    preview = str(Path(glb).with_suffix('.png'))

    def work():
        with VRMan() as vrman:
            return vrman.avatar_from_spec({'library': library, 'profile': profile, **spec}, glb, slim=not full,
                                          preview=preview)
    return with_preview(await run(work))


@mcp.tool()
async def create_avatar_from_photo(photo_path: str, gender: str, consent: bool, region: str = 'asian',
                                   photo_face: bool = False, out_path: str | None = None, full: bool = False,
                                   library: str = catalog.DEFAULT_LIBRARY, profile: str | None = None) -> list:
    """照片 → 3D 头像 GLB（附预览图）。照片在本机处理、不上传。
    consent 必须为 true：表示用户确认照片是本人或已获授权。gender 是照片里的性别（female/male），region 是五官风格。
    photo_face=false：按照片挑最像的素材（发型、肤色、五官比例）；true：照片直出，按照片捏脸形并把照片贴到脸上，更像本人。
    照片里是小孩时传 profile="child"，用儿童素材来配。"""
    glb = output_path(out_path, '.glb')
    preview = str(Path(glb).with_suffix('.png'))

    def work():
        with VRMan() as vrman:
            return vrman.avatar_from_photo(photo_path, glb, gender, region, photo_face, slim=not full,
                                           preview=preview, consent=consent, library=library, profile=profile)
    return with_preview(await run(work))


@mcp.tool()
async def render_talking_video(text: str, out_path: str | None = None, photo_path: str | None = None,
                               avatar_path: str | None = None, spec: dict | None = None,
                               voice: str = 'zh-CN-XiaoxiaoNeural', rate: str = '+0%', style: str = 'default',
                               width: int = 720, background: str = '#1a1d29', watermark: bool = True,
                               consent: bool = False, library: str = catalog.DEFAULT_LIBRARY,
                               profile: str | None = None) -> dict:
    """文本 → 说话视频 MP4（H.264 + AAC）。说话的三选一：photo_path（照片说话，需 consent=true）、
    avatar_path（GLB 头像，可用 create_avatar_* 的结果）、spec（按清单现组装 3D 头像）。
    style：default（复韵母在一个字里滑过去）、simple（优化精简：每字一个口型，靠字与字之间的过渡）、
    talkinghead（相邻口型叠加）或 natural（真人平滑：下巴按声母抬落，嘴唇只在 b/p/m/f 时合拢）；rate 如 "-20%"、"+20%"；watermark 默认在右下角加「AI 生成」。
    用 spec 现组装儿童头像时传 profile="child"。"""
    video = output_path(out_path, '.mp4')
    spec = {'library': library, 'profile': profile, **spec} if spec else None

    def work():
        with VRMan() as vrman:
            return vrman.talking_video(text, video, photo=photo_path, avatar=avatar_path, spec=spec, voice=voice,
                                       rate=rate, style=style, width=width, background=background,
                                       watermark=watermark, consent=consent)
    return await run(work)


if __name__ == '__main__':
    mcp.run()
