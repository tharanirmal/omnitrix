# G — Watch agent: a Galaxy Watch 5 companion for engram (approvals + voice)

Compiled 2026-09-28. Method: WebSearch/WebFetch against vendor docs, Android developer docs, and current
coverage, plus two claims **self-verified by fetching primary sources directly** rather than trusting a
search summary: the Android SDK package sizes come from Google's own package manifest
(`dl.google.com/android/repository/repository2-3.xml`, fetched today) and the JDK 17 size comes from the live
Adoptium release API. Anything I could not confirm this way is marked **UNVERIFIED**. Skims
[E-controlled-execution-security.md](E-controlled-execution-security.md) (watch-approval, habituation, T1/T2/T3
tiers) and [F-landscape-prior-art.md](F-landscape-prior-art.md) (Agent Approve) rather than repeating them —
referenced as "see E §…" / "see F §…" below. `engram/src/engram/serve.py` and `act.py` were read directly for
the current API shape and effect tiers (`read` / `internal` / `external` / `destructive`).

---

## 1. Galaxy Watch 5 today

- **Hardware:** Samsung Exynos W920 (5nm EUV), dual-core Cortex-A55 @ 1.18 GHz, Mali-G68 MP2 GPU, **1.5 GB RAM**,
  16 GB storage, Bluetooth 5.2, Wi-Fi 2.4 GHz + 5 GHz. [Samsung Semiconductor — Exynos
  W920](https://semiconductor.samsung.com/processor/wearable-processor/exynos-w920/) ·
  [GSMArena — Galaxy Watch5 Pro specs](https://www.gsmarena.com/samsung_galaxy_watch5_pro-11749.php)
  **Relevance to engram:** 1.5 GB RAM rules out running any model or ASR on the watch itself — it can only be a
  thin client (capture audio, render a card, hold one Wi-Fi socket). All inference stays on the Mac, which is
  the sovereignty story anyway.
- **Software version:** Confirmed stable as of the update window checked here: **One UI 6 Watch, i.e. Wear OS 5
  (Android 14, API level 34)**. [Android Central — Wear OS
  5](https://www.androidcentral.com/wearables/wear-os-5) · [SamMobile — Watch 5 gets One UI 6 Watch
  stable](https://www.sammobile.com/news/galaxy-watch-5-one-ui-6-watch-stable-update-usa-released/). Whether the
  Watch 5 has since received the **Wear OS 6 (Android 16, API 36)** major bump by 2026-09-28 is **UNVERIFIED and
  contradictory in the coverage found**: one 2025-10-28 report says the Watch 5 is "getting one more update
  before Wear OS 6" ([9to5google](https://9to5google.com/2025/10/28/galaxy-watch-5-is-getting-one-more-update-before-wear-os-6/)),
  while a 2026-06-16 report groups Watch 4/5/6/FE into a shared "Wear OS update" that reads, on inspection, as a
  **security/stability patch rather than a confirmed major-version bump**
  ([SamMobile](https://www.sammobile.com/news/new-galaxy-watch-fe-watch-6-watch-5-watch-4-updates-may-2026-security-patch/)).
  Samsung's own support commitment is "Wear OS upgrades until 2026-12-31" for the Watch 5, which itself implies
  the major bump is not a settled fact yet. **Practical target:** build for `minSdk` around API 30
  (Wear OS 3, to be safe for any Watch 5 that never left Wear OS 5) and `compileSdk`/`targetSdk` 36 for forward
  compatibility; verify the actual installed version on the team's own unit via *Settings → About watch →
  Software information* before the hackathon rather than trusting either report here.
- **Sideloading:** the watch has **no "install unknown sources" toggle** in its Settings UI — apps are installed
  by enabling Developer options (tap Software version 5×) and then `adb install`/`adb push` over Wi-Fi, not
  through an OEM-unlock or unknown-sources flow.
  [DroidWin — sideload via ADB](https://droidwin.com/sideload-apk-install-apps-via-adb-commands-in-galaxy-watch-5-pro/)
  A plain debug-signed `adb install` does not require bootloader/OEM unlock; Knox's warranty-void bit is
  associated with bootloader/recovery unlocking, not ordinary debug installs — this is standard Samsung/Knox
  behavior on phones and reasoned by analogy here rather than independently confirmed for the Watch 5 specifically
  (**UNVERIFIED** for this exact device).
  **Relevance to engram:** no unlock ceremony blocks the hackathon plan — just Developer options + Wireless
  debugging (§3).

---

## 2. Minimal toolchain on macOS (Apple Silicon), without Android Studio

- **JDK:** current Android Gradle Plugin (AGP 9.x) requires **JDK 17** as the build JDK.
  [Android Developers — Java versions in Android builds](https://developer.android.com/build/jdks) ·
  [AGP 9.1.0 release notes](https://developer.android.com/build/releases/about-agp) confirm the same JDK-17
  floor. **Self-verified size:** Eclipse Temurin 17 (jdk-17.0.20.1+1), macOS aarch64 tarball, fetched live from
  the Adoptium release API today: `OpenJDK17U-jdk_aarch64_mac_hotspot_17.0.20.1_1.tar.gz`, **185,851,019 bytes ≈
  185.9 MB**. [Adoptium API](https://api.adoptium.net/v3/assets/latest/17/hotspot?image_type=jdk&os=mac&architecture=aarch64)
- **SDK packages needed** for a Wear OS Compose app deployed straight to a real device (no emulator/system-image
  required at all, since the team has a physical Watch 5): `cmdline-tools;latest`, `platform-tools`,
  `build-tools;36.0.0`, `platforms;android-36` (or 34/35 to match whatever the watch actually reports, §1).
  [sdkmanager reference](https://developer.android.com/tools/sdkmanager) ·
  [Command-line tools overview](https://developer.android.com/tools). **Self-verified exact sizes**, pulled
  directly from Google's package manifest (`dl.google.com/android/repository/repository2-3.xml`, fetched
  2026-09-28), macOS/arm64 archives where OS-specific:
  | Package | Archive | Size |
  |---|---|---|
  | `cmdline-tools;latest` (rev 23.0, tools build 16111833) | `commandlinetools-mac_arm64-16111833_latest.zip` | 155,384,151 B ≈ **148.2 MB** |
  | `platform-tools` (r37.0.1) | `platform-tools_r37.0.1-darwin.zip` | 16,110,554 B ≈ **15.4 MB** |
  | `build-tools;36.0.0` | `build-tools_r36_macosx.zip` | 79,121,749 B ≈ **75.5 MB** |
  | `platforms;android-36` (generic, no host-os) | `platform-36_r02.zip` | 65,878,410 B ≈ **62.8 MB** |

  **Sum ≈ 301.9 MB of SDK archives + 185.9 MB JDK ≈ 488 MB** before touching Gradle. The Gradle wrapper then
  downloads its own distribution (cached, typically 150–200 MB) plus AndroidX/Kotlin/Compose-for-Wear
  dependencies from Google's Maven on the first build (another 150–400 MB depending on how many Wear Compose
  artifacts — `compose-material3`, `compose-foundation`, `wear-ongoing`, etc. — are pulled in). **Budget roughly
  0.8–1.2 GB of total network traffic for a first clean build**, none of which needs Android Studio. The Gradle
  wrapper (`./gradlew`) is sufficient once `ANDROID_HOME`/`local.properties` point at the directories above — no
  project import into an IDE is required.
- **Android Studio, for comparison:** a recent Apple Silicon build's installer `.dmg` was reported at **≈1.49 GB**
  download, expanding to an installed footprint of roughly **8–9.5 GB**
  ([MacUpdate mirror listing](https://android-studio.macupdate.com/); installed-size figure via general community
  reporting, **UNVERIFIED precision**). Studio brings an SDK Manager UI, an AVD manager (not needed here — real
  device only), a device-mirroring pane, and a Logcat viewer with filtering. **Verdict for a hackathon:** with a
  real device already in hand and no need for an emulator, the command-line route (≈490 MB of SDK+JDK archives,
  `gradlew` handles the rest) is the leaner and faster setup — no GUI install wizard, no first-run indexing.
  Reach for Android Studio only if the team wants its Logcat/device-mirror GUI mid-hackathon and can spare the
  extra ~1.5 GB download plus install time.

---

## 3. Deploying to the watch over Wi-Fi

Steps (Samsung's own developer blog plus current Android docs and community write-ups agree on this flow):

1. **Enable Developer options:** *Settings → About watch → Software information*, tap *Software version* five
   times. [DroidWin — enabling developer mode](https://droidwin.com/where-is-install-from-unknown-sources-in-galaxy-watch-4-5/)
2. In *Developer options*, turn on **ADB debugging** and **Wireless debugging**; connect the watch to the same
   Wi-Fi network as the Mac (a phone hotspot works fine for this).
   [Android Developers — Debug Wear OS over Wi-Fi](https://developer.android.com/training/wearables/get-started/debug-wifi) ·
   [Samsung Developer blog — connect Galaxy Watch to Android Studio over Wi-Fi](https://developer.samsung.com/sdp/blog/en/2024/04/30/connect-galaxy-watch-to-android-studio-over-wi-fi)
3. Inside *Wireless debugging*, tap **Pair new device** → shows a 6-digit pairing code plus an IP:port. On the
   Mac: `adb pair <ip>:<pairing_port>`, then type the code when prompted.
4. The main *Wireless debugging* screen also shows a separate **connection** IP:port (a different port from the
   pairing one) — `adb connect <ip>:<connection_port>`.
5. `adb devices` confirms the connection; `adb install app.apk` or Gradle's `installDebug` targets it directly.

**Gotchas:**
- Pairing port and connection port are two different numbers on the same screen — a common source of "pairing
  succeeded but connect fails" confusion. [Technastic — ADB over Wi-Fi on Wear
  OS](https://technastic.com/adb-over-wi-fi-wear-os-watch/)
- Older guides reference a single "Debug over Wi-Fi" toggle; that flow has been replaced on recent Wear builds by
  the AOSP-standard Wireless-debugging pairing-code screen used above — guides describing the old toggle are
  stale. [DroidWin](https://droidwin.com/sideload-apk-install-apps-via-adb-commands-in-galaxy-watch-5-pro/)
- The wireless ADB session can drop when the watch's screen sleeps or the radio powers down to save battery;
  reconnect with `adb connect <ip>:<port>` again rather than re-pairing.
- Active wireless debugging plus an always-on Wi-Fi radio drains the Watch 5's small battery quickly — keep it
  charging between rehearsal runs.
- Disabling Developer options, or a factory reset, wipes the pairing and requires repeating step 3.

**Relevance to engram:** this is the entire install path for the demo — no cable, no Android Studio on the Mac,
`platform-tools`' `adb` alone (15.4 MB, §2) is enough.

---

## 4. Direct Wi-Fi networking from a Wear OS app

By default, a Wear OS app's ordinary network calls are routed through the **paired phone's Bluetooth
connection**, not the watch's own Wi-Fi radio — fine for small syncs, wrong for reaching a LAN IP directly.
[Android Developers — Network access and syncing](https://zditect.com/code/android/network-access-and-sync-on-wear-os-nbspnbsp-android-developers.html)

To get a real Wi-Fi network on a standalone Wear OS app, request one explicitly and bind to it — this is Google's
documented "high-bandwidth network request" pattern:

```kotlin
val callback = object : ConnectivityManager.NetworkCallback() {
    override fun onAvailable(network: Network) {
        connectivityManager.bindProcessToNetwork(network)   // future sockets/DNS use this network
    }
    override fun onLost(network: Network) { /* handle drop */ }
}
connectivityManager.requestNetwork(
    NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build(),
    callback
)
```

[Android Developers — Communicate directly over a network on standalone
devices](https://developer.android.com/training/wearables/data/network-communication) (code and quotes below
are from this page).

- **Duration:** "the device attempts to remain connected to the Wi-Fi network **until the `NetworkCallback` is
  released**" — release explicitly with `bindProcessToNetwork(null)` + `unregisterNetworkCallback(callback)`
  "to preserve battery life" once the transfer is done.
- **Acquisition latency:** "Acquiring a network might not be instantaneous, because a watch's Wi-Fi or cellular
  radio might be off to preserve battery. If the watch can't connect to a network, `onAvailable()` is not
  called" — so a UI needs an explicit "connecting…" state and a timeout, not a silent wait.
- **Battery guidance:** the same doc tells apps to "defer any nonessential networking tasks… until the Wear OS
  device has re-established a Bluetooth or Wi-Fi connection instead of an LTE or metered connection" — i.e.
  request the Wi-Fi network only while actively needed.
- **Cleartext HTTP:** Android 9+ (API 28+) blocks cleartext traffic by default. `engram/src/engram/serve.py`
  serves plain HTTP via `http.server`, so the watch app needs a `network_security_config.xml` scoping a
  cleartext exception to the Mac's one LAN IP, referenced from the manifest via
  `android:networkSecurityConfig`:
  ```xml
  <network-security-config>
    <domain-config cleartextTrafficPermitted="true">
      <domain includeSubdomains="false">192.168.1.111</domain>
    </domain-config>
  </network-security-config>
  ```
  [Android Developers — Network security configuration](https://developer.android.com/privacy-and-security/security-config) ·
  [worked example](https://devblogs.microsoft.com/xamarin/cleartext-http-android-network-security/)

**Relevance to engram:** `serve.py` today binds only to `127.0.0.1` and refuses foreign Host/Origin headers
(`_refuse_foreign`). The watch needs a **second** listener bound to the Mac's LAN interface (§8) and must
actively request+bind a Wi-Fi network, not assume its default network path reaches that IP; request/release it
around the lifecycle of the approval-listener screen (§5), not for the whole app session, to limit battery cost.

---

## 5. Getting approvals to the watch without FCM

- **(a) Foreground service + long-poll/SSE to the Mac.** Keep an HTTP connection open (hanging GET on
  `/api/act/<id>` until state changes, or a small SSE stream) inside a foreground service. Android 14+ (API 34)
  requires declaring the foreground-service **type** (e.g. `dataSync` or `connectedDevice`) and the matching
  permission. [Android Developers — Changes to foreground
  services](https://developer.android.com/develop/background-work/services/fgs/changes) A foreground service is
  one of Android's explicit, sanctioned exceptions to Doze/background execution limits — which is exactly why
  it's the right primitive here rather than a bare `Service` or `AlarmManager`. Lowest latency (near-instant
  buzz); costs a persistent notification icon and holds the Wi-Fi network open the whole time it runs — worst
  battery of the options, mitigated by only running it while a run is actually in flight.
- **(b) WorkManager periodic polling.** Minimum periodic interval is clamped to **15 minutes**, silently, even if
  a shorter one is requested. [Android Developers — Define work
  requests](https://developer.android.com/develop/background-work/background-tasks/persistent/getting-started/define-work)
  Far too slow for "buzzes when an action awaits approval" live; only useful as a low-power digest fallback —
  this matches E's own recommendation that low-tier items go to a digest rather than an interrupt (see E §"Budget
  the watch").
- **(c) WebSocket from a foreground service.** Same FGS/battery trade-off as (a), push-style instead of
  poll-style; on a one-hop LAN a ~1–2 s long-poll is close enough in latency that the extra protocol complexity
  buys little for a demo.
- **(d) Ongoing Activity API** (`androidx.wear:wear-ongoing`) surfaces a persistent, glanceable status on the
  watch face/status bar for a long-running activity.
  [Android Developers — Display ongoing activities](https://developer.android.com/training/wearables/notifications/ongoing-activity) ·
  [API reference](https://developer.android.com/reference/androidx/wear/ongoing/OngoingActivity)
  Pairs naturally with (a): the foreground service's mandatory notification *becomes* the Ongoing Activity
  surface instead of being a second, separate icon.

**Recommendation for the live demo:** foreground service with a short long-poll (or a single persistent
connection to a small SSE-style endpoint added to `serve.py`), active only while `brain.runs[id].status ==
"waiting"`; represented as an Ongoing Activity so the required persistent notification doubles as the
"approval pending" indicator instead of looking like app clutter.

---

## 6. Approval UI on the watch

- **Full-screen intents are not supported on Wear OS.** `setFullScreenIntent()`/`USE_FULL_SCREEN_INTENT` do not
  work there; Google's own guidance is to use expandable notifications instead.
  [Android Developers — Notifications on Wear OS](https://developer.android.com/training/wearables/notifications)
  Don't port a phone-style lock-screen takeover.
- **Pattern:** a high-priority `NotificationCompat` with two actions (Approve / Deny), collapsed state
  glanceable, expanding to show the preview text and judge confidence; tapping the body (not an action button)
  opens a small Compose-for-Wear screen with the full card — matching engram's existing
  `pending = {tool, effect, preview, judge: {p, ...}}` shape from `serve.py`'s `AgentRun`.
- **Compose for Wear Material 3** (`androidx.wear.compose:compose-material3`, now the recommended library over
  the older `wear.compose.material`) ships `Confirmation`/`SuccessConfirmation` composables for post-tap
  feedback and swipe-to-dismiss out of the box.
  [Wear Compose for Material 3 release notes](https://developer.android.com/jetpack/androidx/releases/wear-compose-m3)
  Haptics for the buzz itself go through the standard `Vibrator`/`VibrationEffect` APIs.
- **Fit with engram's tiers:** E-controlled-execution-security.md already concludes the watch (the
  lowest-attention approval channel) should be reserved for **T1/T2** only, with high-impact/destructive actions
  forced onto the phone with biometric and a field the user must actually interact with, not a single tap (see E
  §"habituation"/"forced interaction", citing E29/E30/E32). engram's own `Effect` tiers in `act.py` —
  `read (0) < internal (1) < external (2) < destructive (3)` — map onto this directly: **route `internal` and
  `external` approvals to the watch; never surface `destructive` there.** Vary the notification's accent/haptic
  pattern per tier, per E29's habituation finding, so a T2 card doesn't look identical to a routine one.

---

## 7. Speech without the cloud

**(a) On-watch `SpeechRecognizer`.** `SpeechRecognizer.createOnDeviceSpeechRecognizer()` plus
`EXTRA_PREFER_OFFLINE` (API 31+) is the documented on-device path, but it fails outright if the on-device
language model isn't already downloaded, and several Wear-specific reports describe devices/emulators returning
"no selected voice recognition service" even where the API should be present.
[dev.to — keep platform speech recognition on-device](https://dev.to/roronoa_/keep-platform-speech-recognition-on-device-on-your-first-mobile-ai-pr-65g)
Whether Samsung's specific Wear build of the recognizer works, or even ships a real on-device model, on the
Galaxy Watch 5 is **UNVERIFIED**. More importantly: the plain (non-on-device) `RecognizerIntent`/`SpeechRecognizer`
default implementation calls out to a cloud service (Google's, or Samsung's) — which breaks the "nothing calls
a cloud service at runtime" judging claim outright, independent of whether it even works on this hardware.

**(b) The sovereign alternative (recommended): record on the watch, transcribe on the Mac.** Capture with
`AudioRecord` at 16 kHz mono PCM16 (the smallest format that's still good for speech ASR — no `MediaRecorder`
container/codec needed) under the `RECORD_AUDIO` permission, then POST the raw bytes over the Wi-Fi path from §4
to a new `/api/transcribe` endpoint on `serve.py`.

**Mac-side local ASR options (Apple M5 Pro, 24 GB):**

| Option | Install | Speed (Apple Silicon, 2026 benchmarks) | Size | ffmpeg? | Fit for a Python/uv project |
|---|---|---|---|---|---|
| **mlx-whisper** (`whisper-large-v3-turbo`) | `pip install mlx-whisper` | 14–30× real-time reported across multiple 2026 benchmarks; large-v3-turbo ≈14–18× real-time on M5-class chips | ~1.5 GB (turbo) vs ~3 GB (large-v3) | No, for the direct Python API (own audio loader) | **Best fit** — pure pip/uv dep, matches the existing mlx/mlx-lm install already in engram's venv |
| **parakeet-mlx** (NVIDIA Parakeet-TDT via MLX) | `pip install parakeet-mlx` | Independently reported up to ~80 ms latency / 50–100×+ real-time for short clips; ~6% WER for the 0.6B English model family | ~0.6–2.5 GB depending on mirror | **CLI shells out to ffmpeg**; the Python `from_pretrained().transcribe()` API does not need it for WAV input | Good fit, full Python library API (`senstella/parakeet-mlx`, mirrored as `EliFuzz/parakeet-mlx`); English-only speed champion |
| **whisper.cpp** | build from source, or third-party bindings | Encoder offloaded to the Apple Neural Engine via Core ML for a 2–3× speedup over CPU-only; sub-1s encoder latency reported on M2+ | ~150 MB (tiny) to ~3 GB (large); 4-bit-quantized large-v3 ≈380 MB, ~1% WER cost | Yes, for anything beyond raw WAV input | Weakest fit — C/C++ core, needs its own Python bindings or a subprocess call |
| **Apple Speech framework / `SpeechAnalyzer`** (macOS 26+) | built into the OS | Fully on-device, "no network call anywhere in the pipeline"; already powers Notes/Voice Memos/Journal | 0 extra install (OS-managed model download) | N/A | Weakest fit for *this* stack — Swift/ObjC API (`import Speech`), needs PyObjC or a small Swift helper binary; adds a second toolchain to an otherwise pure-Python project |

Sources: [mlx-whisper install](https://huggingface.co/mlx-community/whisper-large-v3-turbo) ·
[Whisper Apple Silicon benchmarks (justvoice.ai)](https://justvoice.ai/blog/whisper-benchmark-apple-silicon-m3-m4) ·
[large-v3-turbo vs large-v3, 5× faster (whispernotes.app)](https://whispernotes.app/blog/introducing-whisper-large-v3-turbo) ·
[parakeet-mlx repo](https://github.com/senstella/parakeet-mlx) ·
[NVIDIA Parakeet on Mac, ~80ms (dicta.to)](https://dicta.to/blog/nvidia-parakeet-mac-app/) ·
[whisper.cpp README, Core ML encoder](https://github.com/ggml-org/whisper.cpp) ·
[Apple SpeechAnalyzer overview](https://developer.apple.com/documentation/speech/speechanalyzer) ·
[SpeechAnalyzer on-device, no network call (blog)](https://blog.addpipe.com/apple-speechanalyzer-api/)

**Recommendation:** **mlx-whisper with `whisper-large-v3-turbo`.** It sits next to engram's existing MLX
install with zero new toolchains, needs no ffmpeg on the direct-API path, and its published Apple-Silicon
latency (double-digit real-time multiples) means a ~5 s clip finishes transcribing in well under a second —
invisible next to the several-second `/api/ask` latency the project already has. Keep **parakeet-mlx** noted as
a documented upgrade path if English-only raw speed becomes the bottleneck later; remember its convenience CLI
(not its library) is the one that needs ffmpeg.

---

## 8. Security of exposing the local API to the LAN

- Run a **second** `ThreadingHTTPServer`, bound only to the Mac's LAN interface IP (never `0.0.0.0`), with its
  own handler/allow-list — keep the existing `127.0.0.1`-only page server exactly as it is today, don't relax it.
- **Pairing-token flow:** a loopback-only endpoint mints a short-lived, single-use pairing code (shown on the
  Mac's own page); the watch redeems it once for a long random bearer token (≥32 bytes of entropy); store only a
  **salted hash** of the token, never plaintext, on disk. This is the standard shape for exactly this problem —
  see one concrete instance of the pattern (unrelated project, cited only for the mechanism) in
  [titanarq/studentassistant PR #104](https://github.com/titanarq/studentassistant/pull/104).
- Require `Authorization: Bearer <token>` on every LAN-listener route except the pairing endpoint; additionally
  restrict accepted source IPs to RFC1918/link-local ranges as defense in depth — belt-and-suspenders with the
  token, matching the fail-safe-defaults principle E already cites (Saltzer, in
  E-controlled-execution-security.md).
- **Expose only what the watch needs:** `/api/ask`, `/api/add`, `/api/act`, `/api/act/<id>` (GET, for
  poll/SSE), `/api/act/<id>/decide`, and the new `/api/transcribe` (§7). **Keep localhost-only:** `/api/sql`
  (raw SQL, even read-only-role-scoped), `/api/graph`, `/api/ledger`, `/api/beliefs`, `/api/search`, and the HTML
  page itself — none of those need to leave the Mac for this demo.
- **Rate-limit** the pairing endpoint and `/api/act/*/decide` specifically, so a buggy or compromised watch app
  can't self-inflict a push-bombing loop — the same failure mode E31 already flags for approval requests
  generally.
- **Fail closed:** missing/invalid/expired token, or a Host/Origin mismatch, gets a 403 — reuse
  `serve.py`'s existing `_refuse_foreign` logic, keyed to the LAN host:port, rather than writing a looser
  special case for the watch.
- **Treat the LAN as only semi-trusted:** a venue phone hotspot may have other joined devices, and a
  self-signed TLS cert the watch must trust is impractical to set up under hackathon time pressure — the bearer
  token + IP allow-list + narrow endpoint surface above substitute for transport encryption. Say so explicitly
  as an accepted demo-time gap rather than imply it's solved.
- **Log every watch-originated request** (endpoint, decision, timestamp) into the same hash-chained
  `judgements`/ledger table the page uses, so a watch-approved action is auditable identically to a
  page-approved one — no separate, unaudited approval path.

---

## 9. Prior art

- **Home Assistant Assist on Wear OS.** The official Home Assistant Companion app ships an "Assist" tile on
  Wear OS; when configured with the **Wyoming protocol** and a local Whisper add-on, the whole voice pipeline —
  capture on the wearable, STT on the user's own server — runs with **no cloud call**.
  [Home Assistant — set up a fully local voice assistant](https://www.home-assistant.io/voice_control/voice_remote_local_assistant/) ·
  [Home Assistant — Assist on Android/Wear OS](https://www.home-assistant.io/voice_control/android/)
  **Relevance:** the closest fully-local precedent for "voice on a wearable → local STT → local assistant"; the
  Mac plays the same "local server does STT + reasoning" role engram already plans.
- **gabrielmarcano/agent-watch.** A real **Wear OS** (not Apple Watch) Compose app for answering coding agents
  (Claude Code, OpenCode, Antigravity CLI) from the wrist, via a local Go bridge that "only dials out: no open
  ports, no VPN," relaying through a self-hosted cloud service; the watch never sends raw keystrokes, only
  "answer option X," and the bridge re-verifies the on-screen prompt hasn't changed before acting.
  [GitHub — gabrielmarcano/agent-watch](https://github.com/gabrielmarcano/agent-watch)
  **Relevance:** directly on-point for "approve an agent's action from a Wear OS watch," but it depends on
  Firebase push plus a cloud relay hop — exactly what engram's no-FCM/direct-Wi-Fi requirement rules out. Worth
  borrowing its "bridge re-checks state before acting" idea, not its transport.
- **coder-knock/agent-watch-approval.** Pushes L2/L3-classified tool calls as a signed, one-shot card to
  iPhone/Apple Watch through a **self-hosted Home Assistant** instance — no third-party push, no long-lived
  device secrets, default-deny on timeout/signature-failure/unreachable, single-use tokens, JSONL audit trail.
  [GitHub — coder-knock/agent-watch-approval](https://github.com/coder-knock/agent-watch-approval)
  **Relevance:** Apple Watch, not Wear OS, but its tiering (L0/L1 silent-pass; L2/L3 escalate; L3 never
  auto-allows) and fail-closed design match engram's own effect tiers and E's fail-closed principle almost
  exactly — the best available template for the pairing/token/audit design in §8.
- **Agent Approve** (2026-07-07, already covered in F §2.23). Commercial iOS/Apple Watch app, one-tap
  approve/deny across 14+ coding agents, but an **E2E-encrypted cloud relay** at $14.99/mo.
  [Yahoo Finance coverage](https://finance.yahoo.com/technology/ai/articles/agent-approve-brings-ai-agent-123700683.html)
  **Relevance:** cited only to contrast with the direct-Wi-Fi, no-relay design this project needs — see F for
  the fuller writeup.
- **Samsung's own Wi-Fi pairing docs.** Samsung's developer blog posts for connecting a Galaxy Watch to Android
  Studio / Watch Face Studio over Wi-Fi are the most concrete first-party corroboration of the exact
  `adb pair`/`adb connect` flow in §3, even though they're not agent-related.
  [Samsung Developer blog — connect Galaxy Watch over Wi-Fi](https://developer.samsung.com/sdp/blog/en/2024/04/30/connect-galaxy-watch-to-android-studio-over-wi-fi)

---

## Recommendations

**Toolchain.** Skip Android Studio. JDK 17 (Temurin, 185.9 MB) + `cmdline-tools;latest` (148.2 MB) +
`platform-tools` (15.4 MB) + `build-tools;36.0.0` (75.5 MB) + `platforms;android-36` (62.8 MB) ≈ **488 MB of
SDK+JDK archives**, plus Gradle-wrapper/AndroidX-Compose-for-Wear dependency downloads on the first build
(budget **≈0.8–1.2 GB total**). Deploy straight to the physical Watch 5 over wireless `adb` — no
emulator/system-image ever needed. Fall back to Android Studio (≈1.49 GB `.dmg`, ≈8–9.5 GB installed,
UNVERIFIED precision on the installed figure) only if the team wants its Logcat/device-mirror GUI mid-hackathon
and can spare the extra download and install time.

**Networking.** Request a `TRANSPORT_WIFI` network via `ConnectivityManager.requestNetwork` +
`bindProcessToNetwork` only while the approval-listener or voice screen is foregrounded; release both the
network callback and the foreground service the moment they're idle, per Google's own battery guidance (§4).
Ship a `network_security_config.xml` cleartext exception scoped to the Mac's single LAN IP, never a blanket
allow.

**Approvals.** A foreground service (declared `dataSync`/`connectedDevice` FGS type) holding a short long-poll
or SSE connection to a new LAN-only endpoint on `serve.py`, surfaced to the user as an **Ongoing Activity** so
the mandatory persistent notification doubles as the "approval pending" indicator. Expandable high-priority
notification with Approve/Deny actions plus a Compose-for-Wear-Material3 detail screen for the full
tool/effect/preview/judge card. The watch handles only engram's `internal`/`external` effect tiers; `destructive`
never reaches it — consistent with E's T1/T2-on-watch, T3-on-phone-with-biometric guidance.

**Voice/ASR.** The watch does capture only — `AudioRecord`, 16 kHz mono PCM16, `RECORD_AUDIO` — and POSTs to a
new `/api/transcribe`. The Mac transcribes with **mlx-whisper** (`whisper-large-v3-turbo`): a plain
`pip`/`uv add` dependency next to the existing mlx/mlx-lm install, no ffmpeg needed on the direct-API path,
double-digit real-time multiples on Apple Silicon per multiple 2026 benchmarks — a 5 s clip should finish in a
fraction of a second, invisible next to `/api/ask`'s existing multi-second latency. Do not use the watch's
built-in `SpeechRecognizer`: whether it works on-device on this exact hardware is unverified, and the default
(non-on-device) path calls a cloud service regardless — a direct contradiction of the "nothing calls a cloud
service at runtime" judging claim.

**API/security.** A second `ThreadingHTTPServer` bound to the Mac's LAN interface, separate handler/allow-list
from the localhost one. One-time pairing code → long random bearer token, hashed at rest. Token + Host/Origin +
RFC1918-source checks on every LAN request, fail closed exactly like today's `_refuse_foreign`. Expose only
`/api/ask`, `/api/add`, `/api/act*`, `/api/transcribe`; keep `/api/sql`, `/api/graph`, `/api/ledger`, and the
page itself localhost-only. Log every watch-originated decision into the existing hash-chained ledger.

**Risk list and fallbacks for the live demo:**
- *Watch fails to join the venue Wi-Fi / hotspot flakes* → pre-pair and pre-test on the actual hotspot
  beforehand; keep the existing web page as a visible fallback narrative if the watch drops mid-demo.
- *`adb pair`/`connect` breaks after a reboot or Developer-options reset* → re-pairing takes under a minute; do
  it during setup, not live.
- *`requestNetwork`'s `onAvailable` never fires because the radio is asleep* → have the user wake the screen
  before relying on it; show an explicit "connecting…" state with a bounded timeout rather than a silent hang.
- *Foreground service/Ongoing Activity gets killed by Wear OS's aggressive Doze during a long gap between demo
  beats* → keep rehearsal runs short; add a manual "check now" pull-to-refresh as a fallback trigger.
- *ASR mis-transcribes in a noisy demo hall* → keep the existing typed/tapped note-add and ask flows in the web
  UI as the fallback input method; never make voice the only way to add a note or ask a question while judges
  are watching.
- *Battery drain from a held-open Wi-Fi socket + foreground service over a multi-hour demo day* → don't request
  the Wi-Fi network until the moment it's actually needed (see Networking above); charge between sessions.
- *LAN listener exposes more than intended* → keep the endpoint allow-list explicit and reviewed (§8); never
  proxy the localhost handler wholesale onto the LAN listener.

---

## Open questions

- Whether the team's actual Galaxy Watch 5 units are on Wear OS 5 (Android 14, API 34) or have already reached
  Wear OS 6 (Android 16, API 36) — the 2026 press coverage found here is contradictory; check *Settings → About
  watch → Software information* on the real device instead of trusting either report in §1.
  **Resolved 2026-09-28 (read over adb):** the team's watch is an SM-R905F (Galaxy Watch 5, 44 mm LTE) on
  **Wear OS 5 / One UI 6 Watch: Android 14, API 34**, build R905FXXU1CYI1. Its userspace is **32-bit
  (`armeabi-v7a`)**, so the app must avoid 64-bit-only native libraries. It has about 1.3 GB RAM. Target
  API 34 at runtime: foreground-service types are enforced, and API 35's `dataSync` time limits don't apply.
- Whether Samsung's Wear build of `SpeechRecognizer`/on-device recognition works at all on this specific watch
  — untested; the recommendation above is to skip it entirely rather than resolve this.
- Actual battery drain from holding `requestNetwork(TRANSPORT_WIFI)` plus a foreground service open for a
  multi-hour demo day — no published number was found; worth an on-device test before the event.
- Whether the venue's phone-hotspot Wi-Fi isolates connected clients from each other (some hotspot
  implementations block device-to-device traffic even on the same SSID) — test on the actual phone/carrier that
  will be used, not assumed.
- Precise WER/latency for parakeet-mlx vs. mlx-whisper specifically on short (~5 s) clips — most published 2026
  benchmarks measure long-form throughput, not short-utterance latency; worth a quick local A/B before
  committing to either.
