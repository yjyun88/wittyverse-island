# 위티버스 섬

위티버스 v10 지도와 가운데 섬 3D 샘플을 담은 안드로이드 단독 앱입니다.
실행하면 바로 위티버스 지도가 나오고, 가운데 섬으로 들어가 "🧪 3D 샘플" 버튼을 누르면 3D 섬을 볼 수 있습니다.
(My위티 데모 앱 `mywitti_demo` 안에서 만들던 부분만 따로 떼어 낸 프로젝트입니다.)

## 화면 구성

| 화면 | 내용 |
|---|---|
| 지도 (`web/map/v10.html`) | 낮/밤 전환, 영역 확대, 영역 효과, 캐릭터. 가운데 섬 안에 "🧪 3D 샘플" 버튼 |
| 샘플 1 · 코드 3D | three.js 코드로 만든 섬 |
| 샘플 1-1 · 로우폴리 | Blender 로 만든 로우폴리 섬 |
| **샘플 1-2 · 원화 맞춤** | 원화에 맞춘 성·돔·캠프·나무·폭포·꽃, 폭포 켜기/끄기, **🧭 탐험**(페로 캐릭터를 터치패드로 움직임) |
| 샘플 2 · 원화 기울이기 | 원화 + 깊이 지도로 살짝 기울이기 |
| 샘플 2-2 · 회전 그림 | 여러 방향 그림을 돌려 보기 |

뒤로가기: 3D → 지도 → 앱 종료.

## 폴더

```
android/              안드로이드 앱(웹뷰 하나, 첫 화면 = assets/index.html)
web/
  map/                지도 원본(그림, 마스크, map.json) + 완성본 v10.html
  tools/              지도 생성(make_v10.py, masks_v10.py, cast_v9.py, v10_template.html), three.js(three_inline.txt)
  character/          지도 캐릭터 그림(1_generated_2D), 페로 원화(0_origin)
  island3d/           3D 샘플 템플릿(island*_template.html), 생성 스크립트(make_island3d.py)
    blender/          샘플 1-1·1-2 모델 생성(build_island11.py, build_island12.py)
    src/              모델 결과(island1x.bin/json), 원화·깊이 지도, 회전 그림(views22)
build.sh              생성 + 빌드 + (선택) 설치
```

`android/app/src/main/assets/` 는 `build.sh` 가 만드는 생성물이라 git 에 올리지 않습니다.

## 빌드

필요: Python 3 (`numpy`, `opencv-python`, `pillow`), JDK 17, Android SDK.
처음 한 번 `android/local.properties` 에 `sdk.dir=...` 를 적습니다.

```sh
sh build.sh            # 3D 샘플 생성 + 지도 복사 + 디버그 APK
sh build.sh install    # 빌드 후 기기에 덮어 설치 (ADB_SERIAL 로 기기 지정)
sh build.sh map        # 지도 v10.html 도 원본에서 다시 생성
```

APK: `android/app/build/outputs/apk/debug/app-debug.apk`

### 3D 모델을 고쳤을 때 (샘플 1-2)

Blender 5.2 로 모델을 다시 굽고 `build.sh` 를 실행합니다.

```sh
blender -b --factory-startup --python web/island3d/blender/build_island12.py -- web/island3d/src
sh build.sh install
```

- 실행할 때마다 `겹침 검사:` 결과가 출력됩니다(울타리·디딤돌·바위·텐트·랜턴·꽃 등이 계단·건물·서로와 겹치는지).
- 미리보기만 빠르게: `PREVIEW=미리보기.png PV_T=dome|camp|stairs|stairtop PV_AZ=0 PV_EL=0.4 PV_D=10` 또는 `PV_XYZ=x,y,z` 를 주고 실행하면 AO 굽기 없이 그 부분만 렌더하고 끝납니다.
- 탐험 모드의 이동 가능 지역(0.2 간격 격자)도 이 스크립트가 함께 계산해 `island12.json` 의 `walk` 로 내보냅니다.

## 점검 팁

- 웹뷰 디버깅이 켜져 있어 `adb forward tcp:9222 localabstract:webview_devtools_remote_<pid>` 로 페이지에 붙을 수 있습니다.
- 샘플 1-2 페이지의 점검용 함수: `__view(방위각, 고도, 거리)`, `__show(폭포, 수면)`, `__hero()`, `__pad(x, y)`.
- WebGL 화면은 CDP 스크린샷에 비어 나오므로 `adb exec-out screencap -p` 로 찍습니다.
- 재설치는 `adb install -r` 로만 합니다(강제 종료하면 웹뷰가 흰 화면이 될 수 있음).
