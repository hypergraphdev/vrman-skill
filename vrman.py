#!/usr/bin/env python3
"""Hello Genesis CLI: create characters, scenes, worlds and performances; export GLB/MP4.
Results are printed as JSON. Use --help or <command> --help for options.
Run login once when connecting an installed client to the hosted service.
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
from vrman_agent.creation import Creation, CONTRACT, image_payload  # noqa: E402
from vrman_agent.server import Service  # noqa: E402
from vrman_agent import local_tasks  # noqa: E402


def load_spec(value):
    """--spec 可以是 JSON 字符串，也可以是 JSON 文件路径"""
    if value.lstrip().startswith(('{', '[')):
        return json.loads(value)
    return json.loads(Path(value).expanduser().read_text(encoding='utf-8'))


def cmd_studio(args):
    if args.command == 'task' and args.identifier.startswith('local:'):
        return (local_tasks.cancel if args.cancel else local_tasks.status)(args.identifier[6:])
    with Service() as service:
        client = Creation(service)
        if args.command in ('create', 'render', 'preview', 'export-build') and service.process:
            raise RuntimeError('Long tasks need a persistent service: run server.py separately and set VRMAN_URL, or use the hosted service.')
        if args.command == 'capabilities':
            return client.capabilities()
        if args.command == 'tasks':
            return {'tasks': service.get('/api/agent/tasks')['tasks'] + local_tasks.listing()}
        if args.command == 'search':
            return client.search(args.query, args.kind, args.limit, era=args.era, profile=args.profile)
        if args.command == 'create':
            payload = load_spec(args.payload)
            if args.image: payload['image'] = image_payload(args.image)
            return client.start(args.operation, payload)
        if args.command == 'task':
            result = client.task(args.identifier, args.since, args.cancel)
            for stage in result.get('stages', []): stage.pop('compare', None)
            return result
        if args.command == 'project':
            result = client.project(args.kind, args.action, args.identifier, load_spec(args.payload) if args.payload else None)
            if args.out:
                path = Path(args.out).expanduser().resolve(); path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            return result
        if args.command == 'compile':
            return client.compile(load_spec(args.script), args.save)
        if args.command == 'scene-import': return client.upload_scene(args.path)
        if args.command == 'scene-export': return client.download_scene(args.url, args.out)
        if args.command == 'edit-performance': return client.edit_performance(load_spec(args.payload))
        if args.command in ('render', 'preview', 'export-build'):
            payload = {'out': str(Path(args.out).expanduser().resolve())}
            if args.command == 'render':
                payload.update(id=args.identifier, record=load_spec(args.record) if args.record else None, width=args.width)
            elif args.command == 'preview': payload['url'] = args.url
            else: payload.update(id=args.identifier, build=load_spec(args.build) if args.build else None)
            return local_tasks.start({'render':'performance', 'preview':'scene_preview', 'export-build':'build_export'}[args.command], payload, service)


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
    username = args.username or input('www.hg.network username: ').strip()
    password = getpass.getpass('Password (hidden): ', stream=sys.stderr)
    return remote.login(username, password, args.url)


def cmd_whoami(args):
    return remote.whoami(args.url)


def add_library(command):
    command.add_argument('--library', choices=LIBRARIES + LEGACY_LIBRARIES, default=DEFAULT_LIBRARY, metavar='LIBRARY',
                         help='Current library: refined-current (default); legacy aliases are still accepted')
    command.add_argument('--profile', choices=PROFILES,
                         help='Character profile: adult (default) or child (school-age head, hair, clothing and features)')


def parser():
    p = argparse.ArgumentParser(description='Hello Genesis: characters, scenes, worlds, performances, saved projects and GLB/MP4 export')
    sub = p.add_subparsers(dest='command', required=True)

    a = sub.add_parser('avatar', help='Create a 3D avatar GLB')
    source = a.add_mutually_exclusive_group(required=True)
    source.add_argument('--photo', help='Photo path (requires --consent and --gender)')
    source.add_argument('--spec', help='Avatar spec as inline JSON or a JSON file')
    a.add_argument('--gender', choices=['female', 'male'], help='Photo subject gender (required with --photo)')
    a.add_argument('--region', choices=['asian', 'western'], default='asian', help='Facial style')
    a.add_argument('--photo-face', action='store_true', help='Shape and texture the face from the photo (default matches library parts)')
    a.add_argument('--full', action='store_true', help='Retain all facial channels (default keeps speech and blink morphs)')
    a.add_argument('--preview', help='Save a portrait preview PNG')
    a.add_argument('--consent', action='store_true', help='Confirm the photo is yours or you have permission')
    a.add_argument('--out', required=True)
    add_library(a)
    a.set_defaults(run=cmd_avatar)

    t = sub.add_parser('talk', help='Render a talking video MP4')
    who = t.add_mutually_exclusive_group(required=True)
    who.add_argument('--photo', help='Animate a photo (requires --consent)')
    who.add_argument('--avatar', help='Animate a GLB avatar')
    who.add_argument('--spec', help='Assemble a speaking avatar from a spec')
    t.add_argument('--text', required=True)
    t.add_argument('--voice', default='zh-CN-XiaoxiaoNeural', help='Voice ID (listed by the voices command)')
    t.add_argument('--rate', default='+0%', help='Speech rate, for example -20%% or +20%%')
    t.add_argument('--style', choices=STYLES, default='default',
                   help='Lip sync: default transitions through diphthongs; simple uses one shape per syllable; talkinghead blends adjacent shapes; '
                        'natural smooths jaw movement and closes lips for b/p/m/f')
    t.add_argument('--width', type=int, default=720, help='Video width in pixels')
    t.add_argument('--background', default='#1a1d29', help='Background color for the 3D avatar')
    t.add_argument('--no-watermark', action='store_true', help='Omit the AI-generated label')
    t.add_argument('--consent', action='store_true', help='Confirm the photo is yours or you have permission')
    t.add_argument('--out', required=True)
    add_library(t)
    t.set_defaults(run=cmd_talk)

    s = sub.add_parser('assets', help='Search avatar parts by tags')
    s.add_argument('part', choices=list(PARTS))
    s.add_argument('query', nargs='?', default='')
    s.add_argument('--gender', choices=['female', 'male'])
    s.add_argument('--limit', type=int, default=8)
    add_library(s)
    s.set_defaults(run=cmd_assets)

    g = sub.add_parser('tags', help='List part tags, palettes and facial morph controls')
    g.add_argument('part', nargs='?', choices=list(PARTS))
    add_library(g)
    g.set_defaults(run=cmd_tags)

    v = sub.add_parser('voices', help='List available voices')
    v.set_defaults(run=cmd_voices)

    login = sub.add_parser('login', help='Sign in with hg.network and store a private token locally')
    login.add_argument('--username')
    login.add_argument('--url', help=f'Service URL (default: {remote.PUBLIC_URL})')
    login.set_defaults(run=cmd_login)

    who = sub.add_parser('whoami', help='Show the authenticated account and usage')
    who.add_argument('--url')
    who.set_defaults(run=cmd_whoami)

    for name in ('capabilities', 'tasks', 'search', 'create', 'task', 'project', 'compile', 'scene-import', 'scene-export', 'edit-performance', 'render', 'preview', 'export-build'):
        command = sub.add_parser(name)
        command.set_defaults(run=cmd_studio)
        if name == 'search':
            command.add_argument('query'); command.add_argument('--kind', choices=['props','avatars','motions','sounds'], default='props')
            command.add_argument('--limit', type=int, default=12); command.add_argument('--era'); command.add_argument('--profile')
        if name == 'create':
            command.add_argument('operation', choices=list(CONTRACT['operations'])); command.add_argument('--payload', required=True)
            command.add_argument('--image')
        if name == 'task':
            command.add_argument('identifier'); command.add_argument('--since', type=int, default=0); command.add_argument('--cancel', action='store_true')
        if name == 'project':
            command.add_argument('kind', choices=list(CONTRACT['projects'])); command.add_argument('action', choices=['list','get','save','delete'])
            command.add_argument('--id', dest='identifier'); command.add_argument('--payload'); command.add_argument('--out')
        if name == 'compile': command.add_argument('--script', required=True); command.add_argument('--save', action='store_true')
        if name == 'edit-performance': command.add_argument('--payload', required=True)
        if name == 'scene-import': command.add_argument('path')
        if name in ('scene-export', 'preview'): command.add_argument('url')
        if name in ('scene-export', 'preview', 'render', 'export-build'): command.add_argument('--out', required=True)
        if name in ('render', 'export-build'):
            source = command.add_mutually_exclusive_group(required=True); source.add_argument('--id', dest='identifier')
            source.add_argument('--record' if name == 'render' else '--build')
        if name == 'render': command.add_argument('--width', type=int, default=1280)
    return p


def main():
    args = parser().parse_args()
    if args.command == 'avatar' and args.photo and not args.gender:
        parser().error('--gender is required when creating an avatar from a photo')
    try:
        result = args.run(args)
    except (ValueError, PermissionError, RuntimeError) as error:
        print(json.dumps({'error': str(error)}, ensure_ascii=False))
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
