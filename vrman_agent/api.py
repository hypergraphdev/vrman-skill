"""对外的几个能力（外观模式）：命令行、MCP 服务都只调这里

- 照片 → 3D 头像 GLB（生成相似形象 / 照片直出）
- 描述 → 3D 头像 GLB：Agent 把描述拆成「部位: 标签词」清单，这里按标签挑素材组装
- 文本 + 照片 / 头像 → 说话视频 MP4
- 搜素材、列标签词、列发音人

用照片生成的结果对应真人，调用方必须确认是本人或已获授权（consent=True）；视频默认带「AI 生成」角标。
"""
import base64
import math
import mimetypes
from contextlib import ExitStack
from pathlib import Path

from . import catalog
from .media import make_video, require_ffmpeg
from .page import Browser, StudioPage
from .server import Service

DEFAULT_VOICE = 'zh-CN-XiaoxiaoNeural'
DEFAULT_BACKGROUND = '#1a1d29'
WATERMARK = 'AI 生成'
# 口型播放方式：default 复韵母在一个字里滑过去；simple 优化精简，每字一个口型；talkinghead 相邻口型叠加；
# natural 真人平滑，下巴按声母抬落、嘴唇只在 b/p/m/f 时合拢
STYLES = ('default', 'simple', 'talkinghead', 'natural')
DEFAULT_EYEBROW = {'female': 'female thin high', 'male': 'male thick low'}
CONSENT_REQUIRED = '用照片生成的内容对应真人：请确认照片是本人或已获授权，并传 consent=True'


