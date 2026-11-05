# 샘플 1-1: 가운데 섬 로우폴리 모델을 Blender 로 만들고 AO 를 정점 색에 구워 이진 파일로 내보낸다.
# 사용: blender -b --factory-startup --python build_island11.py -- <출력폴더>
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
OAK_C = (8.2, 0.0)                                           # 둥근 활엽수
PONDB, PONDS = 2.4, 3.3
WFX = 0.8
rimZ = ISL_R(PI / 2)
POND = (0.7, rimZ - blobR(PI / 2, PONDB, PONDS) + 0.3)   # 연못 앞끝이 섬 가장자리에 걸쳐서 물이 바로 폭포로 떨어짐(물길 없음)

def plat_r(a): return blobR(a, PLB, PLS) + 0.18 * nz(math.cos(a) * 2, math.sin(a) * 2, 3.3)
def plat_k(x, z):
    dx, dz = x - PL[0], z - PL[1]; a = math.atan2(dz, dx); r = plat_r(a)
    return smooth(r + 0.2, r - 0.3, math.hypot(dx, dz))
def pond_r(a):
    f = blobR(a, 1.0, PONDS) - 1; n = math.atan2(math.sin(a + PI / 2), math.cos(a + PI / 2))
    return PONDB * (1 + f * (1 - 0.85 * math.exp(-(n / 0.9) ** 2)))          # 북쪽(성 쪽)은 울퉁불퉁함을 줄여 둥글게
def pond_d(x, z):
    dx, dz = x - POND[0], z - POND[1]; return math.hypot(dx, dz) - pond_r(math.atan2(dz, dx))
def chan_k(x, z): return 0.0                                  # 연못과 폭포 사이 물길은 사용자 요청으로 없앰
def stair_h(z): return min(PLY, max(0.0, PLY - (z - (zEdge - 0.45)) * (0.27 / 0.42)))   # 계단 경사선
def H(x, z):
    base = PLY * plat_k(x, z) + 0.07 * nz(x * 0.45, z * 0.45, 1.7)
    w = smooth(1.3, 0.98, abs(x - PL[0]))                     # 계단 폭 안쪽은 언덕을 계단 경사로 파냄
    if w > 0 and zEdge - 1.2 < z < STAIR_END + 0.2:
        base = base * (1 - w) + min(base, stair_h(z) - 0.04) * w
    pd = pond_d(x, z)
    wet = max(smooth(0.5, -0.3, pd), chan_k(x, z))
    hh = base * (1 - wet) - 0.36 * wet
    rd = ISL_R(math.atan2(z, x)) - math.hypot(x, z)
    if wet > 0:                                               # 폭포로 넘치는 가장자리: 수면 바로 아래 높이로 올려 턱을 없앰
        hh = max(hh, -0.1 - 0.26 * smooth(0.1, 0.9, rd))
    wn = smooth(1.85, 1.35, abs(x - WFX)) if z > 0 else 0.0   # 폭포 자리: 가장자리로 갈수록 홈처럼 깎아 내림
    if wn > 0 and rd < 0.7:
        hh = hh * (1 - wn) + min(hh, notch_h(rd)) * wn
    return hh
def notch_h(rd): return -0.1 - 0.22 * smooth(0.6, 0.0, rd)     # 페이지의 폭포 물줄기도 같은 식을 씀

zEdge = PL[1] + plat_r(PI / 2)
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
zz = zEdge - 1.2                                         # 계단 홈 양옆 경계를 또렷하게
while zz < STAIR_END + 0.3:
    for xo in (-1.3, -1.0, 1.0, 1.3): pts.append((PL[0] + xo, zz))
    zz += 0.2
res = delaunay_2d_cdt([Vector(p) for p in pts], [], [], 0, 1e-5)
vco, tris = res[0], res[2]
bm = grp('lit'); lay = bm.loops.layers.float_color['base']
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
    if h < -0.14: c = UNDER
    elif pd < 0.55 or chan_k(cx, cz) > 0.2: c = SAND
    elif ny < 0.8: c = mixc(ROCK, MOSS, R() * 0.4)
    else:
        g = mixc(GRASS_A, GRASS_B, 0.5 + 0.5 * nz(cx * 0.35, cz * 0.35, 5.1))
        if plat_k(cx, cz) > 0.9: g = mixc(g, GRASS_T, 0.5)
        pdd = path_d(cx, cz)
        c = mixc(g, DIRT, smooth(0.65, 0.3, pdd) * 0.8)
    c = jit(c, 0.07)
    for l in f.loops: l[lay] = (c[0], c[1], c[2], 1.0)

