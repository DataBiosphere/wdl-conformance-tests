workflow stdoutWorkflow {
  String message
  call get_stdout { input: message=message }

  output {
    File check_this = get_stdout.check_this
  }
}

task get_stdout {
  String message

  command {
    echo '${message}'
  }

 output {
    File check_this = stdout()
 }
}
