#!/usr/bin/env python3
"""Standalone Gmail OAuth helper. Run from repo root with the venv active.
Saves a fresh token.json, then you can push it to Railway with set_railway_vars.sh."""
import json
import sys
import webbrowser
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
CREDS_FILE = "credentials.json"
TOKEN_FILE = "token.json"

if not Path(CREDS_FILE).exists():
    print(f"ERROR: {CREDS_FILE} not found. Run from the repo root.")
    sys.exit(1)

flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)

# Build the URL manually so we can print it even if webbrowser.open fails
auth_url, _ = flow.authorization_url(
    access_type="offline",
    prompt="consent",
    include_granted_scopes="true",
)

print("\n--- Gmail OAuth ---")
print("Open this URL in your browser and sign in:\n")
print(auth_url)
print()

# Also try to open automatically
webbrowser.open(auth_url)

print("After authorizing, Google will redirect to localhost.")
print("Waiting for callback on http://localhost:8080/ ...")
print("(If the redirect page shows an error that's fine — the token is still captured)\n")

creds = flow.run_local_server(port=8080, open_browser=False, success_message="Auth complete. Return to the terminal.")

Path(TOKEN_FILE).write_text(creds.to_json())
print(f"\nDone! {TOKEN_FILE} saved. Now run:  bash set_railway_vars.sh")