# ---------- 절벽 ----------
RINGS = [(0.0, 0.00, 0.0, 'top'), (-0.12, 0.10, 0.02, 'top'), (-0.5, -0.02, 0.05, 'lip'),
         (-1.4, 0.00, 0.30, 'r'), (-1.6, -0.35, 0.18, 'r'), (-2.9, -0.30, 0.32, 'r'), (-3.1, -0.70, 0.18, 'r'),
         (-4.4, -0.75, 0.35, 'r'), (-4.6, -1.20, 0.18, 'r'), (-5.8, -1.30, 0.35, 'r'), (-6.0, -1.80, 0.2, 'r'),
         (-7.2, -2.00, 0.30, 'r'), (-8.3, -2.60, 0.0, 'r')]
def cliff_r(a, k):
    _, ins, jt, _ = RINGS[k]
    if k >= 3:                                               # 아래로 갈수록 안쪽으로 둥글게 말려 들어감(그릇 모양) + 층진 턱
        r = ISL_R(a) - ISLR * 0.45 * (1 - math.cos(-RINGS[k][0] / 8.3 * PI / 2))
    else:
        r = ISL_R(a) + ins
    if k >= 3: r += (0.18 if k < 7 else 0.08) * nz(math.cos(a) * 1.8, math.sin(a) * 1.8, k * 0.37)
    x, z = math.cos(a) * r, math.sin(a) * r
    if k >= 1 and z > 0 and abs(x - WFX) < 2.25: r -= (0.65 if k >= 2 else 0.3) * smooth(2.25, 1.25, abs(x - WFX))   # 폭포 뒤는 안으로(잔디 테두리가 물 앞으로 나오지 않게)
    return r
crow = []
for k, (dy, ins, jt, kind) in enumerate(RINGS):
    row = []
    for i in range(S):
        a = i / S * TAU
        if k == 0:
            x, z = bnd[i]; y = H(x, z)
        else:
            r = cliff_r(a, k) + (R() - .5) * jt * (0.6 if k < 6 else 0.25)     # 성 언덕 벽처럼 매끈하게
            ytop = H(*bnd[i])
            y = (ytop + dy) if k < 3 else dy + (R() - .5) * jt * 0.4
            x, z = math.cos(a) * r, math.sin(a) * r
        row.append(bm.verts.new((x, y, z)))
    crow.append(row)
RTOP, RBOT = hexc(0x8a80aa), hexc(0x3b3560)
for k in range(len(RINGS) - 1):
    for i in range(S):
        j = (i + 1) % S
        f = bm.faces.new((crow[k][i], crow[k][j], crow[k + 1][j], crow[k + 1][i]))
        f.normal_update(); a = (i + .5) / S * TAU
        if f.normal.dot(Vector((math.cos(a), 0, math.sin(a)))) < 0: f.normal_flip()
        kind = RINGS[k][3]
        fc = f.calc_center_median()
        if kind in ('top', 'lip') and fc.z > 0 and abs(fc.x - WFX) < 1.95: c = mixc(hexc(0x4f5f86), ROCK, R() * 0.3)   # 폭포 시작부: 젖은 바위색
        elif kind == 'top': c = mixc(GRASS_A, hexc(0x4f9a38), R() * 0.4)
        elif kind == 'lip': c = mixc(ROCK, MOSS, 0.25 + R() * 0.2)
        else:
            t = (k - 3) / (len(RINGS) - 4)
            c = mixc(mixc(ROCK, hexc(0x5d5784), min(1, t) * 0.85), MOSS, R() * 0.12)   # 성 언덕 벽과 같은 돌색
        c = jit(c, 0.06)
        for l in f.loops: l[lay] = (c[0], c[1], c[2], 1.0)

# 절벽에 붙은 큰 바위, 바다에 잠긴 바위
def on_cliff(a, y):
    for k in range(3, len(RINGS) - 1):
        if RINGS[k][0] >= y >= RINGS[k + 1][0]:
            t = (RINGS[k][0] - y) / (RINGS[k][0] - RINGS[k + 1][0])
            return cliff_r(a, k) * (1 - t) + cliff_r(a, k + 1) * t
    return cliff_r(a, len(RINGS) - 1)
