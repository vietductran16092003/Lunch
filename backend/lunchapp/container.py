"""Nơi lắp ráp toàn bộ phụ thuộc.

Chỉ có duy nhất chỗ này biết repository nào ghép với service nào. Muốn chạy test
với database tạm thì tạo một ServiceContainer khác, không phải sửa gì trong
service hay controller.
"""

from .config import Config
from .core import Database, EventBroker
from .repositories import (
    AuditLogRepository,
    CatalogRepository,
    DeadlineRepository,
    FundRepository,
    MenuRepository,
    NotificationRepository,
    OrderOwnerRepository,
    OrderRepository,
    RestaurantRepository,
    UserRepository,
)
from .services import (
    AiService,
    AuditService,
    AuthService,
    CollectorService,
    DashboardService,
    DeadlineService,
    FundService,
    GrabService,
    MenuService,
    NotificationService,
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
        self.deadline_repo = DeadlineRepository(database)
        self.fund_repo = FundRepository(database)
        self.notification_repo = NotificationRepository(database)
        self.catalog_repo = CatalogRepository(database)
        self.order_owner_repo = OrderOwnerRepository(database)
        self.audit_log_repo = AuditLogRepository(database)

        # Tầng nghiệp vụ
        self.grab = GrabService(config)
        self.uploads = UploadService(config)
        self.notifications = NotificationService(self.notification_repo, events)
        self.auth = AuthService(self.users, config, notifications=self.notifications)
        self.deadlines = DeadlineService(self.deadline_repo, config, event_broker=events)
        self.audit = AuditService(self.audit_log_repo)
        self.collectors = CollectorService(
            self.order_owner_repo, self.users, self.order_repo, audit_service=self.audit,
        )
        self.restaurants = RestaurantService(self.restaurant_repo, self.grab, events)
        self.menu = MenuService(
            self.menu_items, self.restaurant_repo, self.order_repo, events, config,
            catalog_repository=self.catalog_repo, collector_service=self.collectors,
        )
        self.orders = OrderService(
            self.order_repo, self.menu_items, self.users,
            self.restaurant_repo, events, config,
            deadline_service=self.deadlines, collector_service=self.collectors,
            audit_service=self.audit,
        )
        self.dashboard = DashboardService(
            self.order_repo, self.restaurant_repo, config,
            order_owner_repository=self.order_owner_repo,
        )
        self.reports = ReportService(self.order_repo)
        self.fund = FundService(
            self.fund_repo, self.order_repo, self.users, events, config,
            notifications=self.notifications,
        )
        self.ai = AiService(
            self.order_repo, self.menu_items, self.users, self.restaurant_repo,
            events, deadline_service=self.deadlines, config=config,
        )

    @classmethod
    def build(cls, config=Config) -> "ServiceContainer":
        """Dựng container mặc định từ Config."""
        return cls(Database(config.DB_PATH), EventBroker(), config)
