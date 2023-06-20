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
from ruamel.yaml import YAML

from concurrent.futures import ThreadPoolExecutor, as_completed
from shutil import which
from uuid import uuid4

from WDL.Type import Float as WDLFloat, String as WDLString, File as WDLFile, Int as WDLInt, Boolean as WDLBool, \
    Array as WDLArray, Map as WDLMap, Pair as WDLPair, StructInstance as WDLStruct

from typing import Optional, Iterable, Any
from WDL.Type import Base as WDLBase


class WDLRunner:
    """
    A class describing how to invoke a WDL runner to run a workflow.
    """

    def format_command(self, wdl_file, json_file, results_file, args, verbose):
        raise NotImplementedError


class CromwellStyleWDLRunner(WDLRunner):
    def __init__(self, runner):
        self.runner = runner

    def format_command(self, wdl_file, json_file, results_file, args, verbose):
        return f'{self.runner} {wdl_file} -i {json_file} -m {results_file} {" ".join(args)}'


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
                        run_cmd(cmd='make cromwell', cwd=os.getcwd())
                    self.runner = f'java {log_level} -jar {cromwell} run'

        return super().format_command(wdl_file, json_file, results_file, args, verbose)


class MiniWDLStyleWDLRunner(WDLRunner):
    def __init__(self, runner):
        self.runner = runner

    def format_command(self, wdl_file, json_file, results_file, args, verbose):
        directory = '-d miniwdl-logs'
        return f'{self.runner} {wdl_file} -i {json_file} -o {results_file} {" ".join(args)} {directory} --verbose'


RUNNERS = {
    'cromwell': CromwellWDLRunner(),
    'toil-wdl-runner-old': CromwellStyleWDLRunner('toil-wdl-runner-old'),
    'toil-wdl-runner': CromwellStyleWDLRunner('toil-wdl-runner --outputDialect miniwdl'),
    'miniwdl': MiniWDLStyleWDLRunner('miniwdl run')
}


def run_cmd(cmd, cwd):
    p = subprocess.Popen(cmd, stdout=-1, stderr=-1, shell=True, cwd=cwd)
    stdout, stderr = p.communicate()

    return p.returncode, stdout, stderr


def convert_type(wdl_type: Any) -> Optional[WDLBase]:
    """
    Given a string description of a type in WDL, return an instance
    of a MiniWDL WDL.Type class that represents the given type.

    :param wdl_type: representation of wdl type
    """
    outer_py_typ = wdl_type_to_miniwdl_class(wdl_outer_type(wdl_type))

    if outer_py_typ is WDLStruct:
        # objects currently forced to be typed just like structs
        struct_type = WDLStruct("Struct")
        members = {}

        for k, v in wdl_type.items():
            value_type = convert_type(v)
            # if value type conversion failed, then type is invalid, so return None
            if value_type is None:
                return None
            members[k] = value_type
        struct_type.members = members

        return struct_type

    if outer_py_typ is WDLPair:
        inner_type = wdl_inner_type(wdl_type)

        key_and_value_type = inner_type.split(',')
        if len(key_and_value_type) < 2:
            # either no inner type provided or not enough type provided for pair
            return None
        key_type = key_and_value_type[0].strip()
        value_type = key_and_value_type[1].strip()
        left_type = convert_type(key_type)
        right_type = convert_type(value_type)
        return WDLPair(left_type, right_type)

    if outer_py_typ is WDLMap:
        inner_type = wdl_inner_type(wdl_type)

        key_and_value_type = inner_type.split(',')
        if len(key_and_value_type) < 2:
            # either no types or too few types provided for map
            return None
        key_type = key_and_value_type[0].strip()
        value_type = key_and_value_type[1].strip()
        converted_key_type = convert_type(key_type)
        converted_value_type = convert_type(value_type)

        # if inner type conversion failed, return None
        if None in (converted_key_type, converted_value_type):
            return None

        return WDLMap((converted_key_type, converted_value_type))

    if outer_py_typ is WDLArray:
        inner_type = wdl_inner_type(wdl_type)
        if inner_type in ('Array', ''):
            # no given inner type
            return None
        converted_inner_type = convert_type(inner_type)
        # if inner type conversion failed, then type is invalid, so return None
        return outer_py_typ(converted_inner_type) if converted_inner_type is not None else None
    # primitives remaining
    return wdl_type_to_miniwdl_class(wdl_type)()


