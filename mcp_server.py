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

mcp = FastMCP('vrman', instructions="""Hello Genesis world creation tools. Start with get_studio_capabilities to discover this account's permissions and operation fields.
Documentation and tool descriptions default to English. Respond in the user's language; preserve their narration and dialogue language choices. Keep API keys, asset IDs and enum values exactly as returned, including required Chinese values.
- start_creation supports characters, motions, scenes, stories, explorable worlds, co-creation and educational encounters. Long operations return a task; inspect it with get_creation_task and cancel it with cancel_creation_task.
- build_scene_steps first prepares a reference and returns nextTask. Follow it to see stage GLBs and comparison images. previewUrl opens in desktop, mobile or VR browsers with the same account login.
- manage_project shares characters, builds, world checkpoints and performances with the web studio. Read before editing; checkpoint updates need the current revision. Reconcile conflicts instead of overwriting progress.
- compile_performance compiles vrman-script into a replayable record. render_performance_video exports all supplied segments as H.264/AAC MP4 in a local background task.
- queued/running is not completion. Deliver files only from a completed task's result. Do not blindly repeat paid generation after a lost poll. Report missing assets, staging warnings and failed audio.
Character and talking-video tools:
- Inspect tag_vocabulary / search_assets before writing a character spec. Example: {"gender":"female","hair":"long wavy","hair_color":"#6b4423","glasses":"round thin_frame","outfit":"formal shirt white"}.
- create_avatar_from_photo processes the photo locally and requires the user's existing or newly obtained authorization before consent=true.
- render_talking_video accepts a photo, GLB avatar or character spec and includes an AI-generated label by default. Choose a voice matching the user's dialogue language.
- There is one current library, refined-current; library can be omitted. Use morphs with the keys and ranges in tag_vocabulary.controls. Initial model downloads may take several minutes.
- For children use profile="child" consistently. Children use outfit, not shirt, and do not support beards, makeup or hand accessories. Many child tags are Chinese; use the returned IDs or exact tags, such as 卫衣 (sweatshirt).
- Files default to ~/vrman-output/ (agent/output/ in repository mode). Avatars include a preview image: inspect it before delivery.
- If authentication expires, ask the user to run vrman.py login in their own terminal. Never request their password in chat or put tokens in preview links.
""")


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
    """Inspect avatar part tags, skin/hair palettes and facial morph controls before writing a spec.
    Parts include hair, eyes, eyebrow, beard, makeup, glasses, headwear, facewear, facemask, shirt,
    outfit, faceshape, eyeshape, noseshape and lipshape. controls lists morphs keys and valid ranges.
    profile is adult (default) or child. Omit library to use refined-current; legacy aliases remain accepted."""
    return {'tags': catalog.tag_vocabulary(part, library=library, profile=profile), 'colors': catalog.palettes(),
            'controls': catalog.controls(library, profile)}


@mcp.tool()
def search_assets(part: str, query: str = '', gender: str | None = None, limit: int = 8,
                  library: str = catalog.DEFAULT_LIBRARY, profile: str | None = None) -> list:
    """Search avatar parts by library tags, for example part="glasses", query="round thin_frame gold".
    gender female/male filters to that gender and unisex assets. Returned IDs can be used directly in a spec.
    Use profile="child" for child assets; many child tags are Chinese and can be searched verbatim."""
    return catalog.search_assets(part, query, gender, limit, library=library, profile=profile)


@mcp.tool()
async def list_voices() -> list:
    """List available voice IDs, names, descriptions and languages.
    The API default is zh-CN-XiaoxiaoNeural (Mandarin female); choose a voice matching the requested dialogue language."""
    def work():
        with VRMan() as vrman:
            return vrman.voices()
    return await run(work)


@mcp.tool()
async def create_avatar_from_description(spec: dict, out_path: str | None = None, full: bool = False,
                                         library: str = catalog.DEFAULT_LIBRARY, profile: str | None = None) -> list:
    """Assemble a 3D avatar as GLB with a portrait preview.
    spec accepts gender (female/male), region (asian/western), skin and hair_color (hex or palette names),
    plus part names mapped to tags or asset IDs; "none" omits a part. morphs uses the listed controls and ranges.
    profile="child" selects child assets; an explicit profile inside spec takes precedence.
    Also accepts {appearance: saved appearance}, {look: describe_character result}, or {preset: character ID from co-creation}.
    Returned appearance can be saved with manage_project as a character. Photo textures stay in the local GLB by default.
    full=false keeps speech/blink morphs; full=true retains all expression and facial adjustment channels."""
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
    """Create a GLB avatar and preview from a photo, processed locally without uploading the original.
    consent=true confirms the user's authorization. gender is female/male; region selects the facial style.
    photo_face=false matches library parts, skin and proportions; true shapes and textures the face from the photo.
    Use profile="child" for a child's photo and ensure guardian authorization."""
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
    """Render one speaking portrait or avatar as H.264/AAC MP4.
    Choose photo_path (requires consent=true), avatar_path (GLB), or spec (assemble a character).
    style: default transitions through diphthongs; simple uses one shape per syllable; talkinghead blends adjacent
    shapes; natural smooths jaw movement with lip closure for b/p/m/f. rate accepts values such as "-20%" or "+20%".
    watermark defaults to an AI-generated label. Use profile="child" when assembling a child spec.
    Choose a voice matching the requested dialogue language; English documentation does not change the default voice."""
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
