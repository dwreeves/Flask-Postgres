.PHONY: install
install:
	pip install flit
	flit install --deps develop

.PHONY: build
build:
	flit build

.PHONY: publish
publish:
	flit publish

.PHONY: test
test:
	pytest
