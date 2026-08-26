# Cell 3 — obtain GeoChat source code (model architecture)
import json
import subprocess
from pathlib import Path

config = json.loads(Path("/content/phase9b_geochat_smoke/smoke_config.json").read_text())
geochat_src = Path(config["geochat_src"])

if (geochat_src / "geochat").is_dir():
    print(f"GeoChat source already present at {geochat_src}")
else:
    print(f"Cloning {config['geochat_repo']} ...")
    subprocess.check_call(
        ["git", "clone", "--depth", "1", config["geochat_repo"], str(geochat_src)]
    )
    print("Clone complete.")

print("GeoChat package path:", geochat_src)
