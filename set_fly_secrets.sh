#!/bin/bash
# Push all secrets and env vars to Fly.io.
# Run from repo root: bash set_fly_secrets.sh
set -e
cd "$(dirname "$0")"

python3 - <<'EOF'
import json, subprocess, os

env = {}
with open(".env") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        env[key.strip()] = val.strip().strip('"').strip("'")

creds = json.dumps(json.load(open("credentials.json")))
token  = json.dumps(json.load(open("token.json")))

secrets = {
    "TELEGRAM_BOT_TOKEN":     env["TELEGRAM_BOT_TOKEN"],
    "TELEGRAM_CHAT_ID":       env["TELEGRAM_CHAT_ID"],
    "GMAIL_CREDENTIALS_JSON": creds,
    "GMAIL_TOKEN_JSON":       token,
}

args = ["fly", "secrets", "set"] + [f"{k}={v}" for k, v in secrets.items()]
result = subprocess.run(args, capture_output=True, text=True)
if result.returncode == 0:
    print("Secrets set. Fly will redeploy automatically.")
else:
    print("Error:", result.stderr)
    raise SystemExit(1)
EOF
