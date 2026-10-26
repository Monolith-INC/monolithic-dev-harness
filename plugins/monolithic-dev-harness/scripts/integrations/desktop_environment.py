"""Allowlisted Linux desktop context for browser OAuth; explicit values always win."""

import os
import subprocess
import sys
from collections.abc import Mapping

from core.result import attempt, value_or

DESKTOP_KEYS = frozenset(
    {
        "DISPLAY",
        "WAYLAND_DISPLAY",
        "XAUTHORITY",
        "XDG_RUNTIME_DIR",
        "DBUS_SESSION_BUS_ADDRESS",
        "XDG_CURRENT_DESKTOP",
        "XDG_SESSION_DESKTOP",
        "DESKTOP_SESSION",
        "XDG_SESSION_TYPE",
        "XDG_DATA_DIRS",
        "XDG_CONFIG_DIRS",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
    }
)


def merge_desktop_environment(
    current: Mapping[str, str], desktop: str
) -> dict[str, str]:
    return {
        **dict(
            line.split("=", 1)
            for line in desktop.splitlines()
            if "=" in line and line.split("=", 1)[0] in DESKTOP_KEYS
        ),
        **current,
    }


def provider_environment() -> dict[str, str]:
    match (
        sys.platform,
        all(
            os.environ.get(key)
            for key in ("DBUS_SESSION_BUS_ADDRESS", "XDG_RUNTIME_DIR", "XDG_DATA_DIRS")
        ),
    ):
        case "linux", False:
            return merge_desktop_environment(
                os.environ,
                value_or(
                    attempt(
                        lambda: (
                            subprocess.run(
                                ["systemctl", "--user", "show-environment"],
                                env={
                                    "XDG_RUNTIME_DIR": f"/run/user/{os.getuid()}",
                                    "DBUS_SESSION_BUS_ADDRESS": f"unix:path=/run/user/{os.getuid()}/bus",
                                    **os.environ,
                                },
                                capture_output=True,
                                text=True,
                                check=True,
                                timeout=2,
                            ).stdout
                        ),
                        "desktop_unavailable",
                        "Desktop environment unavailable",
                        OSError,
                        subprocess.SubprocessError,
                    ),
                    "",
                ),
            )
        case _:
            return dict(os.environ)
