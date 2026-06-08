"""Gmail access (read-only): OAuth, list matching messages, fetch a message body."""
import base64
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from . import config

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _materialize_credentials() -> None:
    """Write credential files from env vars when running on a cloud host."""
    creds_path = Path(config.GMAIL_CREDENTIALS_FILE)
    if not creds_path.exists() and config.GMAIL_CREDENTIALS_JSON:
        creds_path.write_text(config.GMAIL_CREDENTIALS_JSON)

    token_path = Path(config.GMAIL_TOKEN_FILE)
    if not token_path.exists() and config.GMAIL_TOKEN_JSON:
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(config.GMAIL_TOKEN_JSON)


def get_service():
    """Return an authorized Gmail service. First run opens a browser to consent."""
    _materialize_credentials()
    creds = None
    token_path = Path(config.GMAIL_TOKEN_FILE)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                config.GMAIL_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=8080, open_browser=False)
        token_path.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def list_recent_message_ids(service, max_results: int = 10) -> list[str]:
    resp = (
        service.users()
        .messages()
        .list(userId="me", q=config.GMAIL_QUERY, maxResults=max_results)
        .execute()
    )
    return [m["id"] for m in resp.get("messages", [])]


def get_message_body(service, message_id: str) -> str:
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )
    return _extract_body(msg.get("payload", {}))


def _extract_body(payload: dict) -> str:
    """Walk the MIME tree and return the best body: text/html preferred over text/plain."""
    if payload.get("body", {}).get("data"):
        return _decode(payload["body"]["data"])

    parts = payload.get("parts", []) or []
    html_body = ""
    plain_body = ""

    for part in parts:
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data:
            if mime == "text/html" and not html_body:
                html_body = _decode(data)
            elif mime == "text/plain" and not plain_body:
                plain_body = _decode(data)
        else:
            # recurse into multipart/* containers
            nested = _extract_body(part)
            if nested and not html_body:
                html_body = nested

    return html_body or plain_body


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data.encode("utf-8")).decode("utf-8", errors="replace")
