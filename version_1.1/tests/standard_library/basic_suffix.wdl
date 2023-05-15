version 1.1

workflow suffixWorkflow {
    input {
        String s
        Array[String] in_arr
    }

    call get_suffix {
        input: s = s, in_arr = in_arr
    }

    output {
        Array[String] str_output = get_suffix.the_suffix
    }
}

task get_suffix {
    input {
        String s
        Array[String] in_arr
    }

    command {}

    output {
        Array[String] the_suffix = suffix(s, in_arr)
    }
}