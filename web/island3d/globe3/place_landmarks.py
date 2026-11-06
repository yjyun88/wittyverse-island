# 3D 산·바위·무지개 배치. 나무·건물과 겹치지 않는 빈 땅에 둔다. 결과는 src/globe3/landmarks.json
# 나무는 trees_all.json(place_trees.py 결과 원본)을 읽고, 산·바위에 걸친 나무를 뺀 결과를 trees.json에 쓴다
# k: 'mtn'=산(s로 크기 차등), 'rock'=바위 무리, 'rainbow'=무지개(산맥의 두 봉우리 사이, lift=들어 올림, to=작은 봉우리 방향)
# 사용: python place_landmarks.py <src/globe3 폴더> [시드]
import sys, json, math, numpy as np
from PIL import Image
from scipy import ndimage as nd
g = sys.argv[1]; rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 9)
tex = np.array(Image.open(g + '/tex.png')).astype(np.float32) / 255
L, H = tex[..., 0], tex[..., 2]; HN, WN = L.shape
import os
TALL = g + '/trees_all.json'                                         # place_trees.py 결과 원본(없으면 trees.json을 원본으로 보관)
if not os.path.exists(TALL): json.dump(json.load(open(g + '/trees.json')), open(TALL, 'w'), separators=(',', ':'))
trees = json.load(open(TALL)); blds = json.load(open(g + '/buildings.json'))
lab, n = nd.label(L > 0.5)

def px(lat, lon):
    return int(min(HN - 1, max(0, (90 - lat) / 180 * HN))), int((lon + 180) / 360 * WN) % WN
def ang(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return math.degrees(math.acos(max(-1, min(1, math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo1 - lo2)))))
def ok(p, need=0.95):
    r, c = px(*p); return L[r, c] > 0.98 and H[r, c] > need
out = []
def free(p, gt, gb, go):
    return (all(ang(p, (t['lat'], t['lon'])) > gt for t in trees) and all(ang(p, (b['lat'], b['lon'])) > gb for b in blds)
            and all(ang(p, (o['lat'], o['lon'])) > go * (1 + 0.5 * o['s']) for o in out))
def add(k, p, s, yaw=None):
    r, c = px(*p)
    out.append({'k': k, 'lat': round(p[0], 2), 'lon': round(p[1], 2), 's': round(float(s), 3),
                'rot': round(float(rng.uniform(0, 360) if yaw is None else yaw), 1), 'H': round(float(H[r, c]), 3)})
def rand_on(li, need=0.98):
    for _ in range(20000):
        p = (math.degrees(math.asin(rng.uniform(-0.85, 0.85))), rng.uniform(-180, 180))
        if lab[px(*p)] == li and ok(p, need): yield p

# 대륙(대륙 안의 한 점)
CONT = {'pine': (30, -150), 'cherry': (24, 33), 'palm': (-15, -63), 'round': (-20, 122)}
LI = {k: lab[px(*p)] for k, p in CONT.items()}
# 산 모양(3D 모델과 같은 옆모습): (반지름, 높이), 모델 크기 0.16*s(지구 반지름 단위)
PROF = [(0.62, 0), (0.58, 0.12), (0.48, 0.35), (0.34, 0.6), (0.2, 0.8), (0.12, 0.895), (0.06, 0.948), (0.025, 0.966), (0, 0.972)]
MSIZE = 0.16
def base_deg(s): return math.degrees(0.62 * MSIZE * s)              # 산 밑변 반지름(°)
def slope_h(dist_deg, s):                                           # 봉우리에서 dist만큼 떨어진 곳의 산비탈 높이(지구 반지름 단위)
    r = math.radians(dist_deg) / (MSIZE * s)
    if r >= 0.62: return 0.0
    for (r0, y0), (r1, y1) in zip(PROF, PROF[1:]):
        if r <= r0 and r >= r1: return (y0 + (y1 - y0) * (r0 - r) / (r0 - r1)) * MSIZE * s
    return 0.97 * MSIZE * s
def on_land(p, R):                                                  # 산 밑변(반지름 R°) 전체가 땅 위인지: 둘레 두 겹, 30° 간격 검사
    if not ok(p, 0.98): return False
    for rr in (R * 0.5, R * 1.0):
        for k in range(12):
            if not ok(step(p, rr, k * math.pi / 6), 0.5): return False
    return True
def dist_at_h(h, s):                                                # 봉우리에서 비탈 높이가 h인 곳까지 거리(°)
    y = h / (MSIZE * s)
    for (r0, y0), (r1, y1) in zip(PROF, PROF[1:]):
        if y0 <= y <= y1: return math.degrees((r0 + (r1 - r0) * (y - y0) / (y1 - y0)) * MSIZE * s)
    return 0.0
