version 1.1
# basic string to file conversion test
workflow wf {
  input {
    String file_str
  }

  output {
    Float out = size(file_str)
  }
}