class VRMan:
    """with VRMan() as vrman: ... 进入时启动（或复用）本地服务和无界面浏览器，退出时都关掉。
    手上已有 Playwright 浏览器（如测试里）就传 browser 共用，退出时不关它"""

    def __init__(self, browser=None):
        self.shared_browser = browser

    def __enter__(self):
        self.stack = ExitStack()
        self.server = self.stack.enter_context(Service())
        self.browser = self.shared_browser or self.stack.enter_context(Browser(cached=self.server.remote))
        return self

    def __exit__(self, *exc):
        return self.stack.__exit__(*exc)

    def open(self, workspace='avatar', library=catalog.DEFAULT_LIBRARY):
        return StudioPage(self.browser, self.server.url, workspace, self.server.token, catalog.check_library(library))

    # ---------- 3D 头像 ----------

    def avatar_from_photo(self, photo, out, gender, region='asian', photo_face=False, slim=True,
                          preview=None, consent=False, library=catalog.DEFAULT_LIBRARY):
        """照片 → GLB。photo_face=False 是「生成相似 3D 形象」（按素材配），True 是「照片直出」（捏脸形、贴照片）。
        library 是挑素材用的素材版本"""
        check_consent(consent)
        photo = existing(photo, '照片')
        page = self.open('photo', library)
        try:
            page.upload_photo(photo)
            page.generate(gender, region, photo_face)
            return self.save_avatar(page, out, slim, preview)
        finally:
            page.close()

    def avatar_from_spec(self, spec, out, slim=True, preview=None):
        """清单 → GLB。spec 例：{"gender": "female", "hair": "long wavy", "hair_color": "栗色", "glasses": "round thin_frame"}，
        可以带 library（素材版本）和 morphs（精调值）"""
        page = self.open('avatar', spec_library(spec))
        try:
            apply_spec(page, spec)
            return self.save_avatar(page, out, slim, preview)
        finally:
            page.close()

    def save_avatar(self, page, out, slim, preview):
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(page.export_glb(slim))
        result = {'glb': str(out), 'size_kb': out.stat().st_size // 1024, 'slim': slim, **page.worn()}
        if preview:
            Path(preview).write_bytes(page.portrait())
            result['preview'] = str(preview)
        return result

    # ---------- 说话视频 ----------

    def talking_video(self, text, out, photo=None, avatar=None, spec=None, voice=DEFAULT_VOICE, rate='+0%',
                      style='default', width=720, background=DEFAULT_BACKGROUND, watermark=True, consent=False):
        """文本 → 说话视频。说话的是 photo（照片）、avatar（GLB 文件）或 spec（按清单现组装的 3D 头像）之一"""
        if sum(x is not None for x in (photo, avatar, spec)) != 1:
            raise ValueError('photo、avatar、spec 三选一')
        if style not in STYLES:
            raise ValueError(f'不认识的口型方式：{style}（可选：{"、".join(STYLES)}）')
        if photo is not None:
            check_consent(consent)
        photo, avatar = existing(photo, '照片'), existing(avatar, 'GLB 头像')
        require_ffmpeg()
        speech = self.synthesize(text, voice, rate)
        page = self.open('photo' if photo else 'avatar', spec_library(spec) if spec else catalog.DEFAULT_LIBRARY)
        try:
            mode = prepare_speaker(page, photo, avatar, spec)
            frames, (w, h) = page.render_frames(speech, mode, width=width, height=width, background=background,
                                                style=style, watermark=WATERMARK if watermark else '')
        finally:
            page.close()
        suffix = mimetypes.guess_extension(speech['mime']) or '.mp3'
        seconds = make_video(frames, base64.b64decode(speech['audio']), suffix, out)
        return {'video': str(out), 'seconds': round(seconds, 2), 'frames': len(frames), 'width': w, 'height': h,
                'voice': voice, 'style': style, 'watermark': WATERMARK if watermark else None}

    def synthesize(self, text, voice, rate):
        return self.server.post('/api/tts', {'text': text, 'voice': voice, 'rate': rate})

    # ---------- 查询 ----------

    def voices(self):
        return catalog.voices(self.server)


def check_consent(consent):
    if not consent:
        raise PermissionError(CONSENT_REQUIRED)


def existing(path, what):
    """文件要先在：路径写错时马上说清楚，不要等页面上传超时"""
    if path is None:
        return None
    path = Path(path).expanduser()
    if not path.is_file():
        raise ValueError(f'{what}文件不存在：{path}')
    return str(path)


def spec_library(spec):
    return catalog.check_library(spec.get('library', catalog.DEFAULT_LIBRARY))


def check_morphs(morphs):
    """精调值：{控制名: 数值}，如 {"v3_eye_spacing": 0.3}"""
    is_number = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    if not isinstance(morphs, dict) or not all(is_number(v) for v in morphs.values()):
        raise ValueError('morphs 要写成 {精调名: 数值}，如 {"v3_eye_spacing": 0.3}')
    return morphs


def apply_spec(page, spec):
    """把清单里每个部位的描述对到素材上，再交给页面组装（页面已按清单的素材版本打开）。值写 none 表示不要这个部位"""
    spec = dict(spec)
    library = catalog.check_library(spec.pop('library', catalog.DEFAULT_LIBRARY))
    morphs = check_morphs(spec.pop('morphs', {}))
    gender = spec.pop('gender', None)
    region = spec.pop('region', None)
    skin = catalog.resolve_color('skin', spec.pop('skin', None))
    hair = catalog.resolve_color('hair', spec.pop('hair_color', None))
    if gender and 'eyebrow' not in spec:
        spec['eyebrow'] = DEFAULT_EYEBROW[gender]      # 没指定眉毛时按性别配（女款细眉、男款粗眉）
    picks, clear = {}, []
    for part, value in spec.items():
        page_type = catalog.PARTS[part][1] if part in catalog.PARTS else None
        if not page_type:
            raise ValueError(f'不认识的部位：{part}（可用：gender、region、skin、hair_color、{"、".join(catalog.PARTS)}）')
        if str(value).lower() in ('none', '无', ''):
            clear.append(page_type)
        else:
            picks[page_type] = catalog.find_asset(part, str(value), gender, library=library)['id']
    if 'outfit' in picks:
        clear.append('shirt')             # 套装和上衣同一个位置，有套装就不要上衣
    page.apply_spec(picks, clear, skin, hair, gender, region, morphs)


def prepare_speaker(page, photo, avatar, spec):
    """让说话的角色上台，返回渲染方式：photo / preview（导入的 GLB）/ custom（现组装的头像）"""
    if photo is not None:
        page.upload_photo(photo)
        page.js("() => window.studio.useActor('photo')")
        page.wait_idle()
        return 'photo'
    if avatar is not None:
        page.import_glb(avatar)
        return 'preview'
    apply_spec(page, spec)
    return 'custom'
