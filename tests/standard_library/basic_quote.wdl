version 1.1

workflow quoteWorkflow{
    input {
        Array[String] str_arr
    }

    output {
        Array[String] result = quote(str_arr)
    }
}