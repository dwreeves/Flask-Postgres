.PHONY: install
install:
	# Deprecated; using uv instead:
	# pip install uv
	# uv pip install --system --extra test -r pyproject.toml
	# uv pip install --system psycopg2
	# export TEST_DATABASE_URI=postgresql+psycopg2://postgres:postgres@postgres:5432/flask_postgres_test_database
	pip install flit
	flit install --deps develop --symlink

.PHONY: build
build:
	flit build

.PHONY: publish
publish:
	flit publish

.PHONY: test
test:
	pytest
