from logging.config import fileConfig

from alembic import context

from docpipe_ingestion.infrastructure.database.base import Base
from docpipe_ingestion.infrastructure.database.engine import (
    create_database_engine,
)
from docpipe_ingestion.infrastructure.database import models  # noqa: F401
from docpipe_ingestion.infrastructure.settings import Settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _settings() -> Settings:
    configured_url = config.get_main_option('sqlalchemy.url')
    if configured_url:
        return Settings(database_url=configured_url)
    return Settings()


def run_migrations_offline() -> None:
    """Run migrations without creating a database connection."""
    settings = _settings()
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with the configured application engine."""
    engine = create_database_engine(_settings())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=connection.dialect.name == 'sqlite',
            )

            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
