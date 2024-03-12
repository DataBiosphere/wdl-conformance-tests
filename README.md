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

## Adding Tests
Tests can be added by editing `conformance.yaml`. \
For example, a new test can be added as follows:
```yaml
- description: |
    Example new test description
  versions: ["draft-2", "1.0", "1.1"] # specify versions to run with
  id: example_test_id # unique ID of test, no 2 tests should have the same id
  tags: ["examples", "behavior"] # specify tags, these don't need to be unique
  inputs:
    dir: tests/example_files # path to directory where test is, can be an absolute or relative path (to run.py)
    wdl: example.wdl # wdl file name
    json: example.json # json file name
  outputs:
    exampleWf.outputVar: # output name, should be workflowName.outputVariable
      type: Boolean # expected output type
      value: True # expected output value
```
The test files must be under the `tests/example_files` directory and be named `example.wdl` and `example.json`.
Each expected output should specified as `wf.var`. For example, `exampleWf.outputVar` is the specifier if the WDL is this:
```wdl
workflow exampleWf {
    output {
        Boolean outputVar = true
    }
}
```
Only one WDL file is necessary to run in all versions, as long as formatting is followed as [stated below](##test-formatting).
## Test formatting
Additionally, in order to keep a single WDL file per each test, the same test for other versions are generated. \
There are two ways for generating these tests: [automatic](###automatic-formatting) or [manual](###manual-formatting).
### Automatic formatting
However, this means that input sections must follow the format:
```wdl
input {
    ...
}
```
And command sections must follow the format
```wdl
# same for triple angle braces
command {
    ...
} # line with isolated closing brace indicates end of command section
```
### Manual formatting
If the format cannot be followed, patch files can be used instead to differentiate from the base file.
The `patch.py` program can be used to do this:
```commandline
python patch.py --version 1.1 --directory tests/basic_stdout
```
The directory `tests/basic_stdout` is the directory that holds all the WDL files written in all versions. The specified version will be the base file to make patch files from.
`--remove` can be provided to delete all other WDL files that aren't the base WDL file, and `--rename` can be used to rename the base WDL file to the same name as the directory.

For example, if `tests/basic_stdout` has 3 WDL files:
```commandline
tests/basic_stdout
├── basic_stdout.json
├── basic_stdout_version_1.0.wdl
├── basic_stdout_version_1.1.wdl
└── basic_stdout_version_draft2.wdl
```
After `python patch.py --version 1.1 --directory tests/basic_stdout` is called, then `patch.py` will use `basic_stdout_version_1.1.wdl` as the base file for patches, and generate 2 patch files to convert from WDL 1.1 to 1.0 and WDL 1.1 to draft-2.
```commandline
tests/basic_stdout
├── ...
├── version_1.0.patch
└── version_draft-2.patch
```
These patch files will be used to create the proper versioned WDL file at runtime (This will take priority over the automatic WDL version conversion).