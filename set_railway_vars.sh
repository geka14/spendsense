#!/bin/bash
# Run from repo root: bash set_railway_vars.sh
set -e
cd "$(dirname "$0")"

python3 - <<'EOF'
import json, subprocess, os

# Parse .env manually (handles values with spaces, colons, quotes)
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

vars_to_set = {
    "TELEGRAM_BOT_TOKEN":     env["TELEGRAM_BOT_TOKEN"],
    "TELEGRAM_CHAT_ID":       env["TELEGRAM_CHAT_ID"],
    "GMAIL_CREDENTIALS_JSON": creds,
    "GMAIL_TOKEN_JSON":       token,
    "DATABASE_PATH":          "/data/spendsense.db",
    "POLL_INTERVAL_SECONDS":  "60",
    "TIMEZONE":               "Asia/Jakarta",
    "WEEKLY_SUMMARY_DAY":     "mon",
    "WEEKLY_SUMMARY_HOUR":    "18",
    "WEEKLY_SUMMARY_MINUTE":  "0",
}

args = ["railway", "variables", "set"] + [f"{k}={v}" for k, v in vars_to_set.items()]
result = subprocess.run(args, capture_output=True, text=True)
if result.returncode == 0:
    print("Done. Railway will redeploy automatically.")
else:
    print("Error:", result.stderr)
    raise SystemExit(1)
EOF
