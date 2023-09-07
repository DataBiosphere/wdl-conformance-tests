version 1.1

# Test all variants of string to file
# toil-wdl-runner separates input, output, scatter, conditional, etc. sections, so test for each

workflow wf {
  input {
    String file_str
    # test for input
    Float in_filesize = size("tests/string_to_file/str_to_file.json")
  }

  String file_str2 = "tests/string_to_file/str_to_file_variants.wdl"
  Array[File] file_arr = ["tests/string_to_file/str_to_file_variants.wdl", "tests/string_to_file/str_to_file.json"]

  # test intermediate
  Float int_filesize = size(file_str2)

  # test conditional
  Boolean b = true
  if (b) {
    Float cond_filesize = size(file_str)
  }
  # test task
  call get_size {
    input:
      f=file_str
  }

  # test scatter
  scatter (file in file_arr) {
    Float scatter_filesize = size(file)
  }

  output {
    Float task_in_size = get_size.in_size
    Float task_out_size = get_size.out_size
    Float task_cmd_size = get_size.cmd_size
    Array[Float] scatter_size = scatter_filesize
    Float in_size = in_filesize
    Float out_size = size("tests/string_to_file/str_to_file_normal.wdl")
    Float int_size = int_filesize
    Float? cond_size = cond_filesize
  }
}

# test task input, command, and output
task get_size {
  input {
    File f
    Float f_size = size(f)
  }

  command {
    echo ~{size(f)}
  }


  output {
    Float out_size = size(f)
    Float in_size = f_size
    Float cmd_size = read_float(stdout())
  }
  
}