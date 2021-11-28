import warnings
import typing as t

import click
from flask import current_app
from flask.cli import AppGroup
from flask.cli import with_appcontext

from flask_postgres import config
from flask_postgres._compat import check_dependencies
from flask_postgres._compat import psycopg
from flask_postgres.cli.types import ContextOption
from flask_postgres.cli.types import PostgresUriParam
from flask_postgres.cli.types import FlaskPostgresGroup
from flask_postgres.ops import create_db
from flask_postgres.ops import drop_db
from flask_postgres.ops import may_not_exist_context
from flask_postgres.utils import get_db
from flask_postgres.utils import echo
from flask_postgres.utils import raise_err_if_disallowed
from flask_postgres.utils import resolve_init_db_callback
from flask_postgres.types import PostgresUri


FC = t.TypeVar("FC", t.Callable[..., t.Any], click.Command)


def get_connection(
        ctx: click.Context,
        uri: str
) -> "psycopg.Connection":
    conn = psycopg.connect(uri)
    conn.autocommit = True
    ctx.call_on_close(conn.close)
    return conn


def uri_option(
        operation_past_tense: str,
        **kwargs
) -> t.Callable[[FC], FC]:
    return click.option(
        "--uri", "-u", "uri",
        cls=ContextOption,
        type=PostgresUriParam(),
        default=lambda: config.get("FLASK_POSTGRES_TARGET_DATABASE_URI"),
        help=f"The URI of the database to be {operation_past_tense}. By"
             " default, this is either the FLASK_POSTGRES_TARGET_DATABASE_URI"
             " or (if that's undefined) the SQLALCHEMY_DATABASE_URI. These"
             " variables can be read either from the Flask app config or from"
             " environment variables.",
        **kwargs
    )


def force_delete_option(
        **kwargs
) -> t.Callable[[FC], FC]:
    return click.option(
        "--force", "-f",
        cls=ContextOption,
        is_flag=True,
        default=False,
        help="If true, then force delete the database.",
        **kwargs,
    )


def force_disconnect_option(
        operation_present_participle: str,
        **kwargs
) -> t.Callable[[FC], FC]:
    return click.option(
        "--force-disconnect", "-fd",
        is_flag=True,
        help="If set, then first attempt to force close all connections to the"
             f" database before {operation_present_participle} it.",
        **kwargs
    )


def overwrite_option(
        operation_present_participle: str,
        **kwargs
) -> t.Callable[[FC], FC]:
    return click.option(
        "--overwrite", "-o",
        is_flag=True,
        help="If set, then first attempt to delete before"
             f" {operation_present_participle} the database. When using this"
             " option, you can also `--force` delete the database and"
             " `--force-close` any connections.",
        **kwargs
    )


def admin_dbname_option(**kwargs) -> t.Callable[[FC], FC]:
    return click.option(
        "--admin-dbname", "-a",
        type=click.STRING,
        default=lambda: config.get("FLASK_POSTGRES_ADMIN_DBNAME"),
        # This one doesn't change too often. So we opt to eagarly load
        # the config variable, rather than treating this as something
        # that's "dynamic."
        show_default=config.get("FLASK_POSTGRES_ADMIN_DBNAME"),
        help="This is the admin database name to use when attempting to"
             " create or drop a database. You probably do not need to"
             " change this."
    )


def _resolve_extra_overwrite_params(
        ctx: click.Context,
        param: click.Parameter,
        value: t.Any
) -> t.Any:
    if not value or ctx.resilient_parsing:
        return value
    if not ctx.params.get("overwrite"):
        warnings.warn(
            f"Passing the flag for `{param.human_readable_name}` when not"
            " overwriting doesn't make sense.",
            SyntaxWarning
        )
    return value


@click.group("psql", cls=FlaskPostgresGroup)
@with_appcontext
def cli():
    """
    Manage your PostgreSQL database instance.
    """
    check_dependencies()
    raise_err_if_disallowed()


cli: AppGroup


@cli.command("create")
@uri_option("created")
@admin_dbname_option()
@force_delete_option(hidden=True,
                     callback=_resolve_extra_overwrite_params)
@force_disconnect_option("creating",
                         hidden=True,
                         callback=_resolve_extra_overwrite_params)
@overwrite_option("creating")
@with_appcontext
@click.pass_context
def create_db_command(
        ctx: click.Context,
        uri: PostgresUri,
        admin_dbname: t.Optional[str] = config.get("FLASK_POSTGRES_ADMIN_DBNAME"),
        overwrite: bool = False,
        **kwargs
):
    """Create the database."""
    if overwrite:
        ctx.forward(drop_db_command)
    admin_uri = uri.admin_uri(admin_dbname)
    conn = get_connection(ctx, admin_uri)
    return create_db(
        conn=conn,
        dbname=uri.dbname,
        command_line_mode=True
    )


create_db_command: click.Command


@cli.command("init")
@with_appcontext
def init_db_command(**kwargs):
    """Init the database."""
    with may_not_exist_context():
        db = get_db()
        if config.registered_callback:
            callback = resolve_init_db_callback(config.registered_callback)
            callback(current_app, db)
        else:
            db.create_all()
        echo(f'database "{db.engine.url.database}" was initialized')


init_db_command: click.Command


@cli.command("drop")
@uri_option("dropped")
@admin_dbname_option()
@force_delete_option()
@force_disconnect_option("dropping")
@with_appcontext
@click.pass_context
def drop_db_command(
        ctx: click.Context,
        uri: PostgresUri,
        admin_dbname: t.Optional[str] = config.get("FLASK_POSTGRES_ADMIN_DBNAME"),
        force: bool = False,
        force_disconnect: bool = False,
        **kwargs
):
    """Delete the database."""
    admin_uri = uri.admin_uri(admin_dbname)
    conn = get_connection(ctx, admin_uri)
    return drop_db(
        conn=conn,
        dbname=uri.dbname,
        command_line_mode=True,
        force_disconnect=force_disconnect,
        confirm=not force
    )


drop_db_command: click.Command


@cli.command("setup")
@uri_option("setup")
@admin_dbname_option()
@force_delete_option(hidden=True,
                     callback=_resolve_extra_overwrite_params)
@force_disconnect_option("setting up",
                         hidden=True,
                         callback=_resolve_extra_overwrite_params)
@overwrite_option("setting up")
@click.pass_context
@with_appcontext
def setup_db_command(
        ctx: click.Context,
        **kwargs
):
    """Create and init the database."""
    ctx.forward(create_db_command)
    ctx.forward(init_db_command)


setup_db_command: click.Command


@cli.command("reset")
@uri_option("reset")
@admin_dbname_option()
@force_delete_option()
@force_disconnect_option("resetting")
@click.pass_context
@with_appcontext
def reset_db_command(
        ctx: click.Context,
        **kwargs
):
    """Delete, then create and init the database."""
    ctx.forward(drop_db_command)
    ctx.forward(create_db_command)
    ctx.forward(init_db_command)


reset_db_command: click.Command
