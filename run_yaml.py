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
    Array as WDLArray, Map as WDLMap, Pair as WDLPair


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
    outer_type = wdl_outer_type(wdl_type)
    inner_type = wdl_inner_type(wdl_type)

    # primitive type
    if outer_type == inner_type:
        return wdl_type_to_python_type(wdl_type)

    return wdl_type_to_python_type(outer_type)(convert_type(inner_type))


def wdl_type_to_python_type(wdl_type):
    """
    Given a WDL type name, return a Python type.

    Currently supports File, Int, Boolean, String, Float, Array, and Map
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
    else:
        raise NotImplementedError
        # return None


def wdl_outer_type(wdl_type):
    """
    Get the outermost type of a WDL type. So "Array[String]" gives "Array".
    """

    return wdl_type.split('[')[0]


def wdl_inner_type(wdl_type):
    """
    Get the interior type of a WDL type. So "Array[String]" gives "String".
    """
    if '[' in wdl_type:
        return '['.join(wdl_type.split('[')[1:])[:-1]
    else:
        return wdl_type


def expand_vars_in_json(json_obj):
    if isinstance(json_obj, list):
        for i, value in enumerate(json_obj):
            if isinstance(value, list) or isinstance(value, dict):
                expand_vars_in_json(value)
            else:
                if isinstance(value, str):
                    json_obj[i] = os.path.expandvars(value)

    if isinstance(json_obj, dict):
        for name, value in json_obj.items():
            if isinstance(value, list) or isinstance(value, dict):
                expand_vars_in_json(value)
            else:
                if isinstance(value, str):
                    json_obj[name] = os.path.expandvars(value)


def validate(expected, result, typ):
    """
    Recursively ensure that the expected output is the same as the resulting output
    """
    if isinstance(typ, WDLArray):
        for i in range(len(expected)):
            if not validate(expected[i], result[i], typ.item_type):
                return False

    if isinstance(typ, WDLMap):
        for key in expected.keys():
            if not validate(expected[key], result[key], typ.item_type):
                return False

    if typ in (WDLInt, WDLFloat, WDLBool, WDLString):
        if expected != result:
            return False

    if typ is WDLFile:
        # check file path exists
        if not os.path.exists(result):
            return {'status': 'FAILED', 'reason': f"{result} not found!"}

        # check md5sum
        with open(result, 'rb') as f:
            md5sum = hashlib.md5(f.read()).hexdigest()
        if md5sum != expected:
            return False
    return True


def verify(expected, results_file, version, ret_code):
    if 'fail' in expected.keys():
        # workflow is expected to fail
        response = verify_failure(expected, version, ret_code)
    else:
        # workflow is expected to run
        response = verify_outputs(expected, results_file, version, ret_code)
    return response


def verify_outputs(expected, results_file, version, ret_code):
    """
    Verify that the test result outputs are the same as the expected output from the configuration file

    File types can be represented by both an md5hash and its filepath. However, MiniWDL returns new output files in a
    new timestamped directory each time, so comparing by filepath will not work. toil-wdl-runner seems to be the same.
    Cromwell seems to return the original filepath, so it should work for that?
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

        if not any(x in ['value', 'md5sum'] for x in expected[identifier]):
            return {'status': 'FAILED', 'reason': f"Test has no expected output!"}

        if 'value' in expected[identifier]:
            # easier to directly compare the result to the output rather than recursively comparing each item
            same = expected[identifier]['value'] == output
            if not same:
                return {'status': 'FAILED', 'reason': f"\nExpected output: {expected[identifier]['value']}\nActual "
                                                      f"result was: {output}!"}

        # file types may be represented as md5 hashes
        # they can also be compared via filepath, but for miniwdl (and toil-wdl-runner),
        # output files seem to be written to a timestamped directory each time
        # should work fine for cromwell though
        if 'md5sum' in expected[identifier]:
            print(output)
            if not validate(expected[identifier]['md5sum'], output, python_type):
                reason = f"For {expected[identifier]}, md5sum does not match for {output}!\n"
                return {'status': 'FAILED', 'reason': reason}

    return {'status': f'SUCCEEDED\t\tWDL version: {version}', 'reason': None}


