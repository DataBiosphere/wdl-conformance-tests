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

The `run.py` script, and most other included scripts, support the followign options:
```
  -h, --help            show this help message and exit
  --verbose             Print more information about a test
  --versions {draft-2,1.0,1.1}, -v {draft-2,1.0,1.1}
                        Select the WDL versions you wish to test against. Ex: -v=draft-2,1.0
  --tags TAGS, -t TAGS  Select the tags to run specific tests
  --numbers NUMBERS, -n NUMBERS
                        Select the WDL test numbers you wish to run. Can be a comma separated list or hyphen separated inclusive ranges. Ex: -n=1-4,6,8-10
  --runner {cromwell,toil-wdl-runner,miniwdl}, -r {cromwell,toil-wdl-runner,miniwdl}
                        Select the WDL runner to use.
  --threads THREADS     Number of tests to run in parallel. The maximum should be the number of CPU cores (not threads due to wall clock timing).
  --time                Time the conformance test run.
  --quiet
  --exclude-numbers EXCLUDE_NUMBERS
                        Exclude certain test numbers.
  --conformance-file CONFORMANCE_FILE
                       Run the given test suite. 
  --toil-args TOIL_ARGS
                        Arguments to pass into toil-wdl-runner. Ex: --toil-args="caching=False"
  --miniwdl-args MINIWDL_ARGS
                        Arguments to pass into miniwdl. Ex: --miniwdl-args="--no-outside-imports"
  --cromwell-args CROMWELL_ARGS
                        Arguments to pass into cromwell. Ex: --cromwell-args="--options=[OPTIONS]"
  --cromwell-pre-args CROMWELL_PRE_ARGS
                        Arguments to set java system properties before calling cromwell. This allows things such as setting cromwell config files with --cromwell-pre-
                        args="-Dconfig.file=build/overrides.conf".
  --id ID               Specify WDL tests by ID.
  --repeat REPEAT       Specify how many times to run each test.
  --jobstore-path JOBSTORE_PATH, -j JOBSTORE_PATH
                        Specify the PARENT directory for the jobstores to be created in.
  --progress            Print the progress of the test suite as it runs.
```
Invoking `run.py` with no options will result in the entire `conformance.yaml` test suite being run, which can take a long time.
Including `--progress` is recommended when running over a long period of time.

The tests to run can be specified with `--id`, `--tags`, and `--numbers`. Tests matching any of the selectors will be run:
```commandline
python run.py --number 1 --id md5 --tags stderr --version 1.0 --runner toil-wdl-runner
Testing runner toil-wdl-runner on WDL versions: 1.0


=== REPORT ===

1: SUCCEEDED: Standard Lib: Basic test for stderr()
Iteration: 1
40: SUCCEEDED: Legacy test for stderr_as_output
Iteration: 1
68: SUCCEEDED: MD5 test
Iteration: 1
3 tests run, 3 succeeded, 0 failed, 0 skipped
```
`--repeat` specifies how many times to run each test. `--threads` allows multiple tests to run simultaneously;
This should be set to no more than the number of physical, highest-performance cores in the system (not counting any efficiency cores or the two logical cores per physical core provided by hyperthreading), in order to ensure consistent timings, if running with `--time` or with the performance testing script.
However, there is no thread reservation system; if a test is not guaranteed to run singlethreaded and all threads are in use, the timings may be influenced.


By default, runner logs are only printed for failed tests. `--verbose` forces logs to always print and `--quiet` forces logs to never print.

If running tests on a cluster, [extra arguments may be necessary](SLURM_README.md).
## Adding Tests
Tests can be added by editing the test suite file: `conformance.yaml` for conformance tests, or `integration.yaml` for longer integration tests.

