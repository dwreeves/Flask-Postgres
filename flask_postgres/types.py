import re
import typing as t
import functools
import warnings

from flask_postgres._compat import psycopg
from flask_postgres import config
from flask_postgres.exceptions import UriValidationError


_db_regex = re.compile(
    r'(?:(?P<scheme>[a-z][a-z0-9\-.]+)(?:\+(?P<driver>[a-z0-9+\-.]+))?://)?'
    r'(?:(?P<user>[^\s:/]*)'
    r'(?::(?P<password>[^\s/]*))?@)?'
    r'(?P<host>[^\s/:?#]+)'
    r'(?::(?P<port>\d+))?'
    r'(?:/(?P<dbname>[^\s?#]*))?',
    re.IGNORECASE,
)


class _PsqlUriParts(t.NamedTuple):
    scheme: str
    driver: t.Optional[str]
    user: t.Optional[str]
    password: t.Optional[str]
    host: str
    port: t.Optional[t.Union[str, int]]
    dbname: str


class PostgresUri(str):

    __slots__ = _PsqlUriParts._fields
    _validate_when_initializing = True
    _validation_config = {
        "port_range": (0, 65535),
        "allowed_schemes": ["postgres", "postgresql"],
        "must_have_dbname": True,
        "regex": _db_regex
    }

    def __init__(
            self,
            uri: t.Optional[str] = None,
            *,
            scheme: str = "postgresql",
            driver: t.Optional[str] = "postgresql",
            user: t.Optional[str] = None,
            password: t.Optional[str] = None,
            host: str = "localhost",
            port: t.Optional[t.Union[str, int]] = 5432,
            dbname: str = None
    ):
        if uri is None:
            self.build(
                scheme=scheme,
                driver=driver,
                user=user,
                password=password,
                host=host,
                port=port,
                dbname=dbname
            )
        else:
            scheme, driver, user, password, host, port, dbname = \
                self._parts_from_str(uri)
        str.__init__(uri)
        self.scheme = scheme
        self.driver = driver
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.dbname = dbname
        if self._validate_when_initializing:
            self.validate(
                uri=uri,
                scheme=scheme,
                driver=driver,
                user=user,
                password=password,
                host=host,
                port=port,
                dbname=dbname
            )
            # ^ above validates that `port` is either int or None.
            # so we can turn it into an int here.
            if self.port is not None:
                self.port = int(self.port)

    @functools.wraps(__init__)
    def __new__(
            cls,
            uri: t.Optional[str] = None,
            **kwargs
    ) -> object:
        return str.__new__(
            cls,
            cls.build(**kwargs) if uri is None else uri  # noqa
        )

    @classmethod
    def _parts_from_str(
            cls,
            s: str
    ) -> _PsqlUriParts:
        match_obj = re.match(cls._validation_config["regex"], s)
        if match_obj is None:
            raise UriValidationError(
                value=s,
                issue="Could not parse as a valid URI."
            )
        return _PsqlUriParts(
            scheme=match_obj.group("scheme"),
            driver=match_obj.group("driver"),
            user=match_obj.group("user"),
            password=match_obj.group("password"),
            host=match_obj.group("host"),
            port=match_obj.group("port"),
            dbname=match_obj.group("dbname"),
        )

    @classmethod
    def build(
            cls,
            *,
            scheme: str = "postgresql",
            driver: t.Optional[str] = None,
            user: t.Optional[str] = None,
            password: t.Optional[str] = None,
            host: str = "localhost",
            port: t.Optional[t.Union[str, int]] = 5432,
            dbname: str,
    ) -> str:
        uri = scheme
        if driver is not None:
            uri += f"+{driver}"
        uri += "://"
        if user is not None:
            uri += user
        if password is not None:
            uri += ":" + password
        if user or password:
            uri += "@"
        uri += host
        if port is not None:
            uri += ":" + str(port)
        uri += f"/{dbname}"
        return uri

    @classmethod
    def validate(
            cls,
            uri: str,
            *,
            scheme: str = "postgresql",
            driver: t.Optional[str] = None,
            user: t.Optional[str] = None,
            password: t.Optional[str] = None,
            host: str = "localhost",
            port: t.Optional[t.Union[str, int]] = 5432,
            dbname: str,
    ) -> bool:
        if dbname is None and cls._validation_config["must_have_dbname"]:
            raise UriValidationError(
                value=uri,
                issue=f"The URI does not contain a database name."
            )
        if scheme.split("+")[0] not in cls._validation_config["allowed_schemes"]:
            raise UriValidationError(
                value=uri,
                issue=f"Scheme {scheme!r} not in"
                      f" {cls._validation_config['allowed_schemes']}."
            )
        if port is not None:
            try:
                int(port)
            except ValueError:
                raise UriValidationError(
                    value=uri,
                    issue=f"Could not cast port {port!r} to int."
                )
            _ = cls._validation_config["port_range"]
            lower, upper = min(_), max(_)
            if not (lower <= int(port) <= upper):
                raise UriValidationError(
                    value=uri,
                    issue=f"Invalid port {port!r}; must be between {lower}"
                          f" and {upper}."
                )
        return True

    @classmethod
    def default(cls) -> "PostgresUri":
        return cls(config.get("FLASK_POSTGRES_TARGET_DATABASE_URI"))

    def dict(self) -> t.Dict[str, t.Optional[t.Union[str, int]]]:
        return {i: getattr(self, i) for i in self.__slots__}

    def connection_dict(self) -> t.Dict[str, t.Optional[t.Union[str, int]]]:
        return {k: v for k, v in self.dict().items() if k in {"dbname", "user", "password", "host", "port"}}

    def admin_uri(self, dbname: t.Optional[str] = None) -> "PostgresUri":
        d = self.dict()
        dbname = dbname or config.get("FLASK_POSTGRES_ADMIN_DBNAME")
        if dbname.startswith("/"):
            warnings.warn(
                "Please do not put a slash in front of the"
                " `FLASK_POSTGRES_ADMIN_DBNAME`.",
                UserWarning
            )
            while dbname.startswith("/"):
                dbname = dbname[1:]
        d["dbname"] = dbname
        return self.__class__(**d)

    def connect(self) -> "psycopg.Connection":
        return psycopg.connect(str(self))
