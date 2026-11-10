# 샘플 1: 원화(concept_2/v10/v10_v3_center.png)에 가깝게 오브젝트별로 다듬은 로우폴리 섬. 결과 src/island1.*
# 사용: blender -b --factory-startup --python build_island1.py -- <출력폴더>
# 좌표는 three.js 와 같은 Y-up 으로 바로 만든다(AO 는 위아래 축과 무관).
import bpy, bmesh, math, random, json, sys, os
import numpy as np
from mathutils import Vector, Matrix, noise
from mathutils.geometry import delaunay_2d_cdt

OUT = sys.argv[sys.argv.index('--') + 1] if '--' in sys.argv else '.'
random.seed(20261104)
R = random.random
TAU, PI = math.tau, math.pi

def blobR(a, base, s): return base * (1 + 0.07 * math.sin(3 * a + s) + 0.05 * math.sin(5 * a + 2.1 * s) + 0.025 * math.sin(11 * a + 0.7 * s))
def smooth(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t)
def nz(x, y, z=0.0): return noise.noise(Vector((x, y, z)))

# ---------- 색 ----------
def s2l(c): return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
def hexc(h): return [s2l(((h >> 16) & 255) / 255), s2l(((h >> 8) & 255) / 255), s2l((h & 255) / 255)]
def mixc(a, b, t): return [a[i] + (b[i] - a[i]) * t for i in range(3)]
def jit(c, j=0.06):
    k = 1 + (R() - 0.5) * 2 * j
    return [min(1, max(0, v * k * (1 + (R() - 0.5) * j * 0.5))) for v in c]
def C(h): return hexc(h) if isinstance(h, int) else h

# ---------- bmesh 그룹 ----------
BM = {}
def grp(name):
    if name not in BM:
        bm = bmesh.new(); bm.loops.layers.float_color.new('base'); BM[name] = bm
    return BM[name]
def paint(bm, faces, color, j=0.06):
    lay = bm.loops.layers.float_color['base']; base = C(color)
    for f in faces:
        c = jit(base, j)
        for l in f.loops: l[lay] = (c[0], c[1], c[2], 1.0)
def faces_of(verts):
    s = set()
    for v in verts: s.update(v.link_faces)
    return list(s)
def M_trs(x, y, z, ry=0.0, sx=1.0, sy=1.0, sz=1.0, rx=0.0, rz=0.0):
    return (Matrix.Translation((x, y, z)) @ Matrix.Rotation(ry, 4, 'Y') @ Matrix.Rotation(rx, 4, 'X')
            @ Matrix.Rotation(rz, 4, 'Z') @ Matrix.Diagonal((sx, sy, sz, 1.0)))

def box(g, x, y, z, w, h, d, color, ry=0.0, bevel=0.0, j=0.05, rx=0.0, rz=0.0):
    bm = grp(g)
    r = bmesh.ops.create_cube(bm, size=1.0, matrix=M_trs(x, y, z, ry, w, h, d, rx, rz))
    fs = faces_of(r['verts']); paint(bm, fs, color, j)
    if bevel > 0:
        edges = list({e for f in fs for e in f.edges})
        try:
            b = bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=1, profile=0.5, affect='EDGES', clamp_overlap=True)
            paint(bm, b['faces'], color, j)
        except Exception as ex:
            print('bevel 실패', ex)
    return fs

def ico(g, x, y, z, r, color, sub=1, jt=0.0, sx=1.0, sy=1.0, sz=1.0, ry=0.0, j=0.08):
    bm = grp(g)
    res = bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=r, matrix=M_trs(x, y, z, ry, sx, sy, sz))
    if jt:
        for v in res['verts']: v.co += Vector(((R() - .5) * jt, (R() - .5) * jt, (R() - .5) * jt))
    fs = faces_of(res['verts']); paint(bm, fs, color, j); return fs

def lathe(g, c, prof, seg, cols, zig=None, jt=0.0, rot=0.0, capb=False, capt=False, j=0.05):
    """prof: [(반지름, 높이)...] 아래→위.  cols: 띠마다 색(리스트) 또는 함수(k, i)."""
    bm = grp(g); lay = bm.loops.layers.float_color['base']
    rings = []
    for k, (r, y) in enumerate(prof):
        if r < 1e-6:
            rings.append([bm.verts.new((c[0], c[1] + y, c[2]))]); continue
        ring = []
        for i in range(seg):
            a = rot + i / seg * TAU
            rr = r * (zig(i, k) if zig else 1.0) + ((R() - .5) * jt if jt else 0)
            yy = y + ((R() - .5) * jt * 0.6 if jt and 0 < k < len(prof) - 1 else 0)
            ring.append(bm.verts.new((c[0] + math.cos(a) * rr, c[1] + yy, c[2] + math.sin(a) * rr)))
        rings.append(ring)
    out = []
    def orient(f, a, n2):
        f.normal_update()
        exp = Vector((math.cos(a) * n2[0], n2[1], math.sin(a) * n2[0]))
        if f.normal.dot(exp) < 0: f.normal_flip()
    def colr(k, i): return C(cols(k, i)) if callable(cols) else C(cols[min(k, len(cols) - 1)])
    for k in range(len(rings) - 1):
        A, B = rings[k], rings[k + 1]
        (r0, y0), (r1, y1) = prof[k], prof[k + 1]
        n2 = (y1 - y0, -(r1 - r0))                     # 단면 위쪽 진행 기준 바깥 방향
        if n2[0] < 0 or (abs(n2[0]) < 1e-9 and r1 > r0): n2 = (-n2[0], -n2[1])
        if r1 < r0 and y1 >= y0: n2 = (abs(y1 - y0), abs(r1 - r0))     # 지붕처럼 안으로 오르면 바깥-위
        if r1 > r0 and abs(y1 - y0) < 1e-6: n2 = (0, -1)                 # 바닥쪽으로 퍼지는 면
        for i in range(seg):
            jn = (i + 1) % seg
            if len(A) == 1: f = bm.faces.new((A[0], B[i], B[jn]))
            elif len(B) == 1: f = bm.faces.new((A[i], A[jn], B[0]))
            else: f = bm.faces.new((A[i], A[jn], B[jn], B[i]))
            orient(f, rot + (i + .5) / seg * TAU, n2)
            cc = jit(colr(k, i), j)
            for l in f.loops: l[lay] = (cc[0], cc[1], cc[2], 1.0)
            out.append(f)
    for flag, ring, up in ((capb, rings[0], -1), (capt, rings[-1], 1)):
        if flag and len(ring) > 2:
            f = bm.faces.new(ring); f.normal_update()
            if f.normal.y * up < 0: f.normal_flip()
            cc = jit(colr(0 if up < 0 else len(rings) - 2, 0), j)
            for l in f.loops: l[lay] = (cc[0], cc[1], cc[2], 1.0)
            out.append(f)
    return out

def tri_prism(g, pts, color, j=0.05, c=None):
    """다각면 목록을 면으로 추가. 면 방향은 기준점 c(없으면 전체 중심)에서 바깥을 향하게 맞춘다."""
    bm = grp(g); fs = []
    allp = [Vector(p) for poly in pts for p in poly]
    cc = Vector(c) if c is not None else sum(allp, Vector()) / len(allp)
    for poly in pts:
        vs = [bm.verts.new(p) for p in poly]; f = bm.faces.new(vs); f.normal_update()
        if (f.calc_center_median() - cc).dot(f.normal) < 0: f.normal_flip()
        fs.append(f)
    paint(bm, fs, color, j); return fs

# ---------- 배치 기준 (샘플 1 과 동일) ----------
ISLR, ISLS = 11.6, 1.3                    # 섬 반지름(샘플 1 은 10.12). 건물 크기는 그대로, 잔디 공간만 넓힘
ISLB = ISLR - 0.12
def ISL_R(a, base=ISLR):
    d = math.atan2(math.sin(a - PI / 2), math.cos(a - PI / 2))
    e = math.atan2(math.sin(a - 2.3), math.cos(a - 2.3))
    return (blobR(a, base, ISLS) * (1 - 0.1 * math.exp(-(d / 0.55) ** 2))    # 앞쪽(폭포)만 약 10% 들임
            * (1 - 0.14 * math.exp(-(e / 0.4) ** 2)))                      # 정면 왼쪽 아래(132도) 혼자 튀어나온 곳 다듬기
PL = (0.5, -5.2); PLB, PLS, PLY = 4.3, 2.4, 1.6          # 성 언덕: 계단이 돌길과 겹치지 않게 샘플 1 보다 1 뒤로
DOME_C = (-5.4, 0.9)                                         # 돔 중심
DR = math.atan2(0.2 - DOME_C[0], 2.6 - DOME_C[1])            # 돔 입구가 섬 가운데 광장을 향하는 회전각
CAMP_C = (5.5, 3.0)                                          # 모닥불 위치
OAK_OLD = (8.2, 0.0)                                         # 옛 활엽수 자리(배치 계산용으로만 유지, 지금은 소나무 한 그루)
OAK_C = (5.4, -1.3)                                          # 둥근 활엽수: 성 언덕과 텐트 사이 빈자리(사용자 요청으로 왼쪽으로 옮김)
PONDB, PONDS = 2.4, 3.3
WFX = 0.8
rimZ = ISL_R(PI / 2)
POND = (0.7, rimZ - blobR(PI / 2, PONDB, PONDS) + 0.3)   # 연못 앞끝이 섬 가장자리에 걸쳐서 물이 바로 폭포로 떨어짐(물길 없음)

def plat_r_raw(a): return blobR(a, PLB, PLS) + 0.18 * nz(math.cos(a) * 2, math.sin(a) * 2, 3.3)
PLAT_LINE = plat_r_raw(PI / 2) - 0.1                         # 계단 앞 언덕 가장자리를 이 깊이의 일직선으로 폄(좌우 굴곡 차이로 계단 벽이 겹치거나 뜨지 않게)
def plat_r(a):
    r0 = plat_r_raw(a); d = abs(math.atan2(math.sin(a - PI / 2), math.cos(a - PI / 2)))
    w = smooth(0.55, 0.32, d)
    if w <= 0: return r0
    return r0 * (1 - w) + (PLAT_LINE / max(0.3, math.sin(a))) * w
def plat_k(x, z):
    dx, dz = x - PL[0], z - PL[1]; a = math.atan2(dz, dx); r = plat_r(a)
    return smooth(r + 0.2, r - 0.3, math.hypot(dx, dz))
def pond_r(a):
    f = blobR(a, 1.0, PONDS) - 1; n = math.atan2(math.sin(a + PI / 2), math.cos(a + PI / 2))
    d_ = math.atan2(math.sin(a - 0.75), math.cos(a - 0.75))
    return PONDB * (1 + 0.2 * f) * (1 + 0.28 * math.exp(-(d_ / 0.75) ** 2))   # 거의 동그랗게 + 오른쪽 아래(폭포 쪽)로 넓혀 혹처럼 파고든 둑을 없앰(사용자 요청)
def pond_d(x, z):
    dx, dz = x - POND[0], z - POND[1]; return math.hypot(dx, dz) - pond_r(math.atan2(dz, dx))
def chan_k(x, z): return 0.0                                  # 연못과 폭포 사이 물길은 사용자 요청으로 없앰
def stair_h(z): return min(PLY, max(0.0, PLY - (z - (zEdge - 0.45)) * (0.27 / 0.42)))   # 계단 경사선
def H(x, z):
    flat = smooth(1.9, 1.4, abs(x - PL[0])) * smooth(zEdge - 1.9, zEdge - 1.4, z)   # 계단 위쪽 주변은 잔물결 없이 평평하게(계단 끝이 묻히거나 뜨지 않게)
    base = PLY * plat_k(x, z) + 0.07 * nz(x * 0.45, z * 0.45, 1.7) * (1 - flat)
    w = smooth(1.1, 1.04, abs(x - PL[0]))                     # 파는 경계를 양옆 돌 벽(0.76~1.16) 밑에 숨김(얇은 지형 벽이 가시처럼 남지 않게)
    if w > 0 and zEdge - 0.62 < z < STAIR_END + 0.2:            # 맨 위 판석 뒤끝부터
        base = base * (1 - w) + min(base, stair_h(z) - 0.04) * w
    pd = pond_d(x, z)
    wet = max(smooth(0.5, -0.3, pd), chan_k(x, z))
    hh = base * (1 - wet) - 0.36 * wet
    rd = ISL_R(math.atan2(z, x)) - math.hypot(x, z)
    if wet > 0:                                               # 폭포로 넘치는 가장자리: 수면 바로 아래 높이로 올려 턱을 없앰
        hh = max(hh, -0.1 - 0.26 * smooth(0.1, 0.9, rd))
    wn = (smooth(2.2, 1.0, abs(x - WFX)) * smooth(1.1, 0.35, rd)) if z > 0 else 0.0   # 폭포 자리 홈: 둥근 그릇(양옆·안쪽으로 서서히 얕아짐, ㄷ자 직선 벽 없음)
    if wn > 0:
        hh = hh * (1 - wn) + min(hh, -0.1 - 0.04 * smooth(0.6, 0.0, rd)) * wn   # 수면(-0.06) 바로 아래로만 얕게(폭포를 꺼도 움푹 꺼진 벽이 안 보이게)
    return hh
def notch_h(rd): return -0.1 - 0.22 * smooth(0.6, 0.0, rd)     # 페이지의 폭포 물줄기도 같은 식을 씀

zEdge = PL[1] + plat_r_raw(PI / 2)                            # 계단 기준선은 펴기 전 값 그대로(계단 위치 유지)
STAIR_END = zEdge + 2.0                                      # 계단 맨 아래 단 앞끝
DOOR = (DOME_C[0] + math.sin(DR) * 2.6, DOME_C[1] + math.cos(DR) * 2.6)   # 돔 입구 앞 디딤돌
DOCK_Z = POND[1] + 0.15                                      # 선착장: 연못 서쪽 물가선(수면 높이와 만나는 곳)
DOCK_X = POND[0]
while H(DOCK_X, DOCK_Z) < -0.06: DOCK_X -= 0.02
def curve(ctrl, step=0.5):
    """제어점을 Catmull-Rom 곡선으로 잇고 거의 같은 간격(step)으로 다시 나눈 점 목록."""
    P = [ctrl[0]] + list(ctrl) + [ctrl[-1]]; dense = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(20):
            t = k / 20; t2, t3 = t * t, t * t * t
            dense.append(tuple(0.5 * (2 * p1[c] + (-p0[c] + p2[c]) * t + (2 * p0[c] - 5 * p1[c] + 4 * p2[c] - p3[c]) * t2 + (-p0[c] + 3 * p1[c] - 3 * p2[c] + p3[c]) * t3) for c in (0, 1)))
    dense.append(ctrl[-1]); out = [dense[0]]; acc = 0.0
    for a, b in zip(dense, dense[1:]):
        acc += math.hypot(b[0] - a[0], b[1] - a[1])
        if acc >= step: out.append(b); acc = 0.0
    if out[-1] != ctrl[-1]: out.append(ctrl[-1])
    return out
