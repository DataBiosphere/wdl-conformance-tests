version 1.0
workflow ceilWorkflow {
  input {
    Float num
  }
  call get_ceil { input: num=ceil(num) }
}

task get_ceil {
  input {
    Float num
  }

  command {
    echo ${num} > output.txt
  }

 output {
    File the_ceiling = 'output.txt'
 }
}
