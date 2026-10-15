"""无界面浏览器里的 VRMan 工作室（页面对象），给 Agent 工具用

照片匹配、捏形、口型、导出这些算法都在网页里，这里不重写，而是开一个看不见的 Chrome 打开工作室，
像用户一样上传照片、点按钮，再调用页面里现成的函数导出 GLB、逐帧渲染说话画面。
"""
import base64
import sys
import urllib.parse
from pathlib import Path

from playwright.sync_api import sync_playwright

VIEWPORT = {'width': 1440, 'height': 900}
# 连线上服务时浏览器缓存存在这里：第二次起素材只确认没变（304），不重新下载
CACHE_DIR = Path.home() / '.cache' / 'vrman' / 'chrome'
TOKEN_COOKIE = 'vrman_token'

READY = "() => window.studio && window.studio.builder.avatarRoot.visible && !window.studio.busy.size"
IDLE = "() => !window.studio.busy.size"

# 导出当前形象为 GLB，返回 base64（不经过下载对话框）
EXPORT_GLB = """async (slim) => {
    const bytes = new Uint8Array(await window.studio.builder.exportGLB({ slim }));
    let text = '';
    for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
    return btoa(text);
}"""

# 按清单组装形象：picks 是 {页面类型: 素材编号}，clear 是要清空的类型
APPLY_SPEC = """async ({ picks, clear, skin, hair, gender, region, morphs }) => {
    const st = window.studio, b = st.builder;
    await st.useActor('custom');
    if (gender) b.setFaceStyle({ gender, region: region || 'asian' });
    for (const type of clear) b.clearSlot(type);
    for (const [type, id] of Object.entries(picks)) {
        const asset = b.getAssets(type).find(a => a.id === id);
        if (!asset) throw new Error(`当前素材库找不到 ${type}: ${id}`);
        await b.applyAsset(asset, type, { strict: true });
    }
    if (skin) b.setColor('skin', skin);
    if (hair) b.setColor('hair', hair);
    for (const [name,value] of Object.entries(morphs || {})) {
        if (!b.library.controls?.some(c => c.name === name)) throw new Error(`当前素材库不支持精调：${name}`);
        b.setControl(name, value);
    }
}"""

# 当前形象用了哪些素材（素材名），给 Agent 回报
WORN = """() => {
    const b = window.studio.builder, out = {};
    for (const [type, id] of Object.entries(b.current)) {
        const asset = id && b.getAssets(type).find(a => a.id === id);
        if (asset) out[type] = asset.name;
    }
    return { parts: out, skin: b.skinColor, hair: b.hairColor };
}"""

# 离屏渲染一张头肩像（3D 形象或导入的 GLB），返回 PNG 的 dataURL
PORTRAIT = """async ({ width, height, background, target }) => {
    const THREE = await import('three');
    const shot = await window.__vrmanShot(THREE, { width, height, background, target });
    shot.render();
    const url = shot.renderer.domElement.toDataURL('image/png');
    shot.dispose();
    return url;
}"""

