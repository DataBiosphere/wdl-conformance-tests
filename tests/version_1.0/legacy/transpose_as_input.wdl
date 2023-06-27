version 1.0
workflow transposeWorkflow {
  # this workflow depends on write_tsv()
  input {
    Array[Array[Int]] in_array
  }

  call copy_output {input: in_array=transpose(in_array)}
}

task copy_output {
  input {
    Array[Array[Int]] in_array
  }

  command {
    cp ${write_tsv(in_array)} output.txt
  }

  output {
    File the_output = 'output.txt'
  }
}