FORK = (PL[0], STAIR_END + 1.25)                             # 계단에서 한 줄로 내려온 뒤 갈라지는 지점
PATHS = [[FORK, (-1.3, 2.95), DOOR],                                          # 갈림길 → 돔 입구
         [(FORK[0] + 0.4, FORK[1] + 0.2), (2.6, 3.3), (CAMP_C[0] - 1.7, CAMP_C[1] + 0.5)],                 # 갈림길 → 캠프 앞(텐트 없는 쪽)
         [(PL[0], STAIR_END + 0.4), FORK],                                      # 계단 → 갈림길(한 줄)
         curve([(-1.62, 3.35), (-2.15, 4.3), (-2.45, 5.4), (DOCK_X - 1.0, DOCK_Z - 0.35), (DOCK_X - 0.6, DOCK_Z)])]   # 삼거리 → 물가 따라 곡선 → 선착장
def seg_d(px, pz, a, b):
    ax, az = a; bx, bz = b; vx, vz = bx - ax, bz - az
    t = max(0, min(1, ((px - ax) * vx + (pz - az) * vz) / (vx * vx + vz * vz)))
    return math.hypot(px - ax - vx * t, pz - az - vz * t)
def path_d(x, z): return min(seg_d(x, z, l[i], l[i + 1]) for l in PATHS for i in range(len(l) - 1))

# ---------- 지형(윗면) ----------
S = 128
bnd = [(math.cos(i / S * TAU) * ISL_R(i / S * TAU), math.sin(i / S * TAU) * ISL_R(i / S * TAU)) for i in range(S)]
pts = list(bnd)
sp = 0.34
gx = -11.0
while gx < 11:
    gz = -11.0
    while gz < 11:
        x, z = gx + (R() - .5) * sp * 0.7, gz + (R() - .5) * sp * 0.7
        if math.hypot(x, z) < ISL_R(math.atan2(z, x)) - 0.2: pts.append((x, z))
        gz += sp
    gx += sp
for k in range(160):                                   # 언덕 가장자리를 또렷하게
    a = k / 160 * TAU
    for off in (0.22, -0.32):
        r = plat_r(a) + off; pts.append((PL[0] + math.cos(a) * r, PL[1] + math.sin(a) * r))
for k in range(240):                                        # 호수 둘레를 촘촘히 여러 겹(물가선이 톱니처럼 보이지 않게)
    a = k / 240 * TAU
    for off in (-0.45, -0.25, -0.1, 0.0, 0.1, 0.25, 0.45):
        r_ = pond_r(a) + off; x_, z_ = POND[0] + math.cos(a) * r_, POND[1] + math.sin(a) * r_
        if math.hypot(x_, z_) < ISL_R(math.atan2(z_, x_)) - 0.2: pts.append((x_, z_))
zz = zEdge - 0.9                                         # 계단 홈 양옆 경계를 또렷하게(벽 바로 바깥 1.17 줄까지 촘촘히 → 긴 삼각형이 벽 밖으로 솟지 않게)
while zz < STAIR_END + 0.3:
    for xo in (-1.17, -1.1, -1.04, -0.9, 0.9, 1.04, 1.1, 1.17): pts.append((PL[0] + xo, zz))
    zz += 0.1
_RS0 = random.getstate()                                    # 지형 칠하기 앞 난수 상태(아래에서 숲 배치가 바뀌지 않게 맞춤)
res = delaunay_2d_cdt([Vector(p) for p in pts], [], [], 0, 1e-5)
vco, tris = res[0], res[2]
bm = grp('ground'); lay = bm.loops.layers.float_color['base']   # 풀바닥은 따로(페이지에서 부드러운 음영)
tv = [bm.verts.new((v.x, H(v.x, v.y), v.y)) for v in vco]
GRASS_A, GRASS_B, GRASS_T = hexc(0x5eb243), hexc(0x7cc64e), hexc(0x86cf55)
SAND, DIRT, ROCK, MOSS, UNDER = hexc(0xdcc68e), hexc(0xc9a877), hexc(0x8c84a6), hexc(0x5f9447), hexc(0x2f6b78)
for t in tris:
    if len(t) != 3: continue
    cx = sum(vco[i].x for i in t) / 3; cz = sum(vco[i].y for i in t) / 3
    if math.hypot(cx, cz) > ISL_R(math.atan2(cz, cx)) - 0.01: continue
    try: f = bm.faces.new([tv[i] for i in t])
    except ValueError: continue
    f.normal_update()
    if f.normal.y < 0: f.normal_flip()
    h = H(cx, cz); ny = f.normal.y; pd = pond_d(cx, cz)
    _rdc = ISL_R(math.atan2(cz, cx)) - math.hypot(cx, cz)
    if cz > 0 and abs(cx - WFX) < 2.6 and _rdc < 1.9 and h < -0.1: c = mixc(hexc(0x2f6b78), mixc(hexc(0x46b4e0), hexc(0x3a9fd2), smooth(1.0, 0.0, _rdc)), smooth(1.9, 1.2, _rdc) * smooth(2.6, 1.8, abs(cx - WFX)))   # 폭포 쪽 물에 잠긴 바닥만 물빛(투명해지는 구간 전체), 물 위 둑은 원래 색   # 폭포로 넘어가는 홈 바닥: 물빛(수면이 투명해져도 어둡게 안 비침)
    elif h < -0.14: c = UNDER
    elif pd < 0.55 or chan_k(cx, cz) > 0.2: c = SAND
    elif ny < 0.8: c = mixc(ROCK, MOSS, R() * 0.4)
    else:
        g = mixc(GRASS_A, GRASS_B, 0.5 + 0.5 * nz(cx * 0.35, cz * 0.35, 5.1))
        if plat_k(cx, cz) > 0.9: g = mixc(g, GRASS_T, 0.5)
        pdd = path_d(cx, cz)
        c = mixc(g, DIRT, smooth(0.65, 0.3, pdd) * 0.8)
    c = jit(c, 0.07)
    for l in f.loops: l[lay] = (c[0], c[1], c[2], 1.0)
for v in bm.verts:                                           # 꼭짓점마다 주변 면 색을 평균 → 삼각형 경계가 안 보이게 매끈한 색
    ls = list(v.link_loops)
    if not ls: continue
    acc = [sum(l[lay][k] for l in ls) / len(ls) for k in range(3)]
    for l in ls: l[lay] = (acc[0], acc[1], acc[2], 1.0)

random.setstate(_RS0)                                       # 지형 면 수가 바뀌어도 이후 난수(숲·바위 배치)는 원래 판과 같게:
for _ in range(31437): R()                                  # 원래 판에서 이 구간이 쓴 횟수만큼 넘김
_RS1 = random.getstate()                                    # 절벽 앞 난수 상태
# ---------- 절벽 ----------
bm = grp('lit'); lay = bm.loops.layers.float_color['base']    # 절벽부터는 다시 각진 로우폴리 그룹
RINGS = [(0.0, 0.00, 0.0, 'top'), (-0.16, 0.14, 0.0, 'top'), (-0.55, 0.06, 0.0, 'lip'),     # 둥근 테두리(흔들림 없음)
         (-1.4, 0.00, 0.30, 'r'), (-1.6, -0.35, 0.18, 'r'), (-2.9, -0.30, 0.32, 'r'), (-3.1, -0.70, 0.18, 'r'),
         (-4.4, -0.75, 0.35, 'r'), (-4.6, -1.20, 0.18, 'r'), (-5.8, -1.30, 0.35, 'r'), (-6.0, -1.80, 0.2, 'r'),
         (-7.2, -2.00, 0.30, 'r'), (-8.3, -2.60, 0.0, 'r')]
def cliff_r(a, k):
    _, ins, jt, _ = RINGS[k]
    if k >= 3:                                               # 아래로 갈수록 안쪽으로 둥글게 말려 들어감(그릇 모양) + 층진 턱
        r = ISL_R(a) - ISLR * 0.45 * (1 - math.cos(-RINGS[k][0] / 8.3 * PI / 2))
    else:
        r = ISL_R(a) + ins
    if k >= 3: r += 0.1 * nz(math.cos(a) * 1.4, math.sin(a) * 1.4, 0.8)        # 매끈한 그릇: 고리마다 같은 완만한 굴곡
    x, z = math.cos(a) * r, math.sin(a) * r
    if k >= 1 and z > 0 and abs(x - WFX) < 3.4: r -= (0.22 if k >= 2 else 0.1) * smooth(3.4, 0.8, abs(x - WFX))   # 폭포 뒤: 아주 조금만, 넓게 들임(양옆 둑과 같은 둥근 테두리로 이어짐)   # 폭포 뒤는 안으로(잔디 테두리가 물 앞으로 나오지 않게)
    return r
CR = random.Random(5150)                                     # 절벽 디테일 전용 난수(R() 순서를 건드리지 않음)
# 세로 돌기둥: 폭이 제각각(정점 2~6칸)인 평평한 기둥 면. 톱니처럼 균일하게 반복되지 않게(사용자 요청)
VCOL, VBND, _c, _i = [], [], 0, 0
while _i < S:
    w = min(CR.choice((2, 3, 3, 4, 4, 5, 6)), S - _i)
    for t in range(w): VCOL.append(_c); VBND.append(t == 0)
    _i += w; _c += 1
NCOL = _c
COL_OUT = [0.03 + CR.random() * 0.09 for _ in range(NCOL)]   # 기둥이 바깥으로 나온 정도(작게, 제각각)
COL_LEN = [CR.uniform(-1.1, 0.5) for _ in range(NCOL)]      # 기둥 아래 끝 길이 차이
COL_LEN = [0.32 * (COL_LEN[(c - 1) % NCOL] + 2 * COL_LEN[c] + COL_LEN[(c + 1) % NCOL]) / 4 for c in range(NCOL)]   # 사용자 요청: 덜 삐죽하게(차이 약 1/3, 이웃과 부드럽게)
COL_PAL = [hexc(0x9a88cc), hexc(0x8494cc), hexc(0x74a4c4), hexc(0xa898d4), hexc(0x8676bc)]   # 보라·청보라·청록 기둥
COL_C = [COL_PAL[int(CR.random() * len(COL_PAL))] for _ in range(NCOL)]
COL_MOSS = [CR.random() < 0.16 for _ in range(NCOL)]
DRAPE = [0.32 + CR.random() * 0.5 for _ in range(S)]         # 잔디가 절벽 위로 흘러내리는 길이
for _ in range(3): DRAPE = [(DRAPE[(i - 1) % S] + 2 * DRAPE[i] + DRAPE[(i + 1) % S]) / 4 for i in range(S)]   # 이웃끼리 부드럽게
def near_fall(a):
    x, z = math.cos(a) * ISLR, math.sin(a) * ISLR; return z > 0 and abs(x - WFX) < 2.4
crow = []
for k, (dy, ins, jt, kind) in enumerate(RINGS):
    row = []
    for i in range(S):
        a = i / S * TAU
        if k == 0:
            x, z = bnd[i]; y = H(x, z)
        else:
            r = cliff_r(a, k); R()                                    # 매끈하게(흔들림 없음, 난수 순서만 유지)
            ytop = H(*bnd[i])
            y = (ytop + dy) if k < 3 else dy
            if k >= 3: R()                                       # 원래 난수 순서 유지(숲 배치가 바뀌지 않게)
            ci = VCOL[i]
            if k == 2:                                          # 잔디가 흘러내리는 가장자리(폭포 쪽으로 갈수록 짧아져 부드럽게 이어짐)
                fx_ = math.cos(a) * ISLR; fall_k = smooth(1.4, 2.6, abs(fx_ - WFX)) if math.sin(a) > 0 else 1.0
                y = ytop - (0.5 + (DRAPE[i] - 0.5) * fall_k)
            x, z = math.cos(a) * r, math.sin(a) * r
        row.append((x, y, z))
    crow.append(row)
GBM = grp('ground'); glay = GBM.loops.layers.float_color['base']
gro = [[GBM.verts.new(p_) for p_ in crow[k]] for k in range(len(crow))]      # 테두리·절벽 모두 매끈 그룹(사용자 요청)
crow = gro
RTOP, RBOT = hexc(0x8a80aa), hexc(0x3b3560)
for k in range(len(RINGS) - 1):
    for i in range(S):
        j = (i + 1) % S
        f = GBM.faces.new((gro[k][i], gro[k][j], gro[k + 1][j], gro[k + 1][i]))
        f.normal_update(); a = (i + .5) / S * TAU
        if f.normal.dot(Vector((math.cos(a), 0, math.sin(a)))) < 0: f.normal_flip()
        kind = RINGS[k][3]
        fc = f.calc_center_median()
        if kind in ('top', 'lip') and fc.z > 0 and abs(fc.x - WFX) < 1.95: c = mixc(hexc(0x4f5f86), ROCK, R() * 0.3)   # 폭포 시작부: 젖은 바위색
        elif kind == 'top': c = mixc(GRASS_A, hexc(0x4f9a38), R() * 0.4)
        elif kind == 'lip':
            _r = R()
            c = mixc(hexc(0x4f9a38), hexc(0x3c7d34), _r) if (DRAPE[i] + DRAPE[j]) / 2 > 0.45 else mixc(COL_C[VCOL[i]], hexc(0x3c7d34), 0.25 + _r * 0.15)   # 흘러내린 잔디 / 짧은 곳은 그 기둥 색(밝은 바위색 조각이 안 보이게)
        else:
            t = (k - 3) / (len(RINGS) - 4); _r = R(); a_ = (i + .5) / S * TAU
            w_ = 0.5 + 0.5 * nz(math.cos(a_) * 1.6, math.sin(a_) * 1.6, 2.2 + t)          # 넓고 완만한 보라↔청록 얼룩
            c = mixc(hexc(0x9286c8), hexc(0x78a2c8), max(0, min(1, w_)))
            c = mixc(c, hexc(0x3d356c), min(1, t) * 0.6)                                   # 아래로 갈수록 어둡게
        jit(c, 0.06)                                             # 원래 난수 순서 유지(결과는 안 씀)
        for l in f.loops: l[glay] = (c[0], c[1], c[2], 1.0)
for row in gro:                                              # 테두리 색도 꼭짓점 평균(세모 경계 안 보이게)
    for v in row:
        ls = list(v.link_loops); acc = [sum(l[glay][q] for l in ls) / len(ls) for q in range(3)]
        for l in ls: l[glay] = (acc[0], acc[1], acc[2], 1.0)

# 절벽에 붙은 큰 바위, 바다에 잠긴 바위
def on_cliff(a, y):
    for k in range(3, len(RINGS) - 1):
        if RINGS[k][0] >= y >= RINGS[k + 1][0]:
            t = (RINGS[k][0] - y) / (RINGS[k][0] - RINGS[k + 1][0])
            return cliff_r(a, k) * (1 - t) + cliff_r(a, k + 1) * t
    return cliff_r(a, len(RINGS) - 1)
