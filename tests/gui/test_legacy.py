# SPDX-License-Identifier: GPL-3.0-or-later
"""Run the shader GUI smoke test through the Blender 4.2–5.1 adapter path.

The adapter is forced on Blender 5.3 so its temporary-file/crop logic can be
exercised without a second Blender installation.
"""

from __future__ import annotations

import os
import runpy

os.environ["NODEATLAS_FORCE_LEGACY"] = "1"
runpy.run_path(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_export.py"),
    run_name="__main__",
)
