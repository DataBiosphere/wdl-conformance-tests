#!/usr/bin/env python3
"""
run.py: Run conformance tests for WDL, grabbing the tests from the tests folder and expected values from
conformance.yaml
"""
import os
import json
import re

import sys
import hashlib
import argparse
import subprocess
import threading
import timeit

from ruamel.yaml import YAML

from concurrent.futures import ThreadPoolExecutor, as_completed, ProcessPoolExecutor
from shutil import which
from uuid import uuid4

from WDL.Type import Float as WDLFloat, String as WDLString, File as WDLFile, Int as WDLInt, Boolean as WDLBool, \
    Array as WDLArray, Map as WDLMap, Pair as WDLPair, StructInstance as WDLStruct

from typing import Optional, Iterable, Any, Dict, Tuple, List
from WDL.Type import Base as WDLBase

from lib import run_cmd, py_type_of_wdl_class, verify_failure, announce_test, print_response, convert_type, run_setup, \
    get_specific_tests, get_wdl_file


class WDLRunner:
    """
    A class describing how to invoke a WDL runner to run a workflow.
    """
    runner: str

    def format_command(self, wdl_file, json_file, results_file, args, verbose):
        raise NotImplementedError


class CromwellStyleWDLRunner(WDLRunner):
    def __init__(self, runner):
        self.runner = runner

    def format_command(self, wdl_file, json_file, results_file, args, verbose):
        return self.runner.split(" ") + [wdl_file, "-i", json_file, "-m", results_file] + args


class CromwellWDLRunner(CromwellStyleWDLRunner):
    download_lock = threading.Lock()

    def __init__(self):
        super().__init__('cromwell')

    def format_command(self, wdl_file, json_file, results_file, args, verbose):
        if self.runner == 'cromwell' and not which('cromwell'):
            with CromwellWDLRunner.download_lock:
                if self.runner == 'cromwell':
                    # if there is no cromwell binary seen on the path, download
                    # our pinned version and use that instead
                    log_level = '-DLOG_LEVEL=OFF' if not verbose else ''
                    cromwell = os.path.abspath('build/cromwell.jar')
                    if not os.path.exists(cromwell):
                        print('Cromwell not seen in the path, now downloading cromwell to run tests... ')
                        run_cmd(cmd='make cromwell'.split(" "), cwd=os.getcwd())
                    self.runner = f'java {log_level} -jar {cromwell} run'

        return super().format_command(wdl_file, json_file, results_file, args, verbose)


class MiniWDLStyleWDLRunner(WDLRunner):
    def __init__(self, runner):
        self.runner = runner

    def format_command(self, wdl_file, json_file, results_file, args, verbose):
        return self.runner.split(" ") + [wdl_file, "-i", json_file, "-o", results_file, "-d", "miniwdl-logs", "--verbose"] + args


RUNNERS = {
    'cromwell': CromwellWDLRunner(),
    'toil-wdl-runner': CromwellStyleWDLRunner('toil-wdl-runner --outputDialect miniwdl --logDebug'),
    'miniwdl': MiniWDLStyleWDLRunner('miniwdl run')
}


