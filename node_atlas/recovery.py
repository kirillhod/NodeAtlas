# SPDX-License-Identifier: GPL-3.0-or-later
"""Crash-safe copy of the editor appearance a capture changes.

The capture changes global preferences: the node background, the grid, the
selected-link tint, ``view.ui_scale`` and ``view.smooth_view``. Blender saves
preferences on a normal exit, so quitting during an export (or a crash that
still flushes preferences) can persist those temporary values. This module
writes them before the first change and offers a one-click restore afterwards;
it never touches the tree, the selection or the view.

The values live in the Blender config folder, not in the .blend, because they
belong to the session and must survive a restart (report section 5 item 26).
"""

from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass

import bpy

from . import capture
from .log import get_logger

log = get_logger()
VERSION = 1
NAME = "pending_export.json"

_PENDING = None
_LOADED = False


@dataclass
class Appearance:
    """The preferences a capture may change."""

    theme: str = ""
    backdrop: tuple[float, float, float] | None = None
    grid_levels: int | None = None
    link_alpha: float | None = None
    ui_scale: float = 1.0
    smooth_view: int = 1
    saved_at: float = 0.0


def path() -> str | None:
    """Return the recovery file path in the Blender config folder."""
    override = os.environ.get("NODEATLAS_RECOVERY_FILE")
    if override:
        return override
    try:
        folder = bpy.utils.user_resource("CONFIG", path="node_atlas", create=True)
    except Exception as exc:
        log.warning("Could not find the Blender config folder: %s", exc)
        return None
    return os.path.join(folder, NAME) if folder else None


def current() -> Appearance:
    """Read the appearance the capture is about to change."""
    prefs = bpy.context.preferences
    theme = prefs.themes[0] if len(prefs.themes) else None
    color = capture.link_highlight_color()
    return Appearance(
        theme=theme.name if theme is not None else "",
        backdrop=capture.current_theme_backdrop(),
        grid_levels=capture.current_theme_grid_levels(),
        link_alpha=float(color[3]) if color is not None else None,
        ui_scale=float(prefs.view.ui_scale),
        smooth_view=int(prefs.view.smooth_view),
        saved_at=time.time(),
    )


def save(appearance: Appearance, filepath: str | None = None) -> bool:
    """Write the marker before the first mutation. Never raises."""
    target = filepath or path()
    if target is None:
        return False
    try:
        folder = os.path.dirname(target)
        if folder:
            os.makedirs(folder, exist_ok=True)
        temporary = target + ".tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump({"version": VERSION, **asdict(appearance)}, handle)
        os.replace(temporary, target)
    except (OSError, TypeError, ValueError) as exc:
        log.warning("Could not write the editor recovery file: %s", exc)
        return False
    if filepath is None:
        _cache(None)
    return True


def load(filepath: str | None = None) -> Appearance | None:
    """Read a marker, or ``None`` when it is absent or malformed."""
    target = filepath or path()
    if target is None:
        return None
    try:
        with open(target, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        log.warning("Could not read the editor recovery file: %s", exc)
        return None
    return _appearance(data)


def clear(filepath: str | None = None) -> None:
    """Remove the marker. Never raises."""
    target = filepath or path()
    if target is not None:
        try:
            os.remove(target)
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning("Could not remove the editor recovery file: %s", exc)
    if filepath is None:
        _cache(None)


def reset_cache() -> None:
    """Forget the cached marker; the next :func:`pending` reads the file."""
    global _LOADED
    _cache(None)
    _LOADED = False


def pending() -> Appearance | None:
    """Return the interrupted appearance when it still needs a restore.

    A marker whose values already match the preferences means Blender did not
    save them before it exited: there is nothing to fix, so the panel stays
    clean and the file is left for another Blender instance.
    """
    global _PENDING, _LOADED
    if not _LOADED:
        _PENDING = load()
        _LOADED = True
    appearance = _PENDING
    if appearance is None:
        return None
    if not actionable(appearance):
        # The values already match, so Blender did not save them before it
        # exited. Keep the file: another Blender instance may be exporting and
        # may still need it.
        return None
    return appearance


def actionable(appearance: Appearance) -> bool:
    """Return whether restoring would change something that is still wrong."""
    now = current()
    if abs(now.ui_scale - appearance.ui_scale) > 1e-4:
        return True
    if now.smooth_view != appearance.smooth_view:
        return True
    if appearance.theme and appearance.theme != now.theme:
        # Theme values belong to their theme; do not touch another one.
        return False
    if appearance.grid_levels is not None and now.grid_levels != appearance.grid_levels:
        return True
    if appearance.backdrop is not None and now.backdrop is not None:
        if any(abs(a - b) > 1e-4 for a, b in zip(now.backdrop, appearance.backdrop)):
            return True
    if appearance.link_alpha is not None and now.link_alpha is not None:
        if abs(now.link_alpha - appearance.link_alpha) > 1e-3:
            return True
    return False


def apply(appearance: Appearance) -> tuple[list[str], list[str]]:
    """Restore the saved appearance. Returns ``(errors, warnings)``."""
    errors: list[str] = []
    warnings: list[str] = []
    now = current()
    theme_is_same = not appearance.theme or appearance.theme == now.theme
    if theme_is_same:
        if appearance.backdrop is not None:
            try:
                capture.set_theme_backdrop(appearance.backdrop)
            except Exception as exc:
                errors.append(f"background restore failed: {exc}")
        if appearance.grid_levels is not None:
            try:
                capture.set_theme_grid_levels(appearance.grid_levels)
            except Exception as exc:
                errors.append(f"grid restore failed: {exc}")
        if appearance.link_alpha is not None:
            try:
                color = capture.link_highlight_color()
                if color is not None:
                    color[3] = float(appearance.link_alpha)
            except Exception as exc:
                errors.append(f"link tint restore failed: {exc}")
    else:
        warnings.append(
            f"the active theme is {now.theme!r}, the saved one was "
            f"{appearance.theme!r}; theme colours were left unchanged"
        )

    prefs = bpy.context.preferences
    try:
        prefs.view.ui_scale = appearance.ui_scale
    except Exception as exc:
        errors.append(f"ui_scale restore failed: {exc}")
    try:
        prefs.view.smooth_view = appearance.smooth_view
    except Exception as exc:
        errors.append(f"smooth_view restore failed: {exc}")
    return errors, warnings


def _cache(appearance: Appearance | None) -> None:
    global _PENDING, _LOADED
    _PENDING = appearance
    _LOADED = True


def _appearance(data) -> Appearance | None:
    """Build an :class:`Appearance` from JSON, ignoring broken fields."""
    if not isinstance(data, dict) or data.get("version") != VERSION:
        return None
    ui_scale = _number(data.get("ui_scale"))
    smooth_view = _number(data.get("smooth_view"))
    if ui_scale is None or smooth_view is None:
        return None
    backdrop = None
    raw = data.get("backdrop")
    if isinstance(raw, (list, tuple)) and len(raw) == 3:
        values = [_number(channel) for channel in raw]
        if all(value is not None for value in values):
            backdrop = tuple(float(value) for value in values)
    grid = _number(data.get("grid_levels"))
    alpha = _number(data.get("link_alpha"))
    theme = data.get("theme")
    return Appearance(
        theme=theme if isinstance(theme, str) else "",
        backdrop=backdrop,
        grid_levels=int(round(grid)) if grid is not None else None,
        link_alpha=alpha,
        ui_scale=ui_scale,
        smooth_view=int(round(smooth_view)),
        saved_at=_number(data.get("saved_at")) or 0.0,
    )


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
