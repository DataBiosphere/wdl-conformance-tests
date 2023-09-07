version 1.1

workflow wf {
    input {}

    call t {}
    output {
        String filepath = t.task_filepath
        String file_basename = t.task_file_basename
    }
}

task t {
    input {
        String filepath = "path/to/file.txt"
        String file_basename = basename(filepath)
    }
    command {}

    output {
        String task_file_basename = file_basename
        String task_filepath = filepath
    }
}