#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK

"""
Extract unit tests from the WDL spec (1.1+) and create a conformance file that is conformance to our representation for this test suite
A good portion of this code is taken and modified from https://github.com/openwdl/wdl-tests/blob/main/scripts/extract_tests.py
"""
import hashlib
import subprocess
import sys

import regex as re
import os
import glob

import json
from ruamel.yaml import YAML
import argparse
import argcomplete
from pathlib import Path
import re
import shutil
from typing import Optional, Union, List, Set, Callable, Any, Dict

from lib import convert_type

import WDL

# Use a parsing regex derived from the one at https://github.com/openwdl/wdl-tests/blob/c9d59f6b7ef0f8e9f65cde92c9e70182c3afbd58/scripts/extract_tests.py#L10-L13
TEST_RE = re.compile(
    r"^<details>\s*<summary>\s*Example: (.+?)\s*```wdl(.+?)```\s*</summary>\s*(?:<p>\s*(?:Example input:\s*```json(.*?)```)?\s*(?:Example output:\s*```json(.*?)```)?\s*(?:Test config:\s*(?:```json(.*?)```)?)?\s*</p>\s*)?</details>$",
    re.I | re.S,
)
RESOURCE_RE = re.compile(
    r"^<details>\s*<summary>\s*Resource: (.+?)\s*```(?:\S*\n)(.+?)```\s*</summary>\s*</details>$",
    re.I | re.S,
)
FILENAME_RE = re.compile(r"(.+?)(_fail)?(_task)?.wdl")
VERSION_RE = re.compile(r"version ([\d.]+)")

# Regex for finding the WDL type of a variable by reading the WDL file per line
# For example, given the wdl workflow:
#   output {
#     File example1 = "example1.txt"
#     File? example2 = "example2.txt"
#     Array[File?] file_array = ["example1.txt", "example2.txt"]
#     Int file_array_len = length(select_all(file_array))
#     Map[String, Pair[Int, File?]] nested = {}
#   }
# For each declaration, the regex will identify type File with variable name example1, etc
regex_var_types_str = r"([\w\[, \]+?]+)\s(\w+)(?:[\s\S]*?(?= =))"


def get_from(d: Optional[Dict[Any, Any]], k: str) -> Any:
    # same as d.get(k) but return None if d is None
    if d is not None:
        return d.get(k)
    return None

def index_from(l: Optional[List[Any]], i: int) -> Any:
    if l is not None:
        return l[i]
    return None


def wdl_type_to_string(wdl_type: WDL.Type.Base) -> Union[Dict[str, Any], str]:
    """
    Convert a MiniWDL type object to its string representation.

    If a struct is provided, a dictionary will be returned with the name of the member and the associated type
    """
    if isinstance(wdl_type, WDL.Type.StructInstance):
        # this is the only construct that we need to decipher to string form
        dictified = {}
        for key, subtype in wdl_type.members.items():
            dictified[key] = wdl_type_to_string(subtype)
        return dictified
    return str(wdl_type)


def extract_output_types(wdl_file: str, fail: bool) -> Dict[str, Union[Dict[str, Any], str]]:
    """
    Extract the output types from a wdl file.

    Returns a dict from field name to string type name, or (for structs)
    sub-dicts of the same structure.
    """
    if fail:
        # since we expect this workflow to fail, there should be no outputs
        return {}

    # Only MiniWDL's parser actually knows how to parse structs, but it might
    # not work on all test cases when there is syntax change in the WDL spec,
    # and it doesn't support Object.

    try:
        document: WDL.Tree.Document = WDL.load(uri=str(wdl_file))
    except Exception as e:
        # TODO: Should we complain about something MiniWDL can't parse?
        # Fall back to regex-based parsing (which can't handle structs)
        return extract_output_types_regex(wdl_file)

    # Otherwise, MiniWDL parsing actually worked.
    # Find the top-level thing
    target: Union[WDL.Tree.Workflow, WDL.Tree.Task]

    if document.workflow:
        target = document.workflow
    elif len(document.tasks) == 1:
        target = document.tasks[0]
    else:
        # this in theory shouldn't be hit, but the source repo has a suspicious
        # --tasks argument passed to miniwdl sometimes
        raise Exception(
            "Multiple tasks founds with no workflow!")

    var_types = dict()
    if target.outputs is not None:
        for output in target.outputs:
            var_types[output.name] = wdl_type_to_string(output.type)

    return var_types


