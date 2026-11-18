"""Send local environment values to Vercel without printing them."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def add(key: str, value: str, cwd: Path) -> None:
    if not value:
        print(f"skipped {key}")
        return
    completed = subprocess.run(
        ["npx", "vercel", "env", "add", key, "production", "--yes", "--force"],
        input=value,
        text=True,
        cwd=cwd,
        capture_output=True,
    )
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "env add failed").strip().splitlines()
        safe = [line for line in message if value not in line]
        print(f"failed {key}: {' '.join(safe)[:300]}")
        sys.exit(completed.returncode)
    print(f"set {key}")


def main() -> None:
    target = Path(sys.argv[1])
    pairs = sys.argv[2:]
    if target.name == "frontend":
        source = parse_env(target / ".env.local")
    else:
        source = parse_env(target / ".env")
    for item in pairs:
        if "=" in item:
            key, value = item.split("=", 1)
        else:
            key, value = item, source[item]
        add(key, value, target)


if __name__ == "__main__":
    main()
