# generic helper functions

import os
import subprocess

from WDL.Type import Float as WDLFloat, String as WDLString, File as WDLFile, Int as WDLInt, Boolean as WDLBool, \
    Array as WDLArray, Map as WDLMap, Pair as WDLPair, StructInstance as WDLStruct

from typing import Optional, Iterable, Any, Dict, Tuple, List
from WDL.Type import Base as WDLBase


def get_first_wdl_line(filename: str) -> str:
    """
    Get the first line of code (not a comment or whitespace) in a wdl file
    """
    with open(filename, 'r') as f:
        for line in f.readlines():
            # skip over comments and empty lines
            if line.lstrip().startswith("#"):
                continue
            if line.strip() == '':
                continue

            return line


def get_wdl_version_from_file(filename: str) -> str:
    """
    Find the wdl version of a wdl file through parsing
    """
    line = get_first_wdl_line(filename)
    if line is None:
        # if None, then nothing was found, so it is draft-2
        return "draft-2"

    # get version
    if "version 1.0" in line:
        return "1.0"
    elif "version 1.1" in line:
        return "1.1"
    else:
        return "draft-2"


def generate_change_command_string(lines):
    """
    Generator to change the expression placeholder syntax in command strings for draft-2

    ex:
    command {
        ~{var}
    }
    turns into
    command {
        ${var}
    }

    Syntax must follow the above and isolated closing braces should only indicate where the command string ends

    """
    iterator = iter(lines)
    in_command = False
    for line in iterator:
        if in_command is False:
            if line.strip() == "command <<<" or line.strip() == "command {":
                in_command = True
            yield line
        else:
            if line.strip() == ">>>" or line.strip() == "}":  # this could be accidentally triggered
                in_command = False
            yield line.replace("~{", "${")


def generate_remove_input(lines):
    """
    Generator to remove input section wrapper for converting to draft-2

    Base wdl file must have the format:
    input {
        ...
    }
    """
    iterator = iter(lines)
    flag = False
    for line in iterator:
        # skip over comments and empty lines
        if line.lstrip().startswith("#"):
            continue
        if line.strip() == '':
            continue

        if "input {" == line.strip():
            flag = True
            continue
        if flag is True and "}" == line.strip():
            flag = False
            continue
        yield line


def generate_replace_version_wdl(version, lines):
    """
    Generator to replace version declaration given an iterator or iterable
    """
    iterator = iter(lines)
    for line in iterator:
        # skip over comments and empty lines
        if line.lstrip().startswith("#"):
            continue
        if line.strip() == '':
            continue

        if version == "1.0":
            yield "version 1.0\n"
        elif version == "1.1":
            yield "version 1.1\n"

        yield from iterator
        return


def generate_wdl(filename: str, wdl_dir: str, target_version: str, outfile_name: str = "generated_wdl.wdl") -> str:
    """
    Generate the wdl file given an existing wdl file and a target version.

    Returns the filename
    """

    # first see what version the base wdl file is
    version = get_wdl_version_from_file(filename)

    # if the wdl file version is the same as the target version, return the wdl file as there is no need to generate
    if version == target_version:
        return filename

    # patchfiles for each version
    # if they exist, use patch instead of parsing/generating
    patch_file_draft2 = f"{wdl_dir}/version_draft-2.patch"  # hardcoded patchfile names
    patch_file_10 = f"{wdl_dir}/version_1.0.patch"
    patch_file_11 = f"{wdl_dir}/version_1.1.patch"
    if target_version == "draft-2" and os.path.exists(patch_file_draft2):
        return patch(filename, patch_file_draft2, wdl_dir, outfile_name=outfile_name)
    if target_version == "1.0" and os.path.exists(patch_file_10):
        return patch(filename, patch_file_10, wdl_dir, outfile_name=outfile_name)
    if target_version == "1.1" and os.path.exists(patch_file_11):
        return patch(filename, patch_file_11, wdl_dir, outfile_name=outfile_name)

    # generate new wdl file
    outfile_path = os.path.join(wdl_dir, outfile_name)
    with open(filename, 'r') as f:
        with open(outfile_path, 'w') as out:
            gen = generate_replace_version_wdl(target_version, f.readlines())
            # if draft-2, remove input section and change command section syntax
            if target_version == "draft-2":
                gen = generate_change_command_string(generate_remove_input(gen))
            for line in gen:
                out.write(line)
    return outfile_path


