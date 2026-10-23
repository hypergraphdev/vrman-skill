"""Reuse the studio renderer, replay, subtitles and sound mixer; deliver real MP4."""
import base64
import json
import re
import subprocess
import time
from pathlib import Path

from .api import VRMan
from .creation import Creation
from .media import require_ffmpeg

START_FILM = """async ({record, watermark}) => {
    const {TheaterVideo} = await import('./theater-video.js');
    const {Replay} = await import('./world-theater.js');
    const runner = studio.world.runner, video = new TheaterVideo(studio, runner);
    const replay = new Replay(runner, () => {});
    replay.options = () => ({voice: true});
    const draw = video.draw.bind(video);
    video.draw = () => { draw(); if (watermark) {
        video.ctx.fillStyle = 'rgba(255,255,255,.8)'; video.ctx.font = '18px sans-serif';
        video.ctx.textAlign = 'right'; video.ctx.fillText('AI generated', 1250, 30);
    }};
    window.__agentFilm = {runner, video, replay, errors: [], events: []};
    // Collect warnings across scene transitions; runner.events is reset for every segment.
    const emit = runner.emit.bind(runner);
    runner.emit = () => { for (const event of runner.events || []) {
        if (event.event === 'skipped' && !window.__agentFilm.events.includes(event)) window.__agentFilm.events.push(event);
    } emit(); };
    video.start(); await video.mix.resume();
    void replay.play(record).catch(e => window.__agentFilm.errors.push(e.message));
}"""

FILM_STATE = """() => {
    const f = window.__agentFilm;
    if (f.runner.state === 'continue') f.runner.next();
    return {state: f.runner.state, active: f.replay.active, segment: f.replay.index,
      total: f.replay.record?.segments.length, step: f.runner.current?.id,
      subtitle: f.runner.subtitle, errors: f.errors, events: f.events};
}"""


def output(payload, suffix):
    target = Path(payload['out']).expanduser().resolve()
    if target.suffix.lower() != suffix:
        raise ValueError(f'Output filename must end in {suffix}')
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def render_performance(payload, task):
    out = output(payload, '.mp4')
    width = payload.get('width', 1280)
    if type(width) is not int or not 320 <= width <= 1920 or width % 2:
        raise ValueError('Video width must be an even number from 320 to 1920')
    with VRMan() as vrman:
        creation = Creation(vrman.server)
        record = creation.project('performance', 'get', payload['id']) if payload.get('id') else payload.get('record')
        if isinstance(record, dict) and record.get('kind') == 'vrman-script':
            record = creation.compile(record)['record']
        if not isinstance(record, dict) or not record.get('segments'):
            raise ValueError('Provide a performance id or compiled record with segments')
        page = vrman.open('world')
        try:
            task.update('Loading performance')
            # Give the stage the output aspect ratio before its camera frames
            # actors, rather than cropping a narrow editor viewport to 16:9.
            page.page.set_viewport_size({'width':1280, 'height':720})
            page.js("() => { Object.assign(studio.stage.container.style, {position:'fixed',inset:'0',width:'100vw',height:'100vh',zIndex:'1000'}); studio.stage.resize(); }")
            page.page.mouse.click(10, 10)
            page.js(START_FILM, {'record': record, 'watermark': payload.get('watermark', True)})
            while True:
                task.check()
                state = page.js(FILM_STATE)
                if state['state'] == 'error' or state['errors']:
                    raise RuntimeError(str(state['errors'] or state.get('subtitle') or 'Performance failed'))
                if state['state'] == 'question':
                    raise RuntimeError('This performance is waiting for a choice. Resolve the interactive branch before exporting.')
                task.update('Rendering performance', progress={k: state[k] for k in ('segment', 'total', 'step')})
                if not state['active'] and state['state'] == 'ended':
                    break
                page.page.wait_for_timeout(300)
            missing_audio = [e for e in state['events'] if e.get('action') == 'say' and '配音失败' in e.get('reason', '')]
            if missing_audio:
                raise RuntimeError('Dialogue audio failed; MP4 was not delivered as a complete performance: ' + str(missing_audio[:3]))
            task.update('Saving recording')
            with page.page.expect_download(timeout=30000) as download:
                page.js("""async () => { const clip = await __agentFilm.video.stop('performance');
                    if (!clip) throw new Error('No frames recorded');
                    const a = document.createElement('a'); a.href = clip.url; a.download = clip.name; a.click();
                }""")
            raw = task.folder / 'recording'
            download.value.save_as(raw)
        finally:
            page.close()
    task.update('Encoding H.264 / AAC')
    temp = task.folder / 'encoded.mp4'
    cmd = [require_ffmpeg(), '-y', '-v', 'error', '-i', str(raw), '-map', '0:v:0', '-map', '0:a:0',
           '-vf', f'scale={width}:-2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
           '-c:a', 'aac', '-movflags', '+faststart', str(temp)]
    with (task.folder / 'ffmpeg.log').open('wb') as log:
        process = subprocess.Popen(cmd, stdout=log, stderr=log)
        try:
            while process.poll() is None:
                task.update('Encoding H.264 / AAC')
                time.sleep(.3)
            if process.returncode:
                raise RuntimeError((task.folder / 'ffmpeg.log').read_text()[-1500:])
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(5)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
    task.check()
    # Copy to destination before replacing: output may be on another volume.
    import shutil
    staging = out.with_name(out.name + '.' + task.folder.name + '.partial')
    try:
        shutil.copyfile(temp, staging)
        staging.replace(out)
    finally:
        staging.unlink(missing_ok=True)
        raw.unlink(missing_ok=True)
        temp.unlink(missing_ok=True)
    return {'video': str(out), 'mime': 'video/mp4', 'videoCodec': 'h264', 'audioCodec': 'aac',
            'bytes': out.stat().st_size, 'width': width, 'segments': len(record['segments']), 'warnings': state['events']}


