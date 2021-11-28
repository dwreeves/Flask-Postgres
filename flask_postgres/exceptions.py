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
