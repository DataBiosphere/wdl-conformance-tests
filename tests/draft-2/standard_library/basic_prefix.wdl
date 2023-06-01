workflow prefixWorkflow {
    Array[String] str_arr
    String pre

    call get_prefix {input: str_arr = str_arr, pre = pre}

    output {
        Array[String] str_output = get_prefix.the_prefix
    }
}

task get_prefix {
    Array[String] str_arr
    String pre

    command {}

    output {
        Array[String] the_prefix = prefix(pre, str_arr)
    }
}