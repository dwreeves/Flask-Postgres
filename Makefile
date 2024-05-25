.PHONY: install
install:
	# Deprecated; using uv instead.
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
