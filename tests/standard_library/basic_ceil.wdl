workflow ceilWorkflow {
  Float num
  call get_ceil { input: num=num }
}

task get_ceil {
  Float num

  command {
    echo 'No command needed.'
  }

 output {
    Int the_ceiling = ceil(num)
 }
}