# (절벽에 붙은 큰 바위·바다 바위는 사용자 요청으로 제거)
# 바닥 덮개: 맨 아래 고리를 가운데 한 점으로 모아 둥근 그릇 바닥으로 막음
cb = GBM.verts.new((0.0, RINGS[-1][0] - 1.2, 0.0))
for i in range(S):
    j = (i + 1) % S
    f = GBM.faces.new((crow[-1][i], crow[-1][j], cb)); f.normal_update()
    if f.normal.y > 0: f.normal_flip()
    c = jit(hexc(0x3d356c), 0.0)
    for l in f.loops: l[glay] = (c[0], c[1], c[2], 1.0)
for v in [cb] + [v for row in gro for v in row]:              # 절벽 색 꼭짓점 평균(매끈)
    ls = list(v.link_loops); acc = [sum(l[glay][q] for l in ls) / len(ls) for q in range(3)]
    for l in ls: l[glay] = (acc[0], acc[1], acc[2], 1.0)

random.setstate(_RS1)                                       # 절벽 고리 수가 바뀌어도 이후 배치는 원래 판과 같게
for _ in range(11008): R()
# ---------- 성 (원화 성 구성에 맞춤) ----------
# 원화: 앞으로 튀어나온 문루(박공 + 금색 아치 창 + 금빛 아치문)와 양옆 작은 탑, 좌우 파란 지붕 날개와 모서리 탑,
# 가운데 둥근 본탑(금색 띠 + 금색 왕관 톱니 + 높은 첨탑 + 깃발), 그 주위로 가늘고 높은 뾰족탑들. 지붕은 아래가 퍼진 비늘 원뿔.
CO = (PL[0], PLY, PL[1] - 0.6)
WALL, WALL2, TRIM, STONE, WIN, GLASS, KGOLD = 0xf2ddb4, 0xe6cc9e, 0xe8b84a, 0xb9a98c, 0xffd27a, 0x7cc8ff, 0xf3cf86
SCALE = [0x2f6fd6, 0x2f6fd6, 0x3d8fe6, 0x4fb3ea, 0x2456b8, 0x5ac8f0]   # 지붕 비늘: 면마다 골라 반짝이는 느낌
FLAGS = []
def cpos(x, y, z): return (CO[0] + x, CO[1] + y, CO[2] + z)
def scale_col(k, i): return SCALE[int(R() * len(SCALE))]
def flagpole(x, y, z, h=0.72):
    lathe('lit', (x, y, z), [(0.03, 0), (0.025, h)], 5, [TRIM]); FLAGS.append([x, y + h - 0.02, z])
def finial(x, y, z, s=1.0):
    lathe('lit', (x, y, z), [(0.07 * s, 0), (0.09 * s, 0.08 * s), (0.05 * s, 0.18 * s), (0.075 * s, 0.26 * s), (0.02 * s, 0.34 * s), (0, 0.85 * s)], 6, [TRIM], j=0.03)
def cone(x, y, z, r, rh, seg=14, flare=1.38):
    """아래가 바깥으로 퍼진 마녀 모자 지붕 + 처마 금띠 + 꼭대기 금 첨침. 첨침 끝 높이를 돌려준다."""
    lathe('lit', (x, y - 0.02, z), [(r * 1.06, 0), (r * flare + 0.02, 0.03), (r * flare + 0.02, 0.09), (r * 1.02, 0.1)], seg, [TRIM], j=0.03)
    prof = [(r * flare, 0.06), (r * 1.12, rh * 0.12), (r * 0.82, rh * 0.3), (r * 0.55, rh * 0.52), (r * 0.3, rh * 0.74), (r * 0.12, rh * 0.9), (0, rh)]
    lathe('lit', (x, y, z), prof, seg, scale_col, capb=True, j=0.04)
    s = max(0.6, r * 1.3)
    finial(x, y + rh - 0.04, z, s)
    return y + rh - 0.04 + 0.85 * s
def arch_poly(w, h, n=5):
    """폭 w, 높이 h 의 위가 둥근 아치 윤곽(아래 가운데 기준, 2D)."""
    rr = w / 2; pts = [(-rr, 0), (rr, 0)]
    for i in range(n + 1):
        a = i / n * PI; pts.append((math.cos(a) * rr, h - rr + math.sin(a) * rr))
    return pts
def arch_win(x, y, z, a, w, h, col=WIN, frame=True):
    """벽면(바깥 방향 각 a) 위에 붙는 아치 창. (x,y,z) = 창 아래 가운데."""
    tx, tz = -math.sin(a), math.cos(a); nx, nz_ = math.cos(a), math.sin(a)
    def face(g, ww, hh, off, c, yo=0.0):
        pts = [(x + tx * u + nx * off, y + v + yo, z + tz * u + nz_ * off) for u, v in arch_poly(ww, hh)]
        tri_prism(g, [pts], c, j=0.02, c=(x - nx, y + hh / 2, z - nz_))
    if frame: face('lit', w + 0.08, h + 0.06, 0.012, TRIM, -0.03)
    face('emit', w, h, 0.022, col)
def ring(c, r, y, t=0.08, col=TRIM, seg=14, out=0.06):
    lathe('lit', (c[0], c[1] + y, c[2]), [(r, 0), (r + out, 0.01), (r + out, t), (r, t + 0.01)], seg, [col], j=0.03)
def tower(x, z, r, h, rh, wins=(), flag=False, belv=False, flare=1.38, seg=14):
    """둥근 탑: 돌 받침 → 크림 몸통 → 금띠 → 지붕. wins = [(높이비, 개수, 금색여부)]"""
    c = cpos(x, 0, z)
    lathe('lit', c, [(r * 1.18, -0.5), (r * 1.15, 0.18), (r * 1.0, 0.3), (r * 1.0, h)], seg, [STONE, STONE, WALL], capt=True)
    ring(c, r, 0.26, 0.07, STONE, seg, 0.08)
    ring(c, r, h - 0.1, 0.12, TRIM, seg, 0.07)
    if belv: ring(c, r, h * 0.6, 0.08, TRIM, seg, 0.06)          # 원화의 꼭대기 창 띠(전망층)
    for fy, n, gold in wins:
        for kk in range(n):
            a = PI / 2 + (kk - (n - 1) / 2) * (1.0 if n <= 2 else 0.8)
            arch_win(c[0] + math.cos(a) * r, c[1] + h * fy, c[2] + math.sin(a) * r, a, r * 0.38, r * 0.85, WIN if gold else GLASS)
    top = cone(c[0], c[1] + h + 0.02, c[2], r, rh, seg, flare)
    if flag: flagpole(c[0], top - 0.05, c[2])
    return c[1] + h
def gable(x0, x1, z0, z1, y, rh, col, along='x', over=0.12, end_col=None):
    """박공 지붕: along 방향으로 용마루. 양 끝 삼각 벽은 end_col."""
    if along == 'x':
        zm = (z0 + z1) / 2
        A = [(x0 - over, y, z1 + over), (x1 + over, y, z1 + over), (x1 + over, y + rh, zm), (x0 - over, y + rh, zm)]
        B = [(x1 + over, y, z0 - over), (x0 - over, y, z0 - over), (x0 - over, y + rh, zm), (x1 + over, y + rh, zm)]
        tri_prism('lit', [A, B], col, j=0.08)
        if end_col: tri_prism('lit', [[(x0, y, z0), (x0, y, z1), (x0, y + rh, zm)], [(x1, y, z1), (x1, y, z0), (x1, y + rh, zm)]], end_col)
    else:
        xm = (x0 + x1) / 2
        A = [(x0 - over, y, z0 - over), (x0 - over, y, z1 + over), (xm, y + rh, z1 + over), (xm, y + rh, z0 - over)]
        B = [(x1 + over, y, z1 + over), (x1 + over, y, z0 - over), (xm, y + rh, z0 - over), (xm, y + rh, z1 + over)]
        tri_prism('lit', [A, B], col, j=0.08)
        if end_col: tri_prism('lit', [[(x0, y, z1), (x1, y, z1), (xm, y + rh, z1)], [(x1, y, z0), (x0, y, z0), (xm, y + rh, z0)]], end_col)
Y0 = CO[1]
# 받침 돌단
box('lit', CO[0], Y0 - 0.15, CO[2] + 0.1, 5.4, 0.5, 3.0, STONE, bevel=0.05)

# --- 본채(가운데, 파란 지붕) ---
hx0, hx1, hz0, hz1, hh = -1.0, 1.0, -1.25, 0.45, 2.5
box('lit', CO[0], Y0 + hh / 2, CO[2] + (hz0 + hz1) / 2, hx1 - hx0, hh, hz1 - hz0, WALL, bevel=0.03)
box('lit', CO[0], Y0 + hh + 0.04, CO[2] + (hz0 + hz1) / 2, hx1 - hx0 + 0.14, 0.12, hz1 - hz0 + 0.14, TRIM)
gable(CO[0] + hx0, CO[0] + hx1, CO[2] + hz0, CO[2] + hz1, Y0 + hh + 0.1, 0.9, SCALE[0], 'x', 0.1, WALL2)
for x in (-0.75, 0.75):                                        # 본채 위층 금빛 창
    arch_win(CO[0] + x, Y0 + 1.75, CO[2] + hz1, PI / 2, 0.24, 0.5)

# --- 좌우 날개(파란 박공 지붕 + 푸른 유리창 + 지붕창) ---
for sx in (-1, 1):
    xa, xb = sorted((sx * 1.05, sx * 2.35))
    wz0, wz1, wh = -0.55, 0.85, 1.45
    box('lit', CO[0] + (xa + xb) / 2, Y0 + wh / 2, CO[2] + (wz0 + wz1) / 2, xb - xa, wh, wz1 - wz0, WALL2, bevel=0.03)
    box('lit', CO[0] + (xa + xb) / 2, Y0 + wh + 0.03, CO[2] + (wz0 + wz1) / 2, xb - xa + 0.1, 0.1, wz1 - wz0 + 0.1, TRIM)
    gable(CO[0] + xa, CO[0] + xb, CO[2] + wz0, CO[2] + wz1, Y0 + wh + 0.08, 0.75, SCALE[0], 'x', 0.1, WALL2)
    for u in (0.3, 0.7):
        arch_win(CO[0] + xa + (xb - xa) * u, Y0 + 0.45, CO[2] + wz1, PI / 2, 0.2, 0.48, GLASS)
    dx = CO[0] + (xa + xb) / 2 + sx * 0.2; dz = CO[2] + 0.35; dy = Y0 + wh + 0.2
    box('lit', dx, dy + 0.22, dz, 0.36, 0.44, 0.4, WALL)
    gable(dx - 0.18, dx + 0.18, dz - 0.2, dz + 0.2, dy + 0.44, 0.26, SCALE[0], 'z', 0.05, WALL)
    arch_win(dx, dy + 0.06, dz + 0.2, PI / 2, 0.16, 0.3)

# --- 문루(앞으로 튀어나온 정문) ---
gx0, gx1, gz0, gz1, gh = -0.62, 0.62, 0.2, 1.45, 2.55
box('lit', CO[0], Y0 + gh / 2, CO[2] + (gz0 + gz1) / 2, gx1 - gx0, gh, gz1 - gz0, WALL, bevel=0.03)
box('lit', CO[0], Y0 + gh + 0.04, CO[2] + (gz0 + gz1) / 2, gx1 - gx0 + 0.14, 0.12, gz1 - gz0 + 0.14, TRIM)
for xx in (gx0, gx1):                                          # 모서리 기둥
    box('lit', CO[0] + xx, Y0 + gh / 2, CO[2] + gz1 - 0.02, 0.16, gh, 0.16, WALL2)
gable(CO[0] + gx0, CO[0] + gx1, CO[2] + gz0, CO[2] + gz1, Y0 + gh + 0.1, 0.95, SCALE[0], 'z', 0.12, WALL)
arch_win(CO[0], Y0 + gh + 0.22, CO[2] + gz1, PI / 2, 0.3, 0.46, WIN)        # 박공의 금색 아치 창
# 아치문: 돌 테두리 + 금 테 + 빛나는 문
tri_prism('lit', [[(CO[0] + u, Y0 - 0.04 + v, CO[2] + gz1 + 0.006) for u, v in arch_poly(1.12, 1.72)]], STONE, c=(CO[0], Y0 + 0.8, CO[2]))
arch_win(CO[0], Y0 - 0.02, CO[2] + gz1 + 0.01, PI / 2, 0.92, 1.55, 0xffc35a)
for x in (-0.33, 0, 0.33):                                     # 문 위 푸른 유리창 줄과 장식 띠
    arch_win(CO[0] + x, Y0 + 1.82, CO[2] + gz1, PI / 2, 0.16, 0.42, GLASS)
box('lit', CO[0], Y0 + 1.68, CO[2] + gz1 + 0.03, gx1 - gx0 + 0.06, 0.08, 0.08, TRIM)

# --- 본탑(가운데) ---
kc = cpos(0, 0, -0.45); kr = 0.62; kb = Y0 + hh - 0.2
lathe('lit', (kc[0], kb, kc[2]), [(kr * 1.08, 0), (kr * 1.08, 0.5), (kr, 0.6), (kr, 2.7), (kr * 0.92, 2.8), (kr * 0.92, 3.6)], 16, [WALL, WALL2, WALL, KGOLD, KGOLD], capt=True)
for yy in (0.5, 1.4, 2.2, 2.7):
    ring((kc[0], kb, kc[2]), kr if yy < 2.8 else kr * 0.92, yy, 0.12, TRIM, 16, 0.07)
for fy in (0.72, 1.55):                                         # 금빛 긴 아치 창 띠
    for kk in range(3):
        a = PI / 2 + (kk - 1) * 0.75
        arch_win(kc[0] + math.cos(a) * kr, kb + fy, kc[2] + math.sin(a) * kr, a, 0.24, 0.55)
ktop = kb + 3.6
for i in range(8):                                             # 금색 왕관: 뾰족한 톱니 8개
    a = i / 8 * TAU + PI / 8
    px, pz = kc[0] + math.cos(a) * kr * 0.98, kc[2] + math.sin(a) * kr * 0.98
    tx, tz = -math.sin(a) * 0.17, math.cos(a) * 0.17; ox, oz = math.cos(a) * 0.07, math.sin(a) * 0.07
    tri_prism('lit', [[(px - tx + ox, ktop - 0.05, pz - tz + oz), (px + tx + ox, ktop - 0.05, pz + tz + oz), (px + ox * 1.6, ktop + 0.62, pz + oz * 1.6)],
                      [(px + tx - ox, ktop - 0.05, pz + tz - oz), (px - tx - ox, ktop - 0.05, pz - tz - oz), (px - ox * 0.5, ktop + 0.62, pz - oz * 0.5)]], TRIM, j=0.04, c=(kc[0], ktop, kc[2]))
