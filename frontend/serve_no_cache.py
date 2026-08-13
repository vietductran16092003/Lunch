"""Server tĩnh cho thư mục frontend, luôn tắt cache — dùng khi phát triển để
khỏi phải Ctrl+Shift+R / Disable cache trong DevTools sau mỗi lần sửa JS/CSS.

Chạy: python serve_no_cache.py [port]  (mặc định port 8080)
"""

import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler


class NoCacheHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    HTTPServer(("", port), NoCacheHandler).serve_forever()
