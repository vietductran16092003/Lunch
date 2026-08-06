"""Điểm khởi chạy backend.

    python run.py
"""

from lunchapp import Config, create_app
from lunchapp.container import ServiceContainer

container = ServiceContainer.build(Config)
app = create_app(Config, container)

if __name__ == "__main__":
    container.database.init_schema()
    # threaded=True là bắt buộc: mỗi kết nối /api/stream giữ một luồng riêng
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
