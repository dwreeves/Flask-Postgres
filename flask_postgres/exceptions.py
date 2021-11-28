import typing as t


class FlaskPostgresException(Exception):

    default: str = None

    def __init__(self, *args):
        if len(args) == 0 and self.default:
            args = [self.default]
        super().__init__(*args)


class SqlaExtensionNotFound(
        FlaskPostgresException,
        AttributeError
):
    default = (
        "The sqlalchemy extension was not registered to the current"
        " application."
    )


class EnvironmentNotAllowed(
        FlaskPostgresException,
        EnvironmentError
):
    default = (
        "This app has been configured so that Flask-Postgres does not run in"
        " this environment."
    )


class CommandLineModeNotActive(
    FlaskPostgresException,
    ValueError
):

    def __init__(self, *args, param=None, value=None):
        self.param = param
        self.value = value
        super().__init__(*args)

    param: str = None
    value: t.Any = None

    @property
    def default(self):
        return (
            f"You input {self.value!r} for the parameter {self.param!r}."
            " This is an invalid input when working outside of command line"
            " mode."
        )


class PostgresUrlNotSet(
        FlaskPostgresException,
        ValueError
):
    default = (
        "A target database URI has not been set. Please either set up the"
        " SQLALCHEMY_DATABASE_URI config variable (recommended), or"
        " alternatively, designate a database URI via the"
        " FLASK_POSTGRES_TARGET_DATABASE_URI config variable."
    )


class UriValidationError(
    FlaskPostgresException,
    TypeError,
):
    value: t.Any = None
    issue: t.Any = None

    def __init__(self, *args, value=None, issue=None):
        self.value = value
        self.issue = issue
        super().__init__(*args)

    @property
    def default(self):
        return (
            f"There was an issue validating a Postgres URI: {self.value!r}."
            f" The issue is: {self.issue}"
        )