For example, a new test can be added as follows:
```yaml
- description: |
    Example new test description
  versions: ["draft-2", "1.0", "1.1"] # specify versions to run with
  id: example_test_id # unique ID of test, no 2 tests should have the same id
  tags: ["examples", "behavior"] # specify tags, these don't need to be unique
  inputs:
    dir: tests/example_files # path to directory where test is, can be an absolute or relative path (from the test suite file)
    wdl: example.wdl # wdl file name
    json: example.json # json file describing test workflow inputs
  outputs:
    exampleWf.outputVar: # output name, should be workflowName.outputVariable
      type: Boolean # expected output type
      value: True # expected output value
```
The test files then should be under the `tests/example_files` directory and be named `example.wdl` and `example.json`.
Each expected output should be specified as `wfName.varName`. For example, `exampleWf.outputVar` is the specifier if the WDL is this:
```wdl
workflow exampleWf {
    output {
        Boolean outputVar = true
    }
}
```
Only one WDL file is used for all WDL versions that a test runs on; the file [will be rewritten and must obey certain formatting conventions](#test-formatting).
## Test formatting
The test runner uses a single WDL file for each test, written for a single WDL version, to run the test across all applicable WDL versions. This is accomplished by rewriting that one WDL file at runtime to produce generated WDL files targeting the other WDL versions.

Test can use either [automatic version conversion](#automatic-version-conversion) or [manual version conversion](#manual-version-conversion) to be runnable across multiple WDL versions from a single file. If a test uses neither, it must be restricted to a single WDL version.
### Automatic version conversion
Different WDL versions (`draft-2`, `1.0`, `1.1`) all have slightly different syntax. To deal with this, the runner will 
automatically convert from one version to another before running a WDL test. As long as the format of a WDL file 
follows these format conventions, the conversion will work properly:

Any input section in WDL code must follow the format:
```wdl
input {
    ...
}
```
Any command section must follow the format:
```wdl
command {
    ...
} # line with isolated closing brace indicates end of command section
```
Any command section can also use triple angle braces:
```wdl
command <<<
    ...
>>>
```

These sections should not have other WDL code on the same line, or have unnecessary newlines in between the section declaration and its block.
For example, these will not work:
```wdl
input {
    ...
} var = 1 # WDL code in input declaration
```
```wdl
input
{ # newline between input keyword and open brace
    ...
}
```
### Manual version conversion
While the format for automatic version conversion should be applicable for most WDL code, there may be WDL syntax that is incompatible 
between WDL versions. If a test needs specific syntax differences between versions (beyond changes to section declarations), patch files can be used instead to describe the differences from a base file.

As long as a test directory has patch files with the name `version_[wdl_version].patch`, the runner will apply
the patch files automatically before each test.

For example, to convert a test file from WDL version `1.1` to `1.0` and `draft-2`, the file structure will look like this:
```commandline
tests/basic_stdout
├── ...
├── basic_stdout.wdl
├── version_1.0.patch
└── version_draft-2.patch
```

To help create these patch files, the `patch.py` program is given:

```commandline
usage: patch.py [-h] --version {1.0,1.1,draft-2} --directory DIRECTORY [--remove REMOVE] [--rename RENAME]

Create patch files in the right format

options:
  -h, --help            show this help message and exit
  --version {1.0,1.1,draft-2}, -v {1.0,1.1,draft-2}
                        The base WDL file's version
  --directory DIRECTORY, -d DIRECTORY
                        Directory where all the WDL files are
  --remove REMOVE       Remove WDL files that are not the base
  --rename RENAME       Rename the base WDL file to the directory (--remove must be set to True too)
```

To use this script, first, create the 2-3 different versioned WDL files in a directory. 

When calling `patch.py`, the base WDL version should be passed into `--version`.
Patch files will be created converting from that base WDL version.

The directory containing all these tests should be passed into `--directory`. All the WDL files must follow the naming convention `[testname]_version_[wdl_version]`. For example, `example_version_1.0`, `example_version_draft-2`.

`--remove` can be provided to delete all other WDL files that aren't the base WDL file, and `--rename` can be used to rename the base WDL file to the same name as the directory. (These options are not necessary.)

For example, if making a new test called `basic_stdout` for all 3 versions:
First create the directory `tests/basic_stdout`. Create the 3 different WDL files, one for each version, and name them appropriately

```commandline
tests/basic_stdout
├── basic_stdout.json
├── basic_stdout_version_1.0.wdl
├── basic_stdout_version_1.1.wdl
└── basic_stdout_version_draft2.wdl
```

Then run the program:
```commandline
python patch.py --version 1.1 --directory tests/basic_stdout
```

`patch.py` will use `basic_stdout_version_1.1.wdl` as the base file for patches, and generate 2 patch files to convert from WDL 1.1 to 1.0 and draft-2.
```commandline
tests/basic_stdout
├── ...
├── version_1.0.patch # new file
└── version_draft-2.patch # new file
```

Then add the tests to the test suite file.
```yaml
- description: |
    Example stdout test
  versions: ["draft-2", "1.0", "1.1"]
  id: ...
  tags: ...
  inputs:
    dir: tests/basic_stdout
    wdl: basic_stdout_version_1.1.wdl
    json: basic_stdout.json
  outputs:
    ...
```
The runner will find and apply the patch files at runtime. (This will take priority over the automatic WDL version conversion.)

To reverse this process, another program `unpatch.py` will do the opposite of `patch.py`. This is useful if new patch files need to be created, but the original WDL files were deleted:
```commandline
usage: unpatch.py [-h] --directory DIRECTORY [--version {1.0,1.1,draft-2}] [--file FILE]

Reverse patch.py to get back the original WDL files. This can be useful if the original WDL files no longer exist and a modification that invalidates the existing patches is necessary.

options:
  -h, --help            show this help message and exit
  --directory DIRECTORY, -d DIRECTORY
                        Directory where all at least the base WDL file and patch files are
  --version {1.0,1.1,draft-2}, -v {1.0,1.1,draft-2}
                        The base WDL file's version. If specified, it will find the first WDL file with this version to create patched files from.
  --file FILE, -f FILE  File name of base WDL file. If specified, it will use it to create patched files from.Takes priority over --version
```
Given a directory `--directory` and the base WDL file version `--version` (or file path `--file`),
the script will get back the original WDL files that were used for `patch.py`.

If the original files used for `patch.py` already exist, then `unpatch.py` will not overwrite them.
## Running Performance Tests
The default runner `run.py` only runs tests and reports on their status in the terminal.
To store the runtime of tests (and eventually graph them), the script `run_performance.py` should be used:
```commandline
python run_performance.py --runners toil-wdl-runner,miniwdl --output performance_output.csv --progress
```
The output will always be in CSV format. `--runners` can specify a comma separated list of runners to test, and `--all-runners` is a shortcut to specify all of them.

### Performance Testing Options
[All options](#options) from the normal `run.py` script are also available in `run_performance.py`. For example, if `--id stdout` is provided, then only the `stdout` test will be measured.

The performance test specific options are:
```commandline
Arguments for running WDL performance tests:
  --output OUTPUT, -o OUTPUT
                        Specify the output CSV file.
  --all-runners, -a     Specify whether to run with all runners. This will override the --runners argument.
  --runners RUNNERS     Specify multiple runners in a comma separated list.
```

## Graphing Performance Tests
The script `create_graph.py` can be used to graph the output of the performance tests:
```commandline
python create_graph.py -f performance_output.csv
```
If no input CSV file is given, then the program will run the entire performance test suite first.
### Graph Options
Similar to the performance testing script, [all options](#options) from the base runner are carried through. However, there are graphing specific options:
```commandline
Arguments for graphing runtimes of WDL tests:
  --from-file FILE, -f FILE
                        Specify a csv file to read from.
  --display-num DISPLAY_NUM, -d DISPLAY_NUM
                        Specify the number of tests to display per graph.
  --display-all, -a     Display all tests on a single graph. Overrides --display-num.
  --ignore-runner IGNORE_RUNNER
                        Specify a runner(s) to ignore in the graph output.
  --precision PRECISION
                        Specify the precision when outputting float values. Ex: Default=0 will result in 1 for float value 1.4...
  --no-labels           Specify to not display extra labels on the graph.
  --graph-type GRAPH_TYPE
```
By default, separate graphs will be created for every 30 tests.

This can be controlled with `--display-num`, which overrides the number of tests to display per graph. `--display-all` forces all tests onto a single graph.

`--graph-type` specifies the type of graph to create. The supported options are `box` and `bar`.
`box` will create a traditional box plot and `bar` will create a bar graph with error bars representing standard deviation. 
### Writing Graphs to a File
The graphs can be written to disk by specifying a (base) filename.

For example, to output a graph with all tests in a PNG with a size of 40 inches by 10 inches (width,height):
```commandline
python create_graph.py -f performance_output.csv --output performance_graph.png --dimensions 40,10 -a
```
If `--display-all` is not specified and there are more tests to graph than `--display-num`, then multiple graph files will be created with the format `[output_file][iteration].[fileext]`.

For example, calling `python create_graph.py -f performance_output.csv --output performance_graph.png` with 90 total tests to graph will result in:
```commandline
.
├── performance_graph1.png
├── performance_graph2.png
└── performance_graph3.png
```
If trying to put all the tests into a single graph, it is likely that dimensions should be provided to make all tests fit.

All output formats implemented by Matplotlib (such as `pdf` and `svg`) are supported.
### Graph Output Options
Other than the previous [general](#options) and [graph specific](#graph-options) options, the options for outputting a graph are:
```commandline
Arguments for specifying how to write the graph to a file.:
  --output OUTPUT, -o OUTPUT
                        Instead of displaying the graphs, output it into an image. If --display-num is set to a number less than the total amount of tests in the CSV file, then multiple images will be created with the naming
                        scheme: [filename][iteration].[fileextension]. For example, if wdl_graph.png is passed, then the first file created will be wdl_graph1.png.
  --dimensions [DIMENSIONS]
                        If custom dimensions are needed, this can be called with input format x_size,y_size in inches. Calling this with no value will size the graph accordingly.
```
### Example Graphs
These are 2 graphs generated from running performance testing on a Slurm cluster.
![Example box graph](examples/example_box_graph.png)
![Example bar graph](examples/example_bar_graph.png)
