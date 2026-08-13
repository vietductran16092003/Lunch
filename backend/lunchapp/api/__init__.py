from .admin_routes import build_admin_blueprint
from .ai_routes import build_ai_blueprint
from .auth_routes import build_auth_blueprint
from .coordinator_routes import build_coordinator_blueprint
from .fund_routes import build_fund_blueprint
from .menu_routes import build_menu_blueprint
from .notification_routes import build_notification_blueprint
from .order_routes import build_order_blueprint
from .role_routes import build_role_blueprint
from .system_routes import build_system_blueprint

__all__ = [
    "build_admin_blueprint",
    "build_ai_blueprint",
    "build_auth_blueprint",
    "build_coordinator_blueprint",
    "build_fund_blueprint",
    "build_menu_blueprint",
    "build_notification_blueprint",
    "build_order_blueprint",
    "build_role_blueprint",
    "build_system_blueprint",
]