def parse_block(text: str, start_pos: int) -> Optional[str]:
    """
    Given text and a position pointing to an opening brace, extract the
    content between matching braces.

    Returns the content between the braces (excluding the braces themselves).
    """
    if start_pos >= len(text) or text[start_pos] != "{":
        raise ValueError("There is no open brace at the given position")

    depth = 0
    cursor = start_pos
    while cursor < len(text):
        char = text[cursor]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        if depth == 0:
            # We just closed the initial opening brace
            return text[start_pos + 1:cursor]
        cursor += 1

    raise ValueError("No closing brace found!")


def extract_output_types_regex(wdl_file) -> Dict[str, str]:
    """
    Given a WDL file, extract all output variable names and its associated types with a regex.

    Returns a dictionary of variable name to type.
    Ex:
      File filename = "path/to/file"
    Will get {"filename": "File"}

    If a workflow is in the file, parses the output section of the workflow.
    Otherwise, parses the output section of the task.
    """
    regex_var_types = re.compile(regex_var_types_str)

    with open(wdl_file, "r") as f:
        wdl_text = f.read()

    for block in ("workflow", "task"):
        # Find the starting brace of the workflow, or else the task
        block_match = re.search(block + r"\s+\w+\s*\{", wdl_text)
        if block_match:
            break

    # Grab the block contents
    block_text = parse_block(wdl_text, block_match.end() - 1)

    # Find the output section
    output_match = re.search(r"output\s*\{", block_text)

    # Grab its contents
    output_text = parse_block(block_text, output_match.end() - 1)

    # Parse variable declarations from the output section
    # TODO: this won't work if the entire declaration isn't on the same line
    var_types = {}
    for line in output_text.split("\n"):
        line = line.strip()
        if "=" in line:
            match = re.search(regex_var_types, line)
            if match is None:
                # this line is not a var declaration
                continue
            name = match.group(2)
            typ = match.group(1)
            var_types[name] = typ

    return var_types


def convert_typed_output_values(output_values: Union[None, str, Dict[str, Any], List[Any]], output_type: WDL.Type.Base,
                                data_dir: Optional[Path], extra_patch_data: Union[List[Any], Dict[str, Any]]) -> Optional[Union[str, Dict[str, Any], List[Any]]]:
    """
    Get the expected output object (in our conformance representation) with respect to the output types. Convert/add extra fields when needed
    to match our conformance test suite.
    Do so by searching the extra yaml/configuration file for an associated key value pair. Can also test if the
    wanted file exists recursively in data_dir. Descends recursively down the type alongside the object.

    This is done to get and add the md5sum of files when converting unit tests.

    Ex: If given hello.txt and type File, try to get the md5sum of the file. Then returns the md5sum as {"md5sum": md5sum} (If regex is in the patch file, can use that too)
    If given "hello" and type String, don't do anything and just return the string value "hello"

    Returns a json/yaml parseable object with the expected values represented as a string or a compound type with leafs of strings.

    """
    if output_values is None and output_type.optional:
        return output_values
    if isinstance(output_type, WDL.Type.File):
        # this will only populate md5sum if the files exist recursively in the data directory
        for path in glob.glob(str(data_dir / "**"), recursive=True):
            if get_from(extra_patch_data, "md5sum") is not None:
                return {'md5sum': extra_patch_data.get("md5sum")}
            if get_from(extra_patch_data, "regex") is not None:
                return {'regex': extra_patch_data.get("regex")}
            # The above methods should be used, else this is a fallback. This isn't guaranteed to find the right file if multiple same filenames exist under data_dir
            if path.endswith(output_values) and os.path.exists(path):
                with open(path, "rb") as f:
                    md5sum = hashlib.md5(f.read()).hexdigest()
                return {'md5sum': md5sum}

    if isinstance(output_type, WDL.Type.StructInstance):
        converted_output = dict()
        for i, (output_key, output_value) in enumerate(output_values.items()):
            try:
                output_value_type = output_type.members[output_key]
            except KeyError:
                # coercion from map to struct can cause some weird type behavior when parsing with miniwdl
                # in the map_to_struct.wdl test, when parsing the output types, the miniwdl parser outputs a struct with the right types
                # but the wrong keys (right member types but wrong member names)
                # So the key lookup will fail even though the corresponding types are actually there
                # See https://github.com/chanzuckerberg/miniwdl/issues/712
                # Since dictionaries past python 3.6 are ordered, find the corresponding type from the current output's position
                output_value_type = list(output_type.members.values())[i]
            converted_output[output_key] = convert_typed_output_values(output_value, output_value_type, data_dir, get_from(extra_patch_data, output_value))
        return converted_output
    if isinstance(output_type, WDL.Type.Map):
        converted_output = dict()
        for output_key, output_value in output_values.items():
            new_output_key = convert_typed_output_values(output_key, output_type.item_type[0], data_dir, get_from(extra_patch_data, output_key))
            new_output_value = convert_typed_output_values(output_value, output_type.item_type[1], data_dir, get_from(extra_patch_data, output_value))
            converted_output[new_output_key] = new_output_value
    if isinstance(output_type, WDL.Type.Pair):
        converted_output = dict()
        if isinstance(output_values, list) and len(output_values) == 2:
            # We're looking at a list representation of a pair. Convert to dict representation.
            output_values = {"left": output_values[0], "right": output_values[1]}
        if isinstance(output_values, dict):
            # key should be left or right
            converted_output["left"] = convert_typed_output_values(output_values["left"], output_type.left_type, data_dir, get_from(extra_patch_data, output_values["left"]))
            converted_output["right"] = convert_typed_output_values(output_values["right"], output_type.right_type, data_dir, get_from(extra_patch_data, output_values["right"]))
        return converted_output
    if isinstance(output_type, WDL.Type.Array):
        converted_output = list()
        for i, output in enumerate(output_values):
            converted_output.append(convert_typed_output_values(output, output_type.item_type, data_dir, index_from(extra_patch_data, i)))
        return converted_output
    # else this is a primitive type
    return output_values


