# WDL (Workflow Description Language) Spec Conformance Tests

Now run WDL Spec Conformance Tests from the comfort of your own environment!  With the
comfort of your own runner!

Designed to be run by any WDL-supporting runner, these tests aim to cover
the entire WDL spec eventually.  Running these tests should not only test a runner's
level of compliance with any given version of the WDL spec, running them regularly 
should also help to ensure that that level of compliance is maintained.

Supported WDL spec versions:

 - [WDL Version "draft-2"](https://github.com/openwdl/wdl/tree/main/versions/draft-2)
 - [WDL Version 1.0](https://github.com/openwdl/wdl/tree/main/versions/1.0)
 - [WDL Version 1.1](https://github.com/openwdl/wdl/tree/main/versions/1.1)

Runners this has been evaluated against:

 - [Toil](https://github.com/DataBiosphere/toil)
 - [miniwdl](https://github.com/chanzuckerberg/miniwdl)
 - [Cromwell](https://github.com/broadinstitute/cromwell)

## Note

The tests in this directory are incomplete and are in the process of being added to.  If you'd like 
to help make these tests more complete, we gladly welcome PRs!

## Usage

```
(venv) quokka@qcore ~/$ python3 run.py --runner toil-wdl-runner --versions 1.1
Testing runner toil-wdl-runner on WDL versions: 1.1

0: SKIPPED: Standard Lib: Basic test for stdout()
1: SKIPPED: Standard Lib: Basic test for stderr()
2: SUCCEEDED: Standard Lib: Basic test for quote()
3: SUCCEEDED: Standard Lib: Basic test for squote()
4: SUCCEEDED: Standard Lib: Basic test for sep()
5: SUCCEEDED: Standard Lib: Basic test for prefix()

...

...

17 tests run, 15 succeeded, 2 failed, 8 skipped
```


## Options

```
(venv) quokka@qcore ~/$ python3 run.py --help
usage: run.py [-h] [--verbose] [--versions VERSIONS] [--tags TAGS]
              [--numbers NUMBERS] [--runner RUNNER] [--threads THREADS]

Run WDL conformance tests.

options:
  -h, --help            show this help message and exit
  --verbose             Print more information about a test
  --versions VERSIONS, -v VERSIONS
                        Select the WDL versions you wish to test against.
  --tags TAGS, -t TAGS  Select the tags to run specific tests
  --numbers NUMBERS, -n NUMBERS
                        Select the WDL test numbers you wish to run.
  --runner RUNNER, -r RUNNER
                        Select the WDL runner to use.
  --threads THREADS     Number of tests to run in parallel.
```
