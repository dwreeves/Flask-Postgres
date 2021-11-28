<p align="center">
  <img src="https://raw.githubusercontent.com/dwreeves/Flask-Postgres/main/docs/src/img/flask-postgres-banner.png">
</p>

<p align="center">
  <img src="https://github.com/dwreeves/Flask-Postgres/workflows/tests/badge.svg">
  <img src="https://github.com/dwreeves/Flask-Postgres/workflows/docs/badge.svg">
</p>

---

## Overview

Simple CLI that provides the following commands:

- **`flask psql create`**
- **`flask psql init`**
- **`flask psql drop`**
- **`flask psql setup`**: create → init
- **`flask psql reset`**: drop → create → init

These commands are available out of the box as long as you're using Flask-SQLAlchemy. **Flask-Postgres** finds your `db` instance for you, so it knows exactly how to create, initialize, and delete your database.

### Why Use **Flask-Postgres**?

- ✅ Simple to use.
- ✅ **Zero changes to your application code required!** Just `pip install flask-postgres` and you're ready to go!
- ✅ Great for small apps.
- ✅ Great for speeding up development.
- ✅ Great for Flask / web dev beginners.

## Example

The below example shows an app with a custom `init_db_callback`, which is optional. 

```python
# app.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_postgres import init_db_callback

app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "postgresql://localhost:5432/example"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

class Pet(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text)

@init_db_callback
def init_db(app, db):
    db.create_all()

    # Add your first pet
    pet = Pet(name="Fido")
    db.session.add(pet)
    db.session.commit()
```

Now run in your terminal:

```shell
flask psql setup
```

And you'll have a Postgres database up and running with the initialized data.

Want to make a change, and don't mind starting everything over? Then run:

```shell
flask psql reset
```

## Setup

```shell
pip install flask-postgres
```

Once you have installed Flask-Postgres, you should be ready to go assuming your code is already set up to use `Flask-SQLAlchemy`. Check that the commands are available here:

```shell
flask psql --help
```

### Custom `init` Callback

Flask-Postgres does not require any more setup than this, unless you want to add a custom callback that runs when `psql init` is executed. The callback can take `app` and/or `db` args, or the function signature can be left blank:

```python
from flask_postgres import init_db_callback

@init_db_callback
def init_db(app, db):
    db.create_all()

# alternatively...
@init_db_callback
def init_db(app):
    ...

# alternatively...
@init_db_callback
def init_db(db):
    ...

# alternatively...
@init_db_callback
def init_db():
    ...
```

Note that your `init_db_callback` will be run inside the application context.

By default, if you do not register a callback, then **Flask-Postgres** will run `db.create_all()` for you when initializing the database. So if all you need is `db.create_all()`, then you can let **Flask-Postgres** take care of it.

## Config

For apps already setup to use Flask-SQLALchemy, all **Flask-Postgres** configuration is optional, and probably is not necessary for most users.

### TLDR

|Name|Type|Description|
|---|---|---|
|`FLASK_POSTGRES_CLI_DISALLOWED_ENVS` | `Sequence[str]` (or `str` delimited by `;`) | List of environments where the `flask psql` CLI is disabled from running.<br /><br />(Default behavior is the CLI is never disabled.)
|`FLASK_POSTGRES_TARGET_DATABASE_URI` | `str` | URL for the Postgres database to be created / initialized / deleted.<br /><br />(Default behavior is to use `SQLALCHEMY_DATABASE_URI`.)
|`FLASK_POSTGRES_ADMIN_PATH` | `str` | Database name to use when connecting to the Postgres server to create or delete another database.<br /><br />(Default behavior is to replace `{dbname}` with `postgres`.)

### Database connection

By default, **Flask-Postgres** uses the `SQLALCHEMY_DATABASE_URI` as the database to be created / initialized / deleted. **Flask-Postgres** replaces the `{dbname}` in the URI with `postgres` to handle database administration.

- If you don't want **Flask-Postgres** to use the SQLAlchemy hook, then you can use the variable `FLASK_POSTGRES_TARGET_DATABASE_URI`.
- If you don't want to connect to create/delete via `-d postgres`, then set the `FLASK_POSTGRES_ADMIN_PATH`.

### Disallowed environments

By default, `flask psql` can be run in any environment. If you want to restrict access to `flask psql` based on the `FLASK_ENV`, then you can set the config variable `FLASK_POSTGRES_CLI_DISALLOWED_ENVS`, which is a sequence of strings.

For example, if you don't want `flask psql` to run in production:

```python
app.config["FLASK_POSTGRES_CLI_DISALLOWED_ENVS"] = ["production"]
```

This is not protection against malicious use-- anyone with access to a terminal in your production environment can do whatever they want. It is good enough protection against mistakes, though.

### Environment variables

You can access all of the above config variables (including `SQLALCHEMY_DATABASE_URI`) through environment variables.

**Flask-Postgres** always prefers Flask app config variables to equivalently named environment variables. Additionally, **Flask-Postgres** always prefers `FLASK_POSTGRES_*` prefixed variables to using `SQLALCHEMY_DATABASE_URI`.

For example, if your environment variable is `SQLALCHEMY_DATABASE_URI=foo`, and your Flask app config variable is `FLASK_POSTGRES_TARGET_DATABASE_URI=bar`, then **Flask-Postgres** will use `bar`.

### CLI Options

CLI options always override everything and work separately from the way that the config resolves variables:

They also work in reverse of the config variables normally. Instead of defining a target database URI `postgresql://localhost:5432/mydb` and replacing the `-d` with `postgres`, instead you define the admin URI `postgresql://localhost:5432/postgres` which creates `mydb`.

It is **not** recommended that you use the CLI options for setting config related variables.

## Caveat

This package is useful if:

- You're a web development novice and are not familiar with / overwhelmed by Docker Compose and Alembic (or alternatives).
- You know Docker Compose and Alembic (or alternatives), but don't want to bother with one or both. For example:
    - Working in a development environment.
    - Fun, minor side project you're hosting on Heroku.

Which is to say, this package is a lightweight alternative to setting up an application in a fully fledged production way.

For serious production stuff, look into Docker Compose (to `create` your database) and Alembic (to `init` your database).
