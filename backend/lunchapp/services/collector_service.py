"""Ai đứng ra đặt/thu tiền của một ngày — không cố định ở admin.

Thực tế: một người trong phòng rủ mọi người đặt chung, tự đặt trên Grab và
thu tiền lại. Ai thêm món đầu tiên cho một ngày thì tự nhận ngày đó; từ lúc
đó chỉ người này (và admin — admin luôn được can thiệp mọi ngày) mới sửa
được thực đơn/chốt đơn/xác nhận thanh toán cho ngày đó.
"""

from ..config import Config, OrderStatus
from ..core.dates import Clock
from ..core.errors import ForbiddenError


class CollectorService:
    def __init__(self, order_owner_repository, user_repository, order_repository=None,
                 audit_service=None):
        self.owners = order_owner_repository
        self.users = user_repository
        # Cần để biết hôm nay còn đơn dở dang hay không (round_status) — không
        # bắt buộc, để test/nơi gọi cũ không truyền vẫn chạy được.
        self.orders = order_repository
        # Ghi vết ai claim/gỡ ngày nào — không bắt buộc, để test cũ không
        # truyền vẫn chạy được (im lặng bỏ qua audit thay vì lỗi).
        self.audit = audit_service

    def owner_of(self, order_date: str):
        """Trả về User đang phụ trách ngày này, hoặc None nếu chưa ai nhận."""
        user_id = self.owners.get_owner(order_date)
        return self.users.find_by_id(user_id) if user_id else None

    def authorize(self, user_id, is_admin: bool, order_date: str):
        """Chặn nếu ngày này đã có người khác phụ trách. Admin luôn qua được."""
        if is_admin:
            return
        owner_id = self.owners.get_owner(order_date)
        if owner_id is not None and int(owner_id) != int(user_id):
            owner = self.users.find_by_id(owner_id)
            name = owner.name if owner else "người khác"
            raise ForbiddenError(
                f"Ngày {order_date} đang do {name} phụ trách đặt hàng — bạn không sửa được."
            )

    def authorize_owner_only(self, user_id, order_date: str):
        """Như authorize() nhưng không cho admin đi tắt — dùng cho việc xác
        nhận đã nhận tiền, chỉ đúng người phụ trách ngày đó mới bấm được."""
        owner_id = self.owners.get_owner(order_date)
        if owner_id is None or user_id is None or int(owner_id) != int(user_id):
            owner = self.users.find_by_id(owner_id) if owner_id else None
            name = owner.name if owner else "chưa xác định"
            raise ForbiddenError(
                f"Chỉ người phụ trách đặt hàng ngày {order_date} ({name}) mới xác nhận nhận tiền được."
            )

    # ===== Bảng chính sách phân quyền =====
    # Mọi hành động gắn với "ai đang phụ trách một ngày" đi qua đúng MỘT trong
    # 3 quy tắc dưới đây — không tự viết lại điều kiện admin/owner ở route hay
    # service khác, để tránh mỗi chỗ hiểu "admin có đi tắt được không" một kiểu.
    #
    #   authorize()                      admin luôn qua — sửa thực đơn/chốt đơn
    #   authorize_owner_only()           admin KHÔNG đi tắt — xác nhận đã nhận
    #                                     tiền, sửa thông tin nhận tiền
    #   authorize_current_round()        admin qua được NẾU vòng chưa ai nhận;
    #                                     đã có người nhận thì kể cả admin cũng
    #                                     không đi tắt — gửi thông báo chung

    def authorize_current_round_owner_only(self, user_id, config=Config):
        """authorize_owner_only() nhưng tự tính ngày của VÒNG ĐANG MỞ (hôm nay
        nếu chưa quá giờ chốt, quá rồi thì ngày kế tiếp) thay vì nhận date từ
        nơi gọi — để mọi route dùng chung một cách tính "vòng hiện tại"."""
        self.authorize_owner_only(user_id, config.current_order_date())

    def authorize_current_round(self, user_id, is_admin: bool, config=Config):
        """Gửi thông báo chung: admin hoặc đúng chủ vòng đặt đang mở mới gửi
        được. Khác authorize() ở chỗ admin KHÔNG đi tắt nếu vòng đó đã có
        người khác nhận — chỉ được đi tắt khi vòng đó CHƯA ai nhận."""
        current_date = config.current_order_date()
        owner = self.owner_of(current_date)
        is_owner = bool(owner and int(owner.id) == int(user_id))

        if not (is_admin or is_owner):
            raise ForbiddenError(
                "Chỉ admin hoặc người đang phụ trách hôm nay mới gửi thông báo được"
            )
        if owner and not is_owner:
            raise ForbiddenError(f"Hôm nay đang do {owner.name} phụ trách — bạn không gửi được")

    def clear(self, order_date: str):
        """Gỡ người phụ trách — dùng khi xoá hẳn một ngày đã lỡ dựng. Việc ghi
        vết "ai bấm gỡ" do nơi gọi (biết actor_id thật sự) tự log, không log
        ở đây vì hàm này không nhận actor_id."""
        self.owners.clear(order_date)

    def claim(self, order_date: str, user_id):
        """Ghi nhận người đầu tiên đứng ra đặt cho ngày này — không ghi đè nếu
        đã có người nhận trước."""
        already_claimed = self.owners.get_owner(order_date) is not None
        self.owners.claim(order_date, user_id, Clock.now())
        if self.audit and not already_claimed:
            self.audit.log(user_id, "date_owner_claimed", "order_date", order_date)

    def authorize_and_claim(self, user_id, is_admin: bool, order_date: str):
        """Tiện ích gộp cho MenuService: kiểm quyền rồi tự nhận ngày luôn — dùng
        khi thêm món đầu tiên (người thêm tự thành chủ ngày nếu chưa ai nhận)."""
        self.authorize(user_id, is_admin, order_date)
        self.claim(order_date, user_id)

    def round_is_open(self, order_date: str) -> bool:
        """Ngày này đã có người nhận VÀ còn đơn nào chưa tới Hoàn tất."""
        owner_id = self.owners.get_owner(order_date)
        if owner_id is None or self.orders is None:
            return False
        orders = self.orders.list_for_date(order_date)
        return any(o.status != OrderStatus.COMPLETED for o in orders)