# (절벽에 붙은 큰 바위·바다 바위는 사용자 요청으로 제거)
# 바닥 덮개: 맨 아래 고리를 가운데 한 점으로 모아 둥근 그릇 바닥으로 막음
cb = bm.verts.new((0.0, RINGS[-1][0] - 1.2, 0.0))
for i in range(S):
    j = (i + 1) % S
    f = bm.faces.new((crow[-1][i], crow[-1][j], cb)); f.normal_update()
    if f.normal.y > 0: f.normal_flip()
    c = jit(hexc(0x5d5784), 0.06)
    for l in f.loops: l[lay] = (c[0], c[1], c[2], 1.0)

# ---------- 성 ----------
CO = (PL[0], PLY, PL[1] - 0.6)
WALL, WALL2, TRIM, STONE, ROOF1, ROOF2, ROOFT, WIN = 0xeedcb6, 0xe2cba3, 0xe0b850, 0xb7a98f, 0x2d62cc, 0x3a78e0, 0x6fa8ff, 0xffd27a
FLAGS = []
def cpos(x, y, z): return (CO[0] + x, CO[1] + y, CO[2] + z)
def flagpole(x, y, z):
    lathe('lit', (x, y, z), [(0.03, 0), (0.025, 0.72)], 5, [TRIM]); FLAGS.append([x, y + 0.7, z])
def window(x, y, z, a, w, h):
    yaw = PI / 2 - a
    box('lit', x - math.cos(a) * 0.015, y, z - math.sin(a) * 0.015, w + 0.08, h + 0.08, 0.06, TRIM, yaw)
    box('emit', x + math.cos(a) * 0.02, y, z + math.sin(a) * 0.02, w, h, 0.06, WIN, yaw, j=0.02)
def tower(x, z, r, h, rh, win, hasflag, roof=ROOF1):
    c = cpos(x, 0, z); seg = 12
    lathe('lit', c, [(r * 1.16, -0.45), (r * 1.13, 0.22), (r * 1.0, 0.32), (r * 1.0, h - 0.06), (r * 1.2, h + 0.04), (r * 1.22, h + 0.2), (r * 1.06, h + 0.2)],
          seg, [STONE, STONE, WALL, TRIM, TRIM, TRIM], capt=True)
    y0 = c[1] + h + 0.18
    lathe('lit', (c[0], y0, c[2]), [(r * 1.34, 0), (r * 1.08, rh * 0.22), (r * 0.48, rh * 0.62), (0, rh)], seg,
          lambda k, i: [ROOF1 if roof == ROOF1 else ROOF2, roof, ROOFT if k == 2 else roof][min(k, 2)], capb=True)
    lathe('lit', (c[0], y0 + rh - 0.05, c[2]), [(0.0, 0), (r * 0.14, 0.06), (r * 0.14, 0.14), (0, 0.22)], 6, [TRIM])
    for kk in range(win):
        for a in (PI / 2, PI / 2 + PI * 2 / 3, PI / 2 - PI * 2 / 3):
            yy = c[1] + h * (0.42 + kk * 0.24)
            window(c[0] + math.cos(a) * r, yy, c[2] + math.sin(a) * r, a, r * 0.3, r * 0.5)
    if hasflag: flagpole(c[0], y0 + rh + 0.1, c[2])
# 본관
k0 = cpos(0, 0, 0.1)
box('lit', k0[0], k0[1] - 0.05, k0[2], 3.9, 0.5, 2.3, STONE, bevel=0.05)
box('lit', k0[0], k0[1] + 1.0, k0[2], 3.6, 2.0, 2.0, WALL, bevel=0.04)
box('lit', k0[0], k0[1] + 2.02, k0[2], 3.78, 0.16, 2.16, TRIM, bevel=0.03)
gx0, gy0 = 1.95, k0[1] + 2.1
tri_prism('lit', [[(k0[0] - gx0, gy0, k0[2] + 1.15), (k0[0] + gx0, gy0, k0[2] + 1.15), (k0[0] + gx0, gy0 + 1.15, k0[2]), (k0[0] - gx0, gy0 + 1.15, k0[2])],
                  [(k0[0] + gx0, gy0, k0[2] - 1.15), (k0[0] - gx0, gy0, k0[2] - 1.15), (k0[0] - gx0, gy0 + 1.15, k0[2]), (k0[0] + gx0, gy0 + 1.15, k0[2])]], ROOF2)
