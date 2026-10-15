"""VRMan 的 Agent 工具：照片或描述 → 3D 头像，文本 + 照片或头像 → 说话视频

    from vrman_agent import VRMan
    with VRMan() as vrman:
        vrman.avatar_from_spec({'gender': 'female', 'hair': 'long wavy'}, 'avatar.glb')
        vrman.talking_video('你好', 'hello.mp4', spec={'gender': 'female', 'hair': 'long wavy'})
"""
from .api import VRMan
from . import remote
from .catalog import palettes, search_assets, tag_vocabulary

__all__ = ['VRMan', 'remote', 'search_assets', 'tag_vocabulary', 'palettes']
