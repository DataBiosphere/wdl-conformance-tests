import argparse
import os
import subprocess
import sys

from lib import get_wdl_version_from_file


def unpatch(directory, version, filename):
    if not (version or filename):
        print("Warning: Both --version or --filename were not provided. Will use the first WDL file found.")
    base_wdl = None
    wdl_files = list()
    patch_files = list()
    wdl_version_exists = False
    if filename is None:
        # version
        for file in os.listdir(directory):
            if file.endswith(".wdl"):
                path = os.path.abspath(os.path.join(directory, file))
                wdl_files.append(path)
                found_version = get_wdl_version_from_file(path)
                if found_version == version and not wdl_version_exists:
                    base_wdl = path
                    wdl_version_exists = True
            if file.endswith(".patch"):
                path = os.path.abspath(os.path.join(directory, file))
                patch_files.append(path)
    else:
        base_wdl = filename
    if base_wdl is None:
        # find first WDL file
        if not wdl_version_exists:
            print(f"WDL file with version {version} was not found. Using first WDL file found.")
        base_wdl = wdl_files[0]

    print(f"Patch from base file {base_wdl}")

    working_dir = os.getcwd()
    os.chdir(directory)
    all_output_files = list()
    try:
        for patch_file in patch_files:
            output_version = os.path.splitext(os.path.basename(patch_file))[0]
            output_basename = os.path.basename(base_wdl)
            for version_name in ["_version_1.0", "_version_1.1", "_version_draft-2"]:
                # filename may have a version suffix if --rename was not used, so get rid of it when recreating
                output_basename = output_basename.replace(version_name, "")
            output_file = os.path.splitext(output_basename)[0] + "_" + output_version + ".wdl"
            if os.path.exists(output_file):
                # if the output file somehow exists, it likely means that the original WDL files were never deleted
                # so there is no reason to recreate them as overwriting them may be unwanted behavior if there are
                # changed that the patch files do not reflect
                print(f"File already exists. Not applying patch to {output_file}")
                continue
            command = f'patch -o {output_file} {base_wdl} {patch_file} -r {output_file}.rej'
            all_output_files.append(output_file)
            subprocess.check_output(command, shell=True)
            print(f"Applied patch to {output_file}")
    except subprocess.CalledProcessError as err:
        # if there is an error, the patch command likely failed, so revert
        print(f"Could not apply patch: {err}")
        # delete the failed patch files
        for output_file in all_output_files:
            # revert
            try:
                os.remove(output_file)
            except FileNotFoundError:
                # maybe the file was never made from the command, on my local machine, it seems like a failed
                # patch command still makes the file though
                pass

    os.chdir(working_dir)


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    parser = argparse.ArgumentParser(description='Reverse patch.py to get back the original WDL files. This can be '
                                                 'useful if the original WDL files no longer exist and a modification '
                                                 'that invalidates the existing patches is necessary.')
    parser.add_argument("--directory", "-d", default=None, required=True,
                        help='Directory where all at least the base WDL file and patch files are')
    parser.add_argument("--version", "-v", default=None, choices=["1.0", "1.1", "draft-2"],
                        help="The base WDL file's version. If specified, it will find the first WDL file with this "
                             "version to create patched files from.")
    parser.add_argument("--file", "-f", default=None,
                        help="File name of base WDL file. If specified, it will use it to create patched files from."
                             "Takes priority over --version")
    args = parser.parse_args(argv)

    unpatch(args.directory, args.version, args.file)


if __name__ == "__main__":
    main()