tri_prism('lit', [[(k0[0] - gx0 + 0.05, gy0, k0[2] - 1.1), (k0[0] - gx0 + 0.05, gy0, k0[2] + 1.1), (k0[0] - gx0 + 0.05, gy0 + 1.1, k0[2])],
                  [(k0[0] + gx0 - 0.05, gy0, k0[2] + 1.1), (k0[0] + gx0 - 0.05, gy0, k0[2] - 1.1), (k0[0] + gx0 - 0.05, gy0 + 1.1, k0[2])]], WALL2)
for dx in (-1.0, 1.0):                                  # 지붕창
    bx, bz = k0[0] + dx, k0[2] + 0.62
    box('lit', bx, gy0 + 0.5, bz, 0.5, 0.55, 0.5, WALL)
    tri_prism('lit', [[(bx - 0.3, gy0 + 0.77, bz + 0.27), (bx + 0.3, gy0 + 0.77, bz + 0.27), (bx, gy0 + 1.08, bz + 0.27)],
                      [(bx + 0.3, gy0 + 0.77, bz + 0.27), (bx + 0.3, gy0 + 0.77, bz - 0.2), (bx, gy0 + 1.08, bz - 0.2), (bx, gy0 + 1.08, bz + 0.27)],
                      [(bx - 0.3, gy0 + 0.77, bz - 0.2), (bx - 0.3, gy0 + 0.77, bz + 0.27), (bx, gy0 + 1.08, bz + 0.27), (bx, gy0 + 1.08, bz - 0.2)]], ROOF1)
    window(bx, gy0 + 0.5, bz + 0.25, PI / 2, 0.2, 0.3)
box('lit', k0[0], k0[1] + 0.74, k0[2] + 1.04, 1.2, 1.5, 0.14, TRIM, bevel=0.03)
box('emit', k0[0], k0[1] + 0.55, k0[2] + 1.12, 0.86, 1.06, 0.06, 0xffc35a, j=0.01)
lathe('emit', (k0[0], k0[1] + 1.07, k0[2] + 1.12), [(0.0, -0.03), (0.43, -0.03), (0.43, 0.03), (0, 0.03)], 12, [0xffc35a], j=0.01)
for x in (-1.25, -0.65, 0.65, 1.25):
    window(k0[0] + x, k0[1] + 1.4, k0[2] + 1.0, PI / 2, 0.22, 0.38)
    window(k0[0] + x, k0[1] + 1.4, k0[2] - 1.0, -PI / 2, 0.22, 0.38)
# 성벽(앞 탑 ↔ 뒤 탑)과 총안
for sx in (-1, 1):
    ax, az, bx2, bz2 = cpos(sx * 2.2, 0, 0.9)[0], cpos(0, 0, 0.9)[2], cpos(sx * 1.8, 0, -0.95)[0], cpos(0, 0, -0.95)[2]
    L = math.hypot(bx2 - ax, bz2 - az); yaw = math.atan2(bx2 - ax, bz2 - az)
    mx, mz = (ax + bx2) / 2, (az + bz2) / 2
    box('lit', mx, CO[1] + 0.7, mz, 0.4, 1.6, L, WALL2, yaw, bevel=0.03)
    for t in range(4):
        u = (t + 0.5) / 4
        box('lit', ax + (bx2 - ax) * u, CO[1] + 1.62, az + (bz2 - az) * u, 0.44, 0.26, 0.22, WALL2, yaw)
# 탑들
tower(0, -0.5, 0.78, 4.7, 2.5, 3, True)
tower(-1.3, 0.15, 0.5, 3.4, 1.75, 2, True, ROOF2)
tower(1.3, 0.15, 0.5, 3.4, 1.75, 2, True, ROOF2)
tower(-2.2, 0.9, 0.46, 2.3, 1.35, 1, False)
tower(2.2, 0.9, 0.46, 2.3, 1.35, 1, False)
tower(-1.8, -0.95, 0.42, 2.9, 1.5, 1, False, ROOF2)
tower(1.8, -0.95, 0.42, 2.9, 1.5, 1, False, ROOF2)
tower(-0.75, -1.25, 0.32, 3.7, 1.2, 1, False)
tower(0.75, -1.25, 0.32, 3.7, 1.2, 1, False)

# ---------- 돌계단 ----------
for i in range(6):
    top = PLY - i * 0.27 + 0.02; Hh = top + 0.35
    box('lit', PL[0], top - Hh / 2, zEdge - 0.35 + i * 0.42, 1.5, Hh, 0.5, 0xc9b897 if i % 2 else 0xb8a888, bevel=0.04)
