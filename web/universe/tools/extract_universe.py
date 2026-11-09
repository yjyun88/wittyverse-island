# 우주(태양계) 콘텐츠 리소스 추출: 웹 빌드가 내려받는 공개 Addressables 묶음에서 Spine·그림·배치·글자·소리를 꺼내 res/ 에 저장
#   필요: UnityPy, brotli, numpy, pillow (예: python -m venv upy && upy/Scripts/pip install UnityPy brotli numpy pillow)
#   사용: <그 파이썬> -I extract_universe.py <캐시 폴더> <res 폴더>
#   원본: https://koominchul.github.io/webgl_test/build_universeWeb/ (Unity 6000.3, Spine 4.1.24) — 위티 앱 우주 화면(Luck9kr.Uisystem.UniverseView)과 같은 콘텐츠
import sys, os, json, urllib.request, urllib.parse, hashlib
import UnityPy, numpy as np
from PIL import Image

CACHE, RES = sys.argv[1], sys.argv[2]
CATALOG = 'https://koominchul.github.io/webgl_test/build_universeWeb/StreamingAssets/aa/catalog.json'
for d in (CACHE, RES, RES + '/img', RES + '/text', RES + '/snd', RES + '/spine'): os.makedirs(d, exist_ok=True)

def fetch(url, path):
    if not os.path.exists(path):
        data = urllib.request.urlopen(urllib.parse.quote(url, safe=':/')).read()
        open(path, 'wb').write(data)
    return path
cat = json.load(open(fetch(CATALOG, CACHE + '/catalog.json'), encoding='utf-8'))
bundles = {os.path.basename(u): u for u in cat['m_InternalIds'] if u.endswith('.bundle')}
def bundle(prefix):
    name = next(n for n in bundles if n.startswith(prefix))
    return fetch(bundles[name], CACHE + '/' + name)
MONO = bundle('98d4ddf33a9786203068b4733102280f_monoscripts')
env = UnityPy.load(MONO, bundle('view_assets'))

# 1) Spine: 스켈레톤 JSON, 아틀라스, 아틀라스 그림(일반 알파)
for o in env.objects:
    if o.type.name == 'TextAsset':
        t = o.read(); b = t.m_Script.encode('utf-8', 'surrogateescape') if isinstance(t.m_Script, str) else bytes(t.m_Script)
        if t.m_Name == 'Planet': open(RES + '/spine/Planet.json', 'wb').write(b)
        if t.m_Name == 'Planet.atlas': open(RES + '/spine/Planet.atlas', 'wb').write(b)
    if o.type.name == 'Texture2D':
        t = o.read()
        if t.m_Name in ('Planet', 'Planet_2'): t.image.save(RES + f'/spine/{t.m_Name}.png')

# 2) 화면 배치(RectTransform 계층)와 UI 그림(Sprite, 9분할 테두리 포함)
sprites = {}
def sprite_name(ref):
    if not ref or ref.path_id == 0: return None
    s = ref.read(); n = s.m_Name
    if n not in sprites:
        s.image.save(RES + f'/img/{n}.png'); b = s.m_Border
        sprites[n] = {'w': round(s.m_Rect.width), 'h': round(s.m_Rect.height), 'border': [round(b.x), round(b.y), round(b.z), round(b.w)]}  # 왼·아래·오른·위
    return n
