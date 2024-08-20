#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
run_unit.py: Run the WDL specification/unit tests.
"""
import argparse
import os
import subprocess
import sys

import argcomplete

from run import WDLConformanceTestRunner, add_options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_options(parser)

    unit_conformance_path = "unit_tests/test_config.yaml"

    parser.add_argument("--config", "-c", default=unit_conformance_path,
                        help="Specify the path of the conformance config file.")
    parser.add_argument("--reset", default=False, action="store_true",
                        help="Specify whether to run the setup script again.")
    parser.add_argument("--force-pull", default=False, action="store_true",
                        help="Specify whether to use the cached SPEC or to force a pull."
                             "The setup script will be run as well.")
    parser.add_argument(
        "--script",
        # default="unit_tests_script.sh",
        default=None,
        help="Bash script to run after extracting the tests. Runs relative to this file. This is to set up the environment for the test suite,"
             "ex mount points and files tests may depend on. (Probably need to run with root)."
    )
    parser.set_defaults(versions="1.1")  # override default to 1.1
    parser.set_defaults(runner="toil-wdl-runner")  # cromwell doesn't support 1.1+

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    spec_dir = f"wdl-{args.versions}-spec"  # there may be a better way to detect that setup_unit_tests.py was ran before than checking a hard coded directory
    if args.reset or not os.path.exists(spec_dir):
        from setup_unit_tests import main as setup_unit_tests_main
        argv = [args.versions, "--output-type=yaml"]
        if args.force_pull:
            argv.append("--force-pull")
        setup_unit_tests_main(argv)

    if args.versions not in ["1.1", "1.2"]:
        raise RuntimeError(f"WDL version is not valid; unit tests are only supported on WDL 1.1+.")

    if args.script is not None:
        # assume it needs to run as root
        if os.geteuid() == 0:
            subprocess.run(["bash", "{args.script}"], shell=True)
        else:
            subprocess.run(["sudo", "bash", "{args.script}"], shell=True)

    conformance_runner = WDLConformanceTestRunner(conformance_file=args.config)
    _, successful_run = conformance_runner.run_and_generate_tests(args)

    if not successful_run:
        # Fail the program overall if tests failed.
        sys.exit(1)


if __name__ == '__main__':
    main()
