.PHONY: check static-check setup-hooks dev-setup test-live install release catalog

PYTHON ?= python3
VERSION ?= dev

static-check:
	./scripts/check_static.sh

setup-hooks:
	git config core.hooksPath .githooks
	@echo 'Git hooks enabled: .githooks'

dev-setup: setup-hooks
	$(PYTHON) -m pip install --requirement requirements-dev.txt

catalog:
	$(PYTHON) scripts/generate_plugin_catalog.py --docs

check:
	$(PYTHON) scripts/generate_plugin_catalog.py --check
	$(PYTHON) scripts/harden_plugins.py --check
	$(PYTHON) scripts/test_safety.py
	$(PYTHON) -m compileall -q plugins scripts test_engines.py
	$(PYTHON) test_engines.py plugins
	$(MAKE) static-check

test-live:
	./test_all_plugins.sh

install:
	./install_plugins.sh

release: catalog
	$(PYTHON) scripts/build_release.py --version $(VERSION) --output working/qbsearch-$(VERSION).zip
