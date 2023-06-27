version 1.0
workflow floorWorkflow {
  input {
    Float num
  }
  call get_floor { input: num=num }
}

task get_floor {
  input {
    Float num
  }

  command {
    echo ${floor(num)} > output.txt
  }

 output {
    File the_flooring = 'output.txt'
 }
}