def patch(filename: str, patch_filename: str, wdl_dir: str, outfile_name: str = "draft-2.wdl") -> str:
    """Run the patch command given an input file, patch file, directory, and output file"""
    outfile_path = os.path.join(wdl_dir, outfile_name)
    subprocess.run(f"patch {filename} {patch_filename} -o {outfile_path}", shell=True)
    return f"{outfile_name}"


def get_wdl_file(wdl_file: str, wdl_dir: str, version: str) -> str:
    """
    Get the right WDL file for a test.

    Takes a base wdl file, the wdl directory, and a version.

    If the base wdl file is already the right version, it will return the base wdl file.
    Else, it will generate/create a new wdl file for the given version.
    """
    outfile_name = f"_version_{version}_{os.path.splitext(os.path.basename(wdl_file))[0]}.wdl"
    return generate_wdl(wdl_file, wdl_dir, version, outfile_name=outfile_name)


def run_cmd(cmd, cwd):
    p = subprocess.Popen(cmd, stdout=-1, stderr=-1, cwd=cwd)
    stdout, stderr = p.communicate()

    return p.returncode, stdout, stderr


def run_setup(setup_script: str):
    """
    Run a setup script
    """
    split_tup = os.path.splitext(setup_script)
    if split_tup[1] == ".py":
        subprocess.run(["python", setup_script])
    else:
        os.chmod(setup_script, 0o755)
        subprocess.run(["/bin/bash", setup_script])


def print_response(response):
    """
    Log a test response that has a status and maybe a reason.
    """
    # remove newlines in description to make printing neater
    parsed_description = response["description"].strip().replace("\n", "; ")
    print(f'{response["number"]}: {response["status"]}: {parsed_description}')
    if response.get("repeat") is not None:
        print(f"Iteration: {response['repeat']}")
    # print reason, exists only if failed or if verbose
    if response.get("reason") is not None:
        print(f'REASON: {response.get("reason")}')
    # if failed or --verbose, stdout and stderr will exist, so print
    if response.get("stdout") is not None:
        print(f'stdout: {response.get("stdout")}\n')
    if response.get("stderr") is not None:
        print(f'stderr: {response.get("stderr")}')
    if response.get("time") is not None:
        real_time = parse_time(response["time"]["real"])
        print(f'\n{"real":<8}{real_time:<10}')


def parse_time(time):
    """
    Parse time of number of seconds into a printable string
    """
    real_min = int(time // 60)
    real_sec = time % 60
    return f"{real_min}m{real_sec:.3f}s"


def announce_test(test_index, test, version, runner):
    parsed_description = test["description"].strip().replace("\n", "; ")
    if version is not None:
        print(f'{test_index}: RUNNING on "{runner}" with WDL version {version}: {parsed_description}')


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


def get_specific_tests(conformance_tests, tag_argument, number_argument, exclude_number_argument, id_argument):
    """
    Given the expected tests, tag argument, and number argument, return a list of all test numbers/indices to run
    """
    given_indices = get_test_indices(number_argument)
    exclude_indices = get_test_indices(exclude_number_argument)
    given_tags = get_tags(tag_argument)
    ids_to_test = None if id_argument is None else set(id_argument.split(','))
    tests = set()
    given_indices = given_indices or []
    for test_number in range(len(conformance_tests)):
        if exclude_indices is not None and test_number in exclude_indices:
            continue
        test_tags = conformance_tests[test_number]['tags']
        test_id = conformance_tests[test_number]['id']
        if test_number in given_indices:
            tests.add(test_number)
        if given_tags is None and ids_to_test is None and len(given_indices) == 0:
            # no test specification, so run all
            tests.add(test_number)
        else:
            if ids_to_test is not None and test_id in ids_to_test:
                tests.add(test_number)
            if given_tags is not None and any(tag in given_tags for tag in test_tags):
                tests.add(test_number)
    return sorted(list(tests))


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


def wdl_inner_type(wdl_type):
    """
    Get the interior type of a WDL type. So "Array[String]" gives "String".
    """
    if '[' in wdl_type:
        return '['.join(wdl_type.split('[')[1:])[:-1]
    else:
        return wdl_type


def wdl_outer_type(wdl_type):
    """
    Get the outermost type of a WDL type. So "Array[String]" gives "Array".
    """
    # deal with structs
    if isinstance(wdl_type, dict):
        return wdl_type
    return wdl_type.split('[')[0]


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
