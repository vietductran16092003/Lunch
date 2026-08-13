import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Repo dùng sqlite3 thô + SQL tay (không SQLAlchemy models), nên alembic chỉ
# đóng vai trò công cụ CHẠY migration — không có ORM metadata để autogenerate
# so sánh. Mọi migration ở đây viết SQL tay qua op.execute(), giống phong cách
# core/database.py.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Trỏ thẳng vào file DB mà app đang dùng (lunchapp.Config.DB_PATH) thay vì đọc
# sqlalchemy.url từ alembic.ini — để dev/test/production không phải khai báo
# trùng đường dẫn DB ở 2 nơi.
if not config.get_main_option("sqlalchemy.url"):
    from lunchapp.config import Config as AppConfig

    db_path = os.environ.get("LUNCH_DB_PATH", AppConfig.DB_PATH)
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Không dùng SQLAlchemy models nên không có metadata để autogenerate so sánh —
# migration mới phải viết tay bằng `alembic revision -m "..."` rồi tự điền SQL.
target_metadata = None

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
