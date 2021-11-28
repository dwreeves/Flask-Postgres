import typing as t
import functools

import click
from flask.cli import ScriptInfo
from flask.cli import AppGroup

from flask_postgres.types import PostgresUri


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


class FlaskPostgresGroup(AppGroup):
    context_class = ContextWithTypoSuggestions
