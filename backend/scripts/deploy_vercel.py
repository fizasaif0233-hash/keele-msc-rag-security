"""Deploy the API or the frontend to a temporary Vercel project.

Secrets are read from the local env files and passed to the CLI. They are not printed.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def redact(text: str, secrets: list[str]) -> str:
    cleaned = text
    for secret in secrets:
        if secret:
            cleaned = cleaned.replace(secret, "[hidden]")
    return cleaned


def deploy(cwd: Path, project: str, env: dict[str, str], build_env: dict[str, str] | None = None) -> str:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        sys.exit("npx was not found.")
    command = [
        npx,
        "vercel",
        "deploy",
        "--prod",
        "--yes",
        "--force",
        "--project",
        project,
        "--create-if-missing",
    ]
    for key, value in env.items():
        command.extend(["--env", f"{key}={value}"])
    for key, value in (build_env or {}).items():
        command.extend(["--build-env", f"{key}={value}"])
    child_env = dict(**{key: value for key, value in __import__("os").environ.items()})
    child_env["VLT_LINK_TYPE"] = "junction"
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, env=child_env)
    secrets = [value for value in [*env.values(), *(build_env or {}).values()] if value]
    output = redact(completed.stdout + "\n" + completed.stderr, secrets)
    print(output)
    if completed.returncode != 0:
        sys.exit(completed.returncode)
    start = output.find("{")
    end = output.rfind("}")
    if start != -1 and end > start:
        try:
            payload = json.loads(output[start:end + 1])
            deployment = payload.get("deployment") or {}
            url = deployment.get("productionUrl") or deployment.get("url")
            if url:
                return url if url.startswith("https://") else f"https://{url}"
        except json.JSONDecodeError:
            pass
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("https://"):
            return stripped
    sys.exit("No deployment URL was returned.")


def main() -> None:
    target = sys.argv[1]
    if target == "api":
        env = parse_env(BACKEND / ".env")
        env["STORAGE_DIR"] = "/tmp/uploads"
        url = deploy(BACKEND, "keele-msc-rag-api", env)
    elif target == "web":
        api_url = sys.argv[2].rstrip("/")
        local = parse_env(FRONTEND / ".env.local")
        public = {
            "NEXT_PUBLIC_SUPABASE_URL": local["NEXT_PUBLIC_SUPABASE_URL"],
            "NEXT_PUBLIC_SUPABASE_ANON_KEY": local["NEXT_PUBLIC_SUPABASE_ANON_KEY"],
            "NEXT_PUBLIC_API_URL": api_url,
        }
        url = deploy(FRONTEND, "keele-msc-rag-web", public, public)
    else:
        sys.exit("Use api or web.")
    print(f"DEPLOY_URL {url}")


if __name__ == "__main__":
    main()
