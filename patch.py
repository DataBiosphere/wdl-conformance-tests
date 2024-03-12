import argparse
import os
import subprocess
import sys

from lib import get_wdl_version_from_file

def highest_version_in_filelist(lst):
    # not the prettiest approach
    basename_lst = list(map(lambda x : get_wdl_version_from_file(x), lst))
    in_order = ["1.1", "1.0", "draft-2"]
    for version_wdl in in_order:
        if version_wdl in basename_lst:
            return basename_lst.index(version_wdl)

def create_patch(directory, base_version, remove=False, rename=False):
    files = list()
    base_wdl = None
    for file in os.listdir(directory):
        if file.endswith(".wdl"):
            path = os.path.abspath(os.path.join(directory, file))
            files.append(path)
            if get_wdl_version_from_file(path) == base_version:
                base_wdl = path
    if base_wdl is None:
        raise Exception(f"No WDL file found with version {base_version}!")
    working_dir = os.getcwd()
    os.chdir(directory)
    for file in files:
        if file != base_wdl:
            version = get_wdl_version_from_file(file)
            command = f'diff -u {base_wdl} {file} > version_{version}.patch'
            subprocess.run(command, shell=True)
            if remove:
                os.remove(file)
    if remove and rename:
        os.rename(base_wdl, f"{os.path.basename(directory)}.wdl")
    os.chdir(working_dir)

def main(argv=sys.argv[1:]):
    parser = argparse.ArgumentParser(description='Create patch files in the right format')
    parser.add_argument("--version", "-v", default=None, required=True, choices=["1.0", "1.1", "draft-2"],
                        help="The base WDL file's version")
    parser.add_argument("--directory", "-d", default=None, required=True,
                        help='Directory where all the WDL files are')
    parser.add_argument("--remove", default=False,
                        help='Remove WDL files that are not the base')
    parser.add_argument("--rename", default=False,
                        help='Rename the base WDL file to the directory (--remove must be set to True too)')
    args = parser.parse_args(argv)

    create_patch(args.directory, args.version, args.remove, args.rename)

if __name__ == "__main__":
    main()