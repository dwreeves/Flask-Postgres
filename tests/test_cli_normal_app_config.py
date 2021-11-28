import typing as t
import pytest
import sqlalchemy as sa
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from flask_postgres.utils import database_exists
from flask_postgres import init_db_callback
from flask_postgres.config import reset_init_db_callback


@pytest.fixture
def db() -> SQLAlchemy:
    return SQLAlchemy()


@pytest.fixture
def example_model(db):
    class Pet(db.Model):
        id = db.Column(db.Integer, primary_key=True, autoincrement=True)
        name = db.Column(db.Text)
    return Pet


@pytest.fixture
def typically_configured_app(base_app, uri, db, example_model) -> Flask:
    base_app.config["SQLALCHEMY_DATABASE_URI"] = uri
    base_app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(base_app)
    return base_app


@pytest.fixture
def custom_init_db_callback(
        typically_configured_app: Flask,
        db: SQLAlchemy,
        example_model
):

    @init_db_callback
    def callback(db: SQLAlchemy):
        db.create_all()
        pet = example_model(name="Fido")
        db.session.add(pet)
        db.session.commit()

    yield

    reset_init_db_callback()


def test_psql_create_command(
        admin_connection,
        typically_configured_app: Flask,
        db_params: dict
):
    dbname = db_params.get("dbname")

    assert not database_exists(dbname, admin_connection)

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(typically_configured_app.cli, ["psql", "create"])

    assert res.exit_code == 0
    assert res.output == f'database "{dbname}" was created\n'
    assert database_exists(dbname, admin_connection)


def test_psql_init_command(
        typically_configured_app: Flask,
        activated_database,
        db,
        example_model,
        db_params: dict
):
    dbname = db_params.get("dbname")

    with typically_configured_app.app_context():
        db_inspector = sa.inspect(db.engine)
        assert not db_inspector.has_table("pet")

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(typically_configured_app.cli, ["psql", "init"])

    assert res.exit_code == 0
    assert res.output == f'database "{dbname}" was initialized\n'

    with typically_configured_app.app_context():
        db_inspector = sa.inspect(db.engine)
        assert db_inspector.has_table("pet")

    with typically_configured_app.app_context():
        first_row_of_data = db.session.query(example_model).first()
    assert first_row_of_data is None


def test_psql_init_command_when_db_not_created(
        typically_configured_app: Flask,
        db,
        example_model,
        db_params: dict,
        admin_connection
):
    dbname = db_params.get("dbname")

    assert not database_exists(dbname, admin_connection)

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(typically_configured_app.cli, ["psql", "init"])

    assert res.output == f'database "{dbname}" does not exist\n', res.output
    assert not database_exists(dbname, admin_connection)


def test_psql_init_command_with_custom_callback(
        typically_configured_app: Flask,
        activated_database,
        db_params: dict,
        db,
        example_model,
        custom_init_db_callback,
):
    dbname = db_params.get("dbname")

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(typically_configured_app.cli, ["psql", "init"])

    assert res.exit_code == 0, res.output
    assert res.output == f'database "{dbname}" was initialized\n', res.output

    with typically_configured_app.app_context():
        first_row_of_data = db.session.query(example_model).first()

    assert first_row_of_data is not None


class CliTestConf(t.NamedTuple):
    options: t.List[str]
    type_in_db_name: bool = False


@pytest.mark.parametrize(
    "cli_test_conf", [
        CliTestConf(options=[], type_in_db_name=True),
        CliTestConf(options=["-f"]),
        CliTestConf(options=["--force"]),
        CliTestConf(options=["--force"]),
    ]
)
def test_psql_drop_command(
        admin_connection,
        typically_configured_app: Flask,
        activated_database,
        db_params: dict,
        cli_test_conf: CliTestConf
):
    dbname = db_params.get("dbname")

    assert database_exists(dbname, admin_connection)

    if cli_test_conf.type_in_db_name:
        input_stream = dbname
    else:
        input_stream = None

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(
        typically_configured_app.cli,
        ["psql", "drop", *cli_test_conf.options],
        input=input_stream
    )

    assert res.exit_code == 0

    if cli_test_conf.type_in_db_name:
        assert res.output.startswith("Are you sure"), res.output
        assert res.output.endswith(f'\ndatabase "{dbname}" was deleted\n'), res.output
    else:
        assert res.output == f'database "{dbname}" was deleted\n', res.output

    assert not database_exists(dbname, admin_connection)


