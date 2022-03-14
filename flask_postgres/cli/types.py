import typing as t
import functools

import click
from flask.cli import ScriptInfo
from flask.cli import AppGroup

from flask_postgres.types import PostgresUri

try:
    import rich_click
except ImportError:
    rich_click = None

from flask_postgres import config


__use_rich_click = config.get("FLASK_POSTGRES_RICH_CLICK")

if isinstance(__use_rich_click, str):
    __use_rich_click = __use_rich_click.lower() in ["1", "true", "yes", "y"]

if __use_rich_click and rich_click is None:
    import warnings
    warnings.warn("`FLASK_POSTGRES_RICH_CLICK` is set to True,"
                  " but Rich-Click is not installed."
                  " Defaulting to not using Rich-Click",
                  UserWarning)
    __use_rich_click = False


class ContextMixin(click.Parameter):

    def get_default(
            self,
            ctx: click.Context,
            *args,
            **kwargs
    ) -> t.Optional[t.Any]:
        with ctx.ensure_object(ScriptInfo).load_app().app_context():
            return super().get_default(ctx, *args, **kwargs)


class ContextOption(ContextMixin, click.Option):
    """Option that can load defaults with an active app context."""
    pass


class ContextArgument(ContextMixin, click.Argument):
    """Argument that can load defaults with an active app context."""
    pass


class PostgresUriParam(click.types.StringParamType):

    def convert(
        self,
        value: t.Any,
        param: t.Optional[click.Parameter],
        ctx: t.Optional[click.Context]
    ) -> t.Optional[PostgresUri]:
        if value is None or isinstance(value, PostgresUri):
            return value
        return PostgresUri(super().convert(value, param, ctx))


class ContextWithTypoSuggestions(click.Context):

    @functools.wraps(click.Context.fail)
    def fail(self, message: str, *args, **kwargs):
        if message == "No such command 'delete'.":
            message += " Perhaps you meant 'drop'?"
        if message == "No such command 'initialize'.":
            message += " Perhaps you meant 'init'?"
        if message == "No such command 'overwrite'.":
            message += " Perhaps you meant 'reset'?"
        return super().fail(message, *args, **kwargs)  # noqa


if __use_rich_click:

    class FlaskPostgresGroup(rich_click.RichGroup, AppGroup):
        context_class = ContextWithTypoSuggestions
        command_class = rich_click.RichCommand
        group_class = rich_click.RichGroup

else:

    class FlaskPostgresGroup(AppGroup):
        context_class = ContextWithTypoSuggestions