top = cone(kc[0], ktop + 0.05, kc[2], kr * 0.82, 2.5, 16, 1.25)
flagpole(kc[0], top - 0.05, kc[2], 0.8)

# --- 둘레 탑들 (원화의 위치·높이 순서에 맞춤) ---
tower(-0.98, 1.35, 0.3, 2.15, 1.35, [(0.62, 1, False)], seg=12)            # 문루 왼쪽 작은 탑
tower(0.98, 1.35, 0.3, 2.15, 1.35, [(0.62, 1, False)], seg=12)             # 문루 오른쪽 작은 탑
tower(-2.55, 0.75, 0.34, 2.0, 1.45, [(0.35, 1, False), (0.72, 2, True)], belv=True, seg=12)   # 왼쪽 모서리 탑
tower(2.55, 0.75, 0.34, 2.0, 1.45, [(0.35, 1, False), (0.72, 2, True)], belv=True, seg=12)    # 오른쪽 모서리 탑
tower(-0.82, -0.05, 0.22, 3.5, 1.25, [(0.7, 1, True)], seg=10)              # 본탑 앞 가는 뾰족탑
tower(0.82, -0.05, 0.22, 3.5, 1.25, [(0.7, 1, True)], seg=10)
tower(-1.55, -0.55, 0.4, 4.0, 1.9, [(0.45, 1, True), (0.75, 3, True)], belv=True)          # 왼쪽 높은 탑
tower(-2.35, -0.95, 0.42, 3.1, 1.75, [(0.7, 2, True)])                      # 왼쪽 뒤 탑
tower(1.75, -0.6, 0.62, 3.3, 1.75, [(0.4, 2, False), (0.72, 3, True)], flag=True, belv=True, flare=1.42, seg=16)   # 오른쪽 큰 탑
tower(-0.5, -1.25, 0.24, 5.0, 1.35, [(0.8, 1, True)], seg=10)               # 본탑 뒤 가는 탑 두 개
tower(0.55, -1.2, 0.24, 4.6, 1.3, [(0.8, 1, True)], seg=10)

# ---------- 돌계단 (원화처럼 둥글넓적한 판석이 조금씩 비뚤게 쌓이고 양옆은 바위) ----------
for i in range(6):
    top = PLY - i * 0.27 + 0.02; Hh = top + 0.35; zc = zEdge - 0.35 + i * 0.42
    box('lit', PL[0], top - Hh / 2 - 0.08, zc - 0.04, 1.3, Hh - 0.12, 0.46, 0x9c8a6c, bevel=0.04)          # 받침(그늘진 몸통)
    w = 1.38 + R() * 0.14; yaw = (R() - 0.5) * 0.12; dx = (R() - 0.5) * 0.08
    box('lit', PL[0] + dx, top - 0.06, zc + 0.02, w, 0.16, 0.52, 0xdcc89e if i % 2 else 0xcfb98c, yaw, bevel=0.06, j=0.04)   # 판석
STAIR_CHEEKS = []
CHW = 0.4                                                   # 양옆 돌 벽 폭(사용자 요청으로 절반)
def plateau_z(x):                                           # 이 x 에서 언덕 윗면(H >= PLY-0.08)이 끝나는 앞쪽 z
    z = zEdge - 2.0
    while z < zEdge + 1.0 and H(x, z) >= PLY - 0.08: z += 0.02
    return z
for sx in (-1, 1):                                          # 양옆: 절벽을 깎아 낸 듯한 거친 돌 벽(땅에서 단 높이까지 채움)
    xc = PL[0] + sx * (0.76 + CHW / 2)
    pz = min(plateau_z(xc - CHW / 2), plateau_z(xc + CHW / 2))   # 언덕이 먼저 끝나는 쪽 기준(틈이 안 생기게)
    for i in range(6):
        _r = R(); top = PLY - i * 0.27 - 0.055; zc = zEdge - 0.35 + i * 0.42   # 모든 칸 같은 규칙: 덮개 윗면 = 그 단 높이(맨 위 칸은 언덕 잔디 PLY 와 같음), 판석 윗면보다 일정하게 0.04 아래
        z0, z1 = zc - 0.25, zc + 0.25
        if i == 0: z0 = min(z0, pz - 0.32)                    # 맨 위 블록은 언덕 안쪽까지 뒤로 늘림(언덕 모서리가 비어져 나오지 않게)
        if z1 < pz - 0.05: continue                          # 언덕 안에 완전히 묻히는 블록은 뺌
        z0 = max(z0, pz - 0.12) if i > 0 else z0
        zm, dz = (z0 + z1) / 2, z1 - z0
        x = xc + (R() - 0.5) * 0.03; bw = CHW
        base = min(H(x, zm), top - 0.4) - 0.3; hh = top - base
        box('lit', x, base + hh / 2, zm, bw, hh, dz, mixc(hexc(0x76708e), hexc(0x8a83a0), R()), (R() - 0.5) * 0.06, bevel=0.05, j=0.05)
        box('lit', x + sx * 0.01, top + 0.02, zm, bw + 0.02, 0.07, dz - 0.02, 0x5f9a48, (R() - 0.5) * 0.04, j=0.08)       # 위에 덮인 풀
        STAIR_CHEEKS.append((x, zm, CHW / 2, dz / 2))
    print('계단 벽', '왼쪽' if sx < 0 else '오른쪽', '언덕 끝 z', round(pz, 2), '계단 맨 위 z', round(zEdge - 0.6, 2))

# ---------- 울타리 (언덕 앞 가장자리) ----------
FENCE_POSTS = []
def fence(points, y=None):
    WOOD = 0x9a6b3e
    for i, (x, z) in enumerate(points):
        yy = H(x, z) if y is None else y
        box('lit', x, yy + 0.28, z, 0.09, 0.62, 0.09, WOOD, R() * 0.3); FENCE_POSTS.append((x, z))
        if i:
            px, pz = points[i - 1]; pyy = H(px, pz) if y is None else y
            L = math.hypot(x - px, z - pz); yaw = math.atan2(x - px, z - pz)
            for hh in (0.22, 0.44):
                box('lit', (x + px) / 2, (yy + pyy) / 2 + hh, (z + pz) / 2, 0.05, 0.06, L, 0x8a5e35, yaw, j=0.04)
for a0, a1 in ((PI / 2 + 0.22, PI / 2 + 0.85), (PI / 2 - 0.22, PI / 2 - 0.85)):
    ptsF = []
    for t in range(8):
        a = a0 + (a1 - a0) * t / 7; r = plat_r(a) - 0.45
        ptsF.append((PL[0] + math.cos(a) * r, PL[1] + math.sin(a) * r))
    fence([q for q in ptsF if abs(q[0] - PL[0]) >= 1.4], PLY)            # 계단 돌 벽과 겹치지 않게

# ---------- 돔 천문대 (원화 구성에 맞춤) ----------
# 원화: 높은 보라 원통 몸통(은분홍 세로 기둥 + 청록 전구 줄) → 두툼한 연보라 처마 → 보라에서 청록으로 바뀌는 돔(은 갈빗살 + 별 점)
#       → 꼭대기 은 꼭지 + 깃발. 입구는 튀어나온 아치 문틀 + 반원통 청록 유리 차양 + 금빛 안쪽 + 자홍 커튼 + 둥근 계단.
DOME = (DOME_C[0], H(*DOME_C), DOME_C[1])
DRUM, DRUMD, PILL, RIM, RIB, SILV = 0x8c78d0, 0x7562bc, 0xe8d4ec, 0xc9b6ea, 0xeee0f6, 0xe4e6f2
DR0, DH, DDR = 1.72, 1.25, 1.78            # 몸통 반지름·높이, 돔 반지름
DSY = 0.9                                  # 돔 세로 눌림
def rot_d(x, z):
    c, s = math.cos(DR), math.sin(DR); return (DOME[0] + x * c + z * s, DOME[2] - x * s + z * c)
def LP(x, y, z):                           # 입구 기준 지역 좌표(+z 가 바깥) → 월드
    wx, wz = rot_d(x, z); return (wx, DOME[1] + y, wz)
FRONT = math.atan2(math.cos(DR), math.sin(DR))       # 입구 방향의 lathe 각(cos a, sin a) = (sin DR, cos DR)
def near_front(a, w=0.55): return abs(math.atan2(math.sin(a - FRONT), math.cos(a - FRONT))) < w
# 받침 + 몸통 + 아래 띠 + 처마
lathe('lit', DOME, [(DR0 + 0.2, -0.25), (DR0 + 0.18, 0.08), (DR0 + 0.06, 0.12)], 24, [STONE, 0xa89cc8], capt=False)
lathe('lit', DOME, [(DR0, 0.1), (DR0, DH)], 24, lambda k, i: DRUM if i % 2 else DRUMD, j=0.04)
lathe('lit', DOME, [(DR0 + 0.04, 0.1), (DR0 + 0.1, 0.12), (DR0 + 0.1, 0.24), (DR0 + 0.04, 0.26)], 24, [PILL], j=0.03)
lathe('lit', DOME, [(DR0, DH - 0.02), (DR0 + 0.16, DH), (DR0 + 0.2, DH + 0.1), (DR0 + 0.16, DH + 0.22), (DR0 - 0.02, DH + 0.24)], 24, [RIM, RIM, 0xe2d6f6, RIM], j=0.03)
# 세로 기둥 12개(입구 쪽은 빼고) + 기둥 사이 청록 전구 줄(늘어진 곡선)
PILLARS = [i / 12 * TAU + FRONT + TAU / 24 for i in range(12)]
for a in PILLARS:
    if near_front(a, 0.5): continue
    box('lit', DOME[0] + math.cos(a) * (DR0 + 0.04), DOME[1] + DH / 2 + 0.08, DOME[2] + math.sin(a) * (DR0 + 0.04), 0.13, DH - 0.2, 0.09, PILL, PI / 2 - a, j=0.03)
for k in range(12):
    a0, a1 = PILLARS[k], PILLARS[k] + TAU / 12
    if near_front(a0, 0.5) or near_front(a1, 0.5): continue
    for t in range(1, 8):
        u = t / 8; a = a0 + (a1 - a0) * u; yy = DH - 0.22 - 0.32 * math.sin(u * PI)
        box('emit', DOME[0] + math.cos(a) * (DR0 + 0.06), DOME[1] + yy, DOME[2] + math.sin(a) * (DR0 + 0.06), 0.07, 0.07, 0.07, 0x6ff0e6 if t % 2 else 0xb8fff4, PI / 2 - a, j=0.03)
# 돔: 입구 반대쪽(그늘)은 짙은 보라, 입구 쪽 오른편(빛)은 밝은 청록
LIGHT_A = FRONT - 0.6
def dome_col(k, i):
    a = (i + 0.5) / 28 * TAU
    t = 0.5 + 0.5 * math.cos(a - LIGHT_A); t = t * (0.75 + 0.25 * k / 8)
    return mixc(hexc(0x9a86e0), hexc(0xa6e6f4), max(0.0, min(1.0, t * t * 1.1)))
dy0 = DOME[1] + DH + 0.2
prof = [(DDR * math.cos(t / 8 * PI / 2), DSY * DDR * math.sin(t / 8 * PI / 2)) for t in range(9)]
prof[-1] = (0, prof[-1][1])
lathe('lit', (DOME[0], dy0, DOME[2]), prof, 28, dome_col, j=0.03)
# 은 갈빗살 12줄: 돔 표면 위로 살짝 띄운 띠
for r_i in range(12):
    a = r_i / 12 * TAU + FRONT; ca, sa = math.cos(a), math.sin(a); tx, tz = -sa * 0.045, ca * 0.045
    pts = []
    for t in range(9):
        e = t / 8 * PI / 2 * 0.93
        rr = DDR * math.cos(e) + 0.03; yy = dy0 + DSY * DDR * math.sin(e) + 0.03
        pts.append((DOME[0] + ca * rr, yy, DOME[2] + sa * rr))
    for t in range(8):
        (x0, y0_, z0), (x1, y1, z1) = pts[t], pts[t + 1]
        tri_prism('lit', [[(x0 - tx, y0_, z0 - tz), (x0 + tx, y0_, z0 + tz), (x1 + tx, y1, z1 + tz), (x1 - tx, y1, z1 - tz)]], RIB, j=0.03, c=(DOME[0], dy0, DOME[2]))
dtop = dy0 + DSY * DDR
lathe('lit', (DOME[0], dtop - 0.12, DOME[2]), [(0.42, 0), (0.46, 0.08), (0.34, 0.2), (0.12, 0.26), (0, 0.28)], 12, [SILV, SILV, 0xffffff], j=0.03)
flagpole(DOME[0], dtop + 0.12, DOME[2])
# --- 입구: 튀어나온 아치 문틀 ---
EZ0, EZ1, EW, EH, VR = 1.25, 2.15, 0.72, 1.25, 0.72      # 앞뒤 범위, 반폭, 기둥 높이, 차양 반지름
for sx in (-1, 1):
    px, pz = rot_d(sx * EW, (EZ0 + EZ1) / 2)
    box('lit', px, DOME[1] + EH / 2 + 0.05, pz, 0.16, EH, EZ1 - EZ0, 0xb8a6dc, DR, bevel=0.02)      # 옆벽
    px, pz = rot_d(sx * EW, EZ1)
    box('lit', px, DOME[1] + EH / 2 + 0.05, pz, 0.2, EH + 0.04, 0.16, PILL, DR, bevel=0.02)          # 앞 기둥
    px, pz = rot_d(sx * (EW - 0.18), EZ1 - 0.12)                                                     # 자홍 커튼(묶어 올린 삼각)
    cx = sx * (EW - 0.1)
    tri_prism('lit', [[LP(cx, 0.15, EZ1 - 0.1), LP(cx, EH, EZ1 - 0.1), LP(cx - sx * 0.42, EH, EZ1 - 0.1), LP(cx - sx * 0.12, 0.55, EZ1 - 0.1)]], 0xd23c8e, j=0.05, c=LP(0, 0.6, 0))
