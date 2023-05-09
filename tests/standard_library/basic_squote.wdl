version 1.1

workflow squoteWorkflow{
    input {
        Array[String] str_arr
    }

    output {
        Array[String] result = squote(str_arr)
    }
}