def wdl_type_to_miniwdl_class(wdl_type: Any) -> Optional[WDLBase]:
    """
    Given a WDL type name, return a MiniWDL class.

    Currently supports File, Int, Boolean, String, Float, Array, Map, Struct, Object (treated same as Struct)

    Structs are inputted as dictionaries

    :param wdl_type: representation of WDL type
    """

    if wdl_type == 'File':
        return WDLFile
    elif wdl_type == 'Int':
        return WDLInt
    elif wdl_type == 'Boolean':
        return WDLBool
    elif wdl_type == 'String':
        return WDLString
    elif wdl_type == 'Array':
        return WDLArray
    elif wdl_type == 'Float':
        return WDLFloat
    elif wdl_type == 'Map':
        return WDLMap
    elif wdl_type == 'Pair':
        return WDLPair
    elif isinstance(wdl_type, dict):
        return WDLStruct
    else:
        raise NotImplementedError
        # return None


def wdl_outer_type(wdl_type):
    """
    Get the outermost type of a WDL type. So "Array[String]" gives "Array".
    """
    # deal with structs
    if isinstance(wdl_type, dict):
        return wdl_type
    return wdl_type.split('[')[0]


def wdl_inner_type(wdl_type):
    """
    Get the interior type of a WDL type. So "Array[String]" gives "String".
    """
    if '[' in wdl_type:
        return '['.join(wdl_type.split('[')[1:])[:-1]
    else:
        return wdl_type


def expand_vars_in_expected(expected_value: Iterable) -> None:
    """
    For the expected value, expand all ${WDL_DIR} environmental variables

    When WDL functions convert paths to strings, they use the absolute path. ${WDL_DIR} specifies the path of the
    conformance test folder to add before the string of the relative path

    ex: Functions such as quote() and squote() take type File:
      path/to/file.txt
    and turn it into type String:
      "/home/user/wdl-conformance-tests/path/to/file.txt"
    """
    if isinstance(expected_value, list):
        for i, value in enumerate(expected_value):
            if isinstance(value, list) or isinstance(value, dict):
                expand_vars_in_expected(value)
            else:
                if isinstance(value, str):
                    expected_value[i] = os.path.expandvars(value)

    if isinstance(expected_value, dict):
        for name, value in expected_value.items():
            if isinstance(value, list) or isinstance(value, dict):
                expand_vars_in_expected(value)
            else:
                if isinstance(value, str):
                    expected_value[name] = os.path.expandvars(value)

def py_type_of_wdl_class(wdl_type: WDLBase):
    """
    Return python equivalent type for a given WDL.Type class
    """
    if isinstance(wdl_type, WDLInt):
        return int
    elif isinstance(wdl_type, WDLFloat):
        return float
    elif isinstance(wdl_type, WDLBool):
        return bool
    elif isinstance(wdl_type, WDLString):
        return str

def compare_outputs(expected: Any, result: Any, typ: WDLBase):
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
                                                      f"Actual result was: {result}!"}
            for i in range(len(expected)):
                status_result = compare_outputs(expected[i], result[i], typ.item_type)
                if status_result['status'] == 'FAILED':
                    return status_result
        except TypeError:
            return {'status': 'FAILED', 'reason': f"Not an array!\nExpected output: {expected}\n"
                                                  f"Result output: {result}"}

    if isinstance(typ, WDLMap):
        try:
            if len(expected) != len(result):
                return {'status': 'FAILED', 'reason': f"Size of expected and result do not match!\n"
                                                      f"Expected output: {expected}\n"
                                                      f"Actual result was: {result}!"}
            for key in expected.keys():
                status_result = compare_outputs(expected[key], result[key], typ.item_type[1])
                if status_result['status'] == 'FAILED':
                    return status_result
        except (KeyError, TypeError):
            return {'status': 'FAILED', 'reason': f"Not a map or missing keys!\nExpected output: {expected}\n"
                                                  f"Result output: {result}"}

    # WDLStruct also represents WDLObject
    # Objects in conformance will be forced to be typed, same as Structs
    if isinstance(typ, WDLStruct):
        try:
            if len(expected) != len(result):
                return {'status': 'FAILED', 'reason': f"Size of expected and result do not match!\n"
                                                      f"Expected output: {expected}\n"
                                                      f"Actual result was: {result}!"}
            for key in expected.keys():
                status_result = compare_outputs(expected[key], result[key], typ.members[key])
                if status_result['status'] == 'FAILED':
                    return status_result
        except (KeyError, TypeError):
            return {'status': 'FAILED', 'reason': f"Not a struct or missing keys!\nExpected output: {expected}\n"
                                                  f"Result output: {result}"}

    if isinstance(typ, (WDLInt, WDLFloat, WDLBool, WDLString)):
        # check that outputs are the same
        if expected != result:
            return {'status': 'FAILED', 'reason': f"Expected and result do not match!\n"
                                                  f"Expected output: {expected}\n"
                                                  f"Actual result was: {result}!"}
        # check that output types are correct
        if not isinstance(expected, py_type_of_wdl_class(typ)) or not isinstance(result, py_type_of_wdl_class(typ)):
            return {'status': 'FAILED', 'reason': f"Incorrect types!\n"
                                                  f"Expected output: {expected}\n"
                                                  f"Actual result was: {result}!"}

    if isinstance(typ, WDLFile):
        # check file path exists
        if not os.path.exists(result):
            return {'status': 'FAILED', 'reason': f"Result file does not exist!\n"
                                                  f"Expected filepath: {result}!"}

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
                                                  f"Result output: {result}"}
    return {'status': f'SUCCEEDED', 'reason': None}


