# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the shader GUI smoke test through the Blender 4.2–5.1 adapter path.

The adapter is forced on Blender 5.3 so its temporary-file/crop logic can be
exercised without a second Blender installation.
"""

from __future__ import annotations

import os

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_export.py")
os.environ["NODEATLAS_FORCE_LEGACY"] = "1"
with open(path, encoding="utf-8") as handle:
    source = handle.read()
exec(compile(source, path, "exec"), {"__name__": "__main__", "__file__": path})