for sx in (-0.86, 0.86):                                   # 계단 양옆 난간 벽: 단마다 한 칸씩 계단 모양으로 내려감
    for i in range(6):
        top = PLY - i * 0.27 + 0.2; Hh = top + 0.35
        box('lit', PL[0] + sx, top - Hh / 2, zEdge - 0.35 + i * 0.42, 0.22, Hh, 0.44, 0xa89c86, bevel=0.03)
        box('lit', PL[0] + sx, top + 0.02, zEdge - 0.35 + i * 0.42, 0.28, 0.06, 0.46, 0xd8ccb2, j=0.03)
    zb = zEdge - 0.35 + 5 * 0.42 + 0.3                        # 맨 아래 기둥
    box('lit', PL[0] + sx, H(PL[0] + sx, zb) + 0.3, zb, 0.3, 0.6, 0.3, 0xa89c86, bevel=0.03)
    box('lit', PL[0] + sx, H(PL[0] + sx, zb) + 0.63, zb, 0.36, 0.08, 0.36, 0xd8ccb2, j=0.03)

# ---------- 울타리 (언덕 앞 가장자리) ----------
def fence(points, y=None):
    WOOD = 0x9a6b3e
    for i, (x, z) in enumerate(points):
        yy = H(x, z) if y is None else y
        box('lit', x, yy + 0.28, z, 0.09, 0.62, 0.09, WOOD, R() * 0.3)
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
    fence(ptsF, PLY)

# ---------- 돔 천문대 ----------
DOME = (DOME_C[0], H(*DOME_C), DOME_C[1])
LAV, LAVD, PALE = 0xcbc5f0, 0x7f79cc, 0xeeeaff
lathe('lit', DOME, [(1.9, -0.2), (1.85, 0.1), (1.72, 0.95), (1.84, 0.95), (1.84, 1.1), (1.7, 1.1)], 22, [STONE, LAV, PALE, PALE, PALE], capt=False)
prof = [(1.7 * math.cos(t / 9 * PI / 2), 1.0 + 1.7 * math.sin(t / 9 * PI / 2)) for t in range(10)]
prof[-1] = (0, prof[-1][1])
lathe('lit', DOME, prof, 22, lambda k, i: PALE if i % 4 == 0 else (0x8f88d8 if k < 4 else LAVD), j=0.04)
def rot_d(x, z):
    c, s = math.cos(DR), math.sin(DR); return (DOME[0] + x * c + z * s, DOME[2] - x * s + z * c)
px, pz = rot_d(0, 1.75)
box('lit', px, DOME[1] + 0.6, pz, 1.1, 1.2, 0.62, PALE, DR, bevel=0.04)
px, pz = rot_d(0, 2.07); box('emit', px, DOME[1] + 0.48, pz, 0.66, 0.88, 0.04, 0xff7ab8, DR, j=0.02)
px, pz = rot_d(0, 2.3); box('lit', px, DOME[1] + 0.04, pz, 1.3, 0.14, 0.52, 0xc9b897, DR, bevel=0.03)
flagpole(DOME[0], DOME[1] + 2.68, DOME[2])
DOME_STARS = []
for i in range(80):
    a = R() * TAU; e = R() * PI / 2 * 0.88; r = 1.73
    DOME_STARS.append([DOME[0] + math.cos(a) * math.cos(e) * r, DOME[1] + 1.0 + math.sin(e) * r, DOME[2] + math.sin(a) * math.cos(e) * r])

