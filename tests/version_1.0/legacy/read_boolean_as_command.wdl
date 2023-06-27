version 1.0
workflow readBooleanWorkflow {
  input {
    File in_file
  }

  call read_boolean {input: in_file=in_file}
}

task read_boolean {
  input {
    File in_file
  }

  command {
    echo "${read_boolean(in_file)}" > output.txt
  }

  output {
    File the_output = 'output.txt'
  }
}
