"""素材、颜色、发音人：按部位和标签搜素材，把「长卷发、栗色、圆框眼镜」这类描述对到具体素材上

纯 Python，读 dhuman-assets.json、config.js、voices.js（在项目里直接读，单独装的客户端从服务上取），不需要浏览器。
标签是英文词（见 tag_vocabulary），中文描述由调用的 Agent 自己换成这些词。
"""
import json
import re
from collections import Counter
from functools import lru_cache

from .remote import project_text

# 部位 → (清单里的分类, 页面里的类型, 名称筛选)。妆容和面罩在清单里同一分类，按名称分开
PARTS = {
    'hair': ('hair', 'hair', None),
    'eyes': ('eye', 'eyes', None),
    'eyebrow': ('eyebrows', 'eyebrow', None),
    'beard': ('beard', 'beard', None),
    'makeup': ('facemask', 'makeup', lambda name: name.startswith('facemask-makeup')),
    'facemask': ('facemask', 'facemasks', lambda name: not name.startswith('facemask-makeup')),
    'glasses': ('glasses', 'glasses', None),
    'headwear': ('headwear', 'headwear', None),
    'facewear': ('facewear', 'facewear', None),
    'shirt': ('shirt', 'shirt', None),
    'outfit': ('outfit', 'outfit', None),
    'faceshape': ('faceshape', 'faceshapes', None),
    'eyeshape': ('eyeshape', 'eyeshapes', None),
    'noseshape': ('noseshape', 'noseshapes', None),
    'lipshape': ('lipshape', 'lipshapes', None),
}
STYLE_FIELDS = ('hairStyle', 'beardStyle', 'eyebrowStyle', 'eyeStyle', 'glassesStyle')
PALETTES = {'skin': 'skinTones', 'hair': 'hairColors'}
HEX = re.compile(r'^#[0-9a-fA-F]{6}$')


@lru_cache(maxsize=1)
def catalog():
    return json.loads(project_text('dhuman-assets.json'))


def assets_of(part):
    if part not in PARTS:
        raise ValueError(f'不认识的部位：{part}（可用：{", ".join(PARTS)}）')
    category, _, match = PARTS[part]
    return [a for a in catalog()[category] if not match or match(a['name'])]


def words_of(asset):
    """素材的检索词：tags + 各风格字段按下划线拆开"""
    words = set(asset.get('tags', []))
    for field in STYLE_FIELDS:
        if asset.get(field):
            words.add(asset[field])
            words.update(asset[field].split('_'))
    return words


def summary(asset):
    style = next((asset[f] for f in STYLE_FIELDS if asset.get(f)), '')
    return {'name': asset['name'], 'gender': asset.get('gender') or 'any', 'style': style,
            'tags': asset.get('tags', []), 'icon': asset.get('icon', '')}


def search_assets(part, query='', gender=None, limit=8):
    """按标签词打分：精确命中一个标签算 1 分，只是包含算半分；同分时标签少、更专一的在前。
    性别不符的不要（通用款都要）"""
    terms = [t for t in re.split(r'[\s,，、]+', query.lower()) if t]
    scored = []
    for asset in assets_of(part):
        if gender and asset.get('gender') and asset['gender'] != gender:
            continue
        words = words_of(asset)
        score = sum(1 if term in words else 0.5 if any(term in w for w in words) else 0 for term in terms)
        if terms and not score:
            continue
        scored.append((score, -len(words), asset))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    return [summary(asset) for _, _, asset in scored[:limit]]


def find_asset(part, value, gender=None):
    """value 是素材名（如 hair-28）就直接用，否则当检索词取最匹配的一款"""
    exact = next((a for a in assets_of(part) if a['name'] == value), None)
    if exact:
        return exact
    found = search_assets(part, value, gender, limit=1)
    if not found:
        raise ValueError(f'{part} 没找到匹配「{value}」的素材，可以先用 search_assets 看看有哪些标签')
    return next(a for a in assets_of(part) if a['name'] == found[0]['name'])


def tag_vocabulary(part=None, top=60):
    """各部位常用的标签词，告诉 Agent 描述该怎么写"""
    parts = [part] if part else list(PARTS)
    out = {}
    for name in parts:
        counter = Counter(w for a in assets_of(name) for w in words_of(a))
        out[name] = [word for word, _ in counter.most_common(top)]
    return out


@lru_cache(maxsize=1)
def palettes():
    """config.js 里的肤色、发色调色板：{'skin': [{name, color}], 'hair': [...]}"""
    text = project_text('config.js')
    out = {}
    for kind, key in PALETTES.items():
        block = text[text.index(f'{key}:'):]
        block = block[:block.index(']')]
        out[kind] = [{'name': n, 'color': c} for n, c in re.findall(r"name:\s*'([^']+)',\s*color:\s*'([^']+)'", block)]
    return out


def resolve_color(kind, value):
    """颜色可以写 #RRGGBB，也可以写调色板里的名字（如 栗色、小麦）"""
    if not value:
        return None
    if HEX.match(value):
        return value
    for item in palettes()[kind]:
        if item['name'] == value:
            return item['color']
    names = '、'.join(item['name'] for item in palettes()[kind])
    raise ValueError(f'不认识的{"肤色" if kind == "skin" else "发色"}：{value}（可写 #RRGGBB 或：{names}）')


def voices(service):
    """可用的发音人：voices.js 里的固定发音人 + 服务器上的克隆声音；MiMo 要服务器配了密钥才可用
    （经线上 Agent 入口时服务器只开放微软发音人）"""
    fixed = [{'voice': v, 'name': n, 'desc': d, 'lang': lang}
             for v, n, d, lang in re.findall(r"voice\('([^']+)', '([^']+)', '([^']+)', '(\w+)'\)",
                                             project_text('voices.js'))]
    data = service.get('/api/voices')
    clones = [{'voice': f'clone:{c["id"]}', 'name': c['name'], 'desc': '克隆声音', 'lang': 'zh'}
              for c in data.get('voices', [])]
    usable = [v for v in fixed if data.get('mimoReady') or not v['voice'].startswith('mimo:')]
    return clones + usable
