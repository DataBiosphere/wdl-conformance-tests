version 1.0
workflow sizeWorkflow {
  input {
    File in_file
  }

  call get_size {input: in_file=in_file}
}

task get_size {
  input {
    File in_file
  }

  command {
    echo "${size(in_file)}" > output.txt
  }

  output {
    File the_output = 'output.txt'
  }
}
