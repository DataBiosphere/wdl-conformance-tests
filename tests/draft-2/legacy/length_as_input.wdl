workflow lengthWorkflow {
  Array[Int] in_array
  call copy_output {input: num=length(in_array)}

  output {
    File the_output = copy_output.the_output
  }
}

task copy_output {
  Int num

  command {
    echo ${num} > output.txt
  }

  output {
    File the_output = 'output.txt'
  }
}
