"""baseline schema (matches core.database.Database.init_schema)

This is a bridge revision, not a from-scratch schema definition. The app
still owns and runs its schema via lunchapp.core.database.Database.init_schema()
on every boot (see run.py) -- that code is idempotent (CREATE TABLE IF NOT
EXISTS / add-column-if-missing) and keeps working exactly as before.

This migration exists so Alembic has a starting point to build *new* schema
changes on top of, going forward, instead of adding another branch to
_migrate_columns(). It reuses init_schema() rather than re-declaring the
schema a second time, so the two systems can't drift apart.

Any existing database (dev/prod) has already been fully migrated by
init_schema() before Alembic ever touches it, so upgrading here is a no-op
in practice; a brand new, empty database gets the exact same schema either
way. To adopt this baseline on an existing DB without re-running anything,
use `alembic stamp head`.

Revision ID: 24ac7b783b53
Revises:
Create Date: 2026-08-13 09:40:39.649454

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '24ac7b783b53'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from lunchapp.core.database import Database

    bind = op.get_bind()
    db_path = bind.engine.url.database
    Database(db_path).init_schema()


def downgrade() -> None:
    # No downgrade: this baseline maps 1:1 onto the app's own bootstrap
    # schema, which never drops tables. Tearing down the whole schema isn't
    # a meaningful operation here.
    raise NotImplementedError(
        "This baseline has no downgrade -- it mirrors Database.init_schema(), "
        "which is additive-only by design."
    )
