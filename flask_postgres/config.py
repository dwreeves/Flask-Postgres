import os
import typing as t
import warnings

from flask import has_app_context
from flask import current_app

from .exceptions import PostgresUrlNotSet


T = t.TypeVar("T")


# Lazy Loaders


def _target_database_uri_default() -> str:
    db_path = get("SQLALCHEMY_DATABASE_URI")
    if db_path:
        return db_path
    else:
        raise PostgresUrlNotSet


DEFAULT_CONFIG: t.Dict[str, t.Callable[[], t.Any]] = {
    "FLASK_POSTGRES_CLI_DISALLOWED_ENVS": lambda: set(),
    "FLASK_POSTGRES_ADMIN_PATH": lambda: "postgres",
    "FLASK_POSTGRES_TARGET_DATABASE_URI": _target_database_uri_default,
}


def get(key: str) -> t.Any:
    if has_app_context() and key in current_app.config:
        return current_app.config.get(key)
    elif key in os.environ:
        return os.environ.get(key)
    elif key in DEFAULT_CONFIG:
        return DEFAULT_CONFIG.get(key)()
    else:
        return None


def init_db_callback(func: T) -> T:
    current_callback = globals().get("registered_callback")
    if current_callback:
        warnings.warn(
            "One or more init_db_callback's were registered, even though"
            f" a init_db_callback, {current_callback!r}, already exists."
            f" The new callback, {func}, will be registered and replace the"
            " existing one.",
            UserWarning
        )
    globals()["registered_callback"] = func
    return func


def reset_init_db_callback():
    globals()["registered_callback"] = None


registered_callback: callable = None
