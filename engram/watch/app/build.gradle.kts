plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "org.engram.watch"
    compileSdk { version = release(37) { minorApiLevel = 2 } }     // current AndroidX needs 37+
    defaultConfig {
        applicationId = "org.engram.watch"
        minSdk = 30                     // Wear OS 3+: the Galaxy Watch 4 and later
        targetSdk = 36
        versionCode = 1
        versionName = "0.1"
    }
    buildFeatures { compose = true }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2026.09.00"))
    implementation("androidx.wear.compose:compose-material3:1.7.0")
    implementation("androidx.wear.compose:compose-foundation:1.7.0")
    implementation("androidx.activity:activity-compose:1.13.0")
    implementation("androidx.core:core-ktx:1.19.1")
    implementation("androidx.wear:wear-ongoing:1.1.0")
    implementation("androidx.wear:wear-input:1.2.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.11.0")
}
