from .admin_routes import build_admin_blueprint
from .auth_routes import build_auth_blueprint
from .menu_routes import build_menu_blueprint
from .order_routes import build_order_blueprint
from .role_routes import build_role_blueprint
from .system_routes import build_system_blueprint

__all__ = [
    "build_admin_blueprint",
    "build_auth_blueprint",
    "build_menu_blueprint",
    "build_order_blueprint",
    "build_role_blueprint",
    "build_system_blueprint",
]