v2 = lambda v: [round(v.x, 2), round(v.y, 2)]
texts = set()
def node(rt):
    g = rt.m_GameObject.read()
    d = {'name': g.m_Name, 'on': bool(g.m_IsActive), 'amin': v2(rt.m_AnchorMin), 'amax': v2(rt.m_AnchorMax), 'piv': v2(rt.m_Pivot),
         'pos': v2(rt.m_AnchoredPosition), 'size': v2(rt.m_SizeDelta), 'scale': round(rt.m_LocalScale.x, 3)}
    for c in g.m_Components:
        p = c.component if hasattr(c, 'component') else c
        try: ob = p.read()
        except Exception: continue
        tn = ob.object_reader.type.name
        if tn == 'CanvasGroup': d['alpha'] = ob.m_Alpha; continue
        if tn != 'MonoBehaviour': continue
        try: cn = ob.m_Script.read().m_ClassName
        except Exception: continue
        tt = ob.object_reader.read_typetree()
        if cn == 'Image':
            d['img'] = sprite_name(ob.m_Sprite); col = tt['m_Color']; d['color'] = [round(col[k], 3) for k in 'rgba']; d['sliced'] = tt.get('m_Type') == 1
        elif cn == 'SkeletonGraphic': d['spine'] = {'anim': tt['startingAnimation'], 'loop': bool(tt['startingLoop'])}
        elif cn == 'TextMeshProUGUI':
            col = tt['m_fontColor']; d['text'] = {'s': tt['m_text'].strip(), 'size': tt['m_fontSize'], 'color': [round(col[k], 3) for k in 'rgba'], 'spacing': tt.get('m_characterSpacing', 0)}
            texts.add((d['text']['s'], d['text']['size'], tuple(d['text']['color']), d['text']['spacing']))
        elif cn == 'Button': d['button'] = True
        elif cn == 'SFXUIButtonEvent': d['sfx'] = tt.get('soundName')
        elif cn == 'Mask': d['mask'] = True
        elif cn == 'UniverseView': d['hideSlotPrefixes'] = tt.get('hideSlotPrefixes', [])
    kids = []
    for ch in rt.m_Children:
        k = ch.read(); n = k.m_GameObject.read().m_Name
        if not (n.startswith('Renderer') and n[8:].isdigit()): kids.append(node(k))   # SkeletonGraphic 보조 렌더러는 제외
    if kids: d['kids'] = kids
    return d
root = None
for o in env.objects:
    if o.type.name == 'RectTransform':
        rt = o.read()
        if (not rt.m_Father or rt.m_Father.path_id == 0) and rt.m_GameObject.read().m_Name == 'UniverseView': root = node(rt)
