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
    Array as WDLArray, Map as WDLMap, Pair as WDLPair, Object as WDLObject, StructInstance as WDLStruct


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

    py_typ = wdl_type_to_python_type(outer_type)
    # deal with object and struct types, nested type may not be specified
    # miniwdl treats objects as structs essentially
    if py_typ is WDLStruct:
        if outer_type == "Object":
            return WDLStruct("Object")
        else:
            struct_type = WDLStruct("Struct")
            members = wdl_struct_inner_type_to_python_type(inner_type)

            struct_type.members = members

            return struct_type

    if py_typ is WDLPair:
        left_and_right_types = wdl_map_or_pair_inner_type_to_python_type(inner_type)
        left_type = left_and_right_types[0]
        right_type = left_and_right_types[1]
        return WDLPair(left_type, right_type)

    if py_typ is WDLMap:
        return WDLMap(wdl_map_or_pair_inner_type_to_python_type(inner_type))

    # test for primitive types
    if outer_type == inner_type:
        return wdl_type_to_python_type(wdl_type)()

    return py_typ(convert_type(inner_type))


def wdl_struct_inner_type_to_python_type(inner_type):
    if inner_type == 'Struct' or inner_type == 'Pair':
        # maybe this should return an error?
        return {}

    members = {}
    for each in inner_type.split(','):
        name_and_type = [e.strip() for e in each.split(':')]
        members[name_and_type[0]] = convert_type(name_and_type[1])
    return members


def wdl_map_or_pair_inner_type_to_python_type(inner_type):
    if inner_type == 'Map':
        # should probably return/raise an error in the future
        return ()

    key_and_value_type = inner_type.split(',')
    key_type = key_and_value_type[0].strip()
    value_type = key_and_value_type[1].strip()
    return convert_type(key_type), convert_type(value_type)


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
    elif wdl_type == 'Pair':
        return WDLPair
    elif wdl_type == 'Struct' or wdl_type == 'Object':
        return WDLStruct
    else:
        raise NotImplementedError
        # return None


def wdl_outer_type(wdl_type):
    """
    Get the outermost type of a WDL type. So "Array[String]" gives "Array".
    """

    if wdl_type.find('[') > wdl_type.find('{'):
        return wdl_type.split('[')[0]
    else:
        return wdl_type.split('{')[0]


def wdl_inner_type(wdl_type):
    """
    Get the interior type of a WDL type. So "Array[String]" gives "String".
    """
    if wdl_type.find('[') > wdl_type.find('{'):
        return '['.join(wdl_type.split('[')[1:])[:-1]
    elif wdl_type.find('[') < wdl_type.find('{'):
        return '{'.join(wdl_type.split('{')[1:])[:-1]
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

    In the future, make this return where it failed instead to give less generic error messages
    """
    if isinstance(typ, WDLArray):
        for i in range(len(expected)):
            if not validate(expected[i], result[i], typ.item_type):
                return False

    if isinstance(typ, WDLMap):
        for key in expected.keys():
            try:
                if not validate(expected[key], result[key], typ.item_type[1]):
                    return False
            except KeyError:
                return False

    # WDLStruct also represents WDLObject
    if isinstance(typ, WDLStruct):
        if str(typ) == 'Object':
            # Object members are not typed, so there isn't really a way to recursively call validate() again
            # For now, just do a simple comparison
            # As a result, file types in Objects won't be able to have their md5sums compared
            # but since Objects are only supported in Cromwell and MiniWDL dies if it sees an Object, then this
            # in theory shouldn't be an issue?
            # This should still work if in conformance.yaml, you specify the relative path respective to $(WDL_DIR)
            # by doing:
            #   {
            #       file_thing = path/to/file
            #   }
            # instead of:
            #   {
            #       file_thing = {md5sum: some_hash}
            #   }
            return expected == result
        else:
            for key in expected.keys():
                try:
                    if not validate(expected[key], result[key], typ.members[key]):
                        return False
                except KeyError:
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
        if len(expected) > 2:
            return False
        if expected['left'] != result['left'] or expected['right'] != result['right']:
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

        if 'value' not in expected[identifier]:
            return {'status': 'FAILED', 'reason': f"Test has no expected output of key 'value'!"}

        if isinstance(python_type, (WDLInt, WDLFloat, WDLString, WDLBool)):
            # easier to directly compare the result to the output rather than recursively comparing each item
            same = expected[identifier]['value'] == output
            if not same:
                return {'status': 'FAILED', 'reason': f"\nExpected output: {expected[identifier]['value']}\nActual "
                                                      f"result was: {output}!"}
        if isinstance(python_type, WDLArray):
            # in case nested types in arrays are file types
            same = validate(expected[identifier]['value'], output, python_type)
            if not same:
                return {'status': 'FAILED', 'reason': f"\nExpected output: {expected[identifier]['value']}\nActual "
                                                      f"result was: {output}!"}

        if isinstance(python_type, WDLFile):
            if not validate(expected[identifier]['value'], output, python_type):
                reason = f"For {expected[identifier]}, md5sum does not match for {output}!\n"
                return {'status': 'FAILED', 'reason': reason}

        if isinstance(python_type, WDLPair):
            same = validate(expected[identifier]['value'], output, python_type)

            if not same:
                return {'status': 'FAILED',
                        'reason': f"Expected output of pair: {expected[identifier]['value']} is not the same as result: {output}"}

        if isinstance(python_type, WDLMap):
            same = validate(expected[identifier]['value'], output, python_type)
            if not same:
                return {'status': 'FAILED',
                        'reason': f"Expected output of map: {expected[identifier]['value']} is not the same as result: {output}"}

        # WDLStruct same as WDLObject
        if isinstance(python_type, WDLStruct):
            same = validate(expected[identifier]['value'], output, python_type)
            if not same:
                return {'status': 'FAILED',
                        'reason': f"Expected output of Object: {expected[identifier]['value']} is not the same as "
                                  f"result: {output}"}

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

    response.update(verify(outputs, results_file, version, ret_code))

    if not quiet or response['status'] == 'FAILED':
        response['stdout'] = stdout.decode("utf-8", errors="ignore")
        response['stderr'] = stderr.decode("utf-8", errors="ignore")
        response.update({'return': ret_code})

    with LOG_LOCK:
        print_response(test_name, total_tests, response)

    return response


def handle_test(test_name, total_tests, test, runner, version, quiet):
    """
    Decide if the test should be skipped. If not, run it.

    Returns a result that can have status SKIPPED, SUCCEEDED, or FAILED.
    """
    if version not in test['versions']:
        response = {'status': 'SKIPPED', 'reason': f'Test only applies to versions: {",".join(test["versions"])}'}
        with LOG_LOCK:
            print_response(test_name, total_tests, response)
        return response
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

    selected_tests_amt = len(all_tests) * len(versions_to_test)

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        pending_futures = []
        for test_name in all_tests:
            for version in versions_to_test:
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
                                                version,
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