# 页面里的公共小工具：给 3D 形象搭一个离屏机位（头肩取景）
SHOT_HELPER = """() => { window.__vrmanShot = async (THREE, { width, height, background, target }) => {
    const st = window.studio;
    const root = target === 'preview' ? st.preview.root : st.builder.avatarRoot;
    root.updateWorldMatrix(true, true);
    // 头肩取景：头（皮肤网格）再并上挂在头上的东西（头发、眼镜、帽子），头发蓬松就拉远，短发就靠近。
    // 包围盒按网格本身的顶点量：three 自带的会把捏脸形变也算进去，头会被量大一倍
    const meshes = [];
    root.traverse(n => { if (n.isMesh && n.visible && n.geometry.attributes.position) meshes.push(n); });
    const boxOf = m => new THREE.Box3().setFromBufferAttribute(m.geometry.attributes.position).applyMatrix4(m.matrixWorld);
    const head = meshes.find(m => m.material && m.material.name === 'Wolf3D_Skin');
    const headBox = head ? boxOf(head) : new THREE.Box3().setFromObject(root), box = headBox.clone(), center = new THREE.Vector3();
    for (const m of meshes) {
        const part = boxOf(m);
        if (part.min.y > headBox.min.y - 0.02 && part.getCenter(center).y > headBox.min.y + 0.05) box.union(part);
    }
    box.getCenter(center);
    const shoulders = 0.12;                                     // 往下多带一点肩膀
    const fit = (box.max.y - box.min.y + shoulders) * 1.08;
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = st.stage.renderer.toneMapping;
    renderer.toneMappingExposure = st.stage.renderer.toneMappingExposure;
    renderer.setSize(width, height, false);
    renderer.setClearColor(background, 1);
    let environment = null;
    if (st.stage.scene.environment) {
        // 精细版靠环境反射出质感。舞台上的反射贴图属于另一个 WebGL 上下文，这个离屏渲染器用不了，照样再做一份
        const { RoomEnvironment } = await import('three/addons/environments/RoomEnvironment.js');
        const generator = new THREE.PMREMGenerator(renderer), room = new RoomEnvironment();
        environment = generator.fromScene(room, .04);
        room.dispose();
        generator.dispose();
    }
    const camera = new THREE.PerspectiveCamera(30, width / height, 0.01, 100);
    const distance = fit / 2 / Math.tan(THREE.MathUtils.degToRad(15)) / Math.min(1, width / height);
    const aim = center.y - shoulders / 2;
    camera.position.set(center.x, aim, box.max.z + distance);
    camera.lookAt(center.x, aim, center.z);
    return { renderer, camera, render: () => {
        const previous = st.stage.scene.environment;
        st.stage.scene.environment = environment?.texture || null;
        try { renderer.render(st.stage.scene, camera); }
        finally { st.stage.scene.environment = previous; }
    }, dispose: () => { environment?.dispose(); renderer.dispose(); } };
}; }"""

# 逐帧渲染说话画面。第一批时准备好音量包络、时间轴，并停掉页面自己的逐帧驱动，改由这里按固定时间推进；
# 每帧：推口型、眨眼（照片还加头部微动），画到输出画布上，右下角加「AI 生成」角标，存成 JPEG
RENDER_FRAMES = """async (o) => {
    const st = window.studio, speech = st.talk.speech;
    let R = window.__vrmanRender;
    if (!R) {
        st.talk.attach();                 // 先绑定说话对象：它会先停掉播放、清空包络，所以要放在最前
        const bytes = Uint8Array.from(atob(o.audio), c => c.charCodeAt(0));
        speech.envelope = await speech.buildEnvelope(new Blob([bytes], { type: o.mime }));
        speech.timeline = o.timeline;
        speech.timelineSimple = o.timelineSimple;
        speech.timelineTalkingHead = o.timelineTalkingHead;
        speech.timelineNatural = o.timelineNatural;
        st.talk.player.style = o.style;
        const blink = st.blinker.update.bind(st.blinker);
        // 眨眼原本按页面时钟排（可能排在十几秒后），画面时间却从 0 开始：先睁开眼、清掉进行中的眨眼，
        // 再按画面时间重排——当作上一次眨眼在开头前 1.8 秒，第一次落在 0.4～4.2 秒，一句一段的短片段也有机会眨
        st.blinker.finish();
        st.blinker.schedule(-1800);
        st.talk.update = () => {};
        st.blinker.update = () => {};
        st.actor.update = () => {};
        let now = 0;
        Object.defineProperty(speech, 'currentMs', { get: () => now, configurable: true });
        const out = document.createElement('canvas');
        let draw;
        if (o.mode === 'photo') {
            const view = st.photo.view, rig = st.photo.rig;
            out.width = o.width;
            out.height = Math.round(o.width * view.height / view.width / 2) * 2;
            draw = (ctx, ms) => {
                view.update(st.photo.motion.apply(rig.pose(), rig, ms / 1000));
                for (const c of [view.mouthCanvas, view.renderer.domElement]) ctx.drawImage(c, 0, 0, out.width, out.height);
            };
        } else {
            const THREE = await import('three');
            out.width = o.width;
            out.height = Math.round(o.height / 2) * 2;
            const shot = await window.__vrmanShot(THREE, { width: out.width, height: out.height, background: o.background, target: o.mode });
            draw = (ctx) => { shot.render(); ctx.drawImage(shot.renderer.domElement, 0, 0); };
        }
        R = window.__vrmanRender = { out, draw, blink, setNow: v => { now = v; },
            total: Math.ceil(speech.envelope.duration * o.fps), size: [out.width, out.height] };
    }
    const ctx = R.out.getContext('2d');
    const frames = [];
    for (let i = o.from; i < Math.min(o.from + o.count, R.total); i++) {
        const ms = i * 1000 / o.fps;
        R.setNow(ms);
        speech.update();
        R.blink(ms);
        ctx.fillStyle = o.background;
        ctx.fillRect(0, 0, R.out.width, R.out.height);
        R.draw(ctx, ms);
        if (o.watermark) {
            const size = Math.max(14, Math.round(R.out.height * 0.032));
            ctx.font = `600 ${size}px -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`;
            ctx.textAlign = 'right';
            ctx.textBaseline = 'bottom';
            ctx.fillStyle = 'rgba(0, 0, 0, 0.35)';
            ctx.fillText(o.watermark, R.out.width - size * 0.75 + 1, R.out.height - size * 0.6 + 1);
            ctx.fillStyle = 'rgba(255, 255, 255, 0.85)';
            ctx.fillText(o.watermark, R.out.width - size * 0.75, R.out.height - size * 0.6);
        }
        frames.push(R.out.toDataURL('image/jpeg', 0.92));
    }
    return { frames, total: R.total, size: R.size };
}"""