def test_psql_drop_command_wont_delete_on_typo(
        admin_connection,
        typically_configured_app: Flask,
        activated_database,
        db_params: dict,
):
    dbname = db_params.get("dbname")

    assert database_exists(dbname, admin_connection)

    input_stream = dbname + "extratext"

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(
        typically_configured_app.cli,
        ["psql", "drop"],
        input=input_stream
    )

    assert res.exit_code == 1, res.output

    assert res.output.startswith("Are you sure"), res.output
    assert f'\ndatabase "{dbname}" was deleted\n' not in res.output, res.output
    assert f'database "{dbname}" will not be deleted' in res.output, res.output

    assert database_exists(dbname, admin_connection)


def test_psql_setup_command(
        admin_connection,
        typically_configured_app: Flask,
        db_params: dict,
        db,
        example_model
):
    dbname = db_params.get("dbname")

    assert not database_exists(dbname, admin_connection)

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(typically_configured_app.cli, ["psql", "setup"])

    assert res.exit_code == 0, res.output
    assert res.output == (
        f'database "{dbname}" was created\n'
        f'database "{dbname}" was initialized\n'
    ), res.output

    assert database_exists(dbname, admin_connection)

    with typically_configured_app.app_context():
        first_row_of_data = db.session.query(example_model).first()
    assert first_row_of_data is None


def test_psql_setup_command_with_custom_callback(
        admin_connection,
        typically_configured_app: Flask,
        db_params: dict,
        db,
        example_model,
        custom_init_db_callback,
):
    dbname = db_params.get("dbname")

    assert not database_exists(dbname, admin_connection)

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(typically_configured_app.cli, ["psql", "setup"])

    assert res.exit_code == 0, res.output
    assert res.output == (
        f'database "{dbname}" was created\n'
        f'database "{dbname}" was initialized\n'
    ), res.output

    assert database_exists(dbname, admin_connection)

    with typically_configured_app.app_context():
        first_row_of_data = db.session.query(example_model).first()
    assert first_row_of_data is not None


def test_psql_setup_command_when_db_exists(
        admin_connection,
        activated_database,
        typically_configured_app: Flask,
        db_params: dict,
        db,
        example_model
):
    dbname = db_params.get("dbname")

    assert database_exists(dbname, admin_connection)

    with typically_configured_app.app_context():
        db_inspector = sa.inspect(db.engine)
        assert not db_inspector.has_table("pet")

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(typically_configured_app.cli, ["psql", "setup"])

    assert res.exit_code == 0, res.output
    assert res.output == (
        f'database "{dbname}" already exists\n'
        f'database "{dbname}" was initialized\n'
    ), res.output

    assert database_exists(dbname, admin_connection)

    with typically_configured_app.app_context():
        db_inspector = sa.inspect(db.engine)
        assert db_inspector.has_table("pet")

    with typically_configured_app.app_context():
        first_row_of_data = db.session.query(example_model).first()
    assert first_row_of_data is None


def test_psql_reset_command(
        admin_connection,
        typically_configured_app: Flask,
        activated_database,
        db_params: dict,
        db,
        example_model
):
    dbname = db_params.get("dbname")

    assert database_exists(dbname, admin_connection)

    client = typically_configured_app.test_cli_runner()
    res = client.invoke(typically_configured_app.cli, ["psql", "reset", "-f"])

    assert res.exit_code == 0
    assert res.output == (
        f'database "{dbname}" was deleted\n'
        f'database "{dbname}" was created\n'
        f'database "{dbname}" was initialized\n'
    )

    assert database_exists(dbname, admin_connection)

    with typically_configured_app.app_context():
        db_inspector = sa.inspect(db.engine)
        assert db_inspector.has_table("pet")

    with typically_configured_app.app_context():
        first_row_of_data = db.session.query(example_model).first()
    assert first_row_of_data is None
