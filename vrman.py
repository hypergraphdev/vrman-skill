#!/usr/bin/env python3
"""VRMan 命令行：照片或描述 → 3D 头像，文本 + 照片或头像 → 说话视频。结果以 JSON 打印，方便 Agent 读取

  python3 vrman.py avatar --spec '{"gender":"female","hair":"long wavy","hair_color":"栗色"}' --out a.glb --preview a.png
  python3 vrman.py avatar --photo me.jpg --gender female --consent --out me.glb
  python3 vrman.py talk --text "你好" --photo me.jpg --consent --out hello.mp4
  python3 vrman.py talk --text "你好" --avatar a.glb --out hello.mp4
  python3 vrman.py avatar --spec '{"gender":"male","hair":"short","morphs":{"v3_eye_spacing":0.3}}' --out a.glb
  python3 vrman.py avatar --profile child --spec '{"gender":"female","hair":"高马尾","outfit":"卫衣"}' --out kid.glb
  python3 vrman.py assets hair "long wavy" --gender female
  python3 vrman.py tags glasses
  python3 vrman.py voices
  python3 vrman.py login        用 www.hg.network 账号换 token（单独安装、连线上服务时先做一次）
  python3 vrman.py whoami       查看当前 token 属于谁、用了多少
"""
import argparse
import getpass
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vrman_agent import VRMan, catalog, remote  # noqa: E402
from vrman_agent.api import STYLES  # noqa: E402
from vrman_agent.catalog import DEFAULT_LIBRARY, LEGACY_LIBRARIES, LIBRARIES, PARTS, PROFILES  # noqa: E402


def load_spec(value):
    """--spec 可以是 JSON 字符串，也可以是 JSON 文件路径"""
    path = Path(value)
    return json.loads(path.read_text(encoding='utf-8') if path.exists() else value)


def spec_of(args):
    """清单里没写素材库、人物类型时，用 --library、--profile 的"""
    return {'library': args.library, 'profile': args.profile, **load_spec(args.spec)} if args.spec else None


def cmd_avatar(args):
    with VRMan() as vrman:
        if args.photo:
            return vrman.avatar_from_photo(args.photo, args.out, args.gender, args.region, args.photo_face,
                                           not args.full, args.preview, args.consent, args.library, args.profile)
        return vrman.avatar_from_spec(spec_of(args), args.out, not args.full, args.preview)


def cmd_talk(args):
    with VRMan() as vrman:
        return vrman.talking_video(args.text, args.out, photo=args.photo, avatar=args.avatar,
                                   spec=spec_of(args), voice=args.voice, rate=args.rate,
                                   style=args.style, width=args.width, background=args.background,
                                   watermark=not args.no_watermark, consent=args.consent)


def cmd_assets(args):
    return catalog.search_assets(args.part, args.query, args.gender, args.limit, library=args.library,
                                 profile=args.profile)


def cmd_tags(args):
    return {'tags': catalog.tag_vocabulary(args.part, library=args.library, profile=args.profile),
            'colors': catalog.palettes(), 'controls': catalog.controls(args.library, args.profile)}


def cmd_voices(_args):
    with VRMan() as vrman:
        return vrman.voices()


def cmd_login(args):
    """在自己的终端里输入账号密码；密码只发给 hg.network 的登录接口，不保存"""
    username = args.username or input('www.hg.network 用户名：').strip()
    password = getpass.getpass('密码（输入时不显示）：', stream=sys.stderr)
    return remote.login(username, password, args.url)


def cmd_whoami(args):
    return remote.whoami(args.url)


def add_library(command):
    command.add_argument('--library', choices=LIBRARIES + LEGACY_LIBRARIES, default=DEFAULT_LIBRARY, metavar='LIBRARY',
                         help='素材库：只有统一素材库 refined-current（默认，不用写）；旧版本名 original、refined-v2 等还认')
    command.add_argument('--profile', choices=PROFILES,
                         help='人物类型：adult 成人（默认）；child 儿童，用学龄儿童的头模、发型、衣服和五官')


