workflow stdoutWorkflow {
  input {
    String message
  }
  call get_stdout { input: message=message }
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