# 금빛 안쪽(입구 깊숙한 면)과 바닥
FL = 0.32                                                     # 입구 문턱(안쪽 바닥) 높이 = 계단 맨 위
px, pz = rot_d(0, (DR0 - 0.15 + EZ1) / 2)
box('lit', px, DOME[1] + (FL - 0.12) / 2, pz, 2 * (EW - 0.08), FL + 0.12, EZ1 - DR0 + 0.15, 0xe8cf96, DR, j=0.03)
tri_prism('emit', [[LP(-EW + 0.08, FL, DR0 + 0.04), LP(EW - 0.08, FL, DR0 + 0.04), LP(EW - 0.08, EH + 0.05, DR0 + 0.04), LP(-EW + 0.08, EH + 0.05, DR0 + 0.04)]], 0xffc860, j=0.02, c=LP(0, 0.6, 0))
tri_prism('emit', [[LP(-EW + 0.08, FL + 0.01, DR0), LP(-EW + 0.08, FL + 0.01, EZ1 - 0.02), LP(EW - 0.08, FL + 0.01, EZ1 - 0.02), LP(EW - 0.08, FL + 0.01, DR0)]], 0xffd88a, j=0.02, c=LP(0, -1, 1.7))
# 반원통 청록 유리 차양 + 앞쪽 아치 테두리
NV = 9
arc = [(math.cos(i / NV * PI) * VR, EH + 0.05 + math.sin(i / NV * PI) * VR * 0.75) for i in range(NV + 1)]
for i in range(NV):
    (xa, ya), (xb, yb) = arc[i], arc[i + 1]
    col = 0x6fe0f2 if i % 2 else 0x9ff0fa
    tri_prism('emit', [[LP(xa, ya, EZ0 - 0.15), LP(xb, yb, EZ0 - 0.15), LP(xb, yb, EZ1), LP(xa, ya, EZ1)]], col, j=0.04, c=LP(0, EH, (EZ0 + EZ1) / 2))
for i in range(NV):                                           # 차양 앞 테두리(은분홍 아치 띠)
    (xa, ya), (xb, yb) = arc[i], arc[i + 1]
    k0, k1 = 1.12, 1.12
    tri_prism('lit', [[LP(xa, ya, EZ1 + 0.02), LP(xb, yb, EZ1 + 0.02), LP(xb * k1, EH + 0.05 + (yb - EH - 0.05) * k1 + 0.04, EZ1 + 0.02), LP(xa * k0, EH + 0.05 + (ya - EH - 0.05) * k0 + 0.04, EZ1 + 0.02)]], PILL, j=0.03, c=LP(0, EH, 0))
tri_prism('lit', [[LP(arc[i][0], arc[i][1], EZ1 + 0.01) for i in range(NV + 1)]], 0xb8a6dc, j=0.03, c=LP(0, EH, 0))   # 차양 앞 반원 막음(문 위 벽)
# 계단 3단: 문 기둥 바깥(EZ1 + 0.09)부터 시작해 문턱보다 한 단씩 낮게, 아래로 갈수록 넓게
for s in range(3):
    w = 1.4 + s * 0.3; z = EZ1 + 0.09 + 0.13 + s * 0.24; top = FL - 0.1 * (s + 1)
    px, pz = rot_d(0, z)
    box('lit', px, DOME[1] + (top - 0.2) / 2, pz, w, top + 0.2, 0.26, 0xead8a8 if s % 2 else 0xdcc690, DR, bevel=0.03)
DOME_STARS = []
for i in range(70):
    a = R() * TAU; e = R() * PI / 2 * 0.85; r = DDR + 0.02
    if near_front(a, 0.4) and e < 0.25: continue
    DOME_STARS.append([DOME[0] + math.cos(a) * math.cos(e) * r, dy0 + math.sin(e) * r * DSY, DOME[2] + math.sin(a) * math.cos(e) * r])

# ---------- 캠프 ----------
CAMP = (CAMP_C[0], H(*CAMP_C), CAMP_C[1])
# 텐트는 모닥불 뒤쪽(북·동)에 반원으로, 입구는 불을 향함. 앞쪽(서·남)은 돌길과 통나무 의자 자리로 비움
TENTS = [(-0.4, -2.0, 1.0, 0x8e7f9e), (1.55, -1.25, 0.95, 0x3d5da6), (2.0, 0.75, 0.9, 0xf09a3c)]   # 원화: 회보라·파랑(별 무늬)·주황
CAMP_FP = []
for (tx, tz, s, col) in TENTS:
    GL, GE = ('trash', 'trash') if col == 0xf09a3c else ('lit', 'emit')
    if GL == 'lit': CAMP_FP.append((CAMP[0] + tx, CAMP[2] + tz, 0.75 * s, '텐트%d' % len(CAMP_FP)))   # 주황 텐트는 벤치와 겹쳐 사용자 요청으로 뺌(난수 순서 유지)
    cx, cz = CAMP[0] + tx, CAMP[2] + tz; cy = H(cx, cz) - 0.02
    yaw = math.atan2(-tx, -tz)                          # 앞(+z)이 모닥불을 향함
    W, Hh, L = 1.25 * s, 1.15 * s, 1.5 * s
    def P(lx, ly, lz):
        c, sn = math.cos(yaw), math.sin(yaw); return (cx + lx * c + lz * sn, cy + ly, cz - lx * sn + lz * c)
    TC = P(0, Hh * 0.3, 0)
    tri_prism(GL, [[P(-W / 2, 0, L / 2), P(-W / 2, 0, -L / 2), P(0, Hh, -L / 2), P(0, Hh, L / 2)],
                      [P(W / 2, 0, -L / 2), P(W / 2, 0, L / 2), P(0, Hh, L / 2), P(0, Hh, -L / 2)],
                      [P(-W / 2, 0, -L / 2), P(W / 2, 0, -L / 2), P(0, Hh, -L / 2)]], col, 0.05, TC)
    tri_prism(GE, [[P(-W / 2 + 0.02, 0.0, L / 2 - 0.08), P(0, Hh - 0.02, L / 2 - 0.08), P(W / 2 - 0.02, 0.0, L / 2 - 0.08)]], 0xc8321f, 0.03, TC)   # 붉게 빛나는 안쪽
    tri_prism(GE, [[P(-W * 0.24, 0, L / 2 - 0.05), P(W * 0.24, 0, L / 2 - 0.05), P(0, Hh * 0.5, L / 2 - 0.05)]], 0xff8a3a, 0.02, TC)
    tri_prism(GL, [[P(-W / 2, 0, L / 2), P(0, Hh, L / 2), P(-W * 0.3, 0, L / 2 + 0.3)],                       # 젖혀 묶은 앞 덮개(금주황)
                      [P(W / 2, 0, L / 2), P(W * 0.3, 0, L / 2 + 0.3), P(0, Hh, L / 2)]], 0xf6b03c, 0.04, TC)
    for sd in (-1, 1):                                                                                        # 덮개 가장자리 금띠
        tri_prism(GL, [[P(sd * W / 2, 0.0, L / 2 + 0.005), P(0, Hh, L / 2 + 0.005), P(sd * 0.08, Hh - 0.12, L / 2 + 0.005), P(sd * (W / 2 - 0.12), 0.0, L / 2 + 0.005)]], 0xffd76a, 0.03, TC)
    if col == 0x3d5da6:                                                                                       # 파란 텐트 옆면 별 무늬
        for sd in (-1, 1):
            nx_, ny_ = sd * Hh, W / 2; nn = math.hypot(nx_, ny_); nx_, ny_ = nx_ / nn, ny_ / nn
            vx, vy = -sd * W / 2, Hh; vn = math.hypot(vx, vy); vx, vy = vx / vn, vy / vn
            bx0, by0 = sd * W / 4 + nx_ * 0.02, Hh / 2 + ny_ * 0.02
            star = []
            for k in range(10):
                a = k / 10 * TAU; rr = 0.2 * s if k % 2 == 0 else 0.08 * s
                u, v = math.sin(a) * rr, math.cos(a) * rr
                star.append(P(bx0 + vx * v, by0 + vy * v, u))
            tri_prism(GL, [star], 0xdfe6ff, 0.02, TC)
    x1, y1, z1 = P(0, Hh + 0.12, L / 2 + 0.05); box(GL, x1, y1 - 0.1, z1, 0.05, 0.3, 0.05, 0x6b4428)
fx, fz = CAMP[0], CAMP[2]
for i in range(10):                                                      # 원화: 불씨처럼 달아오른 돌무더기
    a = i / 10 * TAU; ico('lit', fx + math.cos(a) * 0.48, CAMP[1] + 0.07, fz + math.sin(a) * 0.48, 0.15, 0x8a6a58 if i % 2 else 0x9c7a62, 0, 0.05)
for i in range(7):
    a = i / 7 * TAU + 0.3; rr = 0.18 + 0.12 * (i % 2)
    ico('emit', fx + math.cos(a) * rr, CAMP[1] + 0.09, fz + math.sin(a) * rr, 0.11, 0xff7a2a if i % 2 else 0xffb04a, 0, 0.04)
for i in range(4):
    a = i / 4 * TAU + 0.3
    box('lit', fx + math.cos(a) * 0.12, CAMP[1] + 0.16, fz + math.sin(a) * 0.12, 0.1, 0.1, 0.75, 0x6b4428, PI / 2 - a, rx=0.4)
for (bx, bz) in ((-1.25, 0.15), (0.95, 1.05)):                            # 판자 벤치(원화): 불 둘레 접선 방향
    x, z = fx + bx, fz + bz; y = H(x, z); n = math.hypot(bx, bz); tx, tz = -bz / n, bx / n; ry = math.atan2(-tz, tx)
    CAMP_FP.append((x, z, 0.5, '벤치%d' % len(CAMP_FP)))
    for o in (-0.09, 0.09):
        box('lit', x - tz * o, y + 0.36, z + tx * o, 1.15, 0.07, 0.16, 0xa65a34, ry, bevel=0.02)
    for u in (-0.42, 0.42):
        box('lit', x + tx * u, y + 0.17, z + tz * u, 0.08, 0.34, 0.34, 0x7a3e22, ry)
for (bx, bz) in ((-0.35, 1.25),):                                          # 통나무 의자 하나는 남김
    x, z = fx + bx, fz + bz; CAMP_FP.append((x, z, 0.55, '통나무%d' % len(CAMP_FP))); bmx = grp('lit'); r = math.atan2(-bz, bx)      # 통나무 축이 불 둘레 접선 방향(-bz, bx)
    res = bmesh.ops.create_cone(bmx, cap_ends=True, cap_tris=False, segments=7, radius1=0.17, radius2=0.17, depth=1.1,
                                matrix=Matrix.Translation((x, H(x, z) + 0.15, z)) @ Matrix.Rotation(r, 4, 'Y'))
    paint(bmx, faces_of(res['verts']), 0x7a4b2b, 0.08)
# 상자·통
for (bx, bz) in ((2.9, -0.35), (3.1, 0.1)):                           # 상자: 텐트 사이 뒤쪽
    x, z = fx + bx, fz + bz; CAMP_FP.append((x, z, 0.3, '상자%d' % len(CAMP_FP))); box('lit', x, H(x, z) + 0.2, z, 0.42, 0.42, 0.42, 0xb07a45, R(), bevel=0.04)
box('lit', fx + 3.0, H(fx + 3.0, fz - 0.12) + 0.6, fz - 0.12, 0.32, 0.32, 0.32, 0xc08a52, 0.6, bevel=0.03)
for (bx, bz) in ((-1.55, -1.6), (-1.85, -1.15)):                       # 통: 왼쪽 텐트 옆
    x, z = fx + bx, fz + bz; y = H(x, z); CAMP_FP.append((x, z, 0.28, '통%d' % len(CAMP_FP)))
    lathe('lit', (x, y, z), [(0.22, 0), (0.26, 0.25), (0.22, 0.52)], 9, [0x9a6b3e, 0x8a5e35], capt=True)
    lathe('lit', (x, y, z), [(0.235, 0.1), (0.235, 0.15)], 9, [0x5c5c66])
    lathe('lit', (x, y, z), [(0.235, 0.39), (0.235, 0.44)], 9, [0x5c5c66])

# ---------- 랜턴 기둥 ----------
LANTERNS = []
LAMP_POS = []
def lantern(x, z, tx, tz):
    """길가 전등: 기둥 + 팔(길 쪽 tx,tz 를 향함) + 등. 캠프 소품과 가까우면 소품 반대쪽으로 비켜 놓는다."""
    for _ in range(20):
        near = [(ox, oz, r) for (ox, oz, r, nm) in CAMP_FP if math.hypot(x - ox, z - oz) < r + 0.45]
        if not near: break
        ox, oz, r = near[0]; d = math.hypot(x - ox, z - oz) or 1e-3
        x, z = x + (x - ox) / d * 0.1, z + (z - oz) / d * 0.1
    LAMP_POS.append((x, z))
    y = H(x, z); a = math.atan2(tz - z, tx - x); ca, sa = math.cos(a), math.sin(a)
    lathe('lit', (x, y - 0.1, z), [(0.1, 0), (0.1, 0.12), (0.06, 0.2), (0.05, 1.3)], 6, [0x3a3a44, 0x4a3a30, 0x4a3a30])
    box('lit', x + ca * 0.13, y + 1.15, z + sa * 0.13, 0.04, 0.04, 0.3, 0x4a3a30, math.atan2(ca, sa))
    lx, lz = x + ca * 0.26, z + sa * 0.26
    box('emit', lx, y + 0.98, lz, 0.14, 0.18, 0.14, 0xffd27a, j=0.02)
    lathe('lit', (lx, y + 1.07, lz), [(0.12, 0), (0, 0.1)], 4, [0x3a2e28], rot=PI / 4, capb=True)
    LANTERNS.append([lx, y + 0.98, lz])
def lamp_ok(x, z):
    if pond_d(x, z) < 0.75 or chan_k(x, z) > 0.02: return False
    if any(math.hypot(x - ax, z - az) < r for ax, az, r in ((CAMP_C[0], CAMP_C[1], 2.9), (DOME_C[0], DOME_C[1], 2.6), (OAK_OLD[0], OAK_OLD[1], 1.5), (OAK_C[0], OAK_C[1], 1.9))): return False
    return not inPl(x, z, 1.25)
def inPl(x, z, k=1.0):
    dx, dz = x - PL[0], z - PL[1]; return math.hypot(dx, dz) < plat_r(math.atan2(dz, dx)) * k
# 가로등(계단 양옆 한 쌍은 사용자 요청으로 제거): 선착장 아래쪽, 돔 입구 앞, 캠프 입구 앞
lantern(DOCK_X - 0.5, DOCK_Z + 0.75, DOCK_X - 0.1, DOCK_Z + 0.3)
_c, _s = math.cos(DR), math.sin(DR)
_j = PATHS[0][1]                                             # 삼거리(계단 길이 돔·선착장으로 갈라지는 곳)
lantern(_j[0] - 0.15, _j[1] - 0.75, _j[0], _j[1])
_m = PATHS[1][1]                                             # 계단과 캠프 사이 길의 가운데
lantern(_m[0] + 0.1, _m[1] - 0.7, _m[0], _m[1])
# (길가 가로등은 사용자 요청으로 제거, 계단 아래 한 쌍만 유지)

# ---------- 연못 선착장 ----------
# 땅 쪽 끝은 물가에 살짝 걸치고 나머지는 물 위로. 둑보다 높게 띄워 지형과 겹치지 않게
DY = max(H(DOCK_X - 0.45 + k * 0.1, DOCK_Z + dz) for k in range(6) for dz in (-0.45, 0, 0.45)) + 0.07
for i in range(7):
    x = DOCK_X - 0.4 + i * 0.24
    box('lit', x, DY, DOCK_Z, 0.21, 0.06, 0.95, 0xb98250 if i % 2 else 0xa8703e, j=0.05)
