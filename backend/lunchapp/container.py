"""Nơi lắp ráp toàn bộ phụ thuộc.

Chỉ có duy nhất chỗ này biết repository nào ghép với service nào. Muốn chạy test
với database tạm thì tạo một ServiceContainer khác, không phải sửa gì trong
service hay controller.
"""

from .config import Config
from .core import Database, EventBroker
from .repositories import (
    MenuRepository,
    OrderRepository,
    RestaurantRepository,
    UserRepository,
)
from .services import (
    AuthService,
    DashboardService,
    GrabService,
    MenuService,
    OrderService,
    ReportService,
    RestaurantService,
    UploadService,
)


class ServiceContainer:
    """Giữ mọi repository và service đã được lắp sẵn."""

    def __init__(self, database: Database, events: EventBroker, config=Config):
        self.config = config
        self.database = database
        self.events = events

        # Tầng truy cập dữ liệu
        self.users = UserRepository(database)
        self.menu_items = MenuRepository(database)
        self.restaurant_repo = RestaurantRepository(database)
        self.order_repo = OrderRepository(database)

        # Tầng nghiệp vụ
        self.grab = GrabService(config)
        self.uploads = UploadService(config)
        self.auth = AuthService(self.users, config)
        self.restaurants = RestaurantService(self.restaurant_repo, self.grab, events)
        self.menu = MenuService(
            self.menu_items, self.restaurant_repo, self.order_repo, events, config
        )
        self.orders = OrderService(
            self.order_repo, self.menu_items, self.users,
            self.restaurant_repo, events, config,
        )
        self.dashboard = DashboardService(self.order_repo, self.restaurant_repo, config)
        self.reports = ReportService(self.order_repo)

    @classmethod
    def build(cls, config=Config) -> "ServiceContainer":
        """Dựng container mặc định từ Config."""
        return cls(Database(config.DB_PATH), EventBroker(), config)
