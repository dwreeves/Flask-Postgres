"""
Compatibility for psycopg.

This repo does not enforce psycopg in the requirements because users may be
using psycopg2 or the psycopg2-binary. All of these installations have a very
similar API. Compatibility across versions is handled here.
"""
_MODULE_NOT_FOUND_MSG = (
    "No module named 'psycopg' or 'psycopg2'."
    " Flask-Postgres depends on either of these modules to handle connections"
    " to PostgreSQL."
)

try:
    import psycopg as psycopg
except ModuleNotFoundError:
    try:
        import psycopg2 as psycopg
    except ModuleNotFoundError:
        psycopg = None


def check_dependencies():
    """
    At some point we can't beat around the bush, and we need to raise an error
    if there is no psycopg module.
    """
    if psycopg is None:
        raise ModuleNotFoundError(_MODULE_NOT_FOUND_MSG)
