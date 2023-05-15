version 1.1

workflow squoteWorkflow{
    input {
        Array[String] str_arr
        Array[Int] int_arr
        Array[Float] float_arr
        Array[Boolean] bool_arr
        Array[File] file_arr
        # Array[Directory] dir_arr
    }

    output {
        Array[String] str_result = squote(str_arr)
        Array[String] int_result = squote(int_arr)
        Array[String] float_result = squote(float_arr)
        Array[String] bool_result = squote(bool_arr)
        Array[String] file_result = squote(file_arr)
        # Array[String] dir_result = quote(dir_arr)
    }
}
