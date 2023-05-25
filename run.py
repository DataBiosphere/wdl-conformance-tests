"""

"""

import os
import json
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


class WDLRunner:
    """
    A class describing how to invoke a WDL runner to run a workflow.
    """

    def format_command(self, wdl_file, json_file, results_file, args, quiet):
        raise NotImplementedError


class CromwellStyleWDLRunner(WDLRunner):
    def __init__(self, runner):
        self.runner = runner

    def format_command(self, wdl_file, json_file, results_file, args, quiet):
        return f'{self.runner} {wdl_file} -i {json_file} -m {results_file} {" ".join(args)}'


class CromwellWDLRunner(CromwellStyleWDLRunner):
    download_lock = threading.Lock()

    def __init__(self):
        super().__init__('cromwell')

    def format_command(self, wdl_file, json_file, results_file, args, quiet):
        if self.runner == 'cromwell' and not which('cromwell'):
            with CromwellWDLRunner.download_lock:
                if self.runner == 'cromwell':
                    # if there is no cromwell binary seen on the path, download
                    # our pinned version and use that instead
                    log_level = '-DLOG_LEVEL=OFF' if quiet else ''
                    cromwell = os.path.abspath('build/cromwell.jar')
                    if not os.path.exists(cromwell):
                        print('Cromwell not seen in the path, now downloading cromwell to run tests... ')
                        run_cmd(cmd='make cromwell', cwd=os.getcwd())
                    self.runner = f'java {log_level} -jar {cromwell} run'

        return super().format_command(wdl_file, json_file, results_file, args, quiet)


class MiniWDLStyleWDLRunner(WDLRunner):
    def __init__(self, runner):
        self.runner = runner

    def format_command(self, wdl_file, json_file, results_file, args, quiet):
        directory = '-d miniwdl-logs'
        return f'{self.runner} {wdl_file} -i {json_file} -o {results_file} {" ".join(args)} {directory}'


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


def convert_type(wdl_type):
    outer_py_typ = wdl_type_to_miniwdl_class(wdl_outer_type(wdl_type))

    if outer_py_typ is WDLStruct:
        # objects currently forced to be typed just like structs
        struct_type = WDLStruct("Struct")
        members = {}

        for k, v in wdl_type.items():
            members[k] = convert_type(v)
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
        return WDLMap((convert_type(key_type), convert_type(value_type)))

    if outer_py_typ is WDLArray:
        inner_type = wdl_inner_type(wdl_type)
        if inner_type == 'Array':
            # no given inner type
            return None
        return outer_py_typ(convert_type(inner_type))
    # primitives remaining
    return wdl_type_to_miniwdl_class(wdl_type)()


def wdl_type_to_miniwdl_class(wdl_type):
    """
    Given a WDL type name, return a MiniWDL class.

    Currently supports File, Int, Boolean, String, Float, Array, Map, Struct, Object (treated same as Struct)
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
    if wdl_type.find('['):
        return '['.join(wdl_type.split('[')[1:])[:-1]
    else:
        return wdl_type


def expand_vars_in_expected(expected_value):
    """
    For the expected value, expand all ${WDL_DIR} environmental variables

    When WDL functions converts paths to strings, it uses the absolute path. ${WDL_DIR} specifies the path of the
    conformance test folder to add before the string of the relative path
    """
    # ex: Functions such as quote() and squote() takes type File:
    #   path/to/file.txt
    # and turns it into type String:
    #   "/home/user/wdl-conformance-tests/path/to/file.txt"
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


def compare_outputs(expected, result, typ):
    """
    Recursively ensure that the expected output object is the same as the resulting output object

    In the future, make this return where it failed instead to give less generic error messages

    :param expected: expected output object from conformance file
    :param result: result ouput object from output file from WDL runner
    :param typ: type of output from conformance file
    """
    if isinstance(typ, WDLArray):
        try:
            if len(expected) != len(result):
                return False
            for i in range(len(expected)):
                if not compare_outputs(expected[i], result[i], typ.item_type):
                    return False
        except TypeError:
            return False

    if isinstance(typ, WDLMap):
        try:
            if len(expected) != len(result):
                return False
            for key in expected.keys():
                if not compare_outputs(expected[key], result[key], typ.item_type[1]):
                    return False
        except (KeyError, TypeError):
            return False

    # WDLStruct also represents WDLObject
    # Objects in conformance will be forced to be typed, same as Structs
    if isinstance(typ, WDLStruct):
        try:
            if len(expected) != len(result):
                return False
            for key in expected.keys():
                if not compare_outputs(expected[key], result[key], typ.members[key]):
                    return False
        except (KeyError, TypeError):
            return False

    if isinstance(typ, (WDLInt, WDLFloat, WDLBool, WDLString)):
        if expected != result:
            return False

    if isinstance(typ, WDLFile):
        # check file path exists
        if not os.path.exists(result):
            return False

        # check md5sum
        with open(result, 'rb') as f:
            md5sum = hashlib.md5(f.read()).hexdigest()
        if md5sum != expected['md5sum']:
            return False

    if isinstance(typ, WDLPair):
        try:
            if len(expected) != 2:
                return False
            if expected['left'] != result['left'] or expected['right'] != result['right']:
                return False
        except (KeyError, TypeError):
            return False

    return True


def run_verify(expected, results_file, ret_code):
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


def verify_outputs(expected, results_file, ret_code):
    """
    Verify that the test result outputs are the same as the expected output from the conformance file

    :param expected: dict of expected output from conformance file
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
        if not compare_outputs(expected[identifier]['value'], output, python_type):
            return {'status': 'FAILED', 'reason': f"\nExpected output: {expected[identifier]['value']}\nActual "
                                                  f"result was: {output}!"}
    return {'status': f'SUCCEEDED', 'reason': None}


