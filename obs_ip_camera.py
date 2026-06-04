#!/usr/bin/env python3
"""Entry point for obs-ip-camera CLI.

Delegates to the main script inside the skill directory.
"""
import importlib.util
import sys
from pathlib import Path

_script = (
    Path(__file__).resolve().parent
    / "skills" / "obs-ip-camera" / "scripts" / "obs_ip_camera.py"
)

spec = importlib.util.spec_from_file_location("obs_ip_camera_skill", _script)
_module = importlib.util.module_from_spec(spec)
sys.modules["obs_ip_camera_skill"] = _module
spec.loader.exec_module(_module)

# Expose main for the console_scripts entry point
main = _module.main

if __name__ == "__main__":
    sys.exit(main())