class WDLConformanceTestRunner:
    tests: List[Dict[Any, Any]]

    def __init__(self, conformance_file: str):
        yaml = YAML(typ='safe')
        with open(conformance_file, 'r') as f:
            self.tests = yaml.load(f)

    def compare_outputs(self, expected: Any, result: Any, typ: WDLBase):
        """
        Recursively ensure that the expected output object is the same as the resulting output object

        In the future, make this return where it failed instead to give less generic error messages

        :param expected: expected value object
        :param result: result value object from WDL runner
        :param typ: type of output from conformance file
        """
        if isinstance(typ, WDLArray):
            try:
                if len(expected) != len(result):
                    # length of output doesn't match
                    return {'status': 'FAILED', 'reason': f"Size of expected and result do not match!\n"
                                                          f"Expected output: {expected}\n"
                                                          f"Actual output: {result}!"}
                for i in range(len(expected)):
                    status_result = self.compare_outputs(expected[i], result[i], typ.item_type)
                    if status_result['status'] == 'FAILED':
                        return status_result
            except TypeError:
                return {'status': 'FAILED', 'reason': f"Not an array!\nExpected output: {expected}\n"
                                                      f"Actual output: {result}"}

        if isinstance(typ, WDLMap):
            try:
                if len(expected) != len(result):
                    return {'status': 'FAILED', 'reason': f"Size of expected and result do not match!\n"
                                                          f"Expected output: {expected}\n"
                                                          f"Actual result was: {result}!"}
                for key in expected.keys():
                    status_result = self.compare_outputs(expected[key], result[key], typ.item_type[1])
                    if status_result['status'] == 'FAILED':
                        return status_result
            except (KeyError, TypeError):
                return {'status': 'FAILED', 'reason': f"Not a map or missing keys!\nExpected output: {expected}\n"
                                                      f"Actual output: {result}"}

        # WDLStruct also represents WDLObject
        # Objects in conformance will be forced to be typed, same as Structs
        if isinstance(typ, WDLStruct):
            try:
                if len(expected) != len(result):
                    return {'status': 'FAILED', 'reason': f"Size of expected and result do not match!\n"
                                                          f"Expected output: {expected}\n"
                                                          f"Actual output: {result}!"}
                for key in expected.keys():
                    status_result = self.compare_outputs(expected[key], result[key], typ.members[key])
                    if status_result['status'] == 'FAILED':
                        return status_result
            except (KeyError, TypeError):
                return {'status': 'FAILED', 'reason': f"Not a struct or missing keys!\nExpected output: {expected}\n"
                                                      f"Actual output: {result}"}

        if isinstance(typ, (WDLInt, WDLFloat, WDLBool, WDLString)):
            # check that outputs are the same
            if expected != result:
                return {'status': 'FAILED', 'reason': f"Expected and result do not match!\n"
                                                      f"Expected output: {expected}\n"
                                                      f"Actual output: {result}!"}
            # check that output types are correct
            if not isinstance(expected, py_type_of_wdl_class(typ)) or not isinstance(result,
                                                                                     py_type_of_wdl_class(
                                                                                         typ)):
                return {'status': 'FAILED', 'reason': f"Incorrect types!\n"
                                                      f"Expected output: {expected}\n"
                                                      f"Actual output: {result}!"}

        if isinstance(typ, WDLFile):
            # check file path exists
            if not os.path.exists(result):
                return {'status': 'FAILED', 'reason': f"Result file does not exist!\n"
                                                      f"Expected filepath: {result}!"}

            if not isinstance(expected, dict):
                return {'status': 'FAILED', 'reason': f"Expected value is not a regex or md5sum!\n"
                                                      f"Expected result was: {expected}"}
            regex = expected.get('regex')
            if regex == "":
                return {'status': 'FAILED', 'reason': f"Expected regex is empty!"}
            if regex is not None:
                # get regex
                re_c = re.compile(regex)
                # check against regex
                with open(result, "r") as f:
                    text = f.read()
                    if not re_c.search(text):
                        return {'status': 'FAILED', 'reason': f"Regex did not match!\n"
                                                              f"Regex: {regex}\n"}
            else:
                # get md5sum
                with open(result, "rb") as f:
                    md5sum = hashlib.md5(f.read()).hexdigest()
                # check md5sum
                if md5sum != expected['md5sum']:
                    return {'status': 'FAILED', 'reason': f"Expected file does not match!\n"
                                                          f"Expected md5sum: {expected['md5sum']}\n"
                                                          f"Actual md5sum: {md5sum}!"}

        if isinstance(typ, WDLPair):
            try:
                if len(expected) != 2:
                    return {'status': 'FAILED', 'reason': f"Expected value is not a pair!\n"
                                                          f"Expected output: {expected}"}
                if expected['left'] != result['left'] or expected['right'] != result['right']:
                    return {'status': 'FAILED', 'reason': f"Expected and result do not match!\n"
                                                          f"Expected output: {expected}\n"
                                                          f"Actual result was: {result}!"}
            except (KeyError, TypeError):
                return {'status': 'FAILED', 'reason': f"Not a pair or missing keys!\nExpected output: {expected}\n"
                                                      f"Actual output: {result}"}
        return {'status': f'SUCCEEDED'}

    def run_verify(self, expected: dict, results_file: str, ret_code: int) -> dict:
        """
        Check either for proper output or proper success/failure of WDL program, depending on if 'fail' is included in
        the conformance test
        """
        if 'fail' in expected.keys():
            # workflow is expected to fail
            response = verify_failure(ret_code)
        else:
            # workflow is expected to run
            response = self.verify_outputs(expected, results_file, ret_code)
        return response

    def verify_outputs(self, expected: dict, results_file: str, ret_code: int) -> dict:
        """
        Verify that the test result outputs are the same as the expected output from the conformance file

        :param expected: expected value object
        :param results_file: filepath of resulting output file from the WDL runner
        :param ret_code: return code from WDL runner
        """
        if ret_code:
            return {'status': 'FAILED', 'reason': f"Workflow failed to run!"}

        try:
            with open(results_file, 'r') as f:
                test_results = json.load(f)
        except OSError:
            return {'status': 'FAILED', 'reason': f'Results file at {results_file} cannot be opened'}
        except json.JSONDecodeError:
            return {'status': 'FAILED', 'reason': f'Results file at {results_file} is not JSON'}

        if len(test_results['outputs']) != len(expected):
            return {'status': 'FAILED',
                    'reason': f"'outputs' section expected {len(expected)} results ({list(expected.keys())}), got "
                              f"{len(test_results['outputs'])} instead ({list(test_results['outputs'].keys())})"}

        result_outputs = test_results['outputs']

        result = {'status': f'SUCCEEDED', 'reason': None}

        # compare expected output to result output
        for identifier, output in result_outputs.items():
            try:
                python_type = convert_type(expected[identifier]['type'])
            except KeyError:
                return {'status': 'FAILED',
                        'reason': f"Output variable name '{identifier}' not found in expected results!"}

            if python_type is None:
                return {'status': 'FAILED', 'reason': f"Invalid expected type: {expected[identifier]['type']}!"}

            if 'value' not in expected[identifier]:
                return {'status': 'FAILED', 'reason': f"Test has no expected output of key 'value'!"}
            result = self.compare_outputs(expected[identifier]['value'], output, python_type)
            if result['status'] == 'FAILED':
                return result
        return result

    # Make sure output groups don't clobber each other.
    LOG_LOCK = threading.Lock()

    def run_single_test(self, test_index: int, test: dict, runner: str, version: str, time: bool, verbose: bool,
                        quiet: bool, args: Optional[Dict[str, Any]]) -> dict:
        """
        Run a test and log success or failure.

        Return the response dict.
        """
        if test.get("setup") is not None:
            run_setup(test["setup"])
        inputs = test['inputs']
        wdl_dir = inputs['dir']
        wdl_input = inputs.get('wdl', f'{wdl_dir}.wdl')  # default wdl name
        json_input = inputs.get('json', f'{wdl_dir}.json')  # default json name
        abs_wdl_dir = os.path.abspath(wdl_dir)
        if version == "draft-2":
            wdl_input = f'{wdl_dir}/{wdl_input}'
        elif version == "1.0":
            wdl_input = f'{wdl_dir}/{wdl_input}'
        elif version == "1.1":
            wdl_input = f'{wdl_dir}/{wdl_input}'
        else:
            return {'status': 'FAILED', 'reason': f'WDL version {version} is not supported!'}

        json_path = f'{wdl_dir}/{json_input}'  # maybe return failing result if no json file found

        wdl_file = os.path.abspath(get_wdl_file(wdl_input, abs_wdl_dir, version))
        json_file = os.path.abspath(json_path)
        test_args = args[runner].split(" ") if args[runner] is not None else []
        outputs = test['outputs']
        results_file = os.path.abspath(f'results-{uuid4()}.json')
        wdl_runner = RUNNERS[runner]
        cmd = wdl_runner.format_command(wdl_file, json_file, results_file, test_args, verbose)

        realtime = None
        if time:
            realtime_start = timeit.default_timer()
            (ret_code, stdout, stderr) = run_cmd(cmd=cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
            realtime_end = timeit.default_timer()
            realtime = realtime_end - realtime_start
        else:
            (ret_code, stdout, stderr) = run_cmd(cmd=cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

        if verbose:
            with self.LOG_LOCK:
                announce_test(test_index, test, version, runner)
        response = self.run_verify(outputs, results_file, ret_code)

        if time:
            response['time'] = {"real": realtime}
        if not quiet and (verbose or response['status'] == 'FAILED'):
            response['stdout'] = stdout.decode("utf-8", errors="ignore")
            response['stderr'] = stderr.decode("utf-8", errors="ignore")
        return response

    def handle_test(self, test_index: int, test: Dict[str, Any], runner: str, version: str, time: bool,
                    verbose: bool, quiet: bool, args: Optional[Dict[str, Any]], repeat: Optional[int] = None,
                    progress: bool = False) -> Dict[str, Any]:
        """
        Decide if the test should be skipped. If not, run it.

        Returns a result that can have status SKIPPED, SUCCEEDED, or FAILED.
        """
        response = {'description': test.get('description'), 'number': test_index, 'id': test.get('id')}
        if version not in test['versions']:
            # Test to skip, if progress is true, then output
            if progress:
                print(f"Skipping test {test_index} (ID: {test['id']}) with runner {runner} on WDL version {version}.")
            response.update({'status': 'SKIPPED'})
            # return reason only if verbose is true
            if verbose:
                response.update({'reason': f'Test only applies to versions: {",".join(test["versions"])}'})
            return response
        else:
            # New test to run, if progress is true, then output
            if progress:
                print(f"Running test {test_index} (ID: {test['id']}) with runner {runner} on WDL version {version}.")
            response.update(self.run_single_test(test_index, test, runner, version, time, verbose, quiet, args))
        if repeat is not None:
            response["repeat"] = repeat
        return response

    def run_and_generate_tests_args(self, tags: Optional[str], numbers: Optional[str], versions: str, runner: str,
                                    threads: int = 1, time: bool = False, verbose: bool = False, quiet: bool = False,
                                    args: Optional[Dict[str, Any]] = None, exclude_numbers: Optional[str] = None,
                                    ids: Optional[str] = None, repeat: Optional[int] = None, progress: bool = False) \
            -> Tuple[List[Any], bool]:
        # Get all the versions to test.
        # Unlike with CWL, WDL requires a WDL file to declare a specific version,
        # and prohibits mixing file versions in a workflow, although some runners
        # might allow it.
        # But the tests all need to be for single WDL versions.
        versions_to_test = set(versions.split(','))
        selected_tests = get_specific_tests(conformance_tests=self.tests, tag_argument=tags, number_argument=numbers,
                                            exclude_number_argument=exclude_numbers, id_argument=ids)
        selected_tests_amt = len(selected_tests) * len(versions_to_test) * repeat
        successes = 0
        skips = 0
        test_responses = list()
        print(f'Testing runner {runner} on WDL versions: {",".join(versions_to_test)}\n')
        with ProcessPoolExecutor(max_workers=threads) as executor:  # process instead of thread so realtime works
            pending_futures = []
            for test_index in selected_tests:
                try:
                    test = self.tests[test_index]
                except KeyError:
                    print(f'ERROR: Provided test [{test_index}] do not exist.')
                    sys.exit(1)
                for version in versions_to_test:
                    for iteration in range(repeat):
                        # Handle each test as a concurrent job
                        result_future = executor.submit(self.handle_test,
                                                        test_index,
                                                        test,
                                                        runner,
                                                        version,
                                                        time,
                                                        verbose,
                                                        quiet,
                                                        args,
                                                        iteration + 1 if repeat is not None else None,
                                                        progress)
                        pending_futures.append(result_future)
            completed_count = 0
            for result_future in as_completed(pending_futures):
                completed_count += 1
                # Go get each result
                result = result_future.result()
                test_responses.append(result)
                if progress:
                    # if progress is true, then print a summarized output of the completed test and current status
                    print(f"{completed_count}/{selected_tests_amt}. Test {result['number']} (ID: {test['id']}) completed "
                          f"with status {result['status']}. ")

        print("\n=== REPORT ===\n")

        # print tests in order to improve readability
        test_responses.sort(key=lambda a: a['number'])
        for response in test_responses:
            print_response(response)
            if response['status'] == 'SUCCEEDED':
                successes += 1
            elif response['status'] == 'SKIPPED':
                skips += 1

        print(
            f'{selected_tests_amt - skips} tests run, {successes} succeeded, {selected_tests_amt - skips - successes} '
            f'failed, {skips} skipped')

        if successes < selected_tests_amt - skips:
            # identify the failing tests
            failed_ids = [str(response['number']) for response in test_responses if
                          response['status'] not in {'SUCCEEDED', 'SKIPPED'}]
            print(f"\tFailures: {','.join(failed_ids)}")
            return test_responses, False
        return test_responses, True

    def run_and_generate_tests(self, options: argparse.Namespace) -> Tuple[List[Any], bool]:
        """
        Call run_and_generate_tests_args with a namespace object
        """
        args = {}
        for runner in RUNNERS.keys():
            if runner == "miniwdl":
                args[runner] = options.miniwdl_args
            if runner == "toil-wdl-runner":
                args[runner] = options.toil_args
            if runner == "cromwell":
                args[runner] = options.cromwell_args
        return self.run_and_generate_tests_args(tags=options.tags, numbers=options.numbers,
                                                versions=options.versions, runner=options.runner,
                                                time=options.time, verbose=options.verbose,
                                                quiet=options.quiet, threads=options.threads,
                                                args=args,
                                                exclude_numbers=options.exclude_numbers,
                                                ids=options.id, repeat=options.repeat,
                                                progress=options.progress)


def add_options(parser) -> None:
    """
    Add options to a parser
    """
    parser.add_argument("--verbose", default=False, action='store_true',
                        help='Print more information about a test')
    parser.add_argument("--versions", "-v", default="1.0",
                        help='Select the WDL versions you wish to test against.')
    parser.add_argument("--tags", "-t", default=None,
                        help='Select the tags to run specific tests')
    parser.add_argument("--numbers", "-n", default=None,
                        help='Select the WDL test numbers you wish to run.')
    parser.add_argument("--runner", "-r", default='cromwell',
                        help='Select the WDL runner to use.')
    parser.add_argument("--threads", type=int, default=1,
                        help='Number of tests to run in parallel.')
    parser.add_argument("--time", default=False, action="store_true",
                        help="Time the conformance test run.")
    parser.add_argument("--quiet", default=False, action="store_true")
    parser.add_argument("--exclude-numbers", default=None, help="Exclude certain test numbers.")
    parser.add_argument("--toil-args", default=None, help="Arguments to pass into toil-wdl-runner. Ex: "
                                                          "--toil-args=\"caching=False\"")
    parser.add_argument("--miniwdl-args", default=None, help="Arguments to pass into miniwdl. Ex: "
                                                             "--miniwdl-args=\"--no-outside-imports\"")
    parser.add_argument("--cromwell-args", default=None, help="Arguments to pass into cromwell. Ex: "
                                                              "--cromwell-args=\"--options=[OPTIONS]\"")
    parser.add_argument("--id", default=None, help="Specify a WDL test by ID.")
    parser.add_argument("--repeat", default=1, type=int, help="Specify how many times to run each test.")
    # Test responses are collected and sorted, so this option allows the script to print out the current progress
    parser.add_argument("--progress", default=False, action="store_true", help="Print the progress of the test suite "
                                                                               "as it runs.")


def main(argv=None):
    # get directory of conformance tests and store as environmental variable
    # used to specify absolute paths in conformance file
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description='Run WDL conformance tests.')
    add_options(parser)
    args = parser.parse_args(argv)

    if args.runner not in RUNNERS:
        print(f'Unsupported runner: {args.runner}')
        sys.exit(1)

    conformance_runner = WDLConformanceTestRunner(conformance_file="conformance.yaml")
    _, successful_run = conformance_runner.run_and_generate_tests(args)
    if not successful_run:
        # Fail the program overall if tests failed.
        sys.exit(1)


if __name__ == '__main__':
    main()