for z in (DOCK_Z - 0.38, DOCK_Z + 0.38):
    box('lit', DOCK_X + 0.32, DY - 0.06, z, 1.5, 0.06, 0.08, 0x7a4b2b, j=0.04)          # 아래 받침대
    for x in (DOCK_X + 0.15, DOCK_X + 1.0):                                              # 물속 기둥
        lathe('lit', (x, -0.5, z), [(0.06, 0), (0.06, DY + 0.58)], 5, [0x6b4428], capt=True)

# ---------- 나룻배 (따로 움직이게 별도 그룹, 멀리서 만들고 원점 기준으로 내보냄) ----------
BOAT_O = (0, 60, 0)
bm_b = grp('boat'); layb = bm_b.loops.layers.float_color['base']
prof = [(0.0, -0.28), (0.3, -0.24), (0.46, -0.1), (0.5, 0.06)]
hull = lathe('boat', BOAT_O, prof, 16, [0x7a3f24, 0x8a4a2a, 0x9a5a32])
rim = lathe('boat', BOAT_O, [(0.5, 0.06), (0.55, 0.08), (0.55, 0.13), (0.45, 0.13)], 16, [0xd09a62, 0xe0ae72, 0xc88c56])   # 뱃전
floor = lathe('boat', (BOAT_O[0], BOAT_O[1] - 0.17, BOAT_O[2]), [(0.35, 0), (0.0, 0.0)], 16, [0x9a6638], j=0.04)   # 배 바닥: 선체 모양 판(직사각형 상자는 선체 밖으로 삐져나와 뺌)
def pinch(fs):                                                            # 길게 늘이고 앞(+z)은 뾰족, 뒤는 조금 좁게
    for v in {v for f in fs for v in f.verts}:
        dz = (v.co.z - BOAT_O[2]) * 2.1; u = dz / 1.05
        k = 1 - 0.8 * max(0.0, u) ** 1.6 - 0.25 * max(0.0, -u) ** 2
        v.co.x = BOAT_O[0] + (v.co.x - BOAT_O[0]) * k; v.co.z = BOAT_O[2] + dz
        if u > 0.6: v.co.y += (u - 0.6) * 0.18                             # 뱃머리 살짝 들림
pinch(hull); pinch(rim); pinch(floor)
for z, w in ((-0.35, 0.76), (0.22, 0.66)): box('boat', BOAT_O[0], BOAT_O[1] - 0.02, BOAT_O[2] + z, w, 0.05, 0.2, 0xb98250)   # 좌석: 좁아지는 앞쪽은 더 좁게(선체 16각형 모서리 안쪽)
box('boat', BOAT_O[0] + 0.17, BOAT_O[1] + 0.01, BOAT_O[2] - 0.05, 0.05, 0.04, 0.8, 0xc79a62, rz=0.1)   # 노: 좁아진 앞뒤에서 선체를 뚫지 않게 짧게

# ---------- 나무 ----------
TREES = []
avoid = [(PL[0], PL[1] - 0.4, 3.4), (DOME_C[0], DOME_C[1], 2.8), (CAMP_C[0] + 0.5, CAMP_C[1] - 0.2, 3.4), (POND[0], POND[1] + 0.2, 3.7), (PL[0], STAIR_END + 0.3, 1.5), (OAK_OLD[0], OAK_OLD[1], 1.7)]
def inPl(x, z, k=1.0):
    dx, dz = x - PL[0], z - PL[1]; return math.hypot(dx, dz) < plat_r(math.atan2(dz, dx)) * k
tries = 0
while len(TREES) < 34 and tries < 6000:
    tries += 1
    a = R() * TAU; ca, sa = math.cos(a), math.sin(a)
    if sa > 0.3 and abs(ca) < 0.62: continue
    r = ISL_R(a, ISLB) * (0.7 + R() * 0.24); x, z = ca * r, sa * r
    if any(math.hypot(x - ax, z - az) < ar for ax, az, ar in avoid): continue
    if inPl(x, z, 1.15) and not inPl(x, z, 0.84): continue
    if inPl(x, z, 1.15) and z < PL[1] - 0.5 and abs(x - PL[0]) < 3.2: continue     # 성 바로 뒤는 비움(뒤에서 봐도 성이 보이게)
    if any(math.hypot(t[0] - x, t[2] - z) < 1.6 for t in TREES): continue
    if path_d(x, z) < 0.8: continue
    back = 1 if z < -1 else 0
    TREES.append([x, H(x, z), z, 0.85 + R() * 0.45 + back * 0.2])
for (x, z, s) in ((-9.6, -1.7, 1.6), (-8.7, 2.2, 1.5), (9.4, -2.5, 1.6), (-5.2, -8.8, 1.7), (5.8, -8.6, 1.7)):
    if not inPl(x, z, 1.15): TREES.append([x, H(x, z), z, s])
TREES = [t for t in TREES if ISL_R(math.atan2(t[2], t[0])) - math.hypot(t[0], t[2]) > 0.5]   # 가장자리에 걸쳐 떠 보이는 나무 제외
TREES = [t for t in TREES if math.hypot(t[0] - OAK_C[0], t[2] - OAK_C[1]) > 2.3]              # 새 활엽수 자리와 겹치는 소나무 제외
TREES.append([OAK_OLD[0], H(*OAK_OLD), OAK_OLD[1], 1.35])                                     # 옛 활엽수 자리는 소나무로 채움
PINE_C = [hexc(0x235c3f), hexc(0x2f7349), hexc(0x3a8752), hexc(0x4a9a5b), hexc(0x5aac64)]
TIERS = {}
def pine(x, y, z, s):
    """원화: 가늘고 키 큰 침엽수. 층이 많고 가지 끝이 아래로 처진 톱니 모양, 꼭대기는 길게 뾰족."""
    var = R(); rot = R() * TAU; n = 6 if var > 0.35 else 5
    lathe('tree', (x, y, z), [(0.14 * s, -0.2), (0.1 * s, 0.9 * s)], 6, [0x6b4428, 0x5a3820], rot=rot)
    tiers = []
    for t in range(n):
        u = t / (n - 1)
        yb = y + (0.55 + t * 3.0 / n) * s; rb = (0.95 - u * 0.62) * s
        ht = (0.95 + (0.45 if t == n - 1 else 0.0)) * s
        tiers.append((yb, rb, ht))
        seg = 12
        zig = lambda i, k: (1.0 if i % 2 == 0 else 0.62) if k in (1, 2) else 1.0
        dark = mixc(PINE_C[0], [0, 0, 0], 0.3)
        col = PINE_C[min(4, int(u * 3.5) + (1 if var > 0.7 else 0))]
        prof = [(0.0, 0.26 * s), (rb * 0.94, 0.02 * s), (rb, -0.1 * s), (rb * 0.58, ht * 0.32), (0, ht)]
        lathe('tree', (x, yb, z), prof, seg,
              lambda k, i, col=col, dark=dark: dark if k == 0 else (mixc(col, dark, 0.35) if k == 1 else (col if k == 2 else mixc(col, [1, 1, .8], 0.12))),
              zig=zig, rot=rot + t * 0.26, jt=0.05 * s, j=0.07)
    TIERS[len(TIERS)] = tiers
    return tiers
TREE_TIERS = [pine(*t) for t in TREES]
# 둥근 활엽수 (원화처럼 굵고 비틀린 줄기, 퍼진 뿌리, 갈라지는 가지, 뭉게구름 잎 덩어리)
OAK = (OAK_C[0], H(*OAK_C), OAK_C[1])
BARK, BARKD = 0x6e4526, 0x4f301a
lathe('tree', (OAK[0], OAK[1] - 0.25, OAK[2]), [(0.55, 0), (0.42, 0.22), (0.3, 0.55), (0.26, 1.0), (0.3, 1.35), (0.36, 1.55)], 9,
      lambda k, i: BARKD if i % 3 == 0 else BARK, jt=0.06, j=0.06)
for k in range(5):                                            # 퍼진 뿌리
    a = k / 5 * TAU + 0.4; ry = math.atan2(math.cos(a), math.sin(a))
    box('tree', OAK[0] + math.cos(a) * 0.45, OAK[1] + 0.02, OAK[2] + math.sin(a) * 0.45, 0.16, 0.14, 0.62, BARKD, ry, rx=0.35, j=0.06)
LIMBS = []
for k, (a, e, L) in enumerate(((0.3, 0.75, 1.15), (1.6, 0.6, 1.0), (2.8, 0.8, 1.1), (4.1, 0.55, 1.05), (5.2, 0.7, 0.95))):   # 가지
    ry = math.atan2(math.cos(a), math.sin(a)); d = (math.cos(a) * math.cos(e), math.sin(e), math.sin(a) * math.cos(e))
    p0 = (OAK[0], OAK[1] + 1.3, OAK[2])
    box('tree', p0[0] + d[0] * L / 2, p0[1] + d[1] * L / 2, p0[2] + d[2] * L / 2, 0.17, 0.17, L, BARK, ry, rx=-e, j=0.06)
    LIMBS.append((p0[0] + d[0] * L, p0[1] + d[1] * L, p0[2] + d[2] * L))
LEAF_LO, LEAF_MID, LEAF_HI = hexc(0x2f6e34), hexc(0x4c9a3e), hexc(0x86cc5a)
def leaf_col(y):
    t = max(0.0, min(1.0, (y - (OAK[1] + 1.6)) / 1.9))
    return mixc(mixc(LEAF_LO, LEAF_MID, min(1, t * 2)), LEAF_HI, max(0, t * 2 - 1))
PUFFS = []
for (lx, ly, lz) in LIMBS:                                    # 가지 끝마다 잎 덩어리
    PUFFS.append((lx, ly + 0.15, lz, 0.72 + R() * 0.15))
for (x, y, z, r) in ((0, 2.75, 0, 1.0), (0.45, 3.2, -0.3, 0.75), (-0.5, 3.1, 0.25, 0.7), (0.1, 3.55, 0.1, 0.6),
                     (0.9, 2.5, 0.6, 0.6), (-0.9, 2.45, -0.5, 0.6), (0.2, 2.1, 0.95, 0.55), (-0.3, 2.05, -1.0, 0.55)):
    PUFFS.append((OAK[0] + x, OAK[1] + y, OAK[2] + z, r))
for (x, y, z, r) in PUFFS:
    ico('tree', x, y, z, r, leaf_col(y), 1, 0.2 * r, sy=0.82, j=0.08)
    ico('tree', x + r * 0.35, y + r * 0.45, z + r * 0.2, r * 0.55, mixc(leaf_col(y + r), LEAF_HI, 0.25), 1, 0.15 * r, sy=0.8, j=0.08)   # 위쪽 밝은 혹

# 전구 위치 (나무 둘레 나선 + 나무 사이 늘어진 줄)
def env_r(tiers, yy):
    best = 0
    for (yb, rb, ht) in tiers:
        if yb <= yy <= yb + ht:
            u = (yy - yb) / ht
            rr = rb * (1 - u / 0.45 * 0.45) if u < 0.45 else rb * 0.55 * (1 - (u - 0.45) / 0.55)
            best = max(best, rr)
    return best
BULBS = []
big = [i for i, t in enumerate(TREES) if t[3] > 1.05][:18]
for i in big:
    x, y, z, s = TREES[i]; off = R() * TAU; tiers = TREE_TIERS[i]
    hh = tiers[0][0] + 0.1
    while hh < tiers[-1][0] + tiers[-1][2] * 0.6:
        rr = env_r(tiers, hh) * 0.92 + 0.04
        a = (hh - y) / s * 2.7 + off
        if rr > 0.15: BULBS.append([x + math.cos(a) * rr, hh, z + math.sin(a) * rr])
        hh += 0.11 * s
tops = [t for t in TREES if t[3] > 1.1]
for i in range(len(tops)):
    for j2 in range(i + 1, len(tops)):
        A, B = tops[i], tops[j2]; d = math.hypot(A[0] - B[0], A[2] - B[2])
        if d < 2.6 or d > 4.2 or R() < 0.45: continue
        ya, yb2 = A[1] + 1.9 * A[3], B[1] + 1.9 * B[3]
        for k in range(1, 12):
            u = k / 12
            BULBS.append([A[0] + (B[0] - A[0]) * u, ya + (yb2 - ya) * u - math.sin(u * PI) * 0.7, A[2] + (B[2] - A[2]) * u])
OAK_BULBS = []
def oak_surface(a, y):                                         # 해당 방향·높이에서 잎 덩어리 겉면까지 거리
    best = 0.0
    for (x, py, z, r) in PUFFS:
        dy = (y - py) / 0.82
        if abs(dy) >= r: continue
        rr = math.sqrt(r * r - dy * dy); cx, cz = x - OAK[0], z - OAK[2]
        proj = cx * math.cos(a) + cz * math.sin(a); perp = -cx * math.sin(a) + cz * math.cos(a)
        if abs(perp) < rr: best = max(best, proj + math.sqrt(rr * rr - perp * perp))
    return best
for (y0, amp, off) in ((OAK[1] + 2.1, 0.22, 0.0), (OAK[1] + 2.7, 0.18, 1.1), (OAK[1] + 3.25, 0.14, 2.3)):
    for k in range(34):
        a = k / 34 * TAU + off; y = y0 - amp * abs(math.sin(a * 3))      # 세 번씩 늘어지는 줄
        rr = oak_surface(a, y)
        if rr > 0.3: OAK_BULBS.append([OAK[0] + math.cos(a) * (rr + 0.04), y, OAK[2] + math.sin(a) * (rr + 0.04)])

# ---------- 돌길 (개수를 줄이고 좌우 지그재그로 고르게, 겹치지 않게) ----------
PATH_STONES = []
PR = random.Random(9090)                                     # 돌길 배치 전용 난수
STONE_LINES = [PATHS[2], PATHS[0], [FORK] + PATHS[1], PATHS[3]]   # 계단→갈림길, 갈림길→돔, 갈림길→캠프(갈림길에서 바로 이어지게), 물가 곡선→선착장
SP = 0.6                                                    # 돌 사이 간격(중심 거리, 돌을 줄이며 조금 좁힘)
def pt_on(line, d):                                         # 꺾인 길을 따라 거리 d 인 점과 방향
    acc = 0.0
    for k in range(len(line) - 1):
        a, b = line[k], line[k + 1]; L = math.hypot(b[0] - a[0], b[1] - a[1])
        if d <= acc + L or k == len(line) - 2:
            u = min(1.0, max(0.0, (d - acc) / L)) if L else 0.0
            return a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u, (b[0] - a[0]) / (L or 1), (b[1] - a[1]) / (L or 1)
        acc += L
