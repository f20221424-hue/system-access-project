"""Root launcher — run the full governance pipeline with: python main.py"""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).parent / "src" / "main.py"), run_name="__main__")
