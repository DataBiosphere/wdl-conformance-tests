import os
import subprocess

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
            if line.strip() == ">>>" or line.strip() == "}": # this could be accidentally triggered
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
    # only tests the first line
    version = get_wdl_version_from_file(filename)

    # if the wdl file version is the same as the target version, return the wdl file as there is no need to generate
    if version == target_version:
        return filename

    # draft-2 and 1.0/1.1 are not interchangeable by just changing the wdl version
    # so if version is draft-2, a patch file is necessary
    patch_file = f"{wdl_dir}/draft-2.patch"  # hardcoded patchfile name
    if target_version == "draft-2" and os.path.exists(patch_file):
        return patch(filename, patch_file, wdl_dir, outfile_name=outfile_name)


    # versions 1.1 and 1.0 should be interchangeable (or at least mostly backwards compatible), so just swap the version declaration at the beginning of the file
    outfile_path = os.path.join(wdl_dir, outfile_name)
    with open(filename, 'r') as f:
        with open(outfile_path, 'w') as out:
            gen = generate_replace_version_wdl(target_version, f.readlines())
            # remove input section declaration if draft-2
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
    outfile_name = f"_version_{version}.wdl"
    return generate_wdl(wdl_file, wdl_dir, version, outfile_name=outfile_name)