# ---------- 캠프 ----------
CAMP = (CAMP_C[0], H(*CAMP_C), CAMP_C[1])
# 텐트는 모닥불 뒤쪽(북·동)에 반원으로, 입구는 불을 향함. 앞쪽(서·남)은 돌길과 통나무 의자 자리로 비움
TENTS = [(-0.4, -2.0, 1.0, 0xf3a24b), (1.55, -1.25, 0.95, 0xf08a3a), (2.0, 0.75, 0.9, 0xe9773a)]
for (tx, tz, s, col) in TENTS:
    cx, cz = CAMP[0] + tx, CAMP[2] + tz; cy = H(cx, cz) - 0.02
    yaw = math.atan2(-tx, -tz)                          # 앞(+z)이 모닥불을 향함
    W, Hh, L = 1.25 * s, 1.15 * s, 1.5 * s
    def P(lx, ly, lz):
        c, sn = math.cos(yaw), math.sin(yaw); return (cx + lx * c + lz * sn, cy + ly, cz - lx * sn + lz * c)
    TC = P(0, Hh * 0.3, 0)
    tri_prism('lit', [[P(-W / 2, 0, L / 2), P(-W / 2, 0, -L / 2), P(0, Hh, -L / 2), P(0, Hh, L / 2)],
                      [P(W / 2, 0, -L / 2), P(W / 2, 0, L / 2), P(0, Hh, L / 2), P(0, Hh, -L / 2)],
                      [P(-W / 2, 0, -L / 2), P(W / 2, 0, -L / 2), P(0, Hh, -L / 2)]], col, 0.05, TC)
    tri_prism('lit', [[P(-W / 2 + 0.02, 0.0, L / 2 - 0.08), P(0, Hh - 0.02, L / 2 - 0.08), P(W / 2 - 0.02, 0.0, L / 2 - 0.08)]], 0x5a2408, 0.03, TC)
    tri_prism('emit', [[P(-W * 0.3, 0, L / 2 - 0.04), P(W * 0.3, 0, L / 2 - 0.04), P(0, Hh * 0.62, L / 2 - 0.04)]], 0xffa040, 0.02, TC)
    tri_prism('lit', [[P(-W / 2, 0, L / 2), P(0, Hh, L / 2), P(-W * 0.32, 0, L / 2 + 0.28)],
                      [P(W / 2, 0, L / 2), P(W * 0.32, 0, L / 2 + 0.28), P(0, Hh, L / 2)]], 0xc96a2a, 0.05, TC)
    x1, y1, z1 = P(0, Hh + 0.12, L / 2 + 0.05); box('lit', x1, y1 - 0.1, z1, 0.05, 0.3, 0.05, 0x6b4428)
fx, fz = CAMP[0], CAMP[2]
for i in range(9):
    a = i / 9 * TAU; ico('lit', fx + math.cos(a) * 0.5, CAMP[1] + 0.06, fz + math.sin(a) * 0.5, 0.14, 0x9a96a8, 0, 0.04)
for i in range(4):
    a = i / 4 * TAU + 0.3
    box('lit', fx + math.cos(a) * 0.12, CAMP[1] + 0.16, fz + math.sin(a) * 0.12, 0.1, 0.1, 0.75, 0x6b4428, PI / 2 - a, rx=0.4)
for (bx, bz) in ((-1.25, 0.15), (-0.35, 1.25), (0.95, 1.05)):          # 통나무 의자: 불을 둘러싸는 방향으로 눕힘
    x, z = fx + bx, fz + bz; bmx = grp('lit'); r = math.atan2(-bz, bx)      # 통나무 축이 불 둘레 접선 방향(-bz, bx)
    res = bmesh.ops.create_cone(bmx, cap_ends=True, cap_tris=False, segments=7, radius1=0.17, radius2=0.17, depth=1.1,
                                matrix=Matrix.Translation((x, H(x, z) + 0.15, z)) @ Matrix.Rotation(r, 4, 'Y'))
    paint(bmx, faces_of(res['verts']), 0x7a4b2b, 0.08)
# 상자·통
for (bx, bz) in ((2.9, -0.35), (3.1, 0.1)):                           # 상자: 텐트 사이 뒤쪽
    x, z = fx + bx, fz + bz; box('lit', x, H(x, z) + 0.2, z, 0.42, 0.42, 0.42, 0xb07a45, R(), bevel=0.04)
box('lit', fx + 3.0, H(fx + 3.0, fz - 0.12) + 0.6, fz - 0.12, 0.32, 0.32, 0.32, 0xc08a52, 0.6, bevel=0.03)
for (bx, bz) in ((-1.55, -1.6), (-1.85, -1.15)):                       # 통: 왼쪽 텐트 옆
    x, z = fx + bx, fz + bz; y = H(x, z)
    lathe('lit', (x, y, z), [(0.22, 0), (0.26, 0.25), (0.22, 0.52)], 9, [0x9a6b3e, 0x8a5e35], capt=True)
    lathe('lit', (x, y, z), [(0.235, 0.1), (0.235, 0.15)], 9, [0x5c5c66])
    lathe('lit', (x, y, z), [(0.235, 0.39), (0.235, 0.44)], 9, [0x5c5c66])