def convert_typed_output_values_from_string(output_values: Union[None, str, Dict[str, Any], List[Any]], output_type: Union[str, Dict[str, Any]],
                                            data_dir: Optional[Path], extra_patch_data: Optional[Dict[str, Any]]):
    output_type_wdl = convert_type(output_type)
    return convert_typed_output_values(output_values, output_type_wdl, data_dir, extra_patch_data)

JSON_PARSEABLE = Union[Dict[Any, Any], List[Any], bool, int, str, float, None]

def recursive_json_apply(json_obj: JSON_PARSEABLE, func: Callable[[Any], Any]) \
        -> JSON_PARSEABLE:
    """
    Transform every primitive type of a JSON object.

    Will recursively descend down until the "leaf" nodes and run a function on the value.
    """
    if isinstance(json_obj, dict):
        return {func(k): recursive_json_apply(v, func) for k, v in json_obj.items()}
    elif isinstance(json_obj, list):
        return [recursive_json_apply(v, func) for v in json_obj]
    elif json_obj is None:
        return None
    else:
        # primitive type
        return func(json_obj)


def generate_config_file(m: re.Match, output_dir: Path, version: str, all_data_files: Optional[Set[str]], data_dir: Optional[Path],
                         output_data_dir: Optional[Path], config: list, extra_patch_data: Optional[Dict[str, Any]]) -> None:
    # Modified from the WDL test extraction example
    """
    Given the regex match object, create the corresponding config entry for conformance.yaml. Adds the config entry to the config argument (which is a list)

    Separated from write_test_file as miniwdl's parser requires all imported files to exist,
    and this is not necessarily true if iterating the spec file top to bottom. And we
    can't use a simple regex as the type of grammar is too basic for things like nested constructs
    """
    file_name, wdl, input_json, output_json, config_json = m.groups()

    f = FILENAME_RE.match(file_name)

    wdl_file = output_dir / file_name

    if config_json is not None:
        config_entry = json.loads(config_json)
    else:
        config_entry = {}

    target, is_fail, is_task = f.groups()

    is_fail = is_fail or config_entry.get("fail", False)  # failure can also be specified in the json

    config_entry["id"] = target

    target_data: Optional[Dict[str, Any]] = None
    for m in extra_patch_data:
        if m.get("id") == target:
            target_data = m
            break

    wdl_dir, wdl_base = os.path.split(wdl_file)

    # the spec assumes all input files are the basenames
    # if we detect a filename in the input, change to a proper relative path
    input_json_dict = {}
    if input_json is not None:
        def if_file_convert(maybe_file):
            if maybe_file in all_data_files:
                # this is a file
                return os.path.join(output_data_dir, maybe_file)  # output_data_dir should already be a relative path dir to the repo TLD
            else:
                return maybe_file

        for k, v in json.loads(input_json.strip()).items():
            input_json_dict[if_file_convert(k)] = recursive_json_apply(v, if_file_convert)

    config_entry["inputs"] = {
        "dir": wdl_dir,
        "wdl": wdl_base,
        "json_string": input_json_dict
    }

    if output_json is not None:
        config_entry["outputs"] = json.loads(output_json.strip())
    else:
        config_entry["outputs"] = {}
    output_var_types = extract_output_types(wdl_file, bool(is_fail))

    if "return_code" not in config_entry:
        config_entry["return_code"] = "*"
    elif isinstance(config_entry["return_code"], str):
        config_entry["return_code"] = [config_entry["return_code"]]

    if bool(is_fail):
        config_entry["outputs"] = {}
    else:
        if output_json is not None:
            target_output_data = get_from(target_data, "outputs")
            for k, v in json.loads(output_json.strip()).items():
                k_base = k.split(".")[-1]
                try:
                    output_type = output_var_types[k_base]
                except KeyError as e:
                    # This happens if the example output mentions a field that doesn't really exist.
                    raise RuntimeError(f"Expected output contains a \"{k_base}\" field that is not an output of the workflow ({', '.join(output_var_types.keys())}).")
                config_entry["outputs"][k] = {
                    "type": output_type,
                    "value": convert_typed_output_values_from_string(v, output_type, data_dir, get_from(get_from(target_output_data, k), "value"))
                }

    if "type" not in config_entry:
        config_entry["type"] = "task" if is_task else "workflow"
    if "target" not in config_entry:
        config_entry["target"] = target
    if "priority" not in config_entry:
        config_entry["priority"] = "required"
    if "exclude_output" not in config_entry:
        config_entry["exclude_output"] = []
    elif isinstance(config_entry["exclude_output"], str):
        config_entry["exclude_output"] = [config_entry["exclude_output"]]
    if "dependencies" not in config_entry:
        config_entry["dependencies"] = []
    elif isinstance(config_entry["dependencies"], str):
        config_entry["dependencies"] = [config_entry["dependencies"]]
    # add extra_patch_data dependencies
    if get_from(target_data, "dependencies") is not None:
        config_entry["dependencies"].extend(target_data["dependencies"])
    if "tags" not in config_entry:
        config_entry["tags"] = []
    elif isinstance(config_entry["tags"], str):
        config_entry["tags"] = [config_entry["tags"]]

    config_entry["tags"].append("unit")

    config_entry["description"] = f"Unit test for {file_name}"

    config_entry["versions"] = [version]

    config.append(config_entry)


