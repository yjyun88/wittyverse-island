"""v10 live-2D world map: day picture on start, a weather button turns it to the night picture with the effects of
v10_v3_effect (aurora, glowing sea, plasma arcs, rocket glow, stage beams ...). Same tap -> island detail flow as v9.
Usage: python -I tools/make_v10.py <map.json> <masks dir (masks_v10.py output on the night picture)> <out.html>
map.json sits next to base_day.png / base_night.png and the detail pictures."""
import base64, io, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np, cv2
from PIL import Image

CFG, MDIR, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
CMAP = json.load(open(CFG, encoding='utf-8'))
here, cdir = os.path.dirname(__file__), os.path.dirname(os.path.abspath(CFG))
night = Image.open(os.path.join(cdir, CMAP.get('night', 'base_night.png'))).convert('RGB'); W, H = night.size
day = Image.open(os.path.join(cdir, CMAP.get('day', 'base_day.png'))).convert('RGB')
assert day.size == night.size, 'day and night pictures must share one layout'
M = np.load(os.path.join(MDIR, 'masks.npz'))
K = W / 1376                                                     # blur radii below were tuned on a 1376px wide map
MS = (W, H) if W <= 1376 else (960, round(H * 960 / W))         # mask texture size (GPU memory on the tablet is tight)

def uri(img, fmt='WEBP', q=90):
    b = io.BytesIO(); img.save(b, fmt, quality=q) if fmt == 'WEBP' else img.save(b, fmt, optimize=True)
    return f'data:image/{fmt.lower()};base64,' + base64.b64encode(b.getvalue()).decode()
u8 = lambda a: (np.clip(a, 0, 1) * 255).astype(np.uint8)
fit = lambda im: im if W <= 1600 else im.resize((1600, round(H * 1600 / W)), Image.LANCZOS)
# tiny, heavily blurred copy: stretched outwards it fills the sides of windows that aren't 16:10
blur = lambda im: uri(Image.fromarray(cv2.GaussianBlur(np.asarray(im.resize((160, 100), Image.LANCZOS)), (0, 0), 3)), q=85)

# masks packed in two RGBA textures (same as v9)
soft = lambda m, s: cv2.GaussianBlur(m.astype(np.float32), (0, 0), s * K)
small = lambda a: cv2.resize(a, MS, interpolation=cv2.INTER_AREA)
m1 = small(np.dstack([soft(M['water'], 1.2), soft(M['sea'], 2), soft(M['sky'], 2), np.clip(soft(M['stars'], .35) * 2.5, 0, 1)]))
m2 = small(np.dstack([M['emis'], np.clip(soft(M['dist'], 9) / 160, 0, 1), soft(M['island'], 1.5), np.zeros((H, W), np.float32)]))
# bloom of the night light sources, half res
src = np.asarray(night).astype(np.float32) / 255 * M['emis'][..., None]
bloom = lambda s: soft(s, 4) * .9 + soft(s, 14) * 1.1 + soft(s, 34) * .9
gmax = max(bloom(src).max(), 1e-6)                                # scale of the undimmed bloom: dimming the brightest source must not brighten the rest
yy, xx = np.mgrid[0:H, 0:W]
for x, y, r, keep in CMAP.get('bloom_dim', []):                  # light sources that bloom too hard at night (campfire, rocket)
    src *= (1 - (1 - keep) * np.exp(-((xx - x) ** 2 + (yy - y) ** 2) / (2 * (r / 2) ** 2)))[..., None]
glow = Image.fromarray(u8(bloom(src) / gmax)).resize((min(W // 2, 960), round(H * min(W // 2, 960) / W)), Image.LANCZOS)

A = {'W': W, 'H': H, 'night': uri(fit(night), q=92), 'day': uri(fit(day), q=92), 'nightBlur': blur(night), 'dayBlur': blur(day), 'm1': uri(Image.fromarray(u8(m1), 'RGBA'), 'PNG'),
     'm2': uri(Image.fromarray(u8(m2), 'RGBA'), 'PNG'), 'glow': uri(glow, q=90), 'horizon': CMAP['horizon'], 'spots': CMAP['spots'], 'zones': {}}
for k, z in CMAP.get('zones', {}).items():
    d = Image.open(os.path.join(cdir, z['detail'])).convert('RGB')
    if d.width > 1600: d = d.resize((1600, round(d.height * 1600 / d.width)), Image.LANCZOS)
    A['zones'][k] = {'name': z['name'], 'poly': z['poly'], 'img': uri(d, q=90), 'blur': blur(d), 'lines': z.get('lines', [])}
if CMAP.get('cast_dir'):
    import cast_v9; A['cast'] = cast_v9.cast(os.path.normpath(os.path.join(cdir, CMAP['cast_dir'])))
html = open(os.path.join(here, 'v10_template.html'), encoding='utf-8').read()
html = html.replace('__THREE__', open(os.path.join(here, 'three_inline.txt'), encoding='utf-8').read()).replace('__ASSETS__', json.dumps(A))
open(OUT, 'w', encoding='utf-8').write(html)
print('v10 written', round(len(html.encode('utf-8')) / 1e6, 2), 'MB')