# ---------- 랜턴 기둥 ----------
LANTERNS = []
def lantern(x, z, tx, tz):
    """길가 전등: 기둥 + 팔(길 쪽 tx,tz 를 향함) + 등."""
    y = H(x, z); a = math.atan2(tz - z, tx - x); ca, sa = math.cos(a), math.sin(a)
    lathe('lit', (x, y - 0.1, z), [(0.1, 0), (0.1, 0.12), (0.06, 0.2), (0.05, 1.3)], 6, [0x3a3a44, 0x4a3a30, 0x4a3a30])
    box('lit', x + ca * 0.13, y + 1.15, z + sa * 0.13, 0.04, 0.04, 0.3, 0x4a3a30, math.atan2(ca, sa))
    lx, lz = x + ca * 0.26, z + sa * 0.26
    box('emit', lx, y + 0.98, lz, 0.14, 0.18, 0.14, 0xffd27a, j=0.02)
    lathe('lit', (lx, y + 1.07, lz), [(0.12, 0), (0, 0.1)], 4, [0x3a2e28], rot=PI / 4, capb=True)
    LANTERNS.append([lx, y + 0.98, lz])
def lamp_ok(x, z):
    if pond_d(x, z) < 0.75 or chan_k(x, z) > 0.02: return False
    if any(math.hypot(x - ax, z - az) < r for ax, az, r in ((CAMP_C[0], CAMP_C[1], 2.9), (DOME_C[0], DOME_C[1], 2.6), (OAK_C[0], OAK_C[1], 1.5))): return False
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
hull = lathe('boat', BOAT_O, prof, 12, [0x8c5a32, 0x7a4b2b, 0x9a6638])
for v in {v for f in hull for v in f.verts}: v.co.z = BOAT_O[2] + (v.co.z - BOAT_O[2]) * 2.1
box('boat', BOAT_O[0], BOAT_O[1] - 0.2, BOAT_O[2], 0.6, 0.04, 1.45, 0x9a6638, j=0.04)          # 배 바닥 판자
for z in (-0.35, 0.3): box('boat', BOAT_O[0], BOAT_O[1] - 0.02, BOAT_O[2] + z, 0.86, 0.05, 0.2, 0xb98250)
box('boat', BOAT_O[0] + 0.3, BOAT_O[1] + 0.02, BOAT_O[2] - 0.1, 0.05, 0.04, 1.2, 0xc79a62, rz=0.1)

# ---------- 나무 ----------
TREES = []
avoid = [(PL[0], PL[1] - 0.4, 3.4), (DOME_C[0], DOME_C[1], 2.8), (CAMP_C[0] + 0.5, CAMP_C[1] - 0.2, 3.4), (POND[0], POND[1] + 0.2, 3.7), (PL[0], STAIR_END + 0.3, 1.5), (OAK_C[0], OAK_C[1], 1.7)]
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
PINE_C = [hexc(0x235c3f), hexc(0x2f7349), hexc(0x3a8752), hexc(0x4a9a5b), hexc(0x5aac64)]
TIERS = {}
def pine(x, y, z, s):
    var = R(); rot = R() * TAU; n = 5 if var > 0.4 else 4
    lathe('tree', (x, y, z), [(0.15 * s, -0.2), (0.11 * s, 0.9 * s)], 6, [0x6b4428, 0x5a3820], rot=rot)
    tiers = []
    for t in range(n):
        yb = y + (0.6 + t * 0.62 * (5 / n)) * s; rb = (1.08 - t * 0.85 / n) * s; ht = (1.05 - t * 0.06) * s
        tiers.append((yb, rb, ht))
        seg = 10
        zig = lambda i, k: (1.0 if i % 2 == 0 else 0.74) if k == 1 else 1.0
        dark = mixc(PINE_C[0], [0, 0, 0], 0.25)
        col = PINE_C[min(4, t + (1 if var > 0.7 else 0))]
        lathe('tree', (x, yb, z), [(0.0, 0.22 * s), (rb, 0.0), (rb * 0.55, ht * 0.45), (0, ht)], seg,
              lambda k, i, col=col, dark=dark: dark if k == 0 else (col if k == 1 else mixc(col, [1, 1, .8], 0.12)),
              zig=zig, rot=rot + t * 0.3, jt=0.06 * s, j=0.07)
    TIERS[len(TIERS)] = tiers
    return tiers