def write_test_files(m: re.Match, output_dir: Path, version: str):
    """
    Given the regex match, write the test file into the output directory.
    Checks if the version and the file to be written match. Also ensures that the file
    does not exist beforehand.
    """
    file_name, wdl, input_json, output_json, config_json = m.groups()

    if file_name is None:
        raise Exception("Missing file name")
    f = FILENAME_RE.match(file_name)
    if f is None:
        raise Exception(f"Invalid file name: {file_name}")

    wdl = wdl.strip()
    v = VERSION_RE.search(wdl)
    if v is None:
        raise Exception("WDL does not contain version statement")
    elif v.group(1) != version:
        raise Exception(f"WDL version {v.group(1)} is not expected version {version} in: {wdl}")

    wdl_file = output_dir / file_name
    if wdl_file.exists():
        raise Exception(f"Test file already exists: {wdl_file}")
    with open(wdl_file, "w") as o:
        o.write(wdl)


def extract_tests(spec: Path, data_dir: Optional[Path], output_dir: Path, version: str, output_type: str, extra_patch_data_path: Optional[Path]):
    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    config = []
    resources = {}
    test_matches = []
    with open(spec) as s:
        buf = None
        for line in s:
            if buf is None and "<details>" in line:
                buf = [line]
            elif buf is not None:
                buf.append(line)
                if "</details>" in line:
                    ex = "".join(buf)
                    buf = None
                    m = TEST_RE.match(ex)
                    if m is None:
                        m = RESOURCE_RE.match(ex)
                        if m is None:
                            raise Exception(f"Regex does not match example {ex}")
                        else:
                            # Handle resource
                            try:
                                resources[m.group(1)] = m.group(2)
                            except Exception as e:
                                raise Exception(
                                    f"Parsing error for resource {ex}"
                                ) from e
                    else:
                        # Handle test
                        try:
                            test_matches.append(m)
                            write_test_files(m, output_dir, version)
                        except Exception as e:
                            raise Exception(
                                f"Error writing files for example {ex}"
                            ) from e

    all_data_files = None
    if data_dir is not None:
        all_data_files = set(os.path.basename(x) for x in glob.glob(str(data_dir / "**"), recursive=True))

    if (data_dir is not None) or resources:
        output_data_dir = (output_dir / "data").resolve()
        os.makedirs(output_data_dir, exist_ok=True)
    else:
        output_data_dir = None

    for name, data in resources.items():
        destination = (output_data_dir / name).resolve()
        if not destination.is_relative_to(output_data_dir):
            raise RuntimeError(f"Disallowed resource path: {name} gives {destination} not in {output_data_dir}")
        destination_dir = destination.parent
        os.makedirs(destination_dir, exist_ok=True)
        with open(destination, "w") as f:
            f.write(data)

    extra_patch_data = None
    if extra_patch_data_path is not None:
        with open(extra_patch_data_path, "r") as e:
            yaml = YAML()
            extra_patch_data = yaml.load(e)

    for m in test_matches:
        try:
            generate_config_file(m, output_dir, version, all_data_files, data_dir, output_data_dir, config, extra_patch_data)
        except Exception as e:
            raise RuntimeError(f"Could not import test case {m.groups()[0]}") from e


    if output_type == "json":
        config_file = output_dir / "test_config.json"
        with open(config_file, "w") as o:
            json.dump(config, o, indent=2)
    else:
        config_file = output_dir / "test_config.yaml"
        with open(config_file, "w") as o:
            yaml = YAML()
            yaml.dump(config, o)

    if data_dir is not None and data_dir.exists():
        shutil.copytree(data_dir, output_data_dir, symlinks=True, dirs_exist_ok=False)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(
        usage="%(prog)s [options]",
        description=(
            "Extracts the unit tests from the spec to be runnable by this test suite (does not run them. See run_unit.py);"
            "test files will be outputted into the `unit_tests` directory and a new conformance file will be created."
            "To run the unit tests, see [insert other script here]"
        )
    )
    parser.add_argument(
        "--version",
        "-v",
        default="1.1",
        help="Version of the spec to grab unit tests out of. Only WDL 1.1 and above has support for built in unit tests.",
        choices=["1.1", "1.2"]
    )
    parser.add_argument(
        "--output-type",
        default="yaml",
        choices=["yaml", "json"],
        help="Specify conformance file output type."
    )
    parser.add_argument(
        "--force-pull",
        default=False,
        action="store_true",
        help="Default behavior does not pull the spec repo if it was already pulled. Specify this argument to force a refresh."
    )
    parser.add_argument(
        "--extra-patch-data", "-e",
        default="unit_tests_patch_data.yaml",
        help="Include extra patch data when extracting the unit tests into the config. "
             "Since we have our own method of testing file outputs, this is mostly used for file hashes/regexes."
    )
    parser.add_argument(
        "--repo",
        # WDL spec may have bugs, may want to use a different repo
        # see openwdl issues #653, #654, #661, #662, #663, #664, #665, #666
        default="https://github.com/openwdl/wdl.git",
        help="Repository to pull from."
    )
    parser.add_argument(
        "--branch",
        default=None,
        help="Branch of the repository to pull from. Will override the corresponding branch to the --version argument."
    )
    parser.add_argument(
        "--spec-dir",
        default=None,
        help="Pre-pulled WDL spec repository directory to use"
    )
    argcomplete.autocomplete(parser)
    args = parser.parse_args(argv)

    output_root = os.getcwd()

    if args.spec_dir is not None:
        spec_dir = args.spec_dir
        os.chdir(spec_dir)
    else:
        spec_dir = f"wdl-{args.version}-spec"
        if not os.path.exists(spec_dir) or args.force_pull is True:
            cmd = f"rm -rf {spec_dir}"
            subprocess.run(cmd.split(), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
            cmd = f"git clone {args.repo} {spec_dir}"
            subprocess.run(cmd.split(), stderr=subprocess.PIPE, stdout=subprocess.PIPE)
        else:
            print(f"Spec dir at {spec_dir} already exists. Specify --force-pull to force a pull.")

        os.chdir(spec_dir)

        # may be fragile if WDL changes their branch naming scheme
        # test fixes are in the 1.1.3 branch as it has not been merged upstream
        if args.version == "1.1":
            repo_version = "1.1.3"
        else:
            repo_version = args.version
        repo_branch = args.branch or f"wdl-{repo_version}"
        cmd = f"git checkout {repo_branch}"
        print(f"Changing to branch {repo_branch}")
        subprocess.run(cmd.split(), stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    os.chdir(output_root)

    # temp
    cmd = f"rm -rf unit_tests"
    subprocess.run(cmd.split(), stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    print("Extracting tests...")
    extract_tests(Path(spec_dir) / Path("SPEC.md"), Path(spec_dir) / Path("tests/data"), Path("unit_tests"), args.version, args.output_type, args.extra_patch_data)


if __name__ == "__main__":
    main()
