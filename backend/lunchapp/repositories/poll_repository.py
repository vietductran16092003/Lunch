"""Truy vấn bảng polls / poll_options / poll_votes."""

from ..models import Poll
from .base import BaseRepository


class PollRepository(BaseRepository):

    def find_open_for_date(self, target_date: str) -> Poll | None:
        return Poll.from_row(
            self._fetch_one(
                "SELECT * FROM polls WHERE poll_date = ? AND closed = 0 "
                "ORDER BY id DESC LIMIT 1",
                (target_date,),
            )
        )

    def find_by_id(self, poll_id) -> Poll | None:
        return Poll.from_row(self._fetch_one("SELECT * FROM polls WHERE id = ?", (poll_id,)))

    def create(self, question: str, poll_date: str, created_by, option_labels: list) -> int:
        with self.db.session(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO polls (question, poll_date, created_by) VALUES (?, ?, ?)",
                (question, poll_date, created_by),
            )
            poll_id = cursor.lastrowid
            cursor.executemany(
                "INSERT INTO poll_options (poll_id, label) VALUES (?, ?)",
                [(poll_id, label) for label in option_labels],
            )
            return poll_id

    def close(self, poll_id):
        self._execute("UPDATE polls SET closed = 1 WHERE id = ?", (poll_id,))

    def options_with_votes(self, poll_id) -> list:
        rows = self._fetch_all(
            """
            SELECT poll_options.id, poll_options.label,
                   COUNT(poll_votes.user_id) AS votes
            FROM poll_options
            LEFT JOIN poll_votes ON poll_votes.option_id = poll_options.id
            WHERE poll_options.poll_id = ?
            GROUP BY poll_options.id
            ORDER BY poll_options.id
            """,
            (poll_id,),
        )
        return [{"id": r["id"], "label": r["label"], "votes": r["votes"]} for r in rows]

    def option_belongs_to_poll(self, poll_id, option_id) -> bool:
        return self._fetch_one(
            "SELECT 1 FROM poll_options WHERE id = ? AND poll_id = ?", (option_id, poll_id)
        ) is not None

    def vote(self, poll_id, user_id, option_id):
        self._execute(
            "INSERT INTO poll_votes (poll_id, user_id, option_id) VALUES (?, ?, ?) "
            "ON CONFLICT(poll_id, user_id) DO UPDATE SET option_id = excluded.option_id, "
            "voted_at = CURRENT_TIMESTAMP",
            (poll_id, user_id, option_id),
        )

    def vote_of(self, poll_id, user_id):
        row = self._fetch_one(
            "SELECT option_id FROM poll_votes WHERE poll_id = ? AND user_id = ?",
            (poll_id, user_id),
        )
        return row["option_id"] if row else None
