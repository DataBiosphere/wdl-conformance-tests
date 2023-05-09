import os
import json
import sys
import hashlib
import argparse
import subprocess
import threading

from concurrent.futures import ThreadPoolExecutor, as_completed
from shutil import which
from uuid import uuid4

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
                        run_cmd(cmd='make cromwell', cwd=os.getcwd(), quiet=quiet)
                    self.runner = f'java {log_level} -jar {cromwell} run'
        
        return super().format_command(wdl_file, json_file, results_file, args, quiet)

class MiniWDLStyleWDLRunner(WDLRunner):
    def __init__(self, runner):
        self.runner = runner
    
    def format_command(self, wdl_file, json_file, results_file, args, quiet):
        return f'{self.runner} {wdl_file} -i {json_file} -o {results_file} {" ".join(args)}'
        
RUNNERS = {
    'cromwell': CromwellWDLRunner(),
    'toil-wdl-runner-old': CromwellStyleWDLRunner('toil-wdl-runner-old'),
    'toil-wdl-runner': CromwellStyleWDLRunner('toil-wdl-runner --outputDialect miniwdl'),
    'miniwdl': MiniWDLStyleWDLRunner('miniwdl run')
}
        

def run_cmd(cmd, cwd, quiet):
    p = subprocess.Popen(cmd, stdout=-1, stderr=-1, shell=True, cwd=cwd)
    stdout, stderr = p.communicate()
   
    result = {}
    if p.returncode:
        result['status'] = 'FAILED'
        result['reason'] = f'Runner exited with code {p.returncode}'
    else:
        result['status'] = 'SUCCEEDED'
    
    if not quiet or p.returncode:
        result['stdout'] = stdout.decode("utf-8", errors="ignore")
        result['stderr'] = stderr.decode("utf-8", errors="ignore")

    return result

def wdl_type_to_python_type(wdl_type):
    """
    Given a WDL type name without generics, like "Array", return a Python type like list.
    """
    
    if wdl_type == 'File':
        # This is a string but it represents a file.
        return str
    elif wdl_type == 'Int':
        return int
    elif wdl_type == 'Boolean':
        return bool
    elif wdl_type == 'String':
        return str
    elif wdl_type == 'Array':
        return list
    else:
        return None
        
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