for line in STONE_LINES:
    total = sum(math.hypot(line[k + 1][0] - line[k][0], line[k + 1][1] - line[k][1]) for k in range(len(line) - 1))
    d, last, kk = 0.0, None, 0
    side = (0.12 if kk % 2 else -0.12) + PR.uniform(-0.03, 0.03); r = PR.uniform(0.23, 0.29)
    while d <= total + 1e-6:                                  # 길을 따라 0.05씩 나아가며, 앞 돌에서 SP 만큼 떨어진 첫 빈자리에 놓는다
        px, pz, tx, tz = pt_on(line, d); d += 0.05
        x, z = px - tz * side, pz + tx * side
        if last and math.hypot(x - last[0], z - last[1]) < SP: continue
        lx = (x - DOME_C[0]) * math.cos(DR) - (z - DOME_C[1]) * math.sin(DR); lz = (x - DOME_C[0]) * math.sin(DR) + (z - DOME_C[1]) * math.cos(DR)
        if abs(lx) < 1.3 and lz < 3.25: continue             # 돔 입구 계단 자리는 비움
        if abs(x - PL[0]) < 1.25 and z < STAIR_END + 0.25: continue   # 성 계단 자리도 비움
        if any(math.hypot(x - x2, z - z2) < r + r2 + 0.03 for (x2, z2, r2) in PATH_STONES): continue   # 다른 길의 돌과 겹치면 조금 더 나아감
        PATH_STONES.append((x, z, r)); last = (x, z); kk += 1
        nseg = 14; ph1, ph2, amp = PR.random() * TAU, PR.random() * TAU, PR.uniform(0.08, 0.16)
        edge = [1 + amp * math.sin(2 * (q / nseg * TAU) + ph1) + 0.6 * amp * math.sin(3 * (q / nseg * TAU) + ph2) + PR.uniform(-0.05, 0.05) for q in range(nseg)]   # 돌마다 불규칙한 둘레
        tone = PR.uniform(-0.05, 0.05); base_ = mixc(hexc(0xa79a84), hexc(0xbcae95), PR.random())   # 흙길에 묻히는 차분한 회갈색(너무 밝아 바둑알처럼 튀지 않게)
        top_ = [min(1, max(0, v + tone)) for v in base_]
        fs = lathe('stone', (x, H(x, z) - 0.02, z), [(r, 0), (r, 0.035), (r * 0.96, 0.06), (r * 0.86, 0.072), (r * 0.5, 0.076), (0, 0.077)], nseg,
                   [mixc(top_, [0.45, 0.42, 0.38], 0.25), top_, top_, top_, top_], zig=lambda i, k, e=edge: e[i], rot=PR.random() * TAU, j=0.01)   # 납작한 판돌: 윗면 평평, 가장자리만 둥글게
        tilt = (PR.uniform(-0.05, 0.05), PR.uniform(-0.05, 0.05))
        for v in {v for f in fs for v in f.verts}: v.co.y += (v.co.x - x) * tilt[0] + (v.co.z - z) * tilt[1]   # 살짝 기울임
        asp, rot = PR.uniform(0.8, 1.0), PR.random() * PI    # 살짝 타원
        ca, sa = math.cos(rot), math.sin(rot)
        for v in {v for f in fs for v in f.verts}:
            dx, dz = v.co.x - x, v.co.z - z
            u1, u2 = dx * ca + dz * sa, (-dx * sa + dz * ca) * asp
            v.co.x, v.co.z = x + u1 * ca - u2 * sa, z + u1 * sa + u2 * ca
        side = (0.12 if kk % 2 else -0.12) + PR.uniform(-0.03, 0.03); r = PR.uniform(0.23, 0.29)
print('디딤돌 개수', len(PATH_STONES))

# ---------- 덤불·풀·꽃·버섯·돌 ----------
ROCKS = []
def clear(x, z, pad=0.0):
    if ISL_R(math.atan2(z, x)) - math.hypot(x, z) < 0.5: return False      # 섬 가장자리에 걸쳐 떠 보이지 않게
    if any(math.hypot(x - ax, z - az) < ar + pad for ax, az, ar in ((CAMP_C[0] + 0.5, CAMP_C[1] - 0.2, 3.0), (DOME_C[0], DOME_C[1], 2.4), (OAK_OLD[0], OAK_OLD[1], 1.4), (OAK_C[0], OAK_C[1], 1.9))): return False
    if pond_d(x, z) < 0.35 or chan_k(x, z) > 0.05: return False
    if inPl(x, z, 1.12) and not inPl(x, z, 0.82): return False
    if inPl(x, z, 0.82) and abs(x - PL[0]) < 3.0 and z < PL[1] + 1.6: return False   # 성 바닥
    if abs(x - PL[0]) < 1.0 and zEdge - 0.6 < z < zEdge + 2.3: return False              # 계단
    return True
def rand_pt(lo=0.45, hi=0.95):
    a = R() * TAU; r = ISL_R(a, ISLB) * (lo + R() * (hi - lo)); return math.cos(a) * r, math.sin(a) * r
# (덤불은 사용자 요청으로 제거)
# (바닥 풀은 사용자 요청으로 제거, 꽃은 유지)
# (꽃은 사용자 요청으로 제거)
n = tries = 0
while n < 14 and tries < 2000:
    tries += 1; t = TREES[int(R() * len(TREES))]; a = R() * TAU; x, z = t[0] + math.cos(a) * 0.9 * t[3], t[2] + math.sin(a) * 0.9 * t[3]
    if not clear(x, z): continue
    y = H(x, z); s = 0.7 + R() * 0.6
    lathe('lit', (x, y, z), [(0.05 * s, 0), (0.04 * s, 0.18 * s)], 6, [0xf2ead8])
    lathe('lit', (x, y + 0.16 * s, z), [(0.0, 0.0), (0.16 * s, 0.0), (0.12 * s, 0.07 * s), (0, 0.12 * s)], 8, [0xf2ead8, 0xd8433a, 0xe0544a], j=0.05); n += 1
n = tries = 0
while n < 34 and tries < 3000:
    tries += 1; x, z = rand_pt(0.3, 0.96)
    if not clear(x, z) or path_d(x, z) < 0.75 or pond_d(x, z) < 0.6 or math.hypot(x - DOCK_X, z - DOCK_Z) < 1.6: continue
    s = 0.12 + R() * 0.22
    if path_d(x, z) < 0.55 + 1.25 * s: continue                    # 디딤돌(중심선에서 최대 0.5)과 바위 크기까지 띄움
    if any(math.hypot(x - lx, z - lz) < 0.45 + 1.2 * s for (lx, lz) in LAMP_POS): continue   # 랜턴 기둥 밑동과 붙지 않게
    ROCKS.append((x, z, 1.2 * s))
    ico('lit', x, H(x, z) + s * 0.25, z, s, mixc(hexc(0x9f98b4), hexc(0x7d7696), R()), 1, 0.35 * s, 1.2, 0.75, 1, R() * TAU, 0.1); n += 1

# ---------- 성 앞 언덕: 풀 덤불·꽃 (사용자 요청, 전용 난수 FR 로 다른 배치 유지) ----------
FR = random.Random(3131)
FLOWER_PTS = []
def front_ok(x, z, pad):
    if H(x, z) < PLY - 0.04 or plat_k(x, z) < 0.97: return False            # 평평한 언덕 위, 가장자리 제외
    if abs(x - PL[0]) < 0.75: return False                                   # 성문~계단 가운데 길은 비움
    if z < CO[2] + 1.75 or z > zEdge - 0.75: return False                    # 성 받침 앞 ~ 계단 맨 위 사이만
    if any(math.hypot(x - fx, z - fz) < 0.35 + pad for (fx, fz) in FENCE_POSTS): return False
    if any(math.hypot(x - qx, z - qz) < qr + pad for (qx, qz, qr) in FLOWER_PTS): return False
    return True
FLC = [0xfff4f0, 0xffd84a, 0xff8fb8, 0xb98cff, 0xff7a6a]
tries = 0
while sum(1 for q in FLOWER_PTS if q[2] < 0.2) < 26 and tries < 4000:      # 꽃
    tries += 1
    x, z = PL[0] + FR.uniform(-3.4, 3.4), FR.uniform(CO[2] + 1.75, zEdge - 0.75)
    if not front_ok(x, z, 0.05): continue
    y = H(x, z); s_ = FR.uniform(0.8, 1.15); hgt = 0.2 * s_
    lathe('lit', (x, y, z), [(0.018, 0), (0.014, hgt)], 4, [0x4f9a38])
    col = FLC[int(FR.random() * len(FLC))]
    for k in range(5):
        a_ = k / 5 * TAU + FR.random()
        ico('lit', x + math.cos(a_) * 0.055 * s_, y + hgt, z + math.sin(a_) * 0.055 * s_, 0.045 * s_, col, 1, 0.0, sy=0.45, j=0.04)
    ico('lit', x, y + hgt + 0.01, z, 0.035 * s_, 0xffc93a if col != 0xffd84a else 0xff9a2a, 1, 0.0, sy=0.6, j=0.03)
    FLOWER_PTS.append((x, z, 0.12))
tries = n_ = 0
while n_ < 22 and tries < 4000:                                             # 풀 덤불
    tries += 1
    x, z = PL[0] + FR.uniform(-3.6, 3.6), FR.uniform(CO[2] + 1.75, zEdge - 0.7)
    if not front_ok(x, z, 0.08): continue
    y = H(x, z); s_ = FR.uniform(0.8, 1.3)
    for k in range(7):
        a_ = FR.random() * TAU; r_ = FR.uniform(0, 0.09) * s_; hb = FR.uniform(0.18, 0.32) * s_
        tx, tz = math.cos(a_) * 0.05, math.sin(a_) * 0.05
        tri_prism('lit', [[(x + math.cos(a_) * r_ - tz, y, z + math.sin(a_) * r_ + tx), (x + math.cos(a_) * r_ + tz, y, z + math.sin(a_) * r_ - tx),
                           (x + math.cos(a_) * (r_ + 0.06), y + hb, z + math.sin(a_) * (r_ + 0.06))]], mixc(hexc(0x4f9e3c), hexc(0x7cc64e), FR.random()), j=0.06, c=(x, y - 1, z))
    FLOWER_PTS.append((x, z, 0.2)); n_ += 1
print('성 앞 꽃·풀', len(FLOWER_PTS))
# ---------- 아래 섬 땅: 꽃·풀 적당히 (사용자 요청) ----------
GR = random.Random(4242)
def low_ok(x, z, pad):
    if not clear(x, z, 0.2): return False                                   # 가장자리·캠프·돔·연못·성 언덕·계단 제외
    if math.hypot(x - OAK_C[0], z - OAK_C[1]) < 1.6: return False
    if abs(x - PL[0]) < 1.6 + pad and z < STAIR_END + 0.5: return False      # 계단·양옆 벽 둘레 비움
    if path_d(x, z) < 0.75 or pond_d(x, z) < 0.7: return False
    if any(math.hypot(x - t[0], z - t[2]) < 0.55 * t[3] + pad for t in TREES): return False
    if any(math.hypot(x - rx, z - rz) < rr + 0.15 + pad for (rx, rz, rr) in ROCKS): return False
    if any(math.hypot(x - lx, z - lz) < 0.45 + pad for (lx, lz) in LAMP_POS): return False
    if any(math.hypot(x - qx, z - qz) < qr + pad for (qx, qz, qr) in FLOWER_PTS): return False
    return True
def plant_flower(x, z, R_):
    y = H(x, z); s_ = R_.uniform(0.85, 1.2); hgt = 0.2 * s_
    lathe('lit', (x, y, z), [(0.018, 0), (0.014, hgt)], 4, [0x4f9a38])
    col = FLC[int(R_.random() * len(FLC))]
    for k in range(5):
        a_ = k / 5 * TAU + R_.random()
        ico('lit', x + math.cos(a_) * 0.055 * s_, y + hgt, z + math.sin(a_) * 0.055 * s_, 0.045 * s_, col, 1, 0.0, sy=0.45, j=0.04)
    ico('lit', x, y + hgt + 0.01, z, 0.035 * s_, 0xffc93a if col != 0xffd84a else 0xff9a2a, 1, 0.0, sy=0.6, j=0.03)
def plant_grass(x, z, R_):
    y = H(x, z); s_ = R_.uniform(0.8, 1.3)
    for k in range(7):
        a_ = R_.random() * TAU; r_ = R_.uniform(0, 0.09) * s_; hb = R_.uniform(0.18, 0.32) * s_
        tx, tz = math.cos(a_) * 0.05, math.sin(a_) * 0.05
        tri_prism('lit', [[(x + math.cos(a_) * r_ - tz, y, z + math.sin(a_) * r_ + tx), (x + math.cos(a_) * r_ + tz, y, z + math.sin(a_) * r_ - tx),
                           (x + math.cos(a_) * (r_ + 0.06), y + hb, z + math.sin(a_) * (r_ + 0.06))]], mixc(hexc(0x4f9e3c), hexc(0x7cc64e), R_.random()), j=0.06, c=(x, y - 1, z))
n0 = len(FLOWER_PTS); nf = ng = tries = 0
while (nf < 30 or ng < 25) and tries < 8000:
    tries += 1
    x, z = rand_pt(0.15, 0.93) if False else (lambda a_, r_: (math.cos(a_) * r_, math.sin(a_) * r_))(GR.random() * TAU, ISL_R(0) * 0 + GR.uniform(1.0, 10.5))
    if nf < 30 and (ng >= 25 or GR.random() < 0.55):
        if not low_ok(x, z, 0.05): continue
        # 꽃은 2~3송이씩 작은 무리로
        for k in range(GR.choice((1, 2, 3))):
            fx, fz = x + GR.uniform(-0.22, 0.22), z + GR.uniform(-0.22, 0.22)
            if k and not low_ok(fx, fz, 0.0): continue
            if not k: fx, fz = x, z
            plant_flower(fx, fz, GR); FLOWER_PTS.append((fx, fz, 0.12)); nf += 1
    elif ng < 25:
        if not low_ok(x, z, 0.08): continue
        plant_grass(x, z, GR); FLOWER_PTS.append((x, z, 0.2)); ng += 1
print('아래 땅 꽃', nf, '풀', ng)
BM.pop('trash', None)
# ---------- 자동 겹침 검사 (경고만 출력) ----------
def _in_rect(x, z, cx, cz, hw, hd, pad=0.0): return abs(x - cx) < hw + pad and abs(z - cz) < hd + pad
WARN = []
if os.environ.get('CHECK_SELFTEST'): FENCE_POSTS.append((PL[0] + 1.0, zEdge)); CAMP_FP.append((CAMP[0] + 2.0, CAMP[2] + 0.75, 0.7, '시험텐트'))
STAIR_RECT = (PL[0], (zEdge - 0.65 + STAIR_END) / 2, 1.2, (STAIR_END - zEdge + 0.65) / 2)
for (x, z) in FENCE_POSTS:
    if _in_rect(x, z, *STAIR_RECT, 0.1): WARN.append('울타리 기둥이 계단과 겹침 %.2f,%.2f' % (x, z))
