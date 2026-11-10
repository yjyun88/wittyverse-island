# 가운데 섬 샘플 HTML 생성.  사용: python make_island3d.py [픽셀배율 상한]
# 결과: index.html(샘플 1 원화 맞춤 로우폴리, 지도에서 처음 열리는 곳), sample2.html(샘플 2), sample2_2.html(샘플 2-1), sample3.html(샘플 3)
# 결과는 android/app/src/main/assets/island3d/ 에 복사(앱이 그대로 씀). 샘플 1 모델은 먼저 blender/build_island1.py 로 src/island1.* 생성.
import os, sys, base64, shutil
here = os.path.dirname(os.path.abspath(__file__))
pr = sys.argv[1] if len(sys.argv) > 1 else '1'
three = open(os.path.join(here, '..', 'tools', 'three_inline.txt'), encoding='utf-8').read()
TABS = ('#tabs{position:fixed;top:14px;right:16px;display:flex;gap:0;border-radius:24px;overflow:hidden;box-shadow:0 3px 10px #0007;z-index:2}'
        '#tabs a{padding:10px 16px;font-size:15px;font-weight:700;color:#dfe8ff;background:#13285acc;text-decoration:none}'
        '#tabs a.on{color:#173064;background:linear-gradient(#fff,#dfe8ff)}')
PAGES = [('index.html', '샘플 1 · 원화 맞춤'), ('sample2.html', '샘플 2 · 원화 기울이기'), ('sample2_2.html', '샘플 2-1 · 회전 그림'), ('sample3.html', '샘플 3 · 3D 지구')]
VIEWS22 = [0, 30, 90, 120, 180, 210, 270, 300, 330]      # src/views22 (prep_views.py 결과). 60·150·240 은 제미나이 결과가 어긋나 제외
def links(cur): return ''.join('<a%s href="%s">%s</a>' % (' class="on"' if f == cur else '', f, t) for f, t in PAGES)
src = lambda f: os.path.join(here, 'src', f)
uri = lambda f, m: 'data:%s;base64,%s' % (m, base64.b64encode(open(src(f), 'rb').read()).decode())
out_dir = os.path.join(here, 'build')                                          # 생성 결과(git 에 올리지 않음)
assets = os.path.join(here, '..', '..', 'android', 'app', 'src', 'main', 'assets', 'island3d')   # 앱 자산
os.makedirs(out_dir, exist_ok=True); os.makedirs(assets, exist_ok=True)
# 위티버스 지도(가운데 섬의 임시 버튼)에서 ?from=map 으로 들어온 경우: 탭 이동은 기록을 쌓지 않고, 나가기는 지도로 돌아감
FROM_MAP = ('<script>(()=>{const q=location.search;if(!/from=map/.test(q))return;'
            'document.querySelectorAll("#tabs a").forEach(a=>a.addEventListener("click",e=>{e.preventDefault();location.replace(a.getAttribute("href")+q);}));'
            'const x=document.getElementById("exit");if(!x)return;x.style.display="block";x.textContent="← 지도로";'
            'x.onclick=()=>{if(history.length>1)history.back();else location.href="../index.html";};})();</script>')
def build(tpl, out, page, extra={}):
    h = open(os.path.join(here, tpl), encoding='utf-8').read()
    for k, v in {'__THREE__': three, '__PR__': pr, '__TABS__': TABS, '__TABLINKS__': links(page), **extra}.items(): h = h.replace(k, v)
    i = h.rfind('</body>'); h = h[:i] + FROM_MAP + '\n' + h[i:]
    open(os.path.join(out_dir, out), 'w', encoding='utf-8').write(h); print(out, len(h))
    shutil.copy(os.path.join(out_dir, out), os.path.join(assets, page))     # 앱 자산(지도 가운데 섬 "3D 샘플" 버튼이 여는 곳)
build('island1_template.html', 'index.html', 'index.html',
      {'__META__': open(src('island1.json'), encoding='utf-8').read(), '__BIN__': base64.b64encode(open(src('island1.bin'), 'rb').read()).decode()})
build('island2_template.html', 'sample2.html', 'sample2.html', {'__IMG__': uri('center_color.jpg', 'image/jpeg'), '__DEPTH__': uri('center_depth_soft.png', 'image/png')})
import json
build('island22_template.html', 'sample2_2.html', 'sample2_2.html',
      {'__VIEWS__': json.dumps([[a, uri('views22/v_%03d.jpg' % a, 'image/jpeg'), uri('views22/d_%03d.png' % a, 'image/png')] for a in VIEWS22])})
# 샘플 3 · 3D 지구: home_hero_earth 로띠의 지구 그림을 3D 구로 만든 것(src/globe3, 생성 스크립트는 globe3/)
G = lambda f: os.path.join(here, 'src', 'globe3', f)
guri = lambda f: 'data:image/png;base64,' + base64.b64encode(open(G(f), 'rb').read()).decode()
from PIL import Image
gplaced = json.load(open(G('props/placed.json'), encoding='utf-8'))
gassets = {'tex': guri('tex.png'),
           'props': [{**p, 'src': guri('props/' + p['file'])} for p in gplaced],
           'trees': json.load(open(G('trees.json'), encoding='utf-8')),   # 3D 나무 배치(globe3/place_trees.py)
           'buildings': json.load(open(G('buildings.json'), encoding='utf-8')),   # 3D 집·풍차 배치(globe3/place_buildings.py)
           'landmarks': json.load(open(G('landmarks.json'), encoding='utf-8')),   # 3D 산·바위·무지개 배치(globe3/place_landmarks.py)
           'coast': json.load(open(G('coast.json'), encoding='utf-8')),   # 3D 등대·돛단배 배치(globe3/place_coast.py)
           'polar': json.load(open(G('polar.json'), encoding='utf-8')),   # 3D 이글루·펭귄 배치(globe3/place_polar.py)
           'clouds': {k: {'src': guri(k + '.png'), 'w': Image.open(G(k + '.png')).width, 'h': Image.open(G(k + '.png')).height} for k in ['cf1', 'cf2', 'cb1', 'cb2']}}
build('island3_template.html', 'sample3.html', 'sample3.html', {'__ASSETS__': json.dumps(gassets)})
