# Unit tests
The WDL spec includes an extractable set of specification tests as per [their specification](https://github.com/openwdl/wdl-tests).
This test suite allows for those tests to be extracted and tested against a variety of runners.

## Notes
- Specification tests are only available for [WDL versions 1.1.1 and above](https://github.com/openwdl/wdl-tests/blob/58ff36209586ed69c9a64d3e0b151a343f12a4eb/README.md?plain=1#L7).
    > Starting with WDL 1.1.1, nearly all the examples in the WDL specification are also test cases that conform to the WDL markdown test specification.
- If running locally, it is **not** recommended to run test IDs `hisat2` and `gatk_haplotype_caller` (test indices 66 and 67). These tests will take a lot of network bandwidth and require a large amount of resources.
- Cromwell is not supported as Cromwell cannot run WDL 1.1+
- MiniWDL cannot run all tests, at least until [this issue is resolved](https://github.com/chanzuckerberg/miniwdl/issues/693)

## Usage
### Extracting Tests
First, use the script `setup_unit_tests.py` to pull the WDL specification and to extract the tests.
Calling the script with no arguments `python setup_unit_tests.py` is recommended, but passing in arguments will not drastically change the behavior of the script.
```commandline
usage: setup_unit_tests.py [options]

Extracts the unit tests from the spec to be runnable by this test suite;test files will be outputted into the `unit_tests` directory and a new conformance file will be created.To run the
unit tests, see [insert other script here]

options:
  -h, --help            show this help message and exit
  --version {1.1,1.2}, -v {1.1,1.2}
                        Version of the spec to grab unit tests out of. Only WDL 1.1 and above has support for built in unit tests.
  --output-type {yaml,json}
                        Specify conformance file output type.
  --force-pull          Default behavior does not pull the spec repo if it was already pulled. Specify this argument to force a refresh.
  --extra-metadata EXTRA_METADATA, -e EXTRA_METADATA
                        Include extra metadata when extracting the unit tests into the config. Since we have our own method of testing file outputs, this is mostly used for file
                        hashes/regexes.
  --script SCRIPT       Bash script to run alongside. This is to set up the environment for the test suite, ex mount points and files tests may depend on.(Probably need to run with root).
  --repo REPO           Repository to pull from.
```

By default, WDL version 1.1 is used, extra metadata from `unit_tests_metadata.yaml` is used, and `yaml` is the default output type.
Other arguments by default are none.

The script will pull the github repository for the specific version of WDL at `wdl-spec-[version]`. The unit tests and configuration file will be extracted into the `unit_tests/` folder. The configuration file will be at `unit_tests/test_config.yaml`, which is used for the `run_unit.py` script.

Before running the test suite, the shell script `unit_tests_script.sh` may need to be executed. This shell script creates several directories that the specification tests will require to exist.
To remove these directories and anything else that the script may create, call `make clean-unit-setup`.

### Running Tests
THen, use the script `run_unit.py` to actually run the tests according to the configuration file. If the default setup was performed,
the script can be used as if using `run.py`.

For example: `python run_unit.py --runner toil-wdl-runner --version 1.1 -n 105-109 --quiet --threads=4 --progress`

There are extra arguments specific to `run_unit.py` that may be useful.
```commandline
  --config CONFIG, -c CONFIG
                        Specify the path of the conformance config file.
  --reset               Specify whether to run the setup script again.
  --force-pull          Specify whether to use the cached SPEC or to force a pull.The setup script will be run as well.
```
The config argument by default is `unit_tests/test_config.yaml`, but can be overridden by passing in the path to another config file.
Resetting the script will extract the tests from the specification file again with the default behavior, essentially calling `setup_unit_tests.py` with no arguments.
Forcing a pull will pull the WDL repository, overwriting the existing WDL repository and specification file, before extracting the tests again. `--reset` must be included for `--force-pull` to work.

To remove the WDL repository and the unit tests folder, call `make clean-unit`.