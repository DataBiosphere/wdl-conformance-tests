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
        Array[String] str_output = squote(str_arr)
        Array[String] int_output = squote(int_arr)
        Array[String] float_output = squote(float_arr)
        Array[String] bool_output = squote(bool_arr)
        Array[String] file_output = squote(file_arr)
        # Array[String] dir_output = quote(dir_arr)
    }
}
