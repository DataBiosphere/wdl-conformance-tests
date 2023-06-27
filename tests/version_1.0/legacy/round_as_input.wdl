version 1.0
workflow roundWorkflow {
  input {
    Float num
  }
  call get_round { input: num=round(num) }
}

task get_round {
  input {
    Float num
  }

  command {
    echo ${num} > output.txt
  }

 output {
    File the_rounding = 'output.txt'
 }
}
