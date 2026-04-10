# OBS IP Camera Skill

将通用 IP 摄像头的视频流接入 OBS Studio，再通过 OBS Virtual Camera 提供给 QQ、Zoom、Teams、Google Meet、浏览器会议或其他视频通话软件。

仓库里的 Codex skill 位于：

```text
skills/obs-ip-camera
```

它不是某个厂商的专用工具。只要摄像头能提供 RTSP 或类似的可播放流地址，就可以按这个流程排查和接入。

## 适用场景

- 把 IP 摄像头作为电脑虚拟摄像头使用
- 用 OBS 管理网络摄像头画面、裁切、缩放、叠加素材
- 排查 `OBS Virtual Camera` 在会议软件里不显示的问题
- 将摄像头麦克风或 OBS 音频通过 BlackHole 等虚拟声卡送入通话软件
- 复用一套 macOS + OBS + IP 摄像头的排障流程

## 环境要求

- macOS
- OBS Studio，建议安装到 `/Applications/OBS.app`
- Codex 或兼容 Codex skill 目录结构的环境
- `ffprobe`，通常随 FFmpeg 安装
- 可访问摄像头所在局域网
- 摄像头的流地址，或至少知道 IP、端口、用户名、密码和 RTSP 路径
- 可选：BlackHole 2ch，用于把 OBS 音频路由到会议软件

常见依赖安装方式：

```bash
brew install ffmpeg
brew install --cask obs
brew install --cask blackhole-2ch
```

不同 macOS 版本、OBS 版本、会议软件版本的权限入口可能略有差异。遇到虚拟摄像头不可见时，优先检查 macOS 的相机扩展和相机权限。

## 安装 Skill

复制 skill 目录到本机 Codex skills 目录：

```bash
mkdir -p ~/.codex/skills
cp -R skills/obs-ip-camera ~/.codex/skills/obs-ip-camera
```

安装后可以在 Codex 中说：

```text
Use $obs-ip-camera to configure an IP camera stream through OBS Virtual Camera on macOS.
```

## 快速使用

如果已知完整 RTSP 地址：

```bash
python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py check \
  --rtsp-url 'rtsp://<user>:<password>@<camera-ip>:554/<path>'

python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py configure-obs \
  --rtsp-url 'rtsp://<user>:<password>@<camera-ip>:554/<path>' \
  --source-name 'IP Camera'
```

如果只知道 IP 和账号密码，并且摄像头使用常见 Dahua/Imou/Lecheng 风格 RTSP 路径：

```bash
python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py check \
  --ip 192.168.1.100 \
  --user admin \
  --password '<device-password>'

python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py configure-obs \
  --ip 192.168.1.100 \
  --user admin \
  --password '<device-password>' \
  --source-name 'IP Camera'
```

如果你的摄像头 RTSP 路径不同，传入自定义路径：

```bash
python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py configure-obs \
  --ip 192.168.1.100 \
  --user admin \
  --password '<device-password>' \
  --rtsp-path '/Streaming/Channels/101' \
  --source-name 'Front Door'
```

## 常见 RTSP 路径

这些只是示例，不保证适用于所有设备：

```text
/cam/realmonitor?channel=1&subtype=0
/Streaming/Channels/101
/h264/ch1/main/av_stream
/live/ch0
```

建议优先从摄像头说明书、厂商 App、ONVIF 工具或设备管理页面确认准确地址。

## OBS 操作流程

1. 先用 `check` 验证摄像头端口和流是否可播放。
2. 完全退出 OBS。
3. 运行 `configure-obs` 写入 OBS 场景配置。
4. 重新打开 OBS。
5. 检查场景中是否出现指定的媒体源，例如 `IP Camera`。
6. 在 OBS 里点击 `启动虚拟摄像机`。
7. 在目标通话软件中选择 `OBS Virtual Camera`。

脚本会在修改 OBS 场景 JSON 前自动创建备份文件。

## macOS 权限

如果会议软件提示没有检测到摄像头，通常是 OBS Virtual Camera 还没有被 macOS 批准。

打开权限页面：

```bash
python3 ~/.codex/skills/obs-ip-camera/scripts/obs_ip_camera.py open-permissions
```

然后检查：

```text
系统设置 -> 通用 -> 登录项与扩展 -> 扩展 -> 相机扩展
```

启用 `OBS Virtual Camera`。

还要检查：

```text
系统设置 -> 隐私与安全性 -> 相机
```

允许 OBS 和目标通话软件访问摄像头。

必要时重置某个应用的相机权限：

```bash
tccutil reset Camera com.obsproject.obs-studio
tccutil reset Camera <target-app-bundle-id>
```

应用的 bundle id 可以这样查看：

```bash
plutil -extract CFBundleIdentifier raw /Applications/App.app/Contents/Info.plist
```

## 音频路由

OBS Virtual Camera 只提供视频，不提供麦克风音频。

如果要把摄像头麦克风或 OBS 中的音频送到会议软件：

1. 安装并启用 BlackHole 2ch 或其他虚拟声卡。
2. 在 OBS 的 `高级音频属性` 中，将目标音频源设置为 `监听并输出`。
3. 在 OBS `设置 -> 音频 -> 高级` 中，把监听设备设置为 `BlackHole 2ch`。
4. 在会议软件中，把麦克风选择为 `BlackHole 2ch`。

建议佩戴耳机，避免扬声器声音被摄像头麦克风再次采集导致回声。

## 风险和注意事项

- RTSP URL 中如果包含用户名和密码，OBS 场景 JSON 会明文保存这些凭据。
- 不要把真实摄像头密码、公网 RTSP 地址或内网敏感地址提交到公开仓库。
- 优先为摄像头创建低权限账号，不要复用管理员密码。
- IP 摄像头音视频可能包含隐私信息；测试和分享日志前先检查是否包含地址、账号、设备名或截图。
- 打开摄像头远程访问、端口转发或公网暴露会增加安全风险。优先只在局域网或 VPN 内使用。
- 虚拟摄像头和虚拟声卡可能带来延迟，视频会议场景中需要实际测试同步情况。
- 一些会议软件需要完全退出后重开，才会重新枚举 `OBS Virtual Camera`。
- macOS 的相机扩展批准是用户级安全操作，脚本只能打开设置页面，不能替你绕过授权。

## 脚本命令

```bash
python3 skills/obs-ip-camera/scripts/obs_ip_camera.py check --help
python3 skills/obs-ip-camera/scripts/obs_ip_camera.py configure-obs --help
python3 skills/obs-ip-camera/scripts/obs_ip_camera.py open-permissions
python3 skills/obs-ip-camera/scripts/obs_ip_camera.py start-virtualcam
```

`check` 会检查端口、流信息、OBS 安装状态、BlackHole 是否存在、OBS Virtual Camera 扩展状态以及最近 OBS 日志中的关键行。

`configure-obs` 会向 OBS 场景中写入一个 `ffmpeg_source`，并设置常见会议软件适用的 `1920x1080 / 30fps` 输出。可以通过参数调整源名称、画布尺寸、FPS、RTSP 路径或完整 URL。