json.dump(root, open(RES + '/layout.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
json.dump(sprites, open(RES + '/sprites.json', 'w', encoding='utf-8'), separators=(',', ':'))

# 2-1) 한국어 문구표(Localization): 행성 이름, 카드 팝업 제목(planet_characteristics_<행성>_0N) → res/strings.json
lenv = UnityPy.load(bundle('localization-string-tables-korean'), bundle('localization-assets-shared'))
lkeys, strings = {}, {}
for o in lenv.objects:
    if o.type.name != 'MonoBehaviour': continue
    try: tt = o.read_typetree()
    except Exception: continue
    if tt.get('m_Entries') and 'm_Key' in tt['m_Entries'][0]:
        for e in tt['m_Entries']: lkeys[e['m_Id']] = e['m_Key']
for o in lenv.objects:
    if o.type.name != 'MonoBehaviour': continue
    try: tt = o.read_typetree()
    except Exception: continue
    for e in tt.get('m_TableData', []):
        k = lkeys.get(e['m_Id'], '')
        if k.startswith('planet_'): strings[k] = e['m_Localized'].strip()
json.dump(strings, open(RES + '/strings.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=0)

# 3) 글자: TextMeshPro 글자 지도(SDF)로 문구 그림을 만든다(2배 해상도). 원본 설정: ONE Mobile POP, 외곽선·그림자 없음
fa = next(o.read_typetree() for o in env.objects if o.type.name == 'MonoBehaviour' and (lambda t: t.get('m_Name') == 'ONE Mobile POP SDF' and 'm_GlyphTable' in t)(o.read_typetree()))
atlas = next(o.read() for o in env.objects if o.type.name == 'Texture2D' and o.read().m_Name == 'ONE Mobile POP SDF Atlas')
A = np.array(atlas.image.convert('RGBA'))[..., 3].astype(np.float32) / 255; AH = A.shape[0]
face = fa['m_FaceInfo']; PT = face['m_PointSize']; PAD = fa['m_AtlasPadding']; G = PAD + 1          # 그라데이션 폭(텍셀) = 패딩+1 (TMP 기본)
glyphs = {g['m_Index']: g for g in fa['m_GlyphTable']}; cmap = {c['m_Unicode']: c['m_GlyphIndex'] for c in fa['m_CharacterTable']}
EXTRA = json.load(open(os.path.join(os.path.dirname(__file__), 'extra_texts.json'), encoding='utf-8'))   # 배치에 없는 문구(카드 제목 등)
for e in EXTRA: texts.add((e['s'], e['size'], tuple(e['color']), e.get('spacing', 0)))
for k, v in strings.items():
    if k.startswith('planet_characteristics_'): texts.add((v, 72, (1, 1, 1, 1), 0))     # 카드 팝업 제목(DetailPopup/Title 72, 흰색)
    elif k.count('_') == 1: texts.add((v, 70, (1, 1, 1, 1), 0))                           # 상세 창 제목(행성 이름 70, 흰색)
textmeta = {}
for s, size, color, spacing in sorted(texts):
    if not s or s == '-': continue
    k = 2.0; sc = size / PT * k                                                   # 글자 지도 텍셀 → 출력 픽셀
    asc, desc = face['m_AscentLine'] * size / PT, face['m_DescentLine'] * size / PT
    adv = []; x = 0.0
    for ch in s:
        g = glyphs[cmap[ord(ch)]]; adv.append((x, g)); x += (g['m_Metrics']['m_HorizontalAdvance'] * size / PT) + spacing * 0.01 * size
    W = int(np.ceil((x - spacing * 0.01 * size + 2) * k)); H = int(np.ceil((asc - desc + 2) * k)); out = np.zeros((H, W), np.float32)
    for x0, g in adv:
        m, r = g['m_Metrics'], g['m_GlyphRect']
        if r['m_Width'] == 0: continue
        cx0, cy0 = r['m_X'] - PAD, AH - (r['m_Y'] + r['m_Height']) - PAD; cw, chh = r['m_Width'] + 2 * PAD, r['m_Height'] + 2 * PAD
        crop = A[cy0:cy0 + chh, cx0:cx0 + cw]
        tw, th = max(1, int(round(cw * sc))), max(1, int(round(chh * sc)))
        d = np.array(Image.fromarray(np.ascontiguousarray(crop), 'F').resize((tw, th), Image.BILINEAR))
        alpha = np.clip((d - 0.5) * 2 * G * sc + 0.5, 0, 1)                        # 가장자리 0.5, 1텍셀 = sc 픽셀
        px = int(round((1 + x0 + (m['m_HorizontalBearingX'] - PAD) * size / PT) * k)); py = int(round((1 + asc - (m['m_HorizontalBearingY'] + PAD) * size / PT) * k))
        ys, xs = slice(max(0, py), min(H, py + th)), slice(max(0, px), min(W, px + tw))
        out[ys, xs] = np.maximum(out[ys, xs], alpha[ys.start - py:ys.stop - py, xs.start - px:xs.stop - px])
    rgba = np.zeros((H, W, 4), np.uint8); rgba[..., :3] = (np.array(color[:3]) * 255).astype(np.uint8); rgba[..., 3] = (out * color[3] * 255).astype(np.uint8)
    key = f'{s}|{size:g}'; fn = hashlib.md5(f'{key}|{color}|{spacing}'.encode()).hexdigest()[:12] + '.png'   # 내용 기반 이름(웹뷰 캐시가 옛 그림을 쓰지 않게)
    Image.fromarray(rgba, 'RGBA').save(RES + '/text/' + fn)
    textmeta[key] = {'f': fn, 'w': W / k, 'h': H / k}
json.dump(textmeta, open(RES + '/text/text.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))

# 4) 소리: 우주 화면에서 쓰는 것만(배경음, 버튼, 장면·행성 내레이션)
senv = UnityPy.load(bundle('sound_assets'))
for o in senv.objects:
    if o.type.name == 'AudioClip':
        a = o.read(); n = a.m_Name
        if n in ('UniverseBGM', 'Selection', 'Button') or n.startswith('planet_'):
            for fname, data in a.samples.items(): open(RES + '/snd/' + n + os.path.splitext(fname)[1], 'wb').write(data)
print('끝: 그림', len(sprites), '문구', len(textmeta), '→', RES)
