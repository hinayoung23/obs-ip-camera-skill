---
name: obs-ip-camera
description: Configure and troubleshoot generic IP cameras on macOS through RTSP or a supplied stream URL, OBS Studio media sources, OBS Virtual Camera, optional BlackHole audio routing, and arbitrary video-call apps. Use when the user wants to connect an IP camera to OBS, test camera network ports or RTSP streams, expose the camera as a virtual webcam, route camera audio to another app, or fix OBS Virtual Camera not appearing in apps such as QQ, Zoom, Teams, Meet, browsers, or other meeting/chat software.
---

# OBS IP Camera

## Workflow

Use the bundled helper first for repeatable checks and OBS scene edits:

```bash
python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py check --ip '<camera-ip>' --user '<user>' --password '<password>'
python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py configure-obs --ip '<camera-ip>' --user '<user>' --password '<password>' --source-name 'IP Camera'
python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py configure-obs --rtsp-url 'rtsp://user:pass@host:554/path' --source-name 'IP Camera'
python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py open-permissions
```

Do not assume a fixed vendor, IP, username, password, port, path, or target app. Ask the user for any missing camera details. If the exact stream URL is known, prefer `--rtsp-url`; otherwise use `--ip`, `--user`, `--password`, `--port`, and `--rtsp-path`.

## Discovering The Stream

1. Confirm the camera IP is reachable on likely ports: `554`, `8554`, `80`, `443`, vendor-specific ports, or user-provided ports.
2. Validate the stream with `ffprobe -rtsp_transport tcp`; record codec, resolution, frame rate, and whether audio is present.
3. If RTSP returns `401 Unauthorized`, ask for the camera's device password or app-generated stream credentials. Do not brute-force credentials.
4. If the camera is not RTSP-capable, ask whether it exposes ONVIF, HTTP-FLV, HLS, SRT, or a vendor app URL; configure OBS with the actual URL format when possible.

Common RTSP shapes to try only when relevant:

```text
rtsp://USER:PASSWORD@IP:554/cam/realmonitor?channel=1&subtype=0
rtsp://USER:PASSWORD@IP:554/Streaming/Channels/101
rtsp://USER:PASSWORD@IP:554/h264/ch1/main/av_stream
rtsp://USER:PASSWORD@IP:554/live/ch0
```

Treat these as examples, not defaults for every user.

## OBS Configuration

1. Check OBS is installed at `/Applications/OBS.app`.
2. If OBS starts through App Translocation or logs say the virtual camera cannot install outside `/Applications`, remove quarantine or reinstall/copy OBS cleanly into `/Applications`.
3. Quit OBS before editing scene JSON. Always back up the scene file first.
4. Add an OBS `ffmpeg_source` media source using the verified stream URL.
5. Set `input_format=rtsp` and `ffmpeg_options=rtsp_transport=tcp` for RTSP streams unless a different protocol requires different settings.
6. Set canvas/output resolution and FPS from the user's target use case; `1920x1080` and `30fps` is a good default for meeting apps.
7. Relaunch OBS and verify the latest log shows the source loaded and no repeated disconnect loop.

Warn the user that URLs containing credentials are stored in OBS scene JSON as plaintext.

## Virtual Camera And App Permissions

OBS Virtual Camera is what other apps see. The physical or IP camera source name usually will not appear directly in meeting apps.

If a target app says no camera is detected, inspect OBS logs and system extension state. Common blockers:

```text
[mac-virtualcam] macOS Camera Extension user approval required
OBS Virtual Camera [activated waiting for user]
```

Open the relevant macOS settings:

```bash
open 'x-apple.systempreferences:com.apple.LoginItems-Settings.extension'
open 'x-apple.systempreferences:com.apple.preference.security?Privacy_Camera'
open 'x-apple.systempreferences:com.apple.preference.security'
```

Tell the user to enable `OBS Virtual Camera` in:

```text
System Settings > General > Login Items & Extensions > Camera Extensions
```

Then quit and reopen OBS and the target app. Start OBS Virtual Camera and select `OBS Virtual Camera` in the target app. If the app has stale permissions, reset its Camera TCC entry using the app's bundle id:

```bash
tccutil reset Camera <bundle-id>
```

Examples: OBS is usually `com.obsproject.obs-studio`; another app's bundle id can be read with `plutil -extract CFBundleIdentifier raw /Applications/App.app/Contents/Info.plist`.

## Optional Audio Routing

OBS Virtual Camera carries video only. To route an IP camera microphone or any OBS audio source into another app:

1. Confirm OBS audio meters move for that source.
2. Install or verify a virtual audio device such as BlackHole.
3. In OBS Advanced Audio Properties, set the desired source to `Monitor and Output`.
4. In OBS Settings > Audio > Advanced, set Monitoring Device to the virtual audio device.
5. In the target app, choose that virtual audio device as microphone.

Warn about latency and echo. Recommend headphones when monitoring remote camera audio.
