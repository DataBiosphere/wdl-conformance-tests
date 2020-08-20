workflow myWorkflow {
    call get_stdout
}

task get_stdout {
  input {
    String message
  }
  command {
    echo '${message}'
  }
  output {
    File check_this = stdout()
  }
}
