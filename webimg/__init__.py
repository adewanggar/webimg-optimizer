"""
webimg: Smart Asset & Image Optimizer for Web/Social Media
"""

import sys

# Ensure UTF-8 output encoding across Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

__version__ = "0.1.0"
__app_name__ = "webimg"
