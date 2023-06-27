workflow ceilWorkflow {
  Float num
  call get_ceil { input: num=ceil(num) }

  output {
    File the_ceiling = get_ceil.the_ceiling
  }
}

task get_ceil {
  Float num

  command {
    echo ${num} > output.txt
  }

 output {
    File the_ceiling = 'output.txt'
 }
}
