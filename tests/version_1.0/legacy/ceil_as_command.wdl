version 1.0
workflow ceilWorkflow {
  input {
    Float num
  }
  call get_ceil { input: num=num }

  output {
    File the_ceiling = get_ceil.the_ceiling
  }
}

task get_ceil {
  input {
    Float num
  }

  command {
    echo ${ceil(num)} > output.txt
  }

 output {
    File the_ceiling = 'output.txt'
 }
}
