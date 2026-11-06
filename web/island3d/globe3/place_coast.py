# 3D 등대·돛단배 배치. 결과는 src/globe3/coast.json
# 등대: 섬(작은 땅 덩어리)에만 하나씩. 섬 가장자리 쪽, 나무와 겹치지 않는 자리
# 돛단배: 바다(대륙 사이 4곳 + 북극해·남극해)마다 한 척, 각 바다 한가운데
# 사용: python place_coast.py <src/globe3 폴더> [시드]
import sys, json, math, numpy as np
from PIL import Image
from scipy import ndimage as nd
g = sys.argv[1]; rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 4)
tex = np.array(Image.open(g + '/tex.png')).astype(np.float32) / 255
L, H = tex[..., 0], tex[..., 2]; HN, WN = L.shape
trees = json.load(open(g + '/trees.json'))
land = L > 0.5
lab, n = nd.label(land); sizes = nd.sum(land, lab, range(1, n + 1))

def px(lat, lon):
    return int(min(HN - 1, max(0, (90 - lat) / 180 * HN))), int((lon + 180) / 360 * WN) % WN
def ll(r, c): return 90 - (r + .5) / HN * 180, (c + .5) / WN * 360 - 180
def ang(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return math.degrees(math.acos(max(-1, min(1, math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo1 - lo2)))))
out = []
def add(k, p, s, yaw=None):
    r, c = px(*p)
    out.append({'k': k, 'lat': round(p[0], 2), 'lon': round(p[1], 2), 's': round(float(s), 3),
                'rot': round(float(rng.uniform(0, 360) if yaw is None else yaw), 1), 'H': round(float(H[r, c]), 3)})

# 등대: 섬(대륙보다 작은 덩어리, 너무 작은 섬 제외)마다 하나. 사용자 요청으로 뺀 섬(NO_LH: 섬 안의 한 점)의 등대는
# 배 배치가 바뀌지 않도록 마지막에 뺌
NO_LH = [(-14, 33), (-15, -11)]
no_lab = {lab[px(*q)] for q in NO_LH}
# 사용자 요청으로 위치를 정한 섬: 섬 안의 한 점 -> 이 지점에 가장 가까운 빈 자리에 등대
LH_PIN = {(-45, -133): (-39.69, -136.53)}
pin_lab = {lab[px(*q)]: v for q, v in LH_PIN.items()}
pinned = {}
for i in range(1, n + 1):
    if sizes[i - 1] >= 30000 or sizes[i - 1] < 1500: continue
    ys, xs = np.nonzero((lab == i) & (H > 0.85))
    if not len(ys): continue
    cy, cx = ys.mean(), xs.mean()
    order = np.argsort(-((ys - cy) ** 2 + (xs - cx) ** 2))       # 섬 중심에서 먼(가장자리 쪽) 자리부터
    if i in pin_lab:                                              # 지정 지점에 가장 가까운 빈 자리(배 배치가 바뀌지 않게 마지막에 바꿔 넣음)
        pr, pc = px(*pin_lab[i])
        for j in np.argsort((ys - pr) ** 2 + (xs - pc) ** 2)[:400]:
            q = ll(ys[j], xs[j])
            if all(ang(q, (t['lat'], t['lon'])) > 1.1 for t in trees): pinned[i] = q; break
    for j in order[:400]:
        p = ll(ys[j], xs[j])
        if all(ang(p, (t['lat'], t['lon'])) > 1.1 for t in trees):
            add('lighthouse', p, rng.uniform(0.95, 1.1))
            out[-1]['from'] = [round(ll(cy, cx)[0], 2), round(ll(cy, cx)[1], 2)]   # 섬 중심(앱에서 문이 바다 쪽을 보게 할 때 씀)
            break

# 돛단배: 바다마다 한 척씩, 그 바다에서 육지와 가장 먼 한가운데에.
# 바다 = 이웃한 두 대륙 사이(경도 구간, 위도 ±45° 안) 4곳 + 북극해·남극해(위도 50° 이상) 2곳
# 육지까지 거리는 구 표면의 실제 거리(3D 점 사이 거리 -> 각도)로 계산
from scipy.spatial import cKDTree
def xyz(lat, lon):
    la, lo = np.radians(lat), np.radians(lon); return np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], -1)
ly, lx = np.nonzero(land[::2, ::2]); llat = 90 - (ly * 2 + 1) / HN * 180; llon = (lx * 2 + 1) / WN * 360 - 180
tree = cKDTree(xyz(llat, llon))
def sea_dist(lat, lon):                                            # 가장 가까운 육지까지 각도(°)
    d, _ = tree.query(xyz(np.array(lat), np.array(lon))); return np.degrees(2 * np.arcsin(np.clip(d / 2, 0, 1)))
CONT_LON = sorted([-139, -63, 33, 122])                            # 대륙 중심 경도
SEAS = [('lon', CONT_LON[k], CONT_LON[(k + 1) % 4]) for k in range(4)] + [('north',), ('south',)]
def in_sea(lat, lon, sea):
    if sea[0] == 'north': return lat > 50
    if sea[0] == 'south': return lat < -50
    a, b = sea[1], sea[2]; d = (lon - a) % 360
    return abs(lat) <= 45 and 0 < d < (b - a) % 360
cl = np.degrees(np.arcsin(rng.uniform(-0.99, 0.99, 60000))); co = rng.uniform(-180, 180, 60000)
keep = np.array([not land[px(a, b)] for a, b in zip(cl, co)]); cl, co = cl[keep], co[keep]
cd = sea_dist(cl, co)
for sea in SEAS:
    m = np.array([in_sea(a, b, sea) for a, b in zip(cl, co)])
    if m.any():
        score = cd - (0.2 * np.abs(cl) if sea[0] == 'lon' else 0)   # 대륙 사이 바다는 적도 쪽(바다 한가운데 높이)을 우선
        k = np.argmax(np.where(m, score, -1e9)); add('boat', (float(cl[k]), float(co[k])), rng.uniform(0.9, 1.1))
out = [o for o in out if not (o['k'] == 'lighthouse' and lab[px(o['lat'], o['lon'])] in no_lab)]
# 사용자 요청으로 뺀 배(근처 3° 안의 배를 뺌)
NO_BOAT = [(-29.6, -117.4)]
out = [o for o in out if not (o['k'] == 'boat' and any(ang((o['lat'], o['lon']), q) < 3 for q in NO_BOAT))]
for o in out:
    li = lab[px(o['lat'], o['lon'])]
    if o['k'] == 'lighthouse' and li in pinned:
        o['lat'], o['lon'] = round(pinned[li][0], 2), round(pinned[li][1], 2); r, c = px(o['lat'], o['lon']); o['H'] = round(float(H[r, c]), 3)
json.dump(out, open(g + '/coast.json', 'w'), separators=(',', ':'))
print(len(out), {k: sum(o['k'] == k for o in out) for k in ['lighthouse', 'boat']})
