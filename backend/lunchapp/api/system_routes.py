"""Endpoint hạ tầng: trang gốc, health check, luồng thông báo, phục vụ ảnh."""

from flask import Blueprint, Response, jsonify, send_from_directory

from ..config import Config, OrderStatus
from ..core.security import require_login


def build_system_blueprint(services, database, events, config=Config) -> Blueprint:
    bp = Blueprint("system", __name__)

    @bp.get("/")
    def root():
        return jsonify({
            "message": "Lunch App API đang chạy. Đây là backend, giao diện nằm ở "
                       "địa chỉ frontend (thường là cổng 8080).",
            "health_check": "/api/health",
        })

    @bp.get("/api/health")
    def health():
        try:
            with database.session() as conn:
                conn.execute("SELECT 1")
            db_status = "ok"
        except Exception as e:
            db_status = f"error: {e}"

        return jsonify({
            "status": "ok",
            "database": db_status,
            "cutoff": config.cutoff_label(),
        })

    @bp.get("/api/config")
    def client_config():
        """Frontend đọc giờ chốt và nhãn trạng thái từ đây, không hardcode lại."""
        return jsonify({
            "cutoff": config.cutoff_label(),
            "cutoff_passed": config.cutoff_passed_today(),
            "steps": [
                {"key": key, "label": OrderStatus.label(key)} for key in OrderStatus.STEPS
            ],
        })

    @bp.get("/api/stream")
    @require_login
    def stream():
        q = events.subscribe()

        def generate():
            try:
                yield from events.stream(q)
            finally:
                events.unsubscribe(q)

        return Response(
            generate(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @bp.get("/api/uploads/<path:filename>")
    def serve_upload(filename):
        return send_from_directory(services.uploads.directory, filename)

    return bp
