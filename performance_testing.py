import argparse
import json
import os.path
import timeit
from typing import Dict, Any, Optional, List

import regex
import subprocess
import sys

from ruamel import yaml

from lib import parse_time
from run import WDLConformanceTestRunner, WDLRunner, CromwellWDLRunner, MiniWDLStyleWDLRunner, CromwellWDLRunner, \
    RUNNERS, add_options


def call_test(options: argparse.Namespace) -> Dict[str, Any]:
    """
    Run all tests and record times
    """
    conformance_file = "conformance.yaml"
    conformance_runner = WDLConformanceTestRunner(conformance_file)
    runners = ["miniwdl", "toil-wdl-runner", "cromwell"] if options.all_runners else [options.runner]
    all_responses = {}
    options.time = True
    for runner in runners:
        realtime_start = timeit.default_timer()
        options.runner = runner
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


def write_times_to_csv(tests_by_id: Dict[str, Any], options: argparse.Namespace) -> None:
    # def get_average_time(test_time_list: List[str]) -> str:
    #     """
    #     Get the average time in a list of test runtimes. Returns SKIPPED or FAILED if any test was skipped or failed.
    #     """
    #     time_sum = 0
    #     for time in test_time_list:
    #         if isinstance(time, str):
    #             # at least one of the runs did not succeed or was skipped
    #             # this should be either skipped or failure
    #             return time
    #         time_sum += time
    #
    #     return str(time_sum / len(test_time_list))

    # def get_lowest_time(test_time_list: List[str]) -> str:
    #     """
    #     Get the lowest time from list of runtimes. Returns SKIPPED or FAILED if any test was skipped or failed.
    #     """
    #     lowest_time = None
    #     for time in test_time_list:
    #         if isinstance(time, str):
    #             return time
    #         lowest_time = time if lowest_time is None or time < lowest_time else lowest_time
    #     return str(lowest_time)
    #
    # def get_highest_time(test_time_list: List[str]) -> str:
    #     """
    #     Get the highest time from list of runtimes. Returns SKIPPED or FAILED if any test was skipped or failed.
    #     """
    #     highest_time = None
    #     for time in test_time_list:
    #         if isinstance(time, str):
    #             return time
    #         highest_time = time if highest_time is None or time > highest_time else highest_time
    #     return str(highest_time)

    # write the average of all runtimes per test id
    runners = ["miniwdl", "toil-wdl-runner", "cromwell"] if options.all_runners else [options.runner]
    with open(options.output, "w") as f:
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
    tests_by_id = call_test(options)
    write_times_to_csv(tests_by_id, options)


def add_performance_testing_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", "-o", default="csv_output.csv",
                        help='Specify the output CSV file.')
    parser.add_argument("--all-runners", "-a", default=False, action="store_true",
                        help="Specify whether to run with all runners")
    # parser.add_argument("--dont-preserve-error", default=True, dest="error", action="store_false")


def main(args):
    parser = argparse.ArgumentParser()
    add_options(parser)
    add_performance_testing_args(parser)

    options = parser.parse_args(args)
    call_and_write_csv(options)


if __name__ == "__main__":
    main(args=sys.argv[1:])
