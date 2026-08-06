"""Bộ nối GrabFood.

Grab không có API công khai cho nhà hàng. Cào thẳng HTML của họ vừa vi phạm điều
khoản sử dụng vừa hỏng mỗi lần họ đổi giao diện, nên mặc định lớp này chỉ *phân
tích* đường dẫn quản trị viên dán vào, rồi để quản trị viên xác nhận lại.

Nếu môi trường triển khai có thỏa thuận riêng với Grab, bật GRAB_FETCH_ENABLED=1
để thử tải thêm dữ liệu công khai từ đường dẫn đó.
"""

import re
from urllib.parse import urlparse

from ..config import Config
from ..core.errors import ValidationError


class GrabService:
    HOSTS = ("food.grab.com", "www.grab.com", "grab.com")

    def __init__(self, config=Config):
        self.config = config

    def is_grab_url(self, url: str) -> bool:
        try:
            host = urlparse(url).netloc.lower()
        except ValueError:
            return False
        return any(host == h or host.endswith("." + h) for h in self.HOSTS)

    def parse_restaurant_url(self, url: str) -> dict:
        """Tách thông tin nhận dạng nhà hàng từ đường dẫn GrabFood."""
        url = (url or "").strip()
        if not url:
            raise ValidationError("Vui lòng dán đường dẫn nhà hàng trên GrabFood")

        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        if not self.is_grab_url(url):
            raise ValidationError("Đường dẫn phải thuộc food.grab.com")

        slug, external_id = self._split_path(urlparse(url).path)
        if not slug:
            raise ValidationError("Không đọc được tên nhà hàng từ đường dẫn")

        info = {
            "name": self._slug_to_name(slug),
            "grab_url": url,
            "external_id": external_id or slug,
            "address": None,
            "rating": None,
            "source": "url",
        }

        if self.config.GRAB_FETCH_ENABLED:
            enriched = self._try_fetch(url)
            if enriched:
                info.update({k: v for k, v in enriched.items() if v})
                info["source"] = "fetch"

        return info

    @staticmethod
    def _split_path(path: str) -> tuple:
        """Dạng phổ biến: /vn/vi/restaurant/<slug>/<external-id>"""
        segments = [s for s in path.split("/") if s]
        if "restaurant" in segments:
            rest = segments[segments.index("restaurant") + 1:]
            slug = rest[0] if rest else None
            external_id = rest[1] if len(rest) > 1 else None
            return slug, external_id
        return (segments[-1] if segments else None), None

    @staticmethod
    def _slug_to_name(slug: str) -> str:
        """'com-tam-ba-hanh' -> 'Com Tam Ba Hanh'.

        Chỉ là gợi ý ban đầu để quản trị viên sửa lại cho đúng dấu tiếng Việt.
        """
        cleaned = re.sub(r"[-_]+", " ", slug).strip()
        return re.sub(r"\s+", " ", cleaned).title()

    def _try_fetch(self, url: str) -> dict | None:
        """Chỉ chạy khi bật cờ. Mọi lỗi đều nuốt để luồng nhập tay vẫn dùng được."""
        try:
            import urllib.request

            request = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0 (compatible; LunchApp/1.0)"}
            )
            with urllib.request.urlopen(
                request, timeout=self.config.GRAB_FETCH_TIMEOUT
            ) as response:
                html = response.read(400_000).decode("utf-8", errors="ignore")
        except Exception:
            return None

        result = {}

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_match:
            title = re.sub(r"\s+", " ", title_match.group(1)).strip()
            title = re.split(r"\s*[|\-–]\s*(?:Grab|GrabFood)", title)[0].strip()
            if title:
                result["name"] = title

        rating_match = re.search(r'"rating(?:Value)?"\s*:\s*"?([0-9.]+)"?', html, re.IGNORECASE)
        if rating_match:
            try:
                rating = float(rating_match.group(1))
                if 0 < rating <= 5:
                    result["rating"] = rating
            except ValueError:
                pass

        address_match = re.search(r'"streetAddress"\s*:\s*"([^"]{3,200})"', html)
        if address_match:
            result["address"] = address_match.group(1)

        return result or None