TREE_TIERS = [pine(*t) for t in TREES]
# 둥근 활엽수
OAK = (OAK_C[0], H(*OAK_C), OAK_C[1])
lathe('tree', OAK, [(0.3, -0.2), (0.22, 1.7)], 7, [0x6b4428])
for (x, y, z, r) in ((0, 2.3, 0, 1.25), (0.8, 1.9, 0.3, 0.95), (-0.7, 2.0, -0.2, 0.95), (0.1, 2.9, -0.4, 0.85), (-0.2, 1.8, 0.8, 0.8), (0.5, 2.1, -0.8, 0.85)):
    ico('tree', OAK[0] + x, OAK[1] + y, OAK[2] + z, r, mixc(hexc(0x4f9e3c), hexc(0x6cbb4a), R()), 1, 0.22 * r, j=0.1)

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
for i in range(70):
    a = R() * TAU; y = 1.4 + R() * 2.0; rr = 1.3 + 0.15 * math.sin(y * 3)
    OAK_BULBS.append([OAK[0] + math.cos(a) * rr, OAK[1] + y, OAK[2] + math.sin(a) * rr])

# ---------- 돌길 ----------
for line in PATHS:
    for i in range(len(line) - 1):
        (ax, az), (bx, bz) = line[i], line[i + 1]; n = math.ceil(math.hypot(bx - ax, bz - az) / 0.5)
        for k in range(n):
            u = k / n; x = ax + (bx - ax) * u + (R() - .5) * 0.25; z = az + (bz - az) * u + (R() - .5) * 0.25
            s = 0.8 + R() * 0.45
            lathe('lit', (x, H(x, z) - 0.02, z), [(0.3 * s, 0), (0.27 * s, 0.07), (0, 0.08)], 7, [0xd4c8ad, 0xe0d6bd], rot=R(), jt=0.03, j=0.06)

# ---------- 덤불·풀·꽃·버섯·돌 ----------
def clear(x, z, pad=0.0):
    if ISL_R(math.atan2(z, x)) - math.hypot(x, z) < 0.5: return False      # 섬 가장자리에 걸쳐 떠 보이지 않게
    if any(math.hypot(x - ax, z - az) < ar + pad for ax, az, ar in ((CAMP_C[0] + 0.5, CAMP_C[1] - 0.2, 3.0), (DOME_C[0], DOME_C[1], 2.4), (OAK_C[0], OAK_C[1], 1.4))): return False
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
    ico('lit', x, H(x, z) + s * 0.25, z, s, mixc(hexc(0x9f98b4), hexc(0x7d7696), R()), 1, 0.35 * s, 1.2, 0.75, 1, R() * TAU, 0.1); n += 1

# ---------- 메시로 만들고 AO 굽기 ----------
for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
scene = bpy.context.scene
objs = {}
for name, bmx in BM.items():
    me = bpy.data.meshes.new(name); bmx.to_mesh(me); me.update()
    ob = bpy.data.objects.new(name, me); scene.collection.objects.link(ob); objs[name] = ob
    mat = bpy.data.materials.new(name); me.materials.append(mat)
    print(name, '면', len(me.polygons))
if scene.world is None: scene.world = bpy.data.worlds.new('W')
scene.world.light_settings.distance = 1.3
scene.render.engine = 'CYCLES'
scene.cycles.device = 'CPU'
scene.cycles.samples = 48
scene.render.bake.target = 'VERTEX_COLORS'
for name in ('lit', 'boat', 'tree'):
    me = objs[name].data
    ao = me.color_attributes.new('ao', 'FLOAT_COLOR', 'CORNER')
    me.color_attributes.active_color = ao
for o in scene.objects: o.select_set(False)
for name in ('lit', 'boat', 'tree'): objs[name].select_set(True)
bpy.context.view_layer.objects.active = objs['lit']
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
meta.update({'flags': r6(FLAGS), 'bulbs': r6(BULBS), 'oakBulbs': r6(OAK_BULBS), 'domeStars': r6(DOME_STARS), 'lanterns': r6(LANTERNS),
             'camp': [round(v, 3) for v in CAMP], 'dome': [round(v, 3) for v in DOME], 'castle': [round(v, 3) for v in CO],
             'rimZ': rimZ, 'wfx': WFX, 'isl': ISLR, 'domeRot': DR, 'pond': [POND[0], POND[1], PONDB, PONDS], 'ply': PLY, 'zEdge': zEdge})
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'island11.bin'), 'wb').write(bytes(blob))
json.dump(meta, open(os.path.join(OUT, 'island11.json'), 'w'))
print('완료', len(blob), '바이트')
