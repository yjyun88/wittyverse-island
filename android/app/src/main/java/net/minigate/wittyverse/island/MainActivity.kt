package net.minigate.wittyverse.island

import android.annotation.SuppressLint
import android.os.Bundle
import android.util.Log
import android.view.View
import android.view.WindowManager
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat

/**
 * 위티버스 섬 단독 앱: 실행하면 바로 위티버스 v10 지도(assets/index.html).
 * 가운데 섬의 "3D 샘플" 버튼 → assets/island3d/ 의 3D 샘플(탭으로 전환, "← 지도로" 로 복귀).
 * 웹 쪽 원본과 생성 스크립트는 저장소의 web/ 폴더에 있다(README 참고).
 */
private const val MAP_URL = "file:///android_asset/index.html"

class MainActivity : ComponentActivity() {
    private lateinit var web: WebView
    private var clearOnLoad = false

    @SuppressLint("SetJavaScriptEnabled", "JavascriptInterface")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)   // 탐험 중 화면이 꺼지지 않게
        WebView.setWebContentsDebuggingEnabled(true)                        // adb 로 화면 점검(개발용)

        web = WebView(this).apply {
            setLayerType(View.LAYER_TYPE_HARDWARE, null)                    // WebGL 하드웨어 레이어
            setBackgroundColor(0xFF050C22.toInt())
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = true
            settings.mediaPlaybackRequiresUserGesture = false
            settings.textZoom = 100                                         // 기기 글꼴 크기 설정을 웹 화면에 적용하지 않음
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView, url: String?) {
                    if (clearOnLoad) { clearOnLoad = false; view.clearHistory() }
                }
            }
            webChromeClient = object : WebChromeClient() {
                override fun onConsoleMessage(m: ConsoleMessage): Boolean {
                    Log.d("WittyverseIsland", "${m.messageLevel()} ${m.sourceId()}:${m.lineNumber()} ${m.message()}")
                    return true
                }
            }
            // 지도 화면의 "나가기" 버튼이 부르는 다리(JS 스레드 → UI 스레드)
            addJavascriptInterface(object {
                @JavascriptInterface
                fun close() { post { finish() } }
            }, "MyWittiApp")
            loadUrl(MAP_URL)
        }
        setContentView(web)
        hideSystemBars()

        // 뒤로가기
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                // 3D 샘플 → 지도, 지도(첫 화면) → 앱 종료. 지도로 돌아갈 때는 기록을 지워 다시 3D 로 가지 않게
                if (web.url?.contains("/island3d/") == true) { clearOnLoad = true; web.loadUrl(MAP_URL) } else finish()
            }
        })
    }

    override fun onWindowFocusChanged(hasFocus: Boolean) {
        super.onWindowFocusChanged(hasFocus)
        if (hasFocus) hideSystemBars()
    }

    private fun hideSystemBars() {
        WindowCompat.setDecorFitsSystemWindows(window, false)
        WindowInsetsControllerCompat(window, window.decorView).apply {
            hide(WindowInsetsCompat.Type.systemBars())
            systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        }
    }

    override fun onPause() { super.onPause(); web.onPause() }
    override fun onResume() { super.onResume(); web.onResume() }
    override fun onDestroy() { web.destroy(); super.onDestroy() }
}
