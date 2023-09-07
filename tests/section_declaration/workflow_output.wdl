version 1.1

workflow wf {
    input {}

    output {
        String filepath = "path/to/file.txt"
        String file_basename = basename(filepath)
    }
}