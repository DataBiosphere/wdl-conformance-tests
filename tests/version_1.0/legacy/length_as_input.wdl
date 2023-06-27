version 1.0
workflow lengthWorkflow {
  input {
    Array[Int] in_array
  }
  call copy_output {input: num=length(in_array)}
}

task copy_output {
  input {
    Int num
  }

  command {
    echo ${num} > output.txt
  }

  output {
    File the_output = 'output.txt'
  }
}
