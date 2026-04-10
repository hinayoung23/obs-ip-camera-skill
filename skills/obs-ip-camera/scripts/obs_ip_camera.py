#!/usr/bin/env python3
import argparse
import configparser
import json
import plistlib
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import quote


OBS_APP = Path("/Applications/OBS.app")
OBS_SUPPORT = Path.home() / "Library/Application Support/obs-studio"
BLACKHOLE_DRIVER = Path("/Library/Audio/Plug-Ins/HAL/BlackHole2ch.driver")
DEFAULT_SOURCE_NAME = "IP Camera"
DEFAULT_RTSP_PATH = "/cam/realmonitor?channel=1&subtype={subtype}"
DEFAULT_PORTS = "80,443,554,8554,37777,8080"


def run(cmd, timeout=10):
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return 127, "", f"command not found: {cmd[0]}"
    except PermissionError as exc:
        return 77, "", f"operation not permitted: {cmd[0]} ({exc})"
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"


def redact(text, secrets):
    for secret in [s for s in secrets if s]:
        text = text.replace(secret, "******")
    return text


def parse_ports(raw):
    ports = []
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        ports.append(int(item))
    return ports


def build_rtsp_url(args, subtype=None):
    if args.rtsp_url:
        return args.rtsp_url
    if not args.ip:
        raise SystemExit("Provide --rtsp-url or --ip.")

    path = args.rtsp_path or DEFAULT_RTSP_PATH
    if subtype is None:
        subtype = args.subtype
    path = path.format(subtype=subtype)
    if not path.startswith("/"):
        path = "/" + path

    auth = ""
    if args.user:
        auth = quote(args.user, safe="")
        if args.password:
            auth += ":" + quote(args.password, safe="")
        auth += "@"
    return f"rtsp://{auth}{args.ip}:{args.port}{path}"


def port_state(ip, port, timeout=2):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return "open"
    except PermissionError:
        return "permission denied"
    except OSError:
        return "closed"


def obs_bundle_version():
    plist_path = OBS_APP / "Contents/Info.plist"
    if not plist_path.exists():
        return None
    with plist_path.open("rb") as fh:
        info = plistlib.load(fh)
    return info.get("CFBundleShortVersionString")


def obs_running():
    code, out, err = run(["ps", "-ax", "-o", "pid,command"], timeout=5)
    if code != 0:
        return [f"could not inspect processes: {err or out}"]
    return [line.strip() for line in out.splitlines() if "/OBS.app/Contents/MacOS/OBS" in line]


