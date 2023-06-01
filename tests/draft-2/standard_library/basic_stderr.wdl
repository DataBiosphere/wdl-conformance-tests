workflow stderrWorkflow {
  String message
  call get_stderr { input: message=message }
}

task get_stderr {
  String message

  command {
    >&2 echo "a journey straight to stderr"
  }

 output {
    File check_this = stderr()
 }
}
