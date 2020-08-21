include common.mk

MODULES=wdl-1.0 tests
CROMWELL_VERSION=52
WOMTOOL_VERSION=52

lint:
	flake8 $(MODULES) *.py

mypy:
	mypy --ignore-missing-imports --no-strict-optional $(MODULES)

build: cromwell womtool

clean:
	rm -rf build

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