def latest_obs_log():
    log_dir = OBS_SUPPORT / "logs"
    if not log_dir.exists():
        return None
    logs = sorted(log_dir.glob("*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def probe_stream(args, subtype=None):
    if shutil.which("ffprobe") is None:
        return False, "ffprobe not found", None
    url = build_rtsp_url(args, subtype)
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-rtsp_transport",
        "tcp",
        "-timeout",
        str(args.timeout_us),
        "-i",
        url,
        "-show_entries",
        "stream=index,codec_type,codec_name,width,height,avg_frame_rate",
        "-of",
        "json",
    ]
    code, out, err = run(cmd, timeout=args.probe_timeout)
    if code != 0:
        return False, redact(err or out, [args.password, args.rtsp_url]), None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return False, "ffprobe returned non-JSON output", None
    return True, "ok", data.get("streams", [])


def find_scene_path(scene_path_arg):
    if scene_path_arg:
        return Path(scene_path_arg).expanduser()
    scene_dir = OBS_SUPPORT / "basic/scenes"
    if not scene_dir.exists():
        raise SystemExit(f"OBS scenes directory not found: {scene_dir}")
    files = sorted(scene_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise SystemExit(f"No OBS scene JSON files found in {scene_dir}")
    return files[0]


def update_profile_video(profile_path_arg, width, height, fps):
    if profile_path_arg:
        profile_path = Path(profile_path_arg).expanduser()
    else:
        profiles = sorted((OBS_SUPPORT / "basic/profiles").glob("*/basic.ini"))
        profile_path = profiles[0] if profiles else None
    if not profile_path or not profile_path.exists():
        print("WARN: OBS profile basic.ini not found; skipped video profile update")
        return

    config = configparser.ConfigParser()
    config.optionxform = str
    config.read(profile_path, encoding="utf-8")
    if "Video" not in config:
        config["Video"] = {}
    config["Video"]["BaseCX"] = str(width)
    config["Video"]["BaseCY"] = str(height)
    config["Video"]["OutputCX"] = str(width)
    config["Video"]["OutputCY"] = str(height)
    config["Video"]["FPSType"] = "0"
    config["Video"]["FPSCommon"] = str(fps)
    config["Video"]["ScaleType"] = "bicubic"
    with profile_path.open("w", encoding="utf-8") as fh:
        config.write(fh, space_around_delimiters=False)
    print(f"Updated OBS video profile: {profile_path}")


def camera_source(source_name, source_uuid, stream_url, input_format, ffmpeg_options):
    return {
        "prev_ver": 536936448,
        "name": source_name,
        "uuid": source_uuid,
        "id": "ffmpeg_source",
        "versioned_id": "ffmpeg_source",
        "settings": {
            "is_local_file": False,
            "input": stream_url,
            "input_format": input_format,
            "ffmpeg_options": ffmpeg_options,
            "buffering_mb": 2,
            "hw_decode": True,
            "restart_on_activate": True,
            "close_when_inactive": False,
            "clear_on_media_end": False,
            "looping": False,
            "speed_percent": 100,
        },
        "mixers": 255,
        "sync": 0,
        "flags": 0,
        "volume": 1.0,
        "balance": 0.5,
        "enabled": True,
        "muted": False,
        "push-to-mute": False,
        "push-to-mute-delay": 0,
        "push-to-talk": False,
        "push-to-talk-delay": 0,
        "hotkeys": {
            "MediaSource.Restart": [],
            "MediaSource.Play": [],
            "MediaSource.Pause": [],
            "MediaSource.Stop": [],
        },
        "deinterlace_mode": 0,
        "deinterlace_field_order": 0,
        "monitoring_type": 0,
        "private_settings": {},
    }


def configure_obs(args):
    running = obs_running()
    active = [row for row in running if not row.startswith("could not inspect")]
    if active and not args.force:
        print("OBS is running. Quit OBS before modifying scene JSON, or pass --force.")
        for row in active:
            print(f"  {row}")
        return 2

    ok, msg, streams = probe_stream(args)
    video = None
    if ok:
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        if video:
            print(
                "Stream video:",
                video.get("codec_name"),
                f"{video.get('width')}x{video.get('height')}",
                video.get("avg_frame_rate"),
            )
        print("Stream audio:", audio.get("codec_name") if audio else "none")
    else:
        print(f"WARN: stream probe failed before configuration: {msg}")

    source_w = int(video.get("width") or args.source_width) if video else args.source_width
    source_h = int(video.get("height") or args.source_height) if video else args.source_height
    scale_x = args.canvas_width / source_w if source_w else 1.0
    scale_y = args.canvas_height / source_h if source_h else 1.0
    stream_url = build_rtsp_url(args)

    scene_path = find_scene_path(args.scene)
    with scene_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    backup = scene_path.with_suffix(scene_path.suffix + f".bak-{time.strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(scene_path, backup)

    source_uuid = str(uuid.uuid4())
    data["sources"] = [s for s in data.get("sources", []) if s.get("name") != args.source_name]

    current_scene_name = data.get("current_scene")
    scene_source = None
    if current_scene_name:
        scene_source = next(
            (s for s in data["sources"] if s.get("id") == "scene" and s.get("name") == current_scene_name),
            None,
        )
    if scene_source is None:
        scene_source = next((s for s in data["sources"] if s.get("id") == "scene"), None)
    if scene_source is None:
        raise SystemExit("No OBS scene source found in scene JSON")

    settings = scene_source.setdefault("settings", {})
    items = [item for item in settings.get("items", []) if item.get("name") != args.source_name]
    next_id = max([item.get("id", 0) for item in items] + [0]) + 1
    settings["id_counter"] = max(settings.get("id_counter", 0), next_id)
    items.append(
        {
            "name": args.source_name,
            "source_uuid": source_uuid,
            "visible": True,
            "locked": False,
            "rot": 0.0,
            "pos": {"x": 0.0, "y": 0.0},
            "scale": {"x": scale_x, "y": scale_y},
            "align": 5,
            "bounds_type": 2,
            "bounds_align": 0,
            "bounds": {"x": float(args.canvas_width), "y": float(args.canvas_height)},
            "crop_left": 0,
            "crop_top": 0,
            "crop_right": 0,
            "crop_bottom": 0,
            "id": next_id,
            "group_item_backup": False,
            "scale_filter": "disable",
            "blend_method": "default",
            "blend_type": "normal",
            "show_transition": {"duration": 0},
            "hide_transition": {"duration": 0},
            "private_settings": {},
        }
    )
    settings["items"] = items
    data["sources"].append(
        camera_source(args.source_name, source_uuid, stream_url, args.input_format, args.ffmpeg_options)
    )

    with scene_path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=4)
        fh.write("\n")

    update_profile_video(args.profile, args.canvas_width, args.canvas_height, args.fps)
    print(f"Backed up scene: {backup}")
    print(f"Configured OBS source '{args.source_name}' in: {scene_path}")
    print("WARN: stream URLs with credentials are stored in OBS scene JSON as plaintext.")
    return 0


def check(args):
    if args.ip:
        print(f"Camera IP: {args.ip}")
        for port in parse_ports(args.ports):
            print(f"Port {port}: {port_state(args.ip, port)}")
    else:
        print("Network port checks skipped: pass --ip to test camera ports")

    if args.rtsp_url or args.ip:
        subtypes = [args.subtype] if args.rtsp_url else [0, 1]
        for subtype in subtypes:
            ok, msg, streams = probe_stream(args, subtype)
            label = "stream" if args.rtsp_url else f"RTSP subtype={subtype}"
            print(f"{label}: {msg}")
            if ok:
                for stream in streams:
                    if stream.get("codec_type") == "video":
                        print(
                            f"  video {stream.get('codec_name')} "
                            f"{stream.get('width')}x{stream.get('height')} "
                            f"{stream.get('avg_frame_rate')}"
                        )
                    elif stream.get("codec_type") == "audio":
                        print(f"  audio {stream.get('codec_name')}")
    else:
        print("Stream probe skipped: pass --rtsp-url or --ip")

    version = obs_bundle_version()
    print(f"OBS app: {'present' if OBS_APP.exists() else 'missing'} {version or ''}".strip())
    code, out, err = run(["xattr", "-l", str(OBS_APP)], timeout=5)
    quarantine = "com.apple.quarantine" in (out + err)
    print(f"OBS quarantine: {'present' if quarantine else 'absent'}")
    for row in obs_running():
        print(f"OBS running: {row}")

    print(f"BlackHole 2ch driver: {'present' if BLACKHOLE_DRIVER.exists() else 'missing'}")

    code, out, err = run(["systemextensionsctl", "list"], timeout=8)
    if code == 0:
        for line in out.splitlines():
            if "obsproject" in line.lower() or "camera" in line.lower():
                print(f"systemextension: {line}")
    else:
        print(f"systemextensionsctl failed: {err or out}")

    log_path = latest_obs_log()
    if log_path:
        print(f"Latest OBS log: {log_path}")
        interesting = []
        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            low = line.lower()
            if (
                "mac-virtualcam" in low
                or args.source_name in line
                or "ffmpeg_source" in low
                or "blackhole" in low
                or "permission for video" in low
                or "virtual camera" in low
            ):
                interesting.append(redact(line, [args.password, args.rtsp_url]))
        for line in interesting[-20:]:
            print(f"  {line}")
    return 0


def open_permissions(_args):
    urls = [
        "x-apple.systempreferences:com.apple.LoginItems-Settings.extension",
        "x-apple.systempreferences:com.apple.preference.security?Privacy_Camera",
        "x-apple.systempreferences:com.apple.preference.security",
    ]
    for url in urls:
        subprocess.run(["open", url], check=False)
    print("Opened macOS extension, camera, and security settings.")
    return 0


def start_virtualcam(_args):
    subprocess.run(["open", "-a", "OBS", "--args", "--startvirtualcam"], check=False)
    print("Requested OBS start with virtual camera.")
    return 0


def add_stream_args(parser, require_stream=False):
    parser.add_argument("--ip", help="Camera host/IP; optional if --rtsp-url is supplied")
    parser.add_argument("--user", help="Camera stream username")
    parser.add_argument("--password", help="Camera stream password")
    parser.add_argument("--port", type=int, default=554)
    parser.add_argument("--rtsp-url", help="Exact stream URL. Prefer this when known.")
    parser.add_argument("--rtsp-path", default=DEFAULT_RTSP_PATH, help="RTSP path; may contain {subtype}")
    parser.add_argument("--subtype", type=int, default=0)
    parser.add_argument("--timeout-us", type=int, default=5000000)
    parser.add_argument("--probe-timeout", type=int, default=12)
    parser.set_defaults(require_stream=require_stream)


def build_parser():
    parser = argparse.ArgumentParser(description="Configure and diagnose an IP camera stream via OBS.")
    sub = parser.add_subparsers(dest="command", required=True)

    check_parser = sub.add_parser("check")
    add_stream_args(check_parser)
    check_parser.add_argument("--ports", default=DEFAULT_PORTS)
    check_parser.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    check_parser.set_defaults(func=check)

    conf = sub.add_parser("configure-obs")
    add_stream_args(conf, require_stream=True)
    conf.add_argument("--scene")
    conf.add_argument("--profile")
    conf.add_argument("--source-name", default=DEFAULT_SOURCE_NAME)
    conf.add_argument("--input-format", default="rtsp")
    conf.add_argument("--ffmpeg-options", default="rtsp_transport=tcp")
    conf.add_argument("--canvas-width", type=int, default=1920)
    conf.add_argument("--canvas-height", type=int, default=1080)
    conf.add_argument("--fps", type=int, default=30)
    conf.add_argument("--source-width", type=int, default=1920)
    conf.add_argument("--source-height", type=int, default=1080)
    conf.add_argument("--force", action="store_true")
    conf.set_defaults(func=configure_obs)

    open_parser = sub.add_parser("open-permissions")
    open_parser.set_defaults(func=open_permissions)

    start_parser = sub.add_parser("start-virtualcam")
    start_parser.set_defaults(func=start_virtualcam)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    if getattr(args, "require_stream", False) and not (args.rtsp_url or args.ip):
        parser.error("configure-obs requires --rtsp-url or --ip")
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
