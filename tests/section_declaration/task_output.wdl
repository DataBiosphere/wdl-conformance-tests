version 1.1

workflow wf {
    input {}

    call t {}
    output {
        String filepath = t.filepath
        String file_basename = t.file_basename
    }
}

task t {
    input {

    }
    command {}

    output {
        String filepath = "path/to/file.txt"
        String file_basename = basename(filepath)
    }
}