import os
import json
import sys
import hashlib
import argparse
import subprocess

from uuid import uuid4


def run_cmd(cmd, cwd, quiet):
    p = subprocess.Popen(cmd, stdout=-1, stderr=-1, shell=True, cwd=cwd)
    stdout, stderr = p.communicate()
    if not quiet:
        print(f'\nstdout: {stdout}\n')
        print(f'\nstderr: {stderr}\n\n')
    if p.returncode:
        print(f'\nstdout: {stdout}\n')
        print(f'\nstderr: {stderr}\n\n')
        raise subprocess.CalledProcessError(p.returncode, cmd, stdout, stderr)


def quiet_print(msg, quiet):
    if not quiet:
        print(msg)


def verify_outputs(expected_outputs, results_file, quiet):
    quiet_print("Checking outputs... ", quiet=quiet)

    with open(results_file, 'r') as f:
        test_results = json.load(f)

    for expected_output in expected_outputs:
        if expected_output['type'] == 'File':
            file_path = test_results['outputs'][expected_output['identifier']]

            # check file path exists
            if not os.path.exists(file_path):
                return {'status': 'FAILED', 'reason': f"{file_path} not found!"}

            # check md5sum
            with open(file_path, 'rb') as f:
                md5sum = hashlib.md5(f.read()).hexdigest()
            if md5sum != expected_output['md5sum']:
                reason = f"md5sum does not match for {file_path}!\n" \
                         f"Expected: {expected_output['md5sum']}\n" \
                         f"Actual: {md5sum}"
                return {'status': 'FAILED', 'reason': reason}

            # check file size
            if str(os.path.getsize(file_path)) != expected_output['size']:
                reason = f"{file_path} is {os.path.getsize(file_path)} bytes " \
                         f"(expected: {expected_output['size']} bytes)!"
                return {'status': 'FAILED', 'reason': reason}
        else:
            raise NotImplementedError('This output type has not been implemented yet.')
    return {'status': 'SUCCEEDED', 'reason': None}


def run_test(test_number, total_tests, test, runner, quiet):
    wdl_file = os.path.abspath(test['wdl'])
    json_file = os.path.abspath(test['json'])
    args = " ".join(test['args'])
    description = test['description']
    outputs = test['outputs']
    results_file = os.path.abspath(f'results-{uuid4()}.json')
    log_level = '-DLOG_LEVEL=OFF' if quiet else ''

    runner = f'java {log_level} -jar ../../build/cromwell.jar run'
    cmd = f'{runner} {wdl_file} -i {json_file} -m {results_file} {args}'

    print(f'\n[{test_number + 1}/{total_tests}] TEST {test_number}: {description}')
    print(f'    RUNNING: {cmd}')

    run_cmd(cmd=cmd, cwd=os.path.dirname(wdl_file), quiet=quiet)

    response = verify_outputs(outputs, results_file, quiet=quiet)
    print(f'[{test_number + 1}/{total_tests}] TEST {test_number}: {response["status"]}!')
    if response["reason"]:
        print(f'    REASON: {response["reason"]}')


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
    parser.add_argument("--quiet", "-q", default=True,
                        help='Suppress printing run messages.')
    parser.add_argument("--versions", "-v", default="1.0",
                        help='Select the WDL versions you wish to test against.')
    parser.add_argument("--numbers", "-n", default='0,1',
                        help='Select the WDL test numbers you wish to run.')
    parser.add_argument("--runner", "-r", default='java -jar ../../build/cromwell.jar run',
                        help='Select the WDL runner to use.')
    args = parser.parse_args(argv)

    with open('conformance.json', 'r') as f:
        tests = json.load(f)

    total_tests = len(tests)

    test_numbers = get_test_numbers(args.numbers) if args.numbers else range(total_tests)
    for test_number in test_numbers:
        run_test(test_number=test_number,
                 total_tests=total_tests,
                 test=tests[str(test_number)],
                 runner=args.runner,
                 quiet=args.quiet)


if __name__ == '__main__':
    main()
