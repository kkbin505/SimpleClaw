import base64
import logging
from googleapiclient.discovery import build
from google_auth import get_credentials

logger = logging.getLogger(__name__)


class GmailClient:
    def __init__(self):
        self.service = build("gmail", "v1", credentials=get_credentials())

    def get_unread_messages(self) -> list[dict]:
        results = self.service.users().messages().list(
            userId="me",
            labelIds=["INBOX", "UNREAD"],
            maxResults=20,
        ).execute()

        messages = results.get("messages", [])
        parsed = []
        for msg in messages:
            try:
                parsed.append(self._get_message(msg["id"]))
            except Exception as e:
                logger.error(f"Failed to fetch message {msg['id']}: {e}")
        return parsed

    def _get_message(self, msg_id: str) -> dict:
        msg = self.service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        return self._parse_message(msg)

    def _parse_message(self, msg: dict) -> dict:
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        return {
            "id": msg["id"],
            "subject": headers.get("Subject", ""),
            "sender": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "body": self._extract_body(msg["payload"]),
        }

    def _extract_body(self, payload: dict) -> str:
        """递归提取纯文本 body"""
        if "parts" in payload:
            for part in payload["parts"]:
                text = self._extract_body(part)
                if text:
                    return text
        elif payload.get("mimeType") == "text/plain":
            data = payload["body"].get("data", "")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        return ""

    def mark_as_read(self, msg_id: str):
        self.service.users().messages().modify(
            userId="me", id=msg_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    def add_label(self, msg_id: str, label_name: str = "AI_PROCESSED"):
        label_id = self._get_or_create_label(label_name)
        self.service.users().messages().modify(
            userId="me", id=msg_id, body={"addLabelIds": [label_id]}
        ).execute()

    def _get_or_create_label(self, label_name: str) -> str:
        labels = self.service.users().labels().list(userId="me").execute()
        for label in labels.get("labels", []):
            if label["name"] == label_name:
                return label["id"]
        created = self.service.users().labels().create(
            userId="me", body={"name": label_name}
        ).execute()
        return created["id"]
