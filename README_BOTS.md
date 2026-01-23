# Bot Instructions

## Virtual Environment

A Python virtual environment with dependencies may be:
- Already activated by the user
- Located at `./venv`
- Located at `../toil/venv`

Check which applies before running Python commands.

## Test Commands

### Extract unit tests from the WDL spec

```bash
python3 setup_unit_tests.py -v 1.1 --extra-patch-data unit_tests_patch_data.yaml --repo https://github.com/openwdl/wdl.git --branch wdl-1.1 --force-pull
```

For WDL 1.2:
```bash
python3 setup_unit_tests.py -v 1.2 --extra-patch-data unit_tests_patch_data.yaml --repo https://github.com/openwdl/wdl.git --branch wdl-1.2 --force-pull
```

### Run a specific unit test

```bash
python run_unit.py --runner toil-wdl-runner --version 1.1 --id hello_parallel --threads=4 --progress
```

### Run all unit tests

```bash
python run_unit.py --runner toil-wdl-runner --version 1.1 --threads=4 --progress
```
