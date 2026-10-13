# Chimera Agent (Android)

Live H.264 screen-capture agent for the Chimera Enterprise platform.

## Build

Open the `agent-android/` folder in Android Studio (Hedgehog or newer) and let
Gradle sync. The project pins:

- Android Gradle Plugin 8.2
- Kotlin 1.9.22
- compileSdk 34, minSdk 26
- OkHttp 4.12 + kotlinx-coroutines

## Run

1. Connect the phone over USB and enable developer options.
2. `Build → Run 'app'` from Android Studio (or `gradle :app:installDebug`).
3. On the phone, fill in the server URL (e.g. `ws://192.168.1.10:17842`) and
   the device id from the Chimera dashboard.
4. Tap **Start streaming** and approve the MediaProjection prompt.

The agent connects to `/api/ws/stream/{device_id}` and pushes one Annex-B NAL
unit per binary frame. The Chimera viewer page (`Карта устройств`) will pick
the stream up automatically.
