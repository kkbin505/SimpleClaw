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
        msg_id = msg["id"]
        body = self._extract_body(msg["payload"])
        
        # 尝试提取 .ics 附件内容
        calendar_data = self._extract_calendar_data(msg["payload"], msg_id)
        if calendar_data:
            body += f"\n\n[日历附件内容 (ICS)]:\n{calendar_data}"

        return {
            "id": msg_id,
            "subject": headers.get("Subject", ""),
            "sender": headers.get("From", ""),
            "date": headers.get("Date", ""),
            "body": body,
        }

    def _extract_calendar_data(self, payload: dict, msg_id: str) -> str:
        """从附件中寻找并提取 .ics 内容"""
        if "parts" in payload:
            for part in payload["parts"]:
                data = self._extract_calendar_data(part, msg_id)
                if data:
                    return data
        
        mime_type = payload.get("mimeType")
        filename = payload.get("filename", "")
        
        if mime_type == "text/calendar" or filename.lower().endswith(".ics"):
            if "body" in payload and "data" in payload["body"]:
                data = payload["body"]["data"]
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
            elif "body" in payload and "attachmentId" in payload["body"]:
                att_id = payload["body"]["attachmentId"]
                return self._fetch_attachment(msg_id, att_id)
        return ""

    def _fetch_attachment(self, msg_id: str, attachment_id: str) -> str:
        """从 API 抓取附件二进制数据并转为文本"""
        try:
            attachment = self.service.users().messages().attachments().get(
                userId="me", messageId=msg_id, id=attachment_id
            ).execute()
            data = attachment.get("data", "")
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
        except Exception as e:
            logger.error(f"Failed to download attachment {attachment_id}: {e}")
            return f"（附件下载失败: {e}）"

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
