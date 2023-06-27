version 1.0
workflow readIntWorkflow {
  input {
    File in_file
  }

  call read_int {input: in_file=in_file}
}

task read_int {
  input {
    File in_file
  }

  command {
    echo "${read_int(in_file)}" > output.txt
  }

  output {
    File the_output = 'output.txt'
  }
}
