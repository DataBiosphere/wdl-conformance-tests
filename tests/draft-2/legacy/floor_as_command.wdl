workflow floorWorkflow {
  Float num
  call get_floor { input: num=num }

  output {
    File the_flooring = get_floor.the_flooring
  }
}

task get_floor {
  Float num

  command {
    echo ${floor(num)} > output.txt
  }

 output {
    File the_flooring = 'output.txt'
 }
}