def verify_failure(expected, version, error_code):
    """
    Verify that the workflow did fail

    This currently only tests if the workflow simply failed to run or not. It cannot differentiate
    between different error codes. Cromwell and MiniWDL (and toil-wdl-runner) return different error codes for the
    same WDL error and the results file that they write to do not look very similar
    toil-wdl-runner doesn't seem to write to the results file at all?
    There might be a better method
    """

    # expected_err_code = expected['fail']
    # if expected_err_code != error_code:
    #     return {'status': 'FAILED',
    #             'reason': f"Expected error code ({expected_err_code}) does not match resulting error code ({error_code})"}

    if not error_code:
        return {'status': 'FAILED',
                'reason': f"Workflow did not fail!"}

    # proper failure, return success
    return {'status': f'SUCCEEDED\t\tWDL version: {version}'}


def announce_test(test_name, total_tests, test, version):
    description = test['description']
    print(f'\n{description}', end="")
    if version is not None:
        print(f'{test_name}: RUNNING\t\tWDL version: {version}')


def get_versions(test, versions_to_test):
    """
    Return all versions for a test to run with

    Returns a list of versions
    """
    versions = []
    for version in test['versions']:
        if version in versions_to_test:
            versions.append(version)

    if len(versions) == 0:
        return None

    return versions


# Make sure output groups don't clobber each other.
LOG_LOCK = threading.Lock()


def print_response(test_name, total_tests, response):
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
            wdl_input = f'draft-2/{wdl_input}'
            json_input = f'draft-2/{json_input}'
        case "1.0":
            wdl_input = f'version_1.0/{wdl_input}'
            json_input = f'version_1.0/{json_input}'
        case "1.1":
            wdl_input = f'version_1.1/{wdl_input}'
            json_input = f'version_1.1/{json_input}'
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

    response.update(verify(outputs, results_file, version, ret_code))

    if not quiet or response['status'] == 'FAILED':
        response['stdout'] = stdout.decode("utf-8", errors="ignore")
        response['stderr'] = stderr.decode("utf-8", errors="ignore")
        response.update({'return': ret_code})

    with LOG_LOCK:
        print_response(test_name, total_tests, response)

    return response


def handle_test(test_name, total_tests, test, runner, versions_to_test, quiet):
    """
    Decide if the test should be skipped. If not, run it.
    
    Returns a result that can have status SKIPPED, SUCCEEDED, or FAILED.
    """
    versions = get_versions(test, versions_to_test)
    if versions is None:
        response = {'status': 'SKIPPED', 'reason': f'Test only applies to versions: {",".join(test["versions"])}'}
        with LOG_LOCK:
            print_response(test_name, total_tests, response)
        return response
    response = {}
    for version in versions:
        response = run_test(test_name, total_tests, test, runner, quiet, version)
    return response


def get_functions(functions):
    all_functions = [i for i in functions.split(',') if i]
    tests = set()
    for f in all_functions:
        tests.add(f)
    return tests


def main(argv=sys.argv[1:]):
    # print(os.path.abspath('.'))
    os.environ['WDL_DIR'] = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(description='Run WDL conformance tests.')
    parser.add_argument("--quiet", "-q", default=False, action='store_true',
                        help='Suppress printing run messages.')
    parser.add_argument("--versions", "-v", default="1.0",
                        help='Select the WDL versions you wish to test against.')
    # parser.add_argument("--numbers", "-n", default=None,
    #                     help='Select the WDL test numbers you wish to run.')
    parser.add_argument("--functions", "-f", default=None,
                        help='Select the functions you wish to only run.')
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

    all_tests = get_functions(args.functions) if args.functions else tests.keys()

    selected_tests_amt = len(all_tests)

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        pending_futures = []
        for test_name in all_tests:
            # test = all_tests[test_name]
            try:
                test = tests[test_name]
                expand_vars_in_json(test)
            except KeyError:
                print(f'ERROR: Provided tests [{", ".join(all_tests)}] do not exist.')
                sys.exit(1)
            # Handle each test as a concurrent job
            result_future = executor.submit(handle_test,
                                            test_name,
                                            total_tests,
                                            test,
                                            runner,
                                            versions_to_test,
                                            args.quiet)
            pending_futures.append(result_future)
        for result_future in as_completed(pending_futures):
            # Go get each result or reraise the relevant exception
            result = result_future.result()
            if result['status'].startswith('SUCCEEDED'):
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
