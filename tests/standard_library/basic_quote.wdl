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
        Array[String] str_result = quote(str_arr)
        Array[String] int_result = quote(int_arr)
        Array[String] float_result = quote(float_arr)
        Array[String] bool_result = quote(bool_arr)
        Array[String] file_result = quote(file_arr)
        # Array[String] dir_result = quote(dir_arr)
    }
}
