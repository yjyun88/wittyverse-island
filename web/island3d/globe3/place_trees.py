# 3D 나무 배치: 숲 무리(그로브) + 드문드문 홀로 선 나무. 결과는 src/globe3/trees.json
# 종류: 0=둥근 나무, 1=침엽수, 2=야자수, 3=벚나무 (대륙마다 기후에 맞는 종류를 주로 심음)
# 사용: python place_trees.py <src/globe3 폴더> [시드]
import sys, json, math, numpy as np
from PIL import Image
g = sys.argv[1]; rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 5)
tex = np.array(Image.open(g + '/tex.png')).astype(np.float32) / 255
L, H = tex[..., 0], tex[..., 2]; HN, WN = L.shape

def px(lat, lon):
    return int(min(HN - 1, max(0, (90 - lat) / 180 * HN))), int((lon + 180) / 360 * WN) % WN
def ang(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return math.degrees(math.acos(max(-1, min(1, math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo1 - lo2)))))
def ok(lat, lon, need=0.9):
    r, c = px(lat, lon); return L[r, c] > 0.98 and H[r, c] > need
def rand_land(need=0.95):
    while True:
        lat = math.degrees(math.asin(rng.uniform(-0.85, 0.85))); lon = rng.uniform(-180, 180)
        if ok(lat, lon, need): return lat, lon
# 섬 판별: 연결된 육지 크기로
from scipy import ndimage as nd
lab, n = nd.label(L > 0.5); sizes = nd.sum(L > 0.5, lab, range(1, n + 1))
def is_island(lat, lon):
    r, c = px(lat, lon); i = lab[r, c]; return i > 0 and sizes[i - 1] < 30000

# 대륙별 기후: 연결된 땅 덩어리 단위로 정함
# 북쪽 큰 대륙=침엽수, 북반구 가로 대륙=벚나무, 적도 남쪽 대륙=야자수, 남동 대륙=둥근 나무
REGION = [((30, -150), 1), ((43, 166), 1), ((24, 33), 3), ((-15, -63), 2), ((-20, 122), 0)]
lab_kind = {}
for p, k in REGION:
    r, c = px(*p); lab_kind[lab[r, c]] = k
def kind(lat, lon, island):
    if island: return 2
    r, c = px(lat, lon); main = lab_kind.get(lab[r, c], 0)
    rng.random()                     # 난수 순서를 그대로 두어 나무 위치가 바뀌지 않게(섞기는 하지 않음)
    return main
trees = []
def add(lat, lon, k, s):
    r, c = px(lat, lon)
    trees.append({'lat': round(lat, 2), 'lon': round(lon, 2), 'k': k, 's': round(s, 3),
                  'rot': round(float(rng.uniform(0, 360)), 1), 'H': round(float(H[r, c]), 3)})
MIN = 1.7   # 나무 사이 최소 간격(°)
# 숲 무리
# 대륙마다 숲 무리 수를 고르게(북쪽 큰 대륙은 경도 180° 너머 조각까지 합쳐 6개)
PER = {REGION[0][0]: 4, REGION[1][0]: 2}
centers = []
for p0, _k in REGION:
    r0, c0 = px(*p0); li = lab[r0, c0]; got = 0
    for _ in range(4000):
        if got >= PER.get(p0, 5): break
        p = rand_land(0.98); r, c = px(*p)
        if lab[r, c] == li and all(ang(p, q) > 11 for q in centers): centers.append(p); got += 1
for la0, lo0 in centers:
    isl = is_island(la0, lo0)
    for _ in range(int(rng.integers(5, 11))):
        for _t in range(40):
            d = rng.uniform(0, 4.5); a = rng.uniform(0, 2 * math.pi)
            lat = la0 + d * math.sin(a); lon = lo0 + d * math.cos(a) / max(0.3, math.cos(math.radians(la0)))
            lon = (lon + 180) % 360 - 180
            if ok(lat, lon) and all(ang((lat, lon), (t['lat'], t['lon'])) > MIN for t in trees):
                k = kind(lat, lon, isl)
                add(lat, lon, k, rng.uniform(0.8, 1.2)); break
# 섬마다 야자수 1~3그루, 내륙에 홀로 선 나무 몇 그루
for i in range(1, n + 1):
    if sizes[i - 1] >= 30000: continue
    ys, xs = np.nonzero((lab == i) & (H > 0.9))
    for j in rng.permutation(len(ys))[:int(rng.integers(1, 4))]:
        lat = 90 - (ys[j] + .5) / HN * 180; lon = (xs[j] + .5) / WN * 360 - 180
        if all(ang((lat, lon), (t['lat'], t['lon'])) > MIN for t in trees): add(lat, lon, 2, rng.uniform(0.8, 1.05))
for _ in range(25):
    lat, lon = rand_land()
    if all(ang((lat, lon), (t['lat'], t['lon'])) > 3 for t in trees): add(lat, lon, kind(lat, lon, is_island(lat, lon)), rng.uniform(0.85, 1.15))
json.dump(trees, open(g + '/trees.json', 'w'), separators=(',', ':'))
json.dump(trees, open(g + '/trees_all.json', 'w'), separators=(',', ':'))   # 원본 보관(place_landmarks.py가 산·바위에 걸친 나무를 빼서 trees.json을 다시 씀)
print(len(trees), 'trees', {k: sum(t['k'] == k for t in trees) for k in range(4)})