def parser():
    p = argparse.ArgumentParser(description='VRMan：照片或描述 → 3D 头像，文本 → 说话视频')
    sub = p.add_subparsers(dest='command', required=True)

    a = sub.add_parser('avatar', help='生成 3D 头像 GLB')
    source = a.add_mutually_exclusive_group(required=True)
    source.add_argument('--photo', help='照片路径（需 --consent、--gender）')
    source.add_argument('--spec', help='头像清单：JSON 字符串或文件，如 {"gender":"male","hair":"short","glasses":"round"}')
    a.add_argument('--gender', choices=['female', 'male'], help='照片里的性别（用照片时必填）')
    a.add_argument('--region', choices=['asian', 'western'], default='asian', help='五官风格')
    a.add_argument('--photo-face', action='store_true', help='照片直出：按照片捏脸形、贴上照片（默认是按素材配）')
    a.add_argument('--full', action='store_true', help='导出完整版（默认说话精简版，3 MB 以内）')
    a.add_argument('--preview', help='另存一张头肩预览图 PNG')
    a.add_argument('--consent', action='store_true', help='确认照片是本人或已获授权')
    a.add_argument('--out', required=True)
    add_library(a)
    a.set_defaults(run=cmd_avatar)

    t = sub.add_parser('talk', help='生成说话视频 MP4')
    who = t.add_mutually_exclusive_group(required=True)
    who.add_argument('--photo', help='照片说话（需 --consent）')
    who.add_argument('--avatar', help='GLB 头像说话')
    who.add_argument('--spec', help='按清单现组装一个 3D 头像来说话')
    t.add_argument('--text', required=True)
    t.add_argument('--voice', default='zh-CN-XiaoxiaoNeural', help='发音人（voices 命令列出）')
    t.add_argument('--rate', default='+0%', help='语速，如 -20%%、+20%%')
    t.add_argument('--style', choices=STYLES, default='default',
                   help='口型播放方式：default 复韵母在字里滑过去；simple 优化精简，每字一个口型；talkinghead 相邻口型叠加；'
                        'natural 真人平滑，下巴按声母抬落、嘴唇只在 b/p/m/f 时合拢')
    t.add_argument('--width', type=int, default=720, help='画面宽度（像素）')
    t.add_argument('--background', default='#1a1d29', help='3D 头像的背景色')
    t.add_argument('--no-watermark', action='store_true', help='不加「AI 生成」角标')
    t.add_argument('--consent', action='store_true', help='确认照片是本人或已获授权')
    t.add_argument('--out', required=True)
    add_library(t)
    t.set_defaults(run=cmd_talk)

    s = sub.add_parser('assets', help='按标签搜素材')
    s.add_argument('part', choices=list(PARTS))
    s.add_argument('query', nargs='?', default='')
    s.add_argument('--gender', choices=['female', 'male'])
    s.add_argument('--limit', type=int, default=8)
    add_library(s)
    s.set_defaults(run=cmd_assets)

    g = sub.add_parser('tags', help='列出各部位的标签词、调色板，以及能精调的五官')
    g.add_argument('part', nargs='?', choices=list(PARTS))
    add_library(g)
    g.set_defaults(run=cmd_tags)

    v = sub.add_parser('voices', help='列出可用的发音人')
    v.set_defaults(run=cmd_voices)

    login = sub.add_parser('login', help='用 www.hg.network 账号换 token，存到 ~/.config/vrman/token')
    login.add_argument('--username')
    login.add_argument('--url', help=f'服务地址（默认 {remote.PUBLIC_URL}）')
    login.set_defaults(run=cmd_login)

    who = sub.add_parser('whoami', help='当前 token 属于谁、用了多少')
    who.add_argument('--url')
    who.set_defaults(run=cmd_whoami)
    return p


def main():
    args = parser().parse_args()
    if args.command == 'avatar' and args.photo and not args.gender:
        parser().error('用照片生成头像时要给 --gender')
    try:
        result = args.run(args)
    except (ValueError, PermissionError, RuntimeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
