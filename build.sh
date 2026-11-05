#!/usr/bin/env sh
# 위티버스 섬: 웹 결과물을 만들어 앱 자산에 넣고 APK 를 빌드한다.
#   sh build.sh            → 3D 샘플 HTML 생성 + 지도 복사 + 디버그 APK 빌드
#   sh build.sh map        → 지도(v10.html)도 원본에서 다시 생성(시간이 조금 걸림)
#   sh build.sh install    → 빌드 후 연결된 기기(ADB_SERIAL 또는 기본 기기)에 install -r
# 필요: Python 3 (numpy, opencv-python, pillow, fonttools), JDK 17, Android SDK(android/local.properties 의 sdk.dir)
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
ASSETS="$ROOT/android/app/src/main/assets"
mkdir -p "$ASSETS/island3d"

if [ "$1" = "map" ]; then
  python -I "$ROOT/web/tools/make_v10.py" "$ROOT/web/map/map.json" "$ROOT/web/map" "$ROOT/web/map/v10.html"
fi
cp "$ROOT/web/map/v10.html" "$ASSETS/index.html"                 # 지도 = 앱 첫 화면
python -I "$ROOT/web/island3d/make_island3d.py" 1.5             # 3D 샘플 → assets/island3d/

cd "$ROOT/android"
if command -v cmd.exe >/dev/null 2>&1; then ./gradlew.bat :app:assembleDebug -q; else ./gradlew :app:assembleDebug -q; fi
APK="$ROOT/android/app/build/outputs/apk/debug/app-debug.apk"
echo "APK: $APK"

if [ "$1" = "install" ]; then
  # 강제 종료(am force-stop) 없이 덮어 설치: 웹뷰 렌더러가 막혀 흰 화면이 되는 것을 피함
  if [ -n "$ADB_SERIAL" ]; then adb -s "$ADB_SERIAL" install -r "$APK"; else adb install -r "$APK"; fi
fi