def launch_browser(playwright, cache_dir=None):
    """无界面 Chrome；Mac 上用 Metal 做 WebGL，渲染快。本机没装 Chrome 时退回 Playwright 自带的 Chromium。
    给了 cache_dir 就用带磁盘缓存的持久上下文（返回 BrowserContext），否则返回 Browser"""
    options = {'headless': True, 'args': ['--use-angle=metal'] if sys.platform == 'darwin' else []}
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)
        options.update(user_data_dir=str(cache_dir), viewport=VIEWPORT)
    launch = playwright.chromium.launch_persistent_context if cache_dir else playwright.chromium.launch
    try:
        return launch(channel='chrome', **options)
    except Exception:
        return launch(**options)


def token_cookie(base_url, token):
    """token 放进 cookie，只发往服务所在的路径（不会带去加载 three.js 的 CDN 等别的网站）"""
    parts = urllib.parse.urlsplit(base_url)
    return {'name': TOKEN_COOKIE, 'value': token, 'domain': parts.hostname, 'path': parts.path.rstrip('/') + '/',
            'secure': parts.scheme == 'https', 'httpOnly': True, 'sameSite': 'Strict'}


class StudioPage:
    """一个打开的工作室页面。workspace 是 avatar / photo / voice"""

    def __init__(self, browser, base_url, workspace='avatar', token=None, library='original'):
        # browser 是 Browser 时每页一个新上下文，关页面时一起关；是共用的持久上下文时只关页面
        self.owns_context = hasattr(browser, 'new_context')
        context = browser.new_context(viewport=VIEWPORT) if self.owns_context else browser
        if token:
            context.add_cookies([token_cookie(base_url, token)])
        self.page = context.new_page()
        # 每次都在网址里写明素材版本：浏览器会记住上次选的版本，不写的话上一次的选择会带到这一次
        self.page.goto(f'{base_url}/index.html?library={library}#{workspace}', timeout=60000)
        self.page.wait_for_function(READY, timeout=90000)
        if self.js('() => window.studio.builder.libraryId') != library:
            self.close()
            raise RuntimeError(f'素材版本 {library} 现在用不了（服务上还没有它的模型），可以先用 original')
        self.page.evaluate(SHOT_HELPER)

    def js(self, script, arg=None):
        return self.page.evaluate(script, arg)

    def wait_idle(self):
        self.page.wait_for_function(IDLE, timeout=60000)

    # ---------- 照片 ----------

    def upload_photo(self, path):
        self.js("() => { document.getElementById('photo-status').className = 'status'; }")
        self.page.set_input_files('#photo-input', str(path))
        self.wait_photo_ready()

    def wait_photo_ready(self):
        self.page.wait_for_function("() => /ok|error/.test(document.getElementById('photo-status').className)", timeout=60000)
        if 'ok' not in self.page.get_attribute('#photo-status', 'class'):
            raise RuntimeError(self.page.text_content('#photo-status').strip())

    def generate(self, gender, region='asian', photo_face=False):
        """照片 → 3D 形象：选好性别、五官，点「生成相似 3D 形象」或「照片直出 3D 头像」，等结果出来"""
        self.page.click(f'#photo-gender [data-value="{gender}"]')
        self.page.click(f'#photo-region [data-value="{region}"]')
        self.js("() => { document.getElementById('match-card').hidden = true; }")
        self.page.click('#photo-head-btn' if photo_face else '#photo-match-btn')
        self.page.wait_for_selector('#match-card:not([hidden])', timeout=120000)
        self.page.wait_for_function("() => !window.studio.busy.size && !document.getElementById('photo-head-btn').disabled",
                                    timeout=60000)

    # ---------- 3D 形象 ----------

    def apply_spec(self, picks, clear, skin=None, hair=None, gender=None, region=None, morphs=None):
        self.js(APPLY_SPEC, {'picks': picks, 'clear': clear, 'skin': skin, 'hair': hair, 'gender': gender,
                             'region': region, 'morphs': morphs or {}})
        self.wait_idle()

    def worn(self):
        return self.js(WORN)

    def export_glb(self, slim=True):
        return base64.b64decode(self.js(EXPORT_GLB, slim))

    def import_glb(self, path):
        """载入一个 GLB 作为舞台角色（带口型通道的能说话）"""
        self.page.set_input_files('#glb-input', str(path))
        self.page.wait_for_selector('#preview-banner:not([hidden])', timeout=30000)
        self.wait_idle()

    def portrait(self, width=512, height=512, background='#1a1d29', target='custom'):
        url = self.js(PORTRAIT, {'width': width, 'height': height, 'background': background, 'target': target})
        return base64.b64decode(url.split(',')[1])

    # ---------- 说话画面 ----------

    def render_frames(self, speech, mode, fps=30, width=720, height=720, background='#1a1d29',
                      style='default', watermark='AI 生成', batch=30):
        """逐帧渲染，按批交回 JPEG 字节；mode 是 photo / custom / preview。返回 (帧列表, 画面尺寸)"""
        frames, start, size = [], 0, None
        while True:
            result = self.js(RENDER_FRAMES, {
                'audio': speech['audio'], 'mime': speech['mime'], 'timeline': speech['visemes'],
                'timelineSimple': speech.get('visemesSimple', speech['visemes']),
                'timelineTalkingHead': speech.get('visemesTalkingHead', speech['visemes']),
                'timelineNatural': speech.get('visemesNatural', speech['visemes']),
                'mode': mode, 'fps': fps, 'width': width, 'height': height, 'background': background,
                'style': style, 'watermark': watermark, 'from': start, 'count': batch,
            })
            frames += [base64.b64decode(url.split(',')[1]) for url in result['frames']]
            size = result['size']
            start += batch
            if start >= result['total']:
                return frames, size

    def close(self):
        (self.page.context if self.owns_context else self.page).close()


class Browser:
    """with Browser() as browser: 用完自动关掉。cached=True 时用带磁盘缓存的持久上下文（连线上服务用）；
    缓存目录被另一个进程占着时退回不带缓存的"""

    def __init__(self, cached=False):
        self.cached = cached

    def __enter__(self):
        self.playwright = sync_playwright().start()
        try:
            self.browser = launch_browser(self.playwright, CACHE_DIR if self.cached else None)
        except Exception:
            if not self.cached:
                raise
            self.browser = launch_browser(self.playwright)
        return self.browser

    def __exit__(self, *exc):
        self.browser.close()
        self.playwright.stop()
