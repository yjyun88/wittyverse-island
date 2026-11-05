# 가운데 섬 샘플 HTML 생성.  사용: python make_island3d.py [픽셀배율 상한]
# 결과: island3d.html(샘플 1, APK 의 index.html), sample1_1.html(샘플 1-1 Blender 로우폴리), sample2.html(샘플 2)
# 결과는 android/app/src/main/assets/island3d/ 에 복사(앱이 그대로 씀). 샘플 1-1·1-2 모델은 먼저 blender/build_island11.py·build_island12.py 로 src/island1x.* 생성.
import os, sys, base64, shutil
here = os.path.dirname(os.path.abspath(__file__))
pr = sys.argv[1] if len(sys.argv) > 1 else '1'
three = open(os.path.join(here, '..', 'tools', 'three_inline.txt'), encoding='utf-8').read()
TABS = ('#tabs{position:fixed;top:14px;right:16px;display:flex;gap:0;border-radius:24px;overflow:hidden;box-shadow:0 3px 10px #0007;z-index:2}'
        '#tabs a{padding:10px 16px;font-size:15px;font-weight:700;color:#dfe8ff;background:#13285acc;text-decoration:none}'
        '#tabs a.on{color:#173064;background:linear-gradient(#fff,#dfe8ff)}')
PAGES = [('index.html', '샘플 1 · 코드 3D'), ('sample1_1.html', '샘플 1-1 · 로우폴리'), ('sample1_2.html', '샘플 1-2 · 원화 맞춤'), ('sample2.html', '샘플 2 · 원화 기울이기'), ('sample2_2.html', '샘플 2-2 · 회전 그림')]
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
build('island_template.html', 'island3d.html', 'index.html')
build('island11_template.html', 'sample1_1.html', 'sample1_1.html',
      {'__META__': open(src('island11.json'), encoding='utf-8').read(), '__BIN__': base64.b64encode(open(src('island11.bin'), 'rb').read()).decode()})
build('island12_template.html', 'sample1_2.html', 'sample1_2.html',
      {'__META__': open(src('island12.json'), encoding='utf-8').read(), '__BIN__': base64.b64encode(open(src('island12.bin'), 'rb').read()).decode()})
build('island2_template.html', 'sample2.html', 'sample2.html', {'__IMG__': uri('center_color.jpg', 'image/jpeg'), '__DEPTH__': uri('center_depth_soft.png', 'image/png')})
import json
build('island22_template.html', 'sample2_2.html', 'sample2_2.html',
      {'__VIEWS__': json.dumps([[a, uri('views22/v_%03d.jpg' % a, 'image/jpeg'), uri('views22/d_%03d.png' % a, 'image/png')] for a in VIEWS22])})
