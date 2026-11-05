"""Effect masks for the live-2D map, measured on the base illustration itself.
Usage: python -I tools/masks_v10.py <base.png> <map.json> <out dir>
map.json: horizon [centre y, side drop, tilt (optional)], island / fall outlines, coral areas (image px; see v10/map.json).
Writes <out>/m_*.png previews and <out>/masks.npz (all at base resolution)."""
import json, sys, numpy as np, cv2
from PIL import Image

SRC, CFG, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
C = json.load(open(CFG, encoding='utf-8'))
im = np.asarray(Image.open(SRC).convert('RGB')).astype(np.float32)
H, W = im.shape[:2]
K = W / 1376                                                     # pixel constants below were tuned on a 1376px wide map
R, G, B = im[..., 0], im[..., 1], im[..., 2]
lum = .299 * R + .587 * G + .114 * B
hsv = cv2.cvtColor(im.astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
sat, val = hsv[..., 1] / 255, hsv[..., 2] / 255
yy, xx = np.mgrid[0:H, 0:W]
hu = (xx - W / 2) / (W / 2)
hz = C['horizon'][0] + hu ** 2 * C['horizon'][1] + hu * (C['horizon'][2] if len(C['horizon']) > 2 else 0)   # sea/sky line, lower at the sides (+ tilt: v10 dips on the left)
odd = lambda v: int(v) | 1

def poly(pts, h=H, w=W, s=1.):
    m = np.zeros((h, w), np.uint8); cv2.fillPoly(m, [(np.array(pts, np.float32) * s).astype(np.int32)], 1); return m.astype(bool)

# refine the hand-traced outline against the picture itself (GrabCut, at ~1376px for speed): the sea near a wrong
# edge otherwise gets no water effects and the shore rings draw the polygon as a dark band
s = 1 / K; h2, w2 = round(H * s), round(W * s)
small = cv2.resize(im.astype(np.uint8), (w2, h2), interpolation=cv2.INTER_AREA)
rough = poly(C['island'], h2, w2, s)
gc = np.full((h2, w2), cv2.GC_BGD, np.uint8)
gc[cv2.dilate(rough.astype(np.uint8), np.ones((61, 61), np.uint8)) > 0] = cv2.GC_PR_BGD
gc[rough] = cv2.GC_PR_FGD
gc[cv2.erode(rough.astype(np.uint8), np.ones((61, 61), np.uint8)) > 0] = cv2.GC_FGD
bg, fg = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
cv2.grabCut(small[..., ::-1].copy(), gc, None, bg, fg, 6, cv2.GC_INIT_WITH_MASK)
isl = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
n_, lab = cv2.connectedComponents(isl.astype(np.uint8)); cnt = np.bincount(lab.ravel()); cnt[0] = 0
keep = cnt >= cnt.max() * .05                                    # v10: three islands that may not touch - keep every big piece
isl = cv2.morphologyEx(keep[lab].astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8)).astype(np.float32)
island = cv2.GaussianBlur(cv2.resize(isl, (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), 2 * K) > .5
fall_zone = poly(C['fall'])

# waterfall + stream: bright cyan/white inside the fall zone
water = fall_zone & (lum > 95) & ((B > R + 25) | (lum > 200))
water = cv2.morphologyEx(water.astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)).astype(bool)
sky = (yy < hz) & ~island
# sea: below the horizon, outside the island (the corals in the corners are kept out by saturation)
coral = np.zeros((H, W), bool)
for c in C.get('corals', []): coral |= poly(c)
sea = (yy >= hz) & ~island & ~(coral & (sat > .45) & (val > .45))
# shoreline distance (in 1376-scale px) for the outgoing ripple rings
dist = cv2.distanceTransform((~island).astype(np.uint8), cv2.DIST_L2, 5) / K
# stars: small bright points in the sky, not the horizon rim or the crystal edges
tophat = lum - cv2.GaussianBlur(lum, (0, 0), 3 * K)
stars = sky & (tophat > 28) & (lum > 120)
stars &= ~(cv2.dilate(island.astype(np.uint8), np.ones((odd(9 * K),) * 2, np.uint8)) > 0) & (yy < hz - 10 * K)
# emissive: bright + saturated, or near-white highlights on the land (neon, fire, windows, crystals)
emis = np.clip(np.clip((val - .78) / .15, 0, 1) * np.clip((sat - .45) / .3, 0, 1) + np.clip((lum - 228) / 20, 0, 1) * .7, 0, 1) * island
emis[water] *= .25

def save(name, m):
    Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).save(f'{OUT}/m_{name}.png')
for n, m in [('water', water), ('sky', sky), ('sea', sea), ('stars', stars), ('emis', emis), ('island', island)]: save(n, m.astype(np.float32))
np.savez_compressed(f'{OUT}/masks.npz', water=water, sky=sky, sea=sea, stars=stars, emis=emis.astype(np.float32), dist=dist, island=island)
# overlay preview: water cyan, shore band blue, sky purple, emissive yellow, stars white, island outline red
ov = im * .45
ov[water] = [0, 255, 255]; ov[sea & (dist < 60)] = ov[sea & (dist < 60)] * .5 + np.array([0, 60, 200]) * .5
ov[sky] = ov[sky] * .6 + np.array([120, 0, 160]) * .4
ov += emis[..., None] * np.array([255, 220, 0]) * .8; ov[stars] = 255
ed = cv2.morphologyEx(island.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((odd(3 * K),) * 2, np.uint8)) > 0; ov[ed] = [255, 60, 60]
Image.fromarray(np.clip(ov, 0, 255).astype(np.uint8)).resize((W // 2, H // 2) if W > 1600 else (W, H)).save(f'{OUT}/m_overlay.png')
print('K', round(K, 2), 'water', water.mean().round(3), 'sky', sky.mean().round(3), 'sea', sea.mean().round(3), 'stars', int(stars.sum()), 'emis', emis.mean().round(3))
