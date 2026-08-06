"""Bộ nối GrabFood.

Grab không có API công khai cho nhà hàng. Cào thẳng HTML của họ vừa vi phạm điều
khoản sử dụng vừa hỏng mỗi lần họ đổi giao diện, nên mặc định module này chỉ
*phân tích* đường dẫn nhà hàng mà quản trị viên dán vào, rồi để quản trị viên xác
nhận lại tên/địa chỉ.

Nếu môi trường triển khai có thỏa thuận riêng với Grab, bật biến môi trường
GRAB_FETCH_ENABLED=1 để module thử tải thêm dữ liệu công khai từ đường dẫn đó.
Toàn bộ phần còn lại của ứng dụng không cần biết dữ liệu đến từ đâu.
"""

import os
import re
from urllib.parse import urlparse

GRAB_HOSTS = ("food.grab.com", "www.grab.com", "grab.com")
FETCH_ENABLED = os.environ.get("GRAB_FETCH_ENABLED") == "1"
FETCH_TIMEOUT_SECONDS = 6


class GrabUrlError(ValueError):
    """Đường dẫn không phải link nhà hàng GrabFood hợp lệ."""


def is_grab_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return False
    return any(host == h or host.endswith("." + h) for h in GRAB_HOSTS)


def _slug_to_name(slug: str) -> str:
    """'com-tam-ba-hanh-quan-1' -> 'Com Tam Ba Hanh Quan 1'.

    Chỉ là gợi ý ban đầu để quản trị viên sửa lại cho đúng dấu tiếng Việt.
    """
    cleaned = re.sub(r"[-_]+", " ", slug).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.title()


def parse_restaurant_url(url: str) -> dict:
    """Tách thông tin nhận dạng nhà hàng từ đường dẫn GrabFood.

    Trả về dict luôn có khóa: name, grab_url, external_id, address, rating, source.
    """
    url = (url or "").strip()
    if not url:
        raise GrabUrlError("Vui lòng dán đường dẫn nhà hàng trên GrabFood")

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    if not is_grab_url(url):
        raise GrabUrlError("Đường dẫn phải thuộc food.grab.com")

    parsed = urlparse(url)
    # Dạng phổ biến: /vn/vi/restaurant/<slug>/<external-id>
    segments = [s for s in parsed.path.split("/") if s]

    external_id = None
    slug = None
    if "restaurant" in segments:
        idx = segments.index("restaurant")
        rest = segments[idx + 1:]
        if rest:
            slug = rest[0]
        if len(rest) > 1:
            external_id = rest[1]
    elif segments:
        slug = segments[-1]

    if not slug:
        raise GrabUrlError("Không đọc được tên nhà hàng từ đường dẫn")

    info = {
        "name": _slug_to_name(slug),
        "grab_url": url,
        "external_id": external_id or slug,
        "address": None,
        "rating": None,
        "source": "url",
    }

    if FETCH_ENABLED:
        enriched = _try_fetch(url)
        if enriched:
            info.update({k: v for k, v in enriched.items() if v})
            info["source"] = "fetch"

    return info


def _try_fetch(url: str) -> dict | None:
    """Cố gắng đọc thêm tiêu đề/đánh giá từ trang công khai.

    Chỉ chạy khi GRAB_FETCH_ENABLED=1. Mọi lỗi đều nuốt và trả None để luồng
    nhập tay vẫn dùng được bình thường.
    """
    try:
        import urllib.request

        request = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; LunchApp/1.0)"},
        )
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
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
