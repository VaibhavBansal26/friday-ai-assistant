from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage as MimeEmailMessage
from urllib.parse import urlencode

import httpx

from friday.domain.models import EmailMessage, EmailThread


class GmailService:
    def __init__(self, client_id: str, redirect_uri: str, client_secret: str | None = None) -> None:
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self.client_secret = client_secret
        self.pending: dict[str, str] = {}
        self.access_token: str | None = None
        self.refresh_token: str | None = None

    @property
    def connected(self) -> bool:
        return self.access_token is not None

    def authorization_url(self) -> str:
        state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self.pending[state] = verifier
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
            "client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code",
            "scope": "openid email https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.compose https://www.googleapis.com/auth/gmail.send",
            "access_type": "offline", "prompt": "consent", "state": state,
            "code_challenge": challenge, "code_challenge_method": "S256",
        })

    def exchange(self, code: str, state: str) -> None:
        verifier = self.pending.pop(state, None)
        if not verifier:
            raise PermissionError("Invalid Gmail OAuth state")
        response = httpx.post("https://oauth2.googleapis.com/token", data={
            "client_id": self.client_id, "code": code, "code_verifier": verifier,
            "grant_type": "authorization_code", "redirect_uri": self.redirect_uri,
            "client_secret": self.client_secret or "",
        }, timeout=20)
        if not response.is_success:
            try:
                payload = response.json()
                description = str(payload.get("error_description", "")).replace("\n", " ")[:240]
                raise RuntimeError(f"Google token exchange rejected: {payload.get('error', 'unknown')} ({description})")
            except ValueError as exc:
                raise RuntimeError("Google token exchange rejected") from exc
        response.raise_for_status()
        payload = response.json()
        self.access_token, self.refresh_token = payload["access_token"], payload.get("refresh_token")

    def configure(self, client_secret: str) -> None:
        if not client_secret.strip():
            raise ValueError("Google client secret is required")
        self.client_secret = client_secret.strip()

    def refresh_access_token(self) -> None:
        if not self.refresh_token or not self.client_secret:
            raise PermissionError("Reconnect Gmail to obtain a refresh token")
        response = httpx.post("https://oauth2.googleapis.com/token", data={
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }, timeout=20)
        if response.status_code in {400, 401}:
            raise PermissionError("Gmail authorization expired; reconnect Gmail")
        response.raise_for_status()
        self.access_token = response.json()["access_token"]

    def recent_threads(self, user_id, limit: int = 20) -> list[EmailThread]:
        if not self.access_token:
            raise PermissionError("Connect Gmail first")
        self.refresh_access_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        listing = httpx.get("https://gmail.googleapis.com/gmail/v1/users/me/threads", params={"maxResults": limit, "q": "newer_than:7d"}, headers=headers, timeout=20)
        listing.raise_for_status()
        results: list[EmailThread] = []
        for item in listing.json().get("threads", []):
            response = httpx.get(f"https://gmail.googleapis.com/gmail/v1/users/me/threads/{item['id']}", params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject"]}, headers=headers, timeout=20)
            response.raise_for_status()
            messages = []
            for message in response.json().get("messages", []):
                values = {entry["name"].lower(): entry["value"] for entry in message.get("payload", {}).get("headers", [])}
                messages.append(EmailMessage(id=message["id"], sender=values.get("from", "Unknown"), recipients=[values.get("to", "")], subject=values.get("subject", "(no subject)"), body=message.get("snippet", ""), received_at=datetime.fromtimestamp(int(message.get("internalDate", "0")) / 1000, UTC)))
            if messages:
                results.append(EmailThread(id=item["id"], user_id=user_id, messages=messages))
        return results

    @staticmethod
    def _decoded_html(payload: dict) -> str:
        if payload.get("mimeType") == "text/html" and payload.get("body", {}).get("data"):
            encoded = payload["body"]["data"]
            return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode("utf-8", "replace")
        for part in payload.get("parts", []):
            value = GmailService._decoded_html(part)
            if value:
                return value
        return ""

    def microsoft_careers_alerts(self, on_date: date) -> list[dict]:
        """Read exact Microsoft Careers alerts for a UTC date; never mutates Gmail."""
        if not self.access_token:
            raise PermissionError("Connect Gmail first")
        self.refresh_access_token()
        headers = {"Authorization": f"Bearer {self.access_token}"}
        next_date = on_date + timedelta(days=1)
        query = (
            "from:donotreply@email.careers.microsoft.com "
            f"after:{on_date:%Y/%m/%d} before:{next_date:%Y/%m/%d} "
            'subject:"new job(s) at Microsoft" -in:spam -in:trash'
        )
        listing = httpx.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            params={"maxResults": 20, "q": query}, headers=headers, timeout=20,
        )
        listing.raise_for_status()
        alerts: list[dict] = []
        for item in listing.json().get("messages", []):
            response = httpx.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{item['id']}",
                params={"format": "full"}, headers=headers, timeout=20,
            )
            response.raise_for_status()
            message = response.json()
            received_at = datetime.fromtimestamp(int(message["internalDate"]) / 1000, UTC)
            if received_at.date() != on_date:
                continue
            header_values = {
                entry["name"].casefold(): entry["value"]
                for entry in message.get("payload", {}).get("headers", [])
            }
            alerts.append({
                "message_id": message["id"],
                "sender": header_values.get("from", "Microsoft Careers"),
                "subject": header_values.get("subject", "Microsoft Careers job alert"),
                "received_at": received_at,
                "message_url": f"https://mail.google.com/mail/#all/{message['id']}",
                "body_html": self._decoded_html(message.get("payload", {})),
            })
        return alerts

    def send_message(self, recipients: list[str], subject: str, body: str, thread_id: str | None = None) -> dict[str, str]:
        if not self.access_token:
            raise PermissionError("Connect Gmail before sending")
        if not recipients or not all("@" in item for item in recipients):
            raise ValueError("At least one valid recipient is required")
        self.refresh_access_token()
        message = MimeEmailMessage()
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode().rstrip("=")
        payload: dict[str, str] = {"raw": raw}
        if thread_id:
            payload["threadId"] = thread_id
        response = httpx.post(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
            json=payload,
            headers={"Authorization": f"Bearer {self.access_token}"},
            timeout=20,
        )
        response.raise_for_status()
        result = response.json()
        return {"message_id": str(result["id"]), "thread_id": str(result.get("threadId", thread_id or ""))}
