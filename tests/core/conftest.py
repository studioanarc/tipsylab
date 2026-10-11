"""Kern-Tests laufen ohne Home Assistant: `core` und `tools` direkt importierbar machen."""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "custom_components", "tipsylab"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

