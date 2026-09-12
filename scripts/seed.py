import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.seed_data import run_seed, DOMAINS

run_seed()
print(f"Seed completed: {len(DOMAINS)} domains, {len(DOMAINS)*5} indicators.")
