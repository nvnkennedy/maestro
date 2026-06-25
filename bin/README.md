# bin/ — bundled command-line tools

Drop standalone executables here and Maestro will find them automatically
(checked before your system `PATH`). The contents of this folder are bundled
into both the PyPI wheel (`scripts/build_pypi.py`) and the Windows installer
(`maestro.spec` → Inno Setup), so a packaged Maestro ships these tools.

## adb (for Android / `adb.*` steps)

Android steps (`adb.shell`, `adb.push`, `adb.screenshot`, …) need the Android
**platform-tools**.

1. Download *SDK Platform-Tools for Windows* from
   https://developer.android.com/tools/releases/platform-tools.
2. Extract the `platform-tools` folder into this directory, so `adb.exe` lives at:

   ```
   bin/platform-tools/adb.exe
   ```

`find_adb()` checks here first (before `PATH` / `ANDROID_HOME`).

## ffmpeg (for webcam image/video capture)

Webcam stills (`camera.capture_webcam`), webcam video (`camera.record_video`)
and device listing (`camera.list_devices`) need **ffmpeg**.

1. Download a Windows build from https://www.gyan.dev/ffmpeg/builds/ (or
   https://ffmpeg.org/download.html).
2. Copy **`ffmpeg.exe`** into this folder, so it lives at:

   ```
   bin/ffmpeg.exe
   ```

That's it — no PATH changes needed. (You can also keep ffmpeg on your system
PATH, or set `ffmpeg_path` on the camera step.)

To find your exact webcam name, run the **"List capture devices (ffmpeg)"**
step, then use that name as `camera_name`.
