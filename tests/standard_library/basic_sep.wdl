version 1.1

workflow sepWorkflow{

    input {
        String delimiter
        Array[String] to_sep
    }
    
    output {
        String result = sep(delimiter, to_sep)
    }
}