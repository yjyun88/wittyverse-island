# 3D 건물 배치: 풍차 1기 + 집 2~4채가 모인 작은 마을. 결과는 src/globe3/buildings.json
# 나무(trees.json)와 겹치지 않는 빈 땅에 둔다. k: 'mill'=풍차, 'house'=집
# 사용: python place_buildings.py <src/globe3 폴더> [시드]
import sys, json, math, numpy as np
from PIL import Image
from scipy import ndimage as nd
g = sys.argv[1]; rng = np.random.default_rng(int(sys.argv[2]) if len(sys.argv) > 2 else 3)
tex = np.array(Image.open(g + '/tex.png')).astype(np.float32) / 255
L, H = tex[..., 0], tex[..., 2]; HN, WN = L.shape
trees = json.load(open(g + '/trees.json'))
lab, n = nd.label(L > 0.5)

def px(lat, lon):
    return int(min(HN - 1, max(0, (90 - lat) / 180 * HN))), int((lon + 180) / 360 * WN) % WN
def ang(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return math.degrees(math.acos(max(-1, min(1, math.sin(la1) * math.sin(la2) + math.cos(la1) * math.cos(la2) * math.cos(lo1 - lo2)))))
def ok(p, need=0.95):
    r, c = px(*p); return L[r, c] > 0.98 and H[r, c] > need
def free(p, gap_tree, gap_b):
    return all(ang(p, (t['lat'], t['lon'])) > gap_tree for t in trees) and all(ang(p, (b['lat'], b['lon'])) > gap_b for b in out)

# 마을을 둘 대륙(대륙 안의 한 점)과 마을 수: 벚나무 대륙 2, 둥근 나무 대륙 2, 침엽수 대륙 1, 야자수 대륙 1
VILLAGES = [((24, 33), 2), ((-20, 122), 2), ((30, -150), 1), ((-15, -63), 1)]
out = []
def add(k, p, yaw, s):
    r, c = px(*p)
    out.append({'k': k, 'lat': round(p[0], 2), 'lon': round(p[1], 2), 'rot': round(yaw, 1), 's': round(s, 3), 'H': round(float(H[r, c]), 3)})
for p0, cnt in VILLAGES:
    li = lab[px(*p0)]; made = 0
    for _ in range(6000):
        if made >= cnt: break
        lat = math.degrees(math.asin(rng.uniform(-0.85, 0.85))); lon = rng.uniform(-180, 180); p = (lat, lon)
        if lab[px(*p)] != li or not ok(p, 0.98) or not free(p, 3.0, 20): continue
        yaw = float(rng.uniform(0, 360))
        add('mill', p, yaw, rng.uniform(0.95, 1.1)); made += 1
        # 풍차 둘레 4~7° 거리에 집 2~4채(집끼리 3.5° 이상)
        for _h in range(int(rng.integers(2, 5))):
            for _t in range(120):
                d = rng.uniform(4.0, 7.0); a = rng.uniform(0, 2 * math.pi)
                q = (lat + d * math.sin(a), (lon + d * math.cos(a) / max(0.3, math.cos(math.radians(lat))) + 180) % 360 - 180)
                if ok(q) and free(q, 2.2, 3.5):
                    add('house', q, yaw + float(rng.uniform(-35, 35)), rng.uniform(0.9, 1.1)); break
json.dump(out, open(g + '/buildings.json', 'w'), separators=(',', ':'))
print(len(out), 'buildings', sum(b['k'] == 'mill' for b in out), 'mills')
