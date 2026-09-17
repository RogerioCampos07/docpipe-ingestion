from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config


def _config(database_path: Path) -> Config:
    project_root = Path(__file__).parents[3]
    config = Config(project_root / 'alembic.ini')
    config.set_main_option('script_location', str(project_root / 'migrations'))
    config.set_main_option('sqlalchemy.url', f'sqlite:///{database_path}')
    return config


def test_migrations_upgrade_empty_database_and_are_reversible(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / 'migration.db'
    config = _config(database_path)

    command.upgrade(config, 'head')

    engine = sa.create_engine(f'sqlite:///{database_path}')
    try:
        inspector = sa.inspect(engine)
        assert {'documents', 'outbox_events'} <= set(
            inspector.get_table_names()
        )
        assert {
            column['name'] for column in inspector.get_columns('documents')
        } == {
            'id',
            'original_name',
            'media_type',
            'size_bytes',
            'sha256',
            'storage_key',
            'status',
            'correlation_id',
            'created_at',
            'updated_at',
        }
        foreign_keys = inspector.get_foreign_keys('outbox_events')
        assert foreign_keys[0]['referred_table'] == 'documents'
    finally:
        engine.dispose()

    command.check(config)
    command.downgrade(config, 'base')

    engine = sa.create_engine(f'sqlite:///{database_path}')
    try:
        tables = set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()
    assert 'documents' not in tables
    assert 'outbox_events' not in tables

    command.upgrade(config, 'head')
