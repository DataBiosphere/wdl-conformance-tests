#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
import argparse
import sys

import argcomplete

from run import WDLConformanceTestRunner, add_options


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_options(parser)

    unit_conformance_path = "unit_tests/test_config.yaml"

    parser.add_argument("--config", "-c", default=unit_conformance_path,
                        help="Specify the path of the conformance config file.")
    parser.set_defaults(version="1.1")  # override default to 1.1
    parser.set_defaults(runner="toil-wdl-runner")  # cromwell doesn't support 1.1+

    argcomplete.autocomplete(parser)
    args = parser.parse_args()

    if args.versions not in ["1.1", "1.2"]:
        raise RuntimeError(f"WDL version is not valid; unit tests are only supported on WDL 1.1+.")

    conformance_runner = WDLConformanceTestRunner(conformance_file=args.config)
    _, successful_run = conformance_runner.run_and_generate_tests(args)

    if not successful_run:
        # Fail the program overall if tests failed.
        sys.exit(1)


if __name__ == '__main__':
    main()