def run_verify(expected: dict, results_file: str, ret_code: int) -> dict:
    """
    Check either for proper output or proper success/failure of WDL program, depending on if 'fail' is included in the
    conformance test
    """
    if 'fail' in expected.keys():
        # workflow is expected to fail
        response = verify_failure(ret_code)
    else:
        # workflow is expected to run
        response = verify_outputs(expected, results_file, ret_code)
    return response


def verify_outputs(expected: dict, results_file: str, ret_code: int) -> dict:
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
                'reason': f"'outputs' section expected {len(test_results['outputs'])} results, got {len(expected)} instead"}

    result_outputs = test_results['outputs']

    result = {'status': f'SUCCEEDED', 'reason': None}

    # compare expected output to result output
    for identifier, output in result_outputs.items():
        try:
            python_type = convert_type(expected[identifier]['type'])
        except KeyError:
            return {'status': 'FAILED', 'reason': f"Output variable name '{identifier}' not found in expected results!"}

        if python_type is None:
            return {'status': 'FAILED', 'reason': f"Invalid expected type: {expected[identifier]['type']}!"}

        if 'value' not in expected[identifier]:
            return {'status': 'FAILED', 'reason': f"Test has no expected output of key 'value'!"}
        result = compare_outputs(expected[identifier]['value'], output, python_type)
        if result['status'] == 'FAILED':
            return result
    return result


def verify_failure(ret_code: int) -> dict:
    """
    Verify that the workflow did fail

    ret_code should be the status code WDL runner outputs when running the test
    :param ret_code: return code from WDL runner

    If ret_code is fail (>0 or True), then return success
    If ret_code is success (0 or False), then return failure
    """
    # This currently only tests if the workflow simply failed to run or not. It cannot differentiate
    # between different error codes. Cromwell and MiniWDL (and toil-wdl-runner) return different error codes for the
    # same WDL error and the results file that they write to do not look very similar
    # toil-wdl-runner doesn't seem to write to the results file at all?
    # There might be a better method
    if not ret_code:
        return {'status': 'FAILED',
                'reason': f"Workflow did not fail!"}

    # proper failure, return success
    return {'status': f'SUCCEEDED'}


def announce_test(test_index, test, version):
    parsed_description = test["description"].strip().replace("\n", "; ")
    if version is not None:
        print(f'{test_index}: RUNNING with WDL version {version}: {parsed_description}')


# Make sure output groups don't clobber each other.
LOG_LOCK = threading.Lock()


def print_response(response):
    """
    Log a test response that has a status and maybe a reason.
    """
    # remove newlines in description to make printing neater
    parsed_description = response["description"].strip().replace("\n", "; ")
    print(f'{response["number"]}: {response["status"]}: {parsed_description}')
    if response["status"] == "FAILED":
        print(f"REASON: {response['reason']}")

    # if failed or --verbose, stdout and stderr will exist, so print
    if response.get("stdout"):
        print(f'stdout: {response.get("stdout")}\n')
    if response.get("stderr"):
        print(f'stderr: {response.get("stderr")}')


def run_test(test_index: str, test: dict, runner: WDLRunner, verbose: bool, version: str) -> dict:
    """
    Run a test and log success or failure.

    Return the response dict.
    """

    if version not in test['versions']:
        return {'status': 'SKIPPED', 'reason': f'Test only applies to versions: {",".join(test["versions"])}'}

    inputs = test['inputs']
    wdl_input = inputs['wdl']
    json_input = inputs['json']
    match version:
        case "draft-2":
            wdl_input = f'tests/draft-2/{wdl_input}'
            json_input = f'tests/draft-2/{json_input}'
        case "1.0":
            wdl_input = f'tests/version_1.0/{wdl_input}'
            json_input = f'tests/version_1.0/{json_input}'
        case "1.1":
            wdl_input = f'tests/version_1.1/{wdl_input}'
            json_input = f'tests/version_1.1/{json_input}'
        case _:
            return {'status': 'FAILED', 'reason': f'WDL version {version} is not supported!'}

    wdl_file = os.path.abspath(wdl_input)
    json_file = os.path.abspath(json_input)

    args = test.get('args', [])
    outputs = test['outputs']
    results_file = os.path.abspath(f'results-{uuid4()}.json')
    cmd = runner.format_command(wdl_file, json_file, results_file, args, verbose)

    (ret_code, stdout, stderr) = run_cmd(cmd=cmd, cwd=os.path.dirname(os.path.abspath(__file__)))

    if verbose:
        with LOG_LOCK:
            announce_test(test_index, test, version)
    response = run_verify(outputs, results_file, ret_code)

    if verbose or response['status'] == 'FAILED':
        response['stdout'] = stdout.decode("utf-8", errors="ignore")
        response['stderr'] = stderr.decode("utf-8", errors="ignore")
    return response


