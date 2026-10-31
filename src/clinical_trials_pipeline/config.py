"""Project paths, resolved from this file so modules work from any working
directory (including notebooks/)."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / "output"
QUERIES_DIR = PROJECT_ROOT / "queries"
