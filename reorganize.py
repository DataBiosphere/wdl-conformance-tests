import os
import json
import re
import shutil
import sys
import hashlib
import argparse
import subprocess
import threading
from ruamel.yaml import YAML

def get_each_test_info(filename):
    yaml = YAML()
    with open(filename, 'r') as f:
        tests = yaml.load(f)

    result = list()

    for test in tests:
        versions = test["versions"]
        wdl_path = test["inputs"]["wdl"]
        json_path = test["inputs"]["json"]

        d = dict()

        d["versions"] = versions
        d["wdl_path"] = wdl_path
        d["json_path"] = json_path
        result.append(d)
    return result
def reorganize_into_folders():
    conformance_file = "conformance_before.yaml"
    all_files = get_each_test_info(conformance_file)
    if os.path.exists("tests"):
        shutil.rmtree("tests")
    working_dir = os.getcwd()
    os.mkdir("tests")
    os.chdir("tests")
    for info in all_files:
        versions = info["versions"]
        wdl_path = info["wdl_path"]
        json_path = info["json_path"]
        wdl_basename = os.path.basename(wdl_path)
        json_basename = os.path.basename(json_path)
        for version in versions:
            if version == "1.0":
                version = "version_1.0"
            elif version == "1.1":
                version = "version_1.1"
            else:
                version = "draft-2"

            full_wdl_path = os.path.join(f"{working_dir}/tests/{version}/{wdl_path}")
            full_json_path = os.path.join(f"{working_dir}/tests/{version}/{json_path}")

            dir_name = os.path.splitext(wdl_basename)[0]
            if not os.path.exists(dir_name):
                os.mkdir(dir_name)

            shutil.copyfile(full_wdl_path, f"{dir_name}/{version}%{wdl_basename}")
            # will overwrite prev which is fine as they are duplicates anyway
            shutil.copyfile(full_json_path, f"{dir_name}/{json_basename}")

    upper_dir = os.path.dirname(os.getcwd())
    os.chdir(upper_dir)


def get_wdl_version_from_file(filename):
    with open(filename, 'r') as f:
        for line in f.readlines():
            # skip over comments and empty lines
            if line.lstrip().startswith("#"):
                continue
            if line.strip() == '':
                continue

            # get version
            if "version 1.0" in line:
                version = "1.0"
            elif "version 1.1" in line:
                version = "1.1"
            else:
                version = "draft-2"

            return version
def highest_version_in_filelist(lst):
    # not the prettiest approach
    basename_lst = list(map(lambda x : get_wdl_version_from_file(x), lst))
    in_order = ["1.1", "1.0", "draft-2"]
    for version_wdl in in_order:
        if version_wdl in basename_lst:
            return basename_lst.index(version_wdl)
def find_if_version_exists_in_filelist(lst, version):
    basename_lst = list(map(lambda x : get_wdl_version_from_file(x), lst))
    return basename_lst.index(version) if version in basename_lst else -1
def consolidate(remove_extra = True):
    # run after reorganize_into_folders if moving from old
    working_dir = os.getcwd()
    for directory in os.listdir("tests"):
        dir_abs = os.path.abspath(os.path.join("tests", directory))
        all_wdl_files = list()
        for file in os.listdir(dir_abs):
            if file.endswith(".wdl"):
                file_path = os.path.abspath(os.path.join(dir_abs, file))
                all_wdl_files.append(file_path)
        highest_version_wdl = all_wdl_files[highest_version_in_filelist(all_wdl_files)]

        i = find_if_version_exists_in_filelist(all_wdl_files, "draft-2")
        highest_version_wdl_basename = os.path.basename(highest_version_wdl)
        if i != -1:
            draft2_wdl_file = all_wdl_files[i]
            draft2_wdl_file_basename = os.path.basename(draft2_wdl_file)
            os.chdir(dir_abs)
            command = f'diff -u {highest_version_wdl_basename} {draft2_wdl_file_basename} > draft-2.patch'
            subprocess.run(command, shell=True)
            os.chdir(working_dir)

        exempt = ["workflow_with_default_input_1.0.wdl", "task_without_default_input_1.0.wdl"] # not the cleanest
        if remove_extra:
            for file in all_wdl_files:
                if file != highest_version_wdl and os.path.basename(file) not in exempt:
                    os.remove(file)

        # rename the files to proper names by removing the temp version differentiator
        # can't do this if the other files aren't removed prior (flag remove_extra) as it will overwrite each other
        if remove_extra:
            for file in os.listdir(dir_abs):
                start_idx = file.find("%")
                if start_idx == -1:
                    continue
                new_filename = file[start_idx+1:]
                abs_src_file = os.path.join(dir_abs, file)
                abs_dst_file = os.path.join(dir_abs, new_filename)
                os.rename(abs_src_file, abs_dst_file)
        else:
            # remove extra should probably have a better name if done this way
            # probably wont use this, but this will differentiate by renaming the wdl files into their appropraite version (ex: version_1.0.wdl)
            for file in os.listdir(dir_abs):
                end_idx = file.find("%")
                if end_idx == -1:
                    continue
                new_filename = f"{file[:end_idx]}.wdl"
                abs_src_file = os.path.join(dir_abs, file)
                abs_dst_file = os.path.join(dir_abs, new_filename)
                os.rename(abs_src_file, abs_dst_file)






def main():
    reorganize_into_folders()
    fix_missing_imports()
    consolidate()

def fix_missing_imports():
    shutil.copyfile("tests/version_1.0/semantics/workflow_with_default_input_1.0.wdl",
                    "tests/null_input_through_workflows_1.0/workflow_with_default_input_1.0.wdl")
    shutil.copyfile("tests/version_1.0/semantics/task_without_default_input_1.0.wdl",
                    "tests/null_input_through_workflows_1.0/task_without_default_input_1.0.wdl")

    shutil.copyfile("tests/version_1.0/semantics/workflow_with_default_input_1.0.wdl",
                    "tests/null_optional_vs_default_1.0/workflow_with_default_input_1.0.wdl")
    shutil.copyfile("tests/version_1.0/semantics/task_without_default_input_1.0.wdl",
                    "tests/null_optional_vs_default_1.0/task_without_default_input_1.0.wdl")

if __name__ == "__main__":
    main()