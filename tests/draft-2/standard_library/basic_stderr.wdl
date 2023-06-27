workflow stderrWorkflow {
  String message
  call get_stderr { input: message=message }

  output {
    File check_this = get_stderr.check_this
  }
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
