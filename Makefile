include common.mk

MODULES=wdl-1.0 tests
CROMWELL_VERSION=85
WOMTOOL_VERSION=85

lint:
	flake8 $(MODULES) *.py

mypy:
	mypy --ignore-missing-imports --no-strict-optional $(MODULES)

build: cromwell womtool

clean-build: clean
	rm -rf build
clean:
	rm -f results*.json
	rm -rf miniwdl-logs
	rm -rf cromwell-executions
	rm -rf cromwell-workflow-logs
	rm -rf wdl-out-*
	find tests -name "_version_1.0*.wdl" -delete
	find tests -name "_version_1.1*.wdl" -delete
	find tests -name "_version_draft-2*.wdl" -delete

clean-csv:
	rm csv_output_*

cromwell:
	mkdir -p build
	if [ ! -f build/cromwell.jar ]; then \
		wget https://github.com/broadinstitute/cromwell/releases/download/$(CROMWELL_VERSION)/cromwell-$(CROMWELL_VERSION).jar -O build/cromwell.jar; fi;
	echo "cromwell version $(CROMWELL_VERSION) has been built!"

womtool:
	mkdir -p build
	if [ ! -f build/womtool.jar ]; then \
		wget https://github.com/broadinstitute/cromwell/releases/download/$(WOMTOOL_VERSION)/womtool-$(WOMTOOL_VERSION).jar -O build/womtool.jar; fi;
	echo "womtool version $(WOMTOOL_VERSION) has been built!"


.PHONY: lint mypy build cromwell womtool clean
