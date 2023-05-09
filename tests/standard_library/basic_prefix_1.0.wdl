version 1.0

workflow prefixWorkflow {
    input {
        Array[String] str_arr
        String pre
    }
    call get_prefix {input: str_arr = str_arr, pre = pre}
    output {
        Array[String] result = prefix("-e ", str_arr)
    }
}

task get_prefix {
    input {
        Array[String] str_arr
        String pre
    }
    command {}
    output {
        Array[String] the_prefix = prefix(pre, str_arr)
    }
}