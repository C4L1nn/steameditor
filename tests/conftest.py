import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIF_DIR = os.path.join(ROOT, "GIF")
for p in (ROOT, GIF_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)
