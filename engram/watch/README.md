# engram for Wear OS

The owner's watch as a second way into engram. It does two things:
- **Approvals.** It buzzes when the gate escalates an action, and you approve or deny it on the watch. Destructive actions are shown but decided on the laptop.
- **Voice.** Say a question, or "remember …" to save a note. The clip is transcribed on the Mac with Whisper, so the audio never leaves the room.

It is a thin client: all thinking stays on the Mac (`engram serve --lan auto`). The design and evidence are in [`docs/research/notes/G-watch-agent.md`](../../docs/research/notes/G-watch-agent.md).

## Build and install (macOS, no Android Studio)

You need JDK 17, the Android command-line tools (platform-tools, build-tools 36, platform 37.2) and Gradle 9.8 or `./gradlew`.

```bash
export JAVA_HOME=$(/usr/libexec/java_home -v 17)
./gradlew assembleDebug
adb pair <watch-ip>:<pair-port> <code>     # once: Developer options → Wireless debugging → Pair new device
adb connect <watch-ip>:<port>              # the port changes whenever wireless debugging restarts
adb install -r -g app/build/outputs/apk/debug/app-debug.apk
```

## Pairing

1. On the Mac, run `uv run engram serve --lan auto`. It prints a one-time code, and `uv run engram watch pair` prints a fresh one.
2. Open engram on the watch. It finds the Mac over mDNS, so you only type the code.
3. Or pair from the laptop: `adb shell am start -n org.engram.watch/.MainActivity --es url http://<mac-ip>:8771 --es code <code>`

## How it stays connected

- **Wi-Fi, not the phone.** Wear OS normally routes traffic through the phone over Bluetooth, which cannot reach the Mac on the LAN. The app asks for Wi-Fi explicitly (`Net`) whenever it needs to talk to the Mac.
- **Galaxy watches still drop Wi-Fi.** They turn Wi-Fi off while asleep near the phone, even while the app asks for it. For demos, turn Bluetooth off on the watch, so Wi-Fi is its only link and stays up.
- **Approvals arrive by long-poll.** A foreground service, shown as an Ongoing Activity, holds a long-poll open to the Mac. There is no cloud push. A new approval arrives within about a second.
- **The Mac can move.** When the hotspot gives it a new address, the app finds it again over mDNS (`_engram._tcp`). The token is only sent after the server proves it holds the token's hash: an HMAC of a fresh nonce. A stranger announcing the same service learns nothing.

## Security trade-offs

- **Plain HTTP on the LAN.** The Mac's address changes from network to network, so it cannot be pinned in `network_security_config.xml`. Anyone on the same hotspot who can sniff traffic could read the bearer token and see requests.
- **What limits the damage.** The token only reaches the watch endpoints: ask, add, decide on non-destructive actions, and voice. The SQL console, graph, ledger and page stay on 127.0.0.1. Use your own hotspot, and revoke a watch with `engram watch forget <name>`.
- **Next step.** TLS with a pinned self-signed certificate, exchanged at pairing, would remove the sniffing risk.
