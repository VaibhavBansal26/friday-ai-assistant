from pathlib import Path

import pytest

from friday.services.attachments import AttachmentService


def test_stores_supported_attachment_locally(tmp_path: Path):
    result = AttachmentService(tmp_path).store("diagram.png", "image/png", b"png-data")
    assert result["kind"] == "image"
    assert Path(result["path"]).read_bytes() == b"png-data"


def test_rejects_unsupported_and_unsafe_files(tmp_path: Path):
    service = AttachmentService(tmp_path)
    with pytest.raises(ValueError, match="Only images"):
        service.store("script.sh", "application/x-sh", b"bad")
    with pytest.raises(ValueError, match="filename"):
        service.store(".secret", "text/plain", b"bad")
