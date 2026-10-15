"""ffmpeg：一组 JPEG 画面 + 一段音频 → MP4（H.264 + AAC，网页、手机都能直接播）"""
import shutil
import subprocess
import tempfile
from pathlib import Path


def require_ffmpeg():
    path = shutil.which('ffmpeg')
    if not path:
        raise RuntimeError('需要 ffmpeg 合成视频：Mac 上可用 brew install ffmpeg 安装')
    return path


def make_video(frames, audio, audio_suffix, out, fps=30):
    """frames：JPEG 字节列表；audio：音频字节。返回视频时长（秒）"""
    ffmpeg = require_ffmpeg()
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        work = Path(work)
        for i, frame in enumerate(frames):
            (work / f'f{i:05d}.jpg').write_bytes(frame)
        voice = work / f'voice{audio_suffix}'
        voice.write_bytes(audio)
        subprocess.run([ffmpeg, '-y', '-v', 'error', '-framerate', str(fps), '-i', str(work / 'f%05d.jpg'),
                        '-i', str(voice), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20',
                        '-c:a', 'aac', '-shortest', '-movflags', '+faststart', str(out)], check=True)
    return len(frames) / fps
