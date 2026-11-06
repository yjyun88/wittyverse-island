# 3D 이글루·펭귄 배치(적게). 큰 섬에 이글루 1개 + 펭귄 2마리
# 이글루: 섬에서 해안과 가장 먼 한가운데. 펭귄: 이글루와 바다 사이(해안 쪽)에, 가장 가까운 바다를 바라보게(to)
# 등대와 4.5° 이상 떨어진 자리, 걸치는 야자수는 뺌. 결과는 src/globe3/polar.json(나무는 trees.json에서 정리)
# 사용: python place_polar.py <src/globe3 폴더> [시드]
import sys, json, math, numpy as np
from PIL import Image
from scipy import ndimage as nd
from scipy.spatial import cKDTree
g = sys.argv[1]; rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 6)
tex = np.array(Image.open(g + '/tex.png')).astype(np.float32) / 255
L, H = tex[..., 0], tex[..., 2]; HN, WN = L.shape
land = L > 0.5; lab, n = nd.label(land)
trees = json.load(open(g + '/trees.json')); coast = json.load(open(g + '/coast.json'))

def px(lat, lon):
    return int(min(HN - 1, max(0, (90 - lat) / 180 * HN))), int((lon + 180) / 360 * WN) % WN
def ll(r, c): return 90 - (r + .5) / HN * 180, (c + .5) / WN * 360 - 180
def ang(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return math.degrees(math.acos(max(-1, min(1, math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo1 - lo2)))))
def xyz(lat, lon):
    la, lo = np.radians(lat), np.radians(lon); return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)
# 바다 점들(가장 가까운 바다 찾기용)
sy, sx = np.nonzero(~land[::2, ::2]); slat = 90 - (sy * 2 + 1) / HN * 180; slon = (sx * 2 + 1) / WN * 360 - 180
sea_tree = cKDTree(xyz(slat, slon))
def nearest_sea(p):
    d, i = sea_tree.query(xyz(np.array(p[0]), np.array(p[1]))); return math.degrees(2 * math.asin(min(1, d / 2))), (float(slat[i]), float(slon[i]))
AVOID = [((o['lat'], o['lon']), 4.5) for o in coast if o['k'] == 'lighthouse']   # 섬의 야자수는 피하지 않고, 걸치면 아래에서 뺌
out = []
def free(p, others=1.6): return all(ang(p, q) > r for q, r in AVOID) and all(ang(p, (o['lat'], o['lon'])) > (3.0 if o['k'] == 'igloo' else others) for o in out)
def add(k, p, yaw=0.0, to=None):
    r, c = px(*p); o = {'k': k, 'lat': round(p[0], 2), 'lon': round(p[1], 2), 'rot': round(float(yaw), 1), 'H': round(float(H[r, c]), 3)}
    if to: o['to'] = [round(to[0], 2), round(to[1], 2)]
    out.append(o)

CAMPS = [(-45, 8)]                     # 큰 섬(섬 안의 한 점). 중간 섬은 너무 좁아 뺌
for cp0 in CAMPS:
    li = lab[px(*cp0)]; ys, xs = np.nonzero((lab == li) & (H > 0.9))
    pts = [ll(y, x) for y, x in zip(ys[::2], xs[::2])]
    lhs = [(o['lat'], o['lon']) for o in coast if o['k'] == 'lighthouse']
    # 해안에서 멀수록 + 등대에서 멀수록 좋은 자리(작은 섬에서 등대와 맞닿지 않게)
    ds = [nearest_sea(p)[0] + 0.6 * min([ang(p, q) for q in lhs] + [10]) for p in pts]
    order = np.argsort(ds)[::-1]
    ig = next((pts[j] for j in order if free(pts[j])), None)
    if ig is None: print('이글루 자리 없음', cp0); continue
    add('igloo', ig, rng.uniform(0, 360))
    # 펭귄: 이글루에서 바다 쪽 방향 ±50° 안, 이글루 둘레(약 2.4°) 밖, 해안에서 0.6° 이상 안쪽
    _, sp = nearest_sea(ig); base = math.atan2(sp[0] - ig[0], (sp[1] - ig[1]) * math.cos(math.radians(ig[0])))
    made = 0
    for _ in range(600):
        if made >= 2: break
        a = base + rng.uniform(-0.9, 0.9); d = rng.uniform(3.8, 4.8)   # 이글루(눈 받침 포함 반지름 약 3.2°) 밖
        q = (ig[0] + d * math.sin(a), (ig[1] + d * math.cos(a) / max(0.3, math.cos(math.radians(ig[0]))) + 180) % 360 - 180)
        r, c = px(*q)
        if lab[r, c] != li or H[r, c] < 0.85: continue
        sd, sq = nearest_sea(q)
        if sd < 0.5 or not free(q): continue
        add('penguin', q, to=sq); made += 1
# 사용자 화면에서 직접 조정한 값: 이글루 위치·입구 방향(to), 왼쪽 펭귄 위치
IGLOO_SET = {'pos': (-47.57, 6.86), 'door_to': (-39.16, 13.79)}
PENG_MOVE = {(-40.09, 11.31): (-39.09, 15.01)}
for o in out:
    if o['k'] == 'igloo' and IGLOO_SET:
        r, c = px(*IGLOO_SET['pos']); o['lat'], o['lon'] = IGLOO_SET['pos']; o['H'] = round(float(H[r, c]), 3); o['to'] = list(IGLOO_SET['door_to'])
    if o['k'] == 'penguin':
        for src, dst in PENG_MOVE.items():
            if ang((o['lat'], o['lon']), src) < 0.5:
                r, c = px(*dst); o['lat'], o['lon'] = dst; o['H'] = round(float(H[r, c]), 3); o['to'] = [round(v, 2) for v in nearest_sea(dst)[1]]
json.dump(out, open(g + '/polar.json', 'w'), separators=(',', ':'))
# 이글루(눈 받침 포함 반지름 약 3.2°) + 1°, 펭귄 둘레 1.2° 안의 나무는 빼서 trees.json에 다시 씀
# (실행 순서: place_trees -> place_buildings -> place_landmarks -> place_coast -> place_polar)
kept = [t for t in trees if all(ang((t['lat'], t['lon']), (o['lat'], o['lon'])) > (4.2 if o['k'] == 'igloo' else 1.2) for o in out)]
json.dump(kept, open(g + '/trees.json', 'w'), separators=(',', ':'))
print('나무', len(trees), '->', len(kept))
print(len(out), [(o['k'], o['lat'], o['lon']) for o in out])
