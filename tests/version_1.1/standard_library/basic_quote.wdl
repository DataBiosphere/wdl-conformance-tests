version 1.1

workflow quoteWorkflow {
    input {
        Array[String] str_arr
        Array[Int] int_arr
        Array[Float] float_arr
        Array[Boolean] bool_arr
        Array[File] file_arr
        # Array[Directory] dir_arr
    }
    output {
        Array[String] str_output = quote(str_arr)
        Array[String] int_output = quote(int_arr)
        Array[String] float_output = quote(float_arr)
        Array[String] bool_output = quote(bool_arr)
        # Array[String] file_output = quote(file_arr)
        # Array[String] dir_output = quote(dir_arr)
    }
}
