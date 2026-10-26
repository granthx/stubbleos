"""Alembic environment. The database URL comes from Settings (env), never from alembic.ini."""

from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy import engine_from_config, pool

from stubbleos.core.config import get_settings
from stubbleos.data.models import CORE, PII, Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

DB_URL = get_settings().database_url
config.set_main_option("sqlalchemy.url", DB_URL.replace("%", "%%"))
target_metadata = Base.metadata


def include_name(name: str | None, type_: str, parent_names: Any) -> bool:
    # PostGIS images ship extra schemas (tiger, topology); only manage ours.
    if type_ == "schema":
        return name in (None, CORE, PII)
    return True


def include_object(obj: Any, name: str | None, type_: str, reflected: bool, compare_to: Any) -> bool:
    return not (type_ == "table" and reflected and name == "spatial_ref_sys")


def run_migrations_offline() -> None:
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        include_name=include_name,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            include_name=include_name,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
