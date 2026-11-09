plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "net.minigate.wittyverse.island"
    compileSdk = 35

    defaultConfig {
        applicationId = "net.minigate.wittyverse.island"
        minSdk = 30
        targetSdk = 35
        versionCode = 1
        versionName = "0.1.0"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = signingConfigs.getByName("debug")
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    // 큰 HTML 자산(수 MB, 그림이 base64 로 들어 있음)은 압축해도 이득이 적고 읽기만 느려짐
    androidResources {
        noCompress += listOf("html", "png", "m4a")
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.activity:activity-ktx:1.9.3")
    implementation("androidx.webkit:webkit:1.12.1")   // WebViewAssetLoader: 앱 자산을 https 주소로 제공(우주 천문대 콘텐츠의 WebGL 텍스처·fetch 용)
}
