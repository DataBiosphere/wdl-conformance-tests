version 1.0

workflow prefixWorkflow {
  input {
    Array[String] str_arr
    String pre
  }
  output {
    Array[String] str_result = prefix(pre, str_arr)
  }
}
