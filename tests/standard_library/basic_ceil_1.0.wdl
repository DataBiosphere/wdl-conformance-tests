version 1.0

workflow ceilWorkflow {
  input { 
    Float num
  }
  call get_ceil { input: num=num }
  output {
    Int the_ceiling = get_ceil.the_ceiling
  }
}

task get_ceil {
  input {
    Float num
  }

  command {
    echo 'No command needed.'
  }

 output {
    Int the_ceiling = ceil(num)
 }
}