def preview_scene(payload, task):
    out = output(payload, '.png')
    url = payload.get('url', '')
    if not re.fullmatch(r'api/scene/file/[0-9a-f]{20}\.glb', url):
        raise ValueError('Use a scene build/upload GLB url')
    with VRMan() as vrman:
        page = vrman.open('scene')
        try:
            task.update('Loading scene')
            page.js("async url => { await studio.scenery.ready; await studio.scenery.importScene(url, 'Scene', url); }", url)
            task.update('Taking preview')
            data = page.js("() => { studio.builder.avatarRoot.visible = false; studio.stage.render(); return studio.stage.renderer.domElement.toDataURL('image/png'); }")
            out.write_bytes(base64.b64decode(data.split(',')[1]))
            summary = page.js('() => studio.scenery.sceneSummary()')
            return {'preview': str(out), 'mime': 'image/png', 'scene': summary, 'url': url,
                    'previewUrl': Creation(vrman.server).link({'import': url})}
        finally:
            page.close()


def export_build(payload, task):
    out = output(payload, '.glb')
    with VRMan() as vrman:
        build = Creation(vrman.server).project('build', 'get', payload['id'])['build'] if payload.get('id') else payload['build']
        page = vrman.open('scene')
        try:
            task.update('Loading build')
            page.page.goto(vrman.server.url + '/props.html')
            page.page.wait_for_function('() => window.propsViewer?.desk && window.propsViewer?.catalog?.length', timeout=90000)
            data = page.js("""async build => { const desk = propsViewer.desk; desk.enter(); await desk.load(build);
                const blob = await desk.glb(); return await new Promise((resolve, reject) => {
                    const reader = new FileReader(); reader.onload = () => resolve(reader.result); reader.onerror = reject; reader.readAsDataURL(blob);
                }); }""", build)
            task.check()
            out.write_bytes(base64.b64decode(data.split(',')[1]))
            return {'path': str(out), 'mime': 'model/gltf-binary', 'bytes': out.stat().st_size}
        finally:
            page.close()
