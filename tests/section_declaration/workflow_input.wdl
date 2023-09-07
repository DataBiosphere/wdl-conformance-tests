version 1.1

workflow wf {
    input {
        String input_filepath = "path/to/file.txt"
        String input_file_basename = basename(input_filepath)
    }

    output {
        String file_basename = input_file_basename
        String filepath = input_filepath
    }
}