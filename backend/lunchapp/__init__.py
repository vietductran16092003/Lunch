"""Lunch App — ứng dụng đặt bữa trưa nội bộ.

Kiến trúc phân tầng:
    api/          Blueprint mỏng, chỉ đọc request và trả JSON
    services/     Toàn bộ nghiệp vụ, không phụ thuộc Flask
    repositories/ Mọi câu SQL
    models/       Thực thể và quy tắc thuộc về chính thực thể
    core/         Hạ tầng dùng chung (database, sự kiện, lỗi, phiên đăng nhập)
"""

from flask import Flask, jsonify
from flask_cors import CORS

from .api import (
    build_admin_blueprint,
    build_auth_blueprint,
    build_menu_blueprint,
    build_order_blueprint,
    build_system_blueprint,
)
from .config import Config, OrderStatus
from .container import ServiceContainer
from .core.errors import AppError

__all__ = ["create_app", "Config", "OrderStatus", "ServiceContainer"]


def create_app(config=Config, container: ServiceContainer | None = None) -> Flask:
    """Tạo ứng dụng Flask đã lắp đủ phụ thuộc.

    Truyền `container` riêng khi test để trỏ vào database tạm.
    """
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_BYTES
    CORS(app, supports_credentials=True)

    services = container or ServiceContainer.build(config)
    app.extensions["lunchapp"] = services

    _register_error_handlers(app, services, config)

    app.register_blueprint(build_system_blueprint(services, services.database,
                                                  services.events, config))
    app.register_blueprint(build_auth_blueprint(services))
    app.register_blueprint(build_menu_blueprint(services))
    app.register_blueprint(build_order_blueprint(services))
    app.register_blueprint(build_admin_blueprint(services))

    return app


def _register_error_handlers(app: Flask, services: ServiceContainer, config):
    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        """Một chỗ duy nhất đổi lỗi nghiệp vụ thành JSON, service không cần biết Flask."""
        return jsonify(error.to_dict()), error.status_code

    @app.errorhandler(413)
    def handle_too_large(_error):
        return jsonify({"error": services.uploads.size_limit_message()}), 413