def verify_outputs(expected_outputs, results_file, quiet):
    try:
        with open(results_file, 'r') as f:
            test_results = json.load(f)
    except OSError:
        return {'status': 'FAILED', 'reason': f'Results file at {results_file} cannot be opened'}
    except json.JSONDecodeError:
        return {'status': 'FAILED', 'reason': f'Results file at {results_file} is not JSON'}
    # print(json.dumps(test_results, indent=4))

    for expected_output in expected_outputs:
        if 'outputs' not in test_results:
            return {'status': 'FAILED', 'reason': f"'outputs' section not found in workflow output JSON!"}
        if not isinstance(test_results['outputs'], dict):
            return {'status': 'FAILED', 'reason': f"'outputs' in workflow JSON is not an object!"}
        if expected_output['identifier'] not in test_results['outputs']:
            return {'status': 'FAILED', 'reason': f"'outputs' in workflow JSON does not contain expected key '{expected_output['identifier']}'!"}
        
        expected_outer_type = wdl_outer_type(expected_output['type'])
        expected_python_type = wdl_type_to_python_type(expected_outer_type)
        
        if expected_python_type is None:
            # We don't support this type yet.
            raise NotImplementedError(f"Type '{expected_outer_type}' is not supported by the test harness!")
        
        got_value = test_results['outputs'][expected_output['identifier']]
        if not isinstance(got_value, expected_python_type):
            # Make sure we got the right type
            reason = f"For {expected_output['identifier']}, item {got_value} of type {type(got_value)} was returned, but {expected_outer_type} {expected_output['value']} was expected!"
            return {'status': 'FAILED', 'reason': reason}

        if expected_outer_type == 'File':
            # check file path exists
            if not os.path.exists(got_value):
                return {'status': 'FAILED', 'reason': f"{got_value} not found!"}

            # check md5sum
            with open(got_value, 'rb') as f:
                md5sum = hashlib.md5(f.read()).hexdigest()
            if md5sum != expected_output['md5sum']:
                reason = f"For {expected_output['identifier']}, md5sum does not match for {got_value}!\n" \
                         f"Expected: {expected_output['md5sum']}\n" \
                         f"Actual: {md5sum}"
                return {'status': 'FAILED', 'reason': reason}

            # check file size
            if str(os.path.getsize(got_value)) != expected_output['size']:
                reason = f"For {expected_output['identifier']}, {got_value} is {os.path.getsize(got_value)} bytes " \
                         f"(expected: {expected_output['size']} bytes)!"
                return {'status': 'FAILED', 'reason': reason}

        elif expected_outer_type == 'Array':
            if len(got_value)!= len(expected_output['value']):
                # Check array length
                reason = f"For {expected_output['identifier']}, array {repr(got_value)} of length {len(expected_output['value'])} was returned, but {expected_output['type']} {repr(expected_output['value'])} of length {len(expected_output['value'])} was expected!"
                return {'status': 'FAILED', 'reason': reason}
        
            expected_inner_type = wdl_inner_type(expected_output['type'])
            expected_inner_python_type = wdl_type_to_python_type(expected_inner_type)
            if expected_inner_python_type is None or expected_inner_type == 'File':
                # We don't support this type as an array item yet.
                raise NotImplementedError(f"Array item type '{expected_inner_type}' is not supported by the test harness!")
            
            for i, item in enumerate(got_value):
                if not isinstance(item, expected_inner_python_type):
                    # Check the type of each item
                    reason = f"For {expected_output['identifier']}, at index {i}, item {item} of type {type(item)} was returned, but {expected_inner_type} {expected_output['value'][i]} was expected!"
                    return {'status': 'FAILED', 'reason': reason}
                
                if item != expected_output['value'][i]:
                    # And its value
                    reason = f"For {expected_output['identifier']}, at index {i}, {expected_inner_type} {repr(item)} was returned, but {repr(expected_output['value'][i])} was expected!"
                    return {'status': 'FAILED', 'reason': reason}
        
                    
        else:
            # check the single value returned
            if got_value != expected_output['value']:
                reason = f"For {expected_output['identifier']}, {expected_outer_type} {repr(got_value)} was returned, but {repr(expected_output['value'])} was expected!"
                return {'status': 'FAILED', 'reason': reason}
            
    return {'status': 'SUCCEEDED', 'reason': None}

def announce_test(test_number, total_tests, test):
    description = test['description']
    print(f'\n[{test_number + 1}/{total_tests}] TEST {test_number}: {description}')
    
def check_test(test, versions_to_test):
    """
    Determine if a test should be skipped.
    
    Returns a response, with SUCCEEDED status if the test should be run, and
    SKIPPED otherwise.
    """
    
    # TODO: Tests have a versions_supported array for some reason but
    # actually can only really be one version.
    version_match = False
    for version in test['versions_supported']:
        if version in versions_to_test:
            version_match = True
            
    if not version_match:
        return {'status': 'SKIPPED', 'reason': f'Test only applies to versions: {",".join(test["versions_supported"])}'}
        
    return {'status': 'SUCCEEDED', 'reason': None}

# Make sure output groups don't clobber each other.
LOG_LOCK = threading.Lock()

def print_response(test_number, total_tests, response):
    """
    Log a test response that has a status and maybe a reason.
    """
    
    print(f'[{test_number + 1}/{total_tests}] TEST {test_number}: {response["status"]}!')
    if response["reason"]:
        print(f'    REASON: {response["reason"]}')
    if 'stdout' in response:
        print(f'\nstdout: {response["stdout"]}\n')
    if 'stderr' in response:
        print(f'\nstderr: {response["stderr"]}\n\n')

