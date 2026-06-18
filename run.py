"""Launch the AI Tutor Streamlit app."""
from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
    root = os.path.dirname(os.path.abspath(__file__))
    os.environ["PYTHONPATH"] = root
    app = os.path.join(root, "app.py")
    raise SystemExit(
        subprocess.call([sys.executable, "-m", "streamlit", "run", app])
    )


if __name__ == "__main__":
    main()