for (x, z, r) in PATH_STONES:
    lx = (x - DOME_C[0]) * math.cos(DR) - (z - DOME_C[1]) * math.sin(DR); lz = (x - DOME_C[0]) * math.sin(DR) + (z - DOME_C[1]) * math.cos(DR)
    if math.hypot(lx, lz) < DR0 + 0.25 + r: WARN.append('디딤돌이 돔과 겹침 %.2f,%.2f' % (x, z))
    if math.hypot(x - CO[0], z - CO[2]) < 2.6: WARN.append('디딤돌이 성과 겹침 %.2f,%.2f' % (x, z))
for (x, z, r) in ROCKS:
    for (x2, z2, r2) in PATH_STONES:
        if math.hypot(x - x2, z - z2) < r + r2: WARN.append('바위가 디딤돌과 겹침 %.2f,%.2f' % (x, z)); break
    if _in_rect(x, z, *STAIR_RECT, r): WARN.append('바위가 계단과 겹침 %.2f,%.2f' % (x, z))
    for (lx, lz) in LAMP_POS:
        if math.hypot(x - lx, z - lz) < r + 0.3: WARN.append('바위가 랜턴과 겹침 %.2f,%.2f' % (x, z))
CAMP_FP.append((OAK_C[0], OAK_C[1], 0.7, '활엽수'))
for (x, z, r) in FLOWER_PTS:
    if _in_rect(x, z, *STAIR_RECT, r): WARN.append('꽃·풀이 계단과 겹침 %.2f,%.2f' % (x, z))
    if any(math.hypot(x - fx, z - fz) < r + 0.05 for (fx, fz) in FENCE_POSTS): WARN.append('꽃·풀이 울타리와 겹침 %.2f,%.2f' % (x, z))
for (x, z) in LAMP_POS:
    for (x2, z2, r2, nm2) in CAMP_FP:
        if math.hypot(x - x2, z - z2) < r2 + 0.3: WARN.append('랜턴이 %s 와 겹침' % nm2)
    if path_d(x, z) < 0.45: WARN.append('랜턴이 돌길 위에 있음 %.2f,%.2f' % (x, z))
for (x, z, r, nm) in CAMP_FP:
    for (x2, z2, r2, nm2) in CAMP_FP:
        if nm < nm2 and nm.rstrip('0123456789') != nm2.rstrip('0123456789') and math.hypot(x - x2, z - z2) < r + r2: WARN.append('%s 와 %s 겹침' % (nm, nm2))   # 같은 종류끼리 쌓은 무더기는 제외
if os.environ.get('PV_T'): print('랜턴-소품 거리', [(nm, round(min(math.hypot(x - ox, z - oz) for (x, z) in LAMP_POS), 2)) for (ox, oz, r, nm) in CAMP_FP])
if os.environ.get('PV_T'): print('울타리 첫 기둥', [(round(x,2), round(z,2)) for (x,z) in FENCE_POSTS if abs(x-PL[0])<2.2])
print('겹침 검사:', '이상 없음' if not WARN else '')
for w in WARN: print('  겹침 경고 -', w)
# ---------- 탐험 모드용 이동 격자: 칸마다 땅 높이 + 갈 수 있는지 ----------
import base64 as _b64
WG_N, WG_X0, WG_S = 121, -12.0, 0.2
def stair_zone(x, z): return abs(x - PL[0]) < 0.72 and zEdge - 0.62 < z < STAIR_END - 0.05
def walk_h(x, z):
    if stair_zone(x, z):
        i = max(0, min(5, round((z - (zEdge - 0.35)) / 0.42)))
        return PLY - i * 0.27 + 0.02
    return H(x, z)
def blocked(x, z):
    rd = ISL_R(math.atan2(z, x)) - math.hypot(x, z)
    if rd < 0.6: return True                                                       # 섬 가장자리
    if pond_d(x, z) < 0.1: return True                                             # 호수
    if abs(x - CO[0]) < 2.95 and CO[2] - 1.6 < z < CO[2] + 1.75: return True       # 성
    lx = (x - DOME_C[0]) * math.cos(DR) - (z - DOME_C[1]) * math.sin(DR); lz = (x - DOME_C[0]) * math.sin(DR) + (z - DOME_C[1]) * math.cos(DR)
    if math.hypot(lx, lz) < DR0 + 0.3 or (abs(lx) < EW + 0.2 and DR0 - 0.2 < lz < EZ1 + 0.25): return True   # 돔과 입구
    if math.hypot(x - CAMP[0], z - CAMP[2]) < 0.7: return True                     # 모닥불
    if any(math.hypot(x - t[0], z - t[2]) < 0.6 * t[3] for t in TREES): return True
    if math.hypot(x - OAK_C[0], z - OAK_C[1]) < 0.75: return True
    if any(math.hypot(x - ox, z - oz) < r for (ox, oz, r, nm) in CAMP_FP): return True
    if any(math.hypot(x - lx_, z - lz_) < 0.2 for (lx_, lz_) in LAMP_POS): return True
    # 작은 바위(ROCKS)는 막지 않음 — 캐릭터가 그냥 통과(사용자 요청)
    if any(math.hypot(x - fx, z - fz) < 0.24 for (fx, fz) in FENCE_POSTS): return True
    if abs(abs(x - PL[0]) - 0.96) < 0.24 and zEdge - 0.7 < z < STAIR_END: return True   # 계단 양옆 벽
    return False
WH = [[0.0] * WG_N for _ in range(WG_N)]; WM = [[0] * WG_N for _ in range(WG_N)]
for gi in range(WG_N):
    for gj in range(WG_N):
        x, z = WG_X0 + gi * WG_S, WG_X0 + gj * WG_S
        WH[gi][gj] = walk_h(x, z); WM[gi][gj] = 1 if blocked(x, z) else 0
for gi in range(1, WG_N - 1):                                                     # 가파른 곳(절벽)은 막음, 계단은 제외
    for gj in range(1, WG_N - 1):
        x, z = WG_X0 + gi * WG_S, WG_X0 + gj * WG_S
        if stair_zone(x, z) or WM[gi][gj]: continue
        d = max(abs(WH[gi][gj] - WH[gi + a][gj + b]) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        if d > 0.3: WM[gi][gj] = 1
_hb = np.array([[round(WH[i][j] * 100) for j in range(WG_N)] for i in range(WG_N)], '<i2').tobytes()
_mb = np.array(WM, np.uint8).tobytes()
WALK = {'n': WG_N, 'x0': WG_X0, 's': WG_S, 'h': _b64.b64encode(_hb).decode(), 'm': _b64.b64encode(_mb).decode()}
SPAWN = (PL[0], STAIR_END + 0.9)
print('바위 자리 중 막힌 칸', sum(WM[round((rx - WG_X0) / WG_S)][round((rz - WG_X0) / WG_S)] for (rx, rz, rr) in ROCKS), '/', len(ROCKS))
print('이동 격자 막힌 칸', int(np.sum(np.array(WM))), '/', WG_N * WG_N)

# ---------- 메시로 만들고 AO 굽기 ----------
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
scene = bpy.context.scene
objs = {}
for name, bmx in BM.items():
    me = bpy.data.meshes.new(name); bmx.to_mesh(me); me.update()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); objs[name] = ob
    mat = bpy.data.materials.new(name); me.materials.append(mat)
    print(name, '면', len(me.polygons))
# 미리보기: PREVIEW=출력png 이면 AO 굽기 없이 정점 색 그대로 성 쪽을 렌더하고 끝낸다 (PV_AZ, PV_EL, PV_D 로 시점)
if os.environ.get('PREVIEW'):
    sc = scene; sc.render.engine = 'BLENDER_WORKBENCH'
    sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'VERTEX'; sh.show_shadows = True; sh.show_cavity = True
    for o in objs.values(): o.data.color_attributes.active_color = o.data.color_attributes['base']
    sc.render.resolution_x, sc.render.resolution_y = 1000, 1100
    sc.world.color = (0.01, 0.015, 0.05)
    az, el, dd = float(os.environ.get('PV_AZ', 0)), float(os.environ.get('PV_EL', 0.42)), float(os.environ.get('PV_D', 17))
    PVT = {'dome': (DOME[0], DOME[1] + 1.4, DOME[2]), 'camp': (CAMP[0] + 0.6, CAMP[1] + 0.6, CAMP[2] - 0.4), 'stairs': (PL[0], PLY - 0.6, zEdge + 0.6),
           'boat': (POND[0], H(*POND) if False else PLY - 1.6, POND[1])}
    tg = Vector(PVT[os.environ['PV_T']]) if os.environ.get('PV_T') in PVT else Vector((CO[0], CO[1] + 3.2, CO[2]))
    if os.environ.get('PV_XYZ'): tg = Vector([float(v) for v in os.environ['PV_XYZ'].split(',')])
    PVT['stairtop'] = (PL[0], PLY, zEdge - 0.4)
    if os.environ.get('PV_T') == 'stairtop': tg = Vector(PVT['stairtop'])
    cd = bpy.data.cameras.new('cam'); cd.lens = 50; cam = bpy.data.objects.new('cam', cd); sc.collection.objects.link(cam)
    cam.location = tg + Vector((math.sin(az) * math.cos(el), math.sin(el), math.cos(az) * math.cos(el))) * dd
    # Y-up 장면이라 카메라 위쪽을 +Y 로 맞춘다
    fwd = (tg - cam.location).normalized(); rt = fwd.cross(Vector((0, 1, 0))).normalized(); up = rt.cross(fwd)
    cam.matrix_world = Matrix((( rt.x, up.x, -fwd.x, cam.location.x), (rt.y, up.y, -fwd.y, cam.location.y), (rt.z, up.z, -fwd.z, cam.location.z), (0, 0, 0, 1)))
    sc.camera = cam; sc.render.filepath = os.environ['PREVIEW']
    bpy.ops.render.render(write_still=True); print('미리보기 저장', os.environ['PREVIEW']); sys.exit(0)
if scene.world is None: scene.world = bpy.data.worlds.new('W')
scene.world.light_settings.distance = 1.3
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 48
scene.render.bake.target = 'VERTEX_COLORS'
for name in ('lit', 'ground', 'boat', 'tree'):
    me = objs[name].data
    ao = me.color_attributes.new('ao', 'FLOAT_COLOR', 'CORNER')
    me.color_attributes.active_color = ao
for o in scene.objects: o.select_set(False)
for name in ('lit', 'ground', 'boat', 'tree'): objs[name].select_set(True)
bpy.context.view_layer.objects.active = objs['lit']
if 'stone' in objs: objs['stone'].hide_render = True       # 디딤돌은 그늘 굽기에서 빼서 땅에 세모난 얼룩이 생기지 않게
import time; t0 = time.time()
bpy.ops.object.bake(type='AO')
print('AO 굽기(초)', round(time.time() - t0, 1))

# ---------- 내보내기 ----------
def lin2s(v):
    v = np.clip(v, 0, 1); return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)
blob = bytearray(); meta = {'groups': {}}
for name, ob in objs.items():
    me = ob.data
    try: me.calc_loop_triangles()
    except Exception: pass
    nt = len(me.loop_triangles)
    tl = np.zeros(nt * 3, np.int32); me.loop_triangles.foreach_get('loops', tl)
    lv = np.zeros(len(me.loops), np.int32); me.loops.foreach_get('vertex_index', lv)
    co = np.zeros(len(me.vertices) * 3, np.float32); me.vertices.foreach_get('co', co); co = co.reshape(-1, 3)
    base = np.zeros(len(me.loops) * 4, np.float32); me.color_attributes['base'].data.foreach_get('color', base); base = base.reshape(-1, 4)[:, :3]
    if 'ao' in me.color_attributes:
        ao = np.zeros(len(me.loops) * 4, np.float32); me.color_attributes['ao'].data.foreach_get('color', ao); ao = ao.reshape(-1, 4)[:, 0]
        print(name, 'AO 최소·평균·최대', float(ao.min()), float(ao.mean()), float(ao.max()))
        k = 0.3 + 0.7 * np.clip(ao, 0, 1) ** 1.1
        if name == 'ground':                                   # 풀바닥 AO 도 꼭짓점별 평균(모서리마다 다르면 세모가 다시 보임)
            _cv = co[lv]; _rr = np.hypot(_cv[:, 0], _cv[:, 2])
            _fall = (_cv[:, 2] > 0) & (np.abs(_cv[:, 0] - WFX) < 2.6) & (_cv[:, 1] < -0.1) & (_rr > ISLR * 0.62)
            k = np.where(_fall, 1.0, k)                        # 폭포 홈 바닥은 그늘 없이(물빛 유지)
            nv = len(me.vertices); sm = np.bincount(lv, weights=k, minlength=nv); ct = np.bincount(lv, minlength=nv)
            k = (sm / np.maximum(ct, 1))[lv]
    else:
        k = np.ones(len(me.loops), np.float32)
    P = co[lv[tl]]
    if name == 'boat': P = P - np.array(BOAT_O, np.float32)
    Cc = base[tl] * k[tl][:, None]
    mn, mx = P.min(0), P.max(0); span = np.maximum(mx - mn, 1e-6)
    q = np.round((P - mn) / span * 65535).astype('<u2')
    c8 = np.round(lin2s(Cc) * 255).astype(np.uint8)
    off = len(blob); blob += q.tobytes(); coff = len(blob); blob += c8.tobytes()
    while len(blob) % 4: blob += b'\0'
    meta['groups'][name] = {'n': int(len(P)), 'pos': off, 'col': coff, 'min': mn.tolist(), 'max': mx.tolist()}
    print(name, '삼각형', nt)
r6 = lambda L: [[round(v, 3) for v in p] for p in L]
meta.update({'walk': WALK, 'spawn': [round(SPAWN[0], 3), round(SPAWN[1], 3)], 'trees': [[round(t[0], 2), round(t[1], 2), round(t[2], 2), round(t[3], 2)] for t in TREES] + [[OAK[0], OAK[1], OAK[2], 1.6]], 'flags': r6(FLAGS), 'bulbs': r6(BULBS), 'oakBulbs': r6(OAK_BULBS), 'domeStars': r6(DOME_STARS), 'lanterns': r6(LANTERNS),
             'camp': [round(v, 3) for v in CAMP], 'dome': [round(v, 3) for v in DOME], 'castle': [round(v, 3) for v in CO],
             'rimZ': rimZ, 'wfx': WFX, 'isl': ISLR, 'domeRot': DR, 'pond': [POND[0], POND[1], PONDB, PONDS], 'ply': PLY, 'zEdge': zEdge})
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'island1.bin'), 'wb').write(bytes(blob))
json.dump(meta, open(os.path.join(OUT, 'island1.json'), 'w'))
print('완료', len(blob), '바이트')
