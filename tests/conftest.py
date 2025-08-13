# Ensure the src/ directory (with zoo package) is on sys.path for imports
import sys
import os

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)
