"""Nghiệp vụ bình chọn quán ăn (Phase 4)."""

from ..core.dates import Clock
from ..core.errors import NotFoundError, ValidationError


class PollService:

    def __init__(self, poll_repository, event_broker):
        self.polls = poll_repository
        self.events = event_broker

    def create_poll(self, question: str, options: list, poll_date, created_by) -> dict:
        poll_date = Clock.date_or_today(poll_date)
        question = (question or "").strip() or "Hôm nay ăn quán nào?"

        labels = [o.strip() for o in (options or []) if o and o.strip()]
        # Bỏ trùng nhưng giữ thứ tự người tạo đã nhập
        labels = list(dict.fromkeys(labels))
        if len(labels) < 2:
            raise ValidationError("Cần ít nhất 2 lựa chọn để bình chọn")

        if self.polls.find_open_for_date(poll_date):
            raise ValidationError(f"Ngày {poll_date} đã có bình chọn đang mở")

        poll_id = self.polls.create(question, poll_date, created_by, labels)
        self.events.publish("poll_opened", {"poll_id": poll_id, "poll_date": poll_date})
        return self._load(poll_id)

    def current(self, target_date=None, user_id=None) -> dict:
        target_date = Clock.date_or_today(target_date)
        poll = self.polls.find_open_for_date(target_date)
        if poll is None:
            return {"poll": None, "date": target_date}
        return {"poll": self._load(poll.id, user_id)["poll"], "date": target_date}

    def vote(self, poll_id, option_id, user_id) -> dict:
        poll = self.polls.find_by_id(poll_id)
        if poll is None:
            raise NotFoundError("Không tìm thấy bình chọn")
        if poll.closed:
            raise ValidationError("Bình chọn đã đóng")
        if not self.polls.option_belongs_to_poll(poll_id, option_id):
            raise ValidationError("Lựa chọn không thuộc bình chọn này")

        self.polls.vote(poll_id, user_id, option_id)
        result = self._load(poll_id, user_id)
        self.events.publish("poll_voted", {"poll_id": poll_id})
        return result

    def close(self, poll_id) -> dict:
        poll = self.polls.find_by_id(poll_id)
        if poll is None:
            raise NotFoundError("Không tìm thấy bình chọn")
        self.polls.close(poll_id)
        self.events.publish("poll_closed", {"poll_id": poll_id})
        return self._load(poll_id)

    def _load(self, poll_id, user_id=None) -> dict:
        poll = self.polls.find_by_id(poll_id)
        poll.options = self.polls.options_with_votes(poll_id)
        voted_option_id = self.polls.vote_of(poll_id, user_id) if user_id else None
        return {"poll": poll.to_dict(voted_option_id)}