def run_test(test_number, total_tests, test, runner, quiet):
    """
    Run a test and log success or failure.
    
    Return the response dict.
    """
    
    wdl_file = os.path.abspath(test['wdl'])
    json_file = os.path.abspath(test['json'])
    args = test.get('args', [])
    outputs = test['outputs']
    results_file = os.path.abspath(f'results-{uuid4()}.json')
    
    cmd = runner.format_command(wdl_file, json_file, results_file, args, quiet)
    
    with LOG_LOCK:
        announce_test(test_number, total_tests, test)
        print(f'    RUNNING: {cmd}')
    
    response = run_cmd(cmd=cmd, cwd=os.path.dirname(wdl_file), quiet=quiet)
    if response['status'] == 'SUCCEEDED':
        response.update(verify_outputs(outputs, results_file, quiet=quiet))
    
    with LOG_LOCK:
        print_response(test_number, total_tests, response)
    return response
    
def handle_test(test_number, total_tests, test, runner, versions_to_test, quiet):
    """
    Decide if the test should be skipped. If not, run it.
    
    Returns a result that can have status SKIPPED, SUCCEEDED, or FAILED.
    """
    
    response = check_test(test, versions_to_test)
    if response['status'] != 'SUCCEEDED':
        with LOG_LOCK:
            announce_test(test_number, total_tests, test)
            print_response(test_number, total_tests, response)
        return response
    
    return run_test(test_number, total_tests, test, runner, quiet)
            
def get_test_numbers(number_argument):
    ranges = [i for i in number_argument.split(',') if i]
    split_ranges = [i.split('-') if '-' in i else [i, i] for i in ranges]
    tests = set()
    for start, end in split_ranges:
        for test_number in range(int(start), int(end) + 1):
            tests.add(test_number)
    return sorted(list(tests))


def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='Run WDL conformance tests.')
    parser.add_argument("--quiet", "-q", default=False, action='store_true',
                        help='Suppress printing run messages.')
    parser.add_argument("--versions", "-v", default="1.0",
                        help='Select the WDL versions you wish to test against.')
    parser.add_argument("--numbers", "-n", default=None,
                        help='Select the WDL test numbers you wish to run.')
    parser.add_argument("--runner", "-r", default='cromwell',
                        help='Select the WDL runner to use.')
    parser.add_argument("--threads", "-t", type=int, default=None,
                        help='Number of tests to run in parallel.')
    args = parser.parse_args(argv)
    
    # Get all the versions to test.
    # Unlike with CWL, WDL requires a WDL file to declare a spacific version,
    # and prohibits mixing file versions in a workflow, although some runners
    # might allow it.
    # But the tests all need to be for single WDL versions.
    versions_to_test = set(args.versions.split(','))

    with open('conformance.json', 'r') as f:
        tests = json.load(f)

    total_tests = len(tests)
   
    if args.runner not in RUNNERS:
        print(f'Unsupported runner: {args.runner}')
        sys.exit(1)
    
    runner = RUNNERS[args.runner]
    
    print(f'Testing runner {args.runner} on WDL versions: {",".join(versions_to_test)}\n') 
   
    successes = 0
    skips = 0

    test_numbers = get_test_numbers(args.numbers) if args.numbers else range(total_tests)
    selected_tests = len(test_numbers)
    
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        pending_futures = []
        for test_number in test_numbers:
            test = tests[str(test_number)]
            
            # Handle each test as a concurrent job
            result_future = executor.submit(handle_test,
                                            test_number,
                                            total_tests,
                                            test,
                                            runner,
                                            versions_to_test,
                                            args.quiet)
            pending_futures.append(result_future)
        for result_future in as_completed(pending_futures):
            # Go get each result or reraise the relevant exception
            result = result_future.result()
            if result['status'] == 'SUCCEEDED':
                successes += 1
            elif result['status'] == 'SKIPPED':
                skips += 1
    
    print(f'{selected_tests - skips} tests run, {successes} succeeded, {selected_tests - skips - successes} failed, {skips} skiped')
    if successes < selected_tests - skips:
        # Fail the program overall if tests failed.
        sys.exit(1)


if __name__ == '__main__':
    main()