def verify_failure(ret_code):
    """
    Verify that the workflow did fail

    ret_code should be what code WDL outputs when running the test
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


def announce_test(test_name, total_tests, test, version):
    description = test['description']
    print(f'\n{description}', end="")
    if version is not None:
        print(f'{test_name}: RUNNING\t\tWDL version: {version}')


# Make sure output groups don't clobber each other.
LOG_LOCK = threading.Lock()


def print_response(test_name, response):
    """
    Log a test response that has a status and maybe a reason.
    """
    print(f'{test_name}: {response["status"]}')
    if 'reason' in response and response['reason']:
        print(f'    REASON: {response["reason"]}')
    if 'return' in response:
        print(f'Runner exited with code {response["return"]}')
    if 'stdout' in response:
        print(f'\nstdout: {response["stdout"]}\n')
    if 'stderr' in response:
        print(f'\nstderr: {response["stderr"]}\n\n')


def run_test(test_name, total_tests, test, runner, quiet, version):
    """
    Run a test and log success or failure.

    Return the response dict.
    """
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
    cmd = runner.format_command(wdl_file, json_file, results_file, args, quiet)
    with LOG_LOCK:
        announce_test(test_name, total_tests, test, version)

    (ret_code, stdout, stderr) = run_cmd(cmd=cmd, cwd=os.path.dirname(os.path.abspath(__file__)))
    response = {}

    response.update(run_verify(outputs, results_file, ret_code))

    if not quiet or response['status'] == 'FAILED':
        response['stdout'] = stdout.decode("utf-8", errors="ignore")
        response['stderr'] = stderr.decode("utf-8", errors="ignore")
        response.update({'return': ret_code})

    with LOG_LOCK:
        print_response(test_name, response)

    return response


def handle_test(test_name, total_tests, test, runner, version, quiet):
    """
    Decide if the test should be skipped. If not, run it.

    Returns a result that can have status SKIPPED, SUCCEEDED, or FAILED.
    """
    if version not in test['versions']:
        response = {'status': 'SKIPPED', 'reason': f'Test only applies to versions: {",".join(test["versions"])}'}
        with LOG_LOCK:
            print_response(test_name, response)
        return response
    response = run_test(test_name, total_tests, test, runner, quiet, version)
    return response


def get_tags(functions):
    if functions is None:
        return []
    all_functions = [i for i in functions.split(',') if i]
    tests = set()
    for f in all_functions:
        tests.add(f)
    return tests


def main(argv=sys.argv[1:]):
    # get directory of conformance tests and store as environmental variable
    #
    os.environ['WDL_DIR'] = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description='Run WDL conformance tests.')
    parser.add_argument("--quiet", "-q", default=False, action='store_true',
                        help='Suppress printing run messages.')
    parser.add_argument("--versions", "-v", default="1.0",
                        help='Select the WDL versions you wish to test against.')
    parser.add_argument("--select", "-s", default=None,
                        help='Select the tags to run specific tests')
    parser.add_argument("--runner", "-r", default='cromwell',
                        help='Select the WDL runner to use.')
    parser.add_argument("--threads", "-t", type=int, default=None,
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

    total_tests = len(tests)

    if args.runner not in RUNNERS:
        print(f'Unsupported runner: {args.runner}')
        sys.exit(1)

    runner = RUNNERS[args.runner]

    print(f'Testing runner {args.runner} on WDL versions: {",".join(versions_to_test)}\n')

    successes = 0
    skips = 0

    specific_tests = get_tags(args.select)

    # get all tests to run by index
    selected_tests = []
    if len(specific_tests) == 0:
        selected_tests = [i for i in range(len(tests))]
    else:
        for i in range(len(tests)):
            test = tests[i]
            if any(func in test['tags'] for func in specific_tests):
                selected_tests.append(i)

    selected_tests_amt = len(selected_tests) * len(versions_to_test)

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        pending_futures = []
        for test_index in selected_tests:
            for version in versions_to_test:
                try:
                    test = tests[test_index]
                    expand_vars_in_expected(test)
                except KeyError:
                    print(f'ERROR: Provided tests [{", ".join(specific_tests)}] do not exist.')
                    sys.exit(1)
                # Handle each test as a concurrent job
                result_future = executor.submit(handle_test,
                                                test_index,
                                                total_tests,
                                                test,
                                                runner,
                                                version,
                                                args.quiet)
                pending_futures.append(result_future)
        for result_future in as_completed(pending_futures):
            # Go get each result or reraise the relevant exception
            result = result_future.result()
            if result['status']=='SUCCEEDED':
                successes += 1
            elif result['status'] == 'SKIPPED':
                skips += 1
    print(
        f'{selected_tests_amt - skips} tests run, {successes} succeeded, {selected_tests_amt - skips - successes} failed, {skips} skipped')

    if successes < selected_tests_amt - skips:
        # Fail the program overall if tests failed.
        sys.exit(1)


if __name__ == '__main__':
    main()