def slerp(a, b, t):                                                 # 두 위경도 사이를 t 비율로 잇는 대원 위의 점
    va = [math.cos(math.radians(a[0])) * math.cos(math.radians(a[1])), math.cos(math.radians(a[0])) * math.sin(math.radians(a[1])), math.sin(math.radians(a[0]))]
    vb = [math.cos(math.radians(b[0])) * math.cos(math.radians(b[1])), math.cos(math.radians(b[0])) * math.sin(math.radians(b[1])), math.sin(math.radians(b[0]))]
    w = math.acos(max(-1, min(1, sum(x * y for x, y in zip(va, vb)))))
    v = [(math.sin((1 - t) * w) * x + math.sin(t * w) * y) / math.sin(w) for x, y in zip(va, vb)]
    return math.degrees(math.asin(v[2])), math.degrees(math.atan2(v[1], v[0]))
def step(p, d, a):
    return (p[0] + d * math.sin(a), (p[1] + d * math.cos(a) / max(0.3, math.cos(math.radians(p[0]))) + 180) % 360 - 180)
# 산맥: 큰 산 1 + 작은 산 1~2. 산기슭만 살짝 맞닿게(밑변 반지름 합의 85%) 띄움
# 무지개: 산맥 3곳에서 큰 봉우리와 첫 작은 봉우리 사이에 걸침(양 다리가 각 비탈에 닿음)
RANGES = [('pine', True), ('pine', False), ('round', True), ('cherry', True), ('palm', False)]
for name, with_rb in RANGES:
    for p in rand_on(LI[name]):
        sb = float(rng.uniform(1.15, 1.35))
        if not free(p, 4.5, 8, 14) or not on_land(p, base_deg(sb)): continue
        peaks = [(p, sb)]
        for _ in range(int(rng.integers(1, 3))):
            for _t in range(120):
                ss = float(rng.uniform(0.75, 0.95)); d = 0.85 * (base_deg(sb) + base_deg(ss)); a = rng.uniform(0, 2 * math.pi)
                q = step(p, d, a)
                if on_land(q, base_deg(ss)) and free(q, 2.6, 6, 0) and all(ang(q, pk) > 0.85 * (base_deg(s0) + base_deg(ss)) - 0.01 for pk, s0 in peaks):
                    peaks.append((q, ss)); break
        if with_rb and len(peaks) < 2: continue          # 무지개를 걸 산맥인데 작은 봉우리를 못 만들면 다른 자리
        for pk, s0 in peaks: add('mtn', pk, s0)
        if with_rb:
            (pb, sb), (ps, ss) = peaks[0], peaks[1]
            # 같은 높이 Lh에서 큰 봉우리·작은 봉우리 비탈에 닿는 두 지점을 무지개 양 끝으로(끝은 비탈에 살짝 묻힘)
            d = ang(pb, ps); Lh = 0.7 * 0.972 * MSIZE * ss   # 작은 봉우리 높이의 70%
            xb, xs = dist_at_h(Lh, sb), dist_at_h(Lh, ss)          # 각 봉우리에서 그 높이 지점까지 거리(°)
            hs = (d - xb - xs) / 2 * 1.2                            # 무지개 반폭(°), 20% 더 넓혀 다리가 비탈에 묻히게
            m = slerp(pb, ps, (xb + (d - xb - xs) / 2) / d)          # 두 끝의 가운데
            sr = math.radians(hs) / (0.62 * 0.13) * 2.0           # 두 배 크기(다리는 양쪽 산 속으로 더 묻힘)
            lift = Lh
            r, c = px(*m)
            out.append({'k': 'rainbow', 'lat': round(m[0], 2), 'lon': round(m[1], 2), 's': round(sr, 3), 'rot': 0,
                        'H': round(float(H[r, c]), 3), 'lift': round(lift, 4), 'to': [round(ps[0], 2), round(ps[1], 2)]})
        break
# 바위 무리: 형상·배치가 어색해 일단 뺌(ROCKS=0). 다시 쓰려면 개수만 바꾸면 됨
ROCKS = 0
rocks = 0
for _ in range(40000 if ROCKS else 0):
    if rocks >= ROCKS: break
    p = (math.degrees(math.asin(rng.uniform(-0.85, 0.85))), rng.uniform(-180, 180))
    if ok(p, 0.9) and free(p, 2.0, 3.5, 3.0): add('rock', p, rng.uniform(0.8, 1.15)); rocks += 1
json.dump(out, open(g + '/landmarks.json', 'w'), separators=(',', ':'))
# 산 밑변 안과 둘레 1°, 바위 무리 둘레에 걸친 나무는 빼서 trees.json으로(산·바위에 붙어 보이지 않게)
def clear_of(t):
    for o in out:
        if o['k'] == 'mtn' and ang((t['lat'], t['lon']), (o['lat'], o['lon'])) < base_deg(o['s']) + 1.0: return False
        if o['k'] == 'rock' and ang((t['lat'], t['lon']), (o['lat'], o['lon'])) < 1.8: return False
    return True
kept = [t for t in trees if clear_of(t)]
json.dump(kept, open(g + '/trees.json', 'w'), separators=(',', ':'))
print('나무', len(trees), '->', len(kept))
print(len(out), {k: sum(o['k'] == k for o in out) for k in ['mtn', 'rock', 'rainbow']})
