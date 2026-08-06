"""Lưu ảnh do quản trị viên tải lên."""

import os
import uuid

from werkzeug.utils import secure_filename

from ..config import Config
from ..core.errors import ValidationError


class UploadService:
    URL_PREFIX = "/api/uploads"

    def __init__(self, config=Config):
        self.config = config
        os.makedirs(self.config.UPLOAD_DIR, exist_ok=True)

    @property
    def directory(self) -> str:
        return self.config.UPLOAD_DIR

    def save(self, file) -> dict:
        """Nhận FileStorage của Flask, trả về đường dẫn dùng được trong thẻ <img>."""
        if file is None or not file.filename:
            raise ValidationError("Vui lòng chọn một file ảnh")

        if not self.config.is_allowed_image(file.filename):
            allowed = ", ".join(sorted(self.config.ALLOWED_IMAGE_EXTENSIONS))
            raise ValidationError(f"Chỉ chấp nhận ảnh định dạng: {allowed}")

        stored_name = self._build_name(file.filename)
        file.save(os.path.join(self.directory, stored_name))

        return {"url": f"{self.URL_PREFIX}/{stored_name}", "filename": stored_name}

    @staticmethod
    def _build_name(original: str) -> str:
        """Giữ lại phần tên gốc cho dễ nhận, thêm hậu tố ngẫu nhiên tránh trùng."""
        stem, extension = original.rsplit(".", 1)
        safe_stem = secure_filename(stem) or "anh"
        return f"{safe_stem[:40]}-{uuid.uuid4().hex[:8]}.{extension.lower()}"

    def size_limit_message(self) -> str:
        limit_mb = self.config.MAX_UPLOAD_BYTES // (1024 * 1024)
        return f"Ảnh vượt quá {limit_mb} MB, vui lòng chọn ảnh nhỏ hơn"
