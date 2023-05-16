version 1.0

workflow failWorkflow {
    input {
        String in
    }

    output {
        Array[String] str_output = prefix(in, in)
    }
}