def handle_test(test_index, test, runner, version, verbose):
    """
    Decide if the test should be skipped. If not, run it.

    Returns a result that can have status SKIPPED, SUCCEEDED, or FAILED.
    """
    response = {'description': test.get('description'), 'number': test_index}
    if version not in test['versions']:
        response.update({'status': 'SKIPPED', 'reason': f'Test only applies to versions: {",".join(test["versions"])}'})
        return response
    else:
        response.update(run_test(test_index, test, runner, verbose, version))
    return response


def get_tags(tags):
    """
    Parse the tag argument

    Given the tag argument, return all tags as a set
    """
    if tags is None:
        return None
    all_tags = [i for i in tags.split(',') if i]
    tests = set()
    for f in all_tags:
        tests.add(f)
    return tests


def get_test_indices(number_argument):
    """
    Parse the number argument

    Given the number argument, return all selected test numbers/indices as a set
    """
    if number_argument is None:
        return None
    ranges = [i for i in number_argument.split(',') if i]
    split_ranges = [i.split('-') if '-' in i else [i, i] for i in ranges]
    tests = set()
    for start, end in split_ranges:
        for test_number in range(int(start), int(end) + 1):
            tests.add(test_number)
    return tests


def get_specific_tests(conformance_tests, tag_argument, number_argument):
    """
    Given the expected tests, tag argument, and number argument, return a list of all test numbers/indices to run
    """
    given_indices = get_test_indices(number_argument)
    given_tags = get_tags(tag_argument)
    tests = set()
    if given_indices is None:
        given_indices = [i for i in range(len(conformance_tests))]
    for test_number in given_indices:
        test_tags = conformance_tests[test_number]['tags']
        if given_tags is None or any(tag in given_tags for tag in test_tags):
            tests.add(test_number)
    return sorted(list(tests))


def main(argv=sys.argv[1:]):
    # get directory of conformance tests and store as environmental variable
    # used to specify absolute paths in conformance file
    os.environ['WDL_DIR'] = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description='Run WDL conformance tests.')
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
    parser.add_argument("--threads", type=int, default=None,
                        help='Number of tests to run in parallel.')
    args = parser.parse_args(argv)

    # Get all the versions to test.
    # Unlike with CWL, WDL requires a WDL file to declare a specific version,
    # and prohibits mixing file versions in a workflow, although some runners
    # might allow it.
    # But the tests all need to be for single WDL versions.
    versions_to_test = set(args.versions.split(','))

    yaml = YAML(typ='safe')
    with open('conformance.yaml', 'r') as f:
        tests = yaml.load(f)

    if args.runner not in RUNNERS:
        print(f'Unsupported runner: {args.runner}')
        sys.exit(1)

    runner = RUNNERS[args.runner]

    print(f'Testing runner {args.runner} on WDL versions: {",".join(versions_to_test)}\n')

    successes = 0
    skips = 0

    selected_tests = get_specific_tests(tests, args.tags, args.numbers)

    selected_tests_amt = len(selected_tests) * len(versions_to_test)

    test_responses = list()

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        pending_futures = []
        for test_index in selected_tests:
            for version in versions_to_test:
                try:
                    test = tests[test_index]
                    expand_vars_in_expected(test)
                except KeyError:
                    print(f'ERROR: Provided test [{test_index}] do not exist.')
                    sys.exit(1)
                # Handle each test as a concurrent job
                result_future = executor.submit(handle_test,
                                                test_index,
                                                test,
                                                runner,
                                                version,
                                                args.verbose)
                pending_futures.append(result_future)
        for result_future in as_completed(pending_futures):
            # Go get each result or reraise the relevant exception
            result = result_future.result()
            test_responses.append(result)
            if result['status'] == 'SUCCEEDED':
                successes += 1
            elif result['status'] == 'SKIPPED':
                skips += 1

        # print tests in order to improve readability
        test_responses.sort(key = lambda a: a['number'])
        for response in test_responses:
            print_response(response)

    print(
        f'{selected_tests_amt - skips} tests run, {successes} succeeded, {selected_tests_amt - skips - successes} failed, {skips} skipped')

    if successes < selected_tests_amt - skips:
        # Fail the program overall if tests failed.
        sys.exit(1)


if __name__ == '__main__':
    main()
