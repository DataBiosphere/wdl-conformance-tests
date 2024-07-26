#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
Run the performance testing suite and output the results to a CSV file.

Output file is specified with --output and runners are specified by --runners or --all-runners. Test options such as
--repeat and -n are carried over from the standalone run.py script.
"""

import argparse
import os.path
import timeit
from typing import Dict, Any, List

import argcomplete
import sys

from lib import parse_time
from run import WDLConformanceTestRunner, add_options


def get_runners(options: argparse.Namespace):
    if options.all_runners:
        return ["miniwdl", "toil-wdl-runner", "cromwell"]
    elif options.runners is None:
        return [options.runner]
    else:
        return options.runners.split(",")


def call_test(options: argparse.Namespace) -> Dict[str, Any]:
    """
    Run all tests and record times
    """
    conformance_runner = WDLConformanceTestRunner(options.conformance_file)
    runners = get_runners(options)
    all_responses = {}
    for runner in runners:
        realtime_start = timeit.default_timer()
        options.runner = runner
        options.time = True
        all_test_responses, successful_run = conformance_runner.run_and_generate_tests(options)
        realtime_end = timeit.default_timer()
        print(f"Total runtime: {parse_time(realtime_end - realtime_start)}")
        all_responses[runner] = all_test_responses

    # consolidate
    ordered_tests_by_id = dict()
    for runner, all_test_responses in all_responses.items():
        for test in all_test_responses:
            test_id = test["id"]
            ordered_tests_by_id.setdefault(test_id, dict())
            test_time = test['time']['real'] if test['status'] == 'SUCCEEDED' else test['status']
            ordered_tests_by_id[test_id].setdefault(runner, list())
            ordered_tests_by_id[test_id][runner].append(test_time)
    return ordered_tests_by_id


def write_times_to_csv(tests_by_id: Dict[str, Any], output: str, runners: List[str]) -> None:
    # write the average of all runtimes per test id
    with open(output, "w") as f:
        f.write("Test ID,Runner,Runtime\n")
        # f.write("Test ID" + "," + ",".join(runners) + "\n")
        for test_id, test_times in tests_by_id.items():
            for runner in runners:
                test_time_list = test_times[runner]
                for test_time in test_time_list:
                    f.write(f"{test_id},{runner},{test_time}\n")
    return


def get_data(test_response: Dict[str, Any], all_test_data: List[Dict[str, Any]]):
    time = test_response['time']['real'] if test_response['status'] == 'SUCCEEDED' else None
    test_number = test_response['number']
    dirname = all_test_data[test_number]['inputs']['dir']
    wdl_basename = all_test_data[test_number]['inputs']['wdl']
    json_basename = all_test_data[test_number]['inputs']['json']
    full_wdl_path = os.path.join(dirname, wdl_basename)
    full_json_path = os.path.join(dirname, json_basename)
    description = all_test_data[test_number]['description']
    test_id = all_test_data[test_number]['id']
    test_dict = {'wdl': full_wdl_path, 'json': full_json_path, 'time': time, 'description': description,
                 'id': test_id}
    return test_dict


def call_and_write_csv(options: argparse.Namespace) -> None:
    runners = get_runners(options)
    output = options.output
    tests_by_id = call_test(options)
    write_times_to_csv(tests_by_id, output, runners)


def add_performance_testing_args(parser: argparse.ArgumentParser) -> None:
    performance_testing_group = parser.add_argument_group("Arguments for running WDL performance tests")
    performance_testing_group.add_argument("--output", "-o", default="csv_output.csv",
                                           help='Specify the output CSV file.')
    performance_testing_group.add_argument("--all-runners", "-a", default=False, action="store_true",
                                           help="Specify whether to run with all runners. This will override the "
                                                "--runners argument.")
    performance_testing_group.add_argument("--runners", default=None,
                                           help="Specify multiple runners in a comma separated list.")


def main(args):
    parser = argparse.ArgumentParser(description=__doc__)
    add_options(parser)
    add_performance_testing_args(parser)
    argcomplete.autocomplete(parser)
    options = parser.parse_args(args)
    call_and_write_csv(options)


if __name__ == "__main__":
    main(args=sys.argv[1:])
