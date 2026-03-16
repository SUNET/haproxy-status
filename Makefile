SOURCE=		src
UV=$(shell which uv)
PIPCOMPILE=$(UV) pip compile --upgrade --generate-hashes --no-strip-extras --index-url https://pypi.sunet.se/simple --emit-index-url
PIPSYNC=$(UV) pip sync --index-url https://pypi.sunet.se/simple

reformat:
	# sort imports and remove unused imports
	ruff check --select F401,I --fix
	# reformat
	ruff format

test:
	PYTHONPATH=$(SOURCE) pytest

typecheck:
	@echo "Type checking this project currently does not work:"
	@echo ""
	@echo "  AssertionError: Cannot find component 'namedtuple@195' for 'haproxy_status.status.namedtuple@195'"
	@echo ""
	#mypy --ignore-missing-imports $(SOURCE)

%ments.txt: %ments.in
	CUSTOM_COMPILE_COMMAND="make update_deps" $(PIPCOMPILE) $< -o $@

update_deps: $(patsubst %ments.in,%ments.txt,$(wildcard *ments.in))

dev_sync_deps:
	@test $${VIRTUAL_ENV?virtual env not activated}
	$(PIPSYNC) test_requirements.txt
