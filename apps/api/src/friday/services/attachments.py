from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4


class AttachmentService:
    MAX_BYTES = 100 * 1024 * 1024
    ALLOWED_PREFIXES = ("image/", "video/")
    ALLOWED_DOCUMENTS = {
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
        "text/markdown",
    }

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def store(self, filename: str, content_type: str, data: bytes) -> dict[str, object]:
        if not data or len(data) > self.MAX_BYTES:
            raise ValueError("Attachment must be between 1 byte and 100 MB")
        if not (content_type.startswith(self.ALLOWED_PREFIXES) or content_type in self.ALLOWED_DOCUMENTS):
            raise ValueError("Only images, videos, PDF, Word, text, and Markdown are supported")
        safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)[:160]
        if not safe_name or safe_name.startswith("."):
            raise ValueError("Attachment filename is invalid")
        attachment_id = str(uuid4())
        path = self.root / f"{attachment_id}-{safe_name}"
        path.write_bytes(data)
        kind = "image" if content_type.startswith("image/") else "video" if content_type.startswith("video/") else "document"
        return {"id": attachment_id, "name": safe_name, "kind": kind, "content_type": content_type, "size": len(data), "path": str(path)}
