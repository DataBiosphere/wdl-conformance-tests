version 1.0

workflow fakeFailWorkflow {
    input {
        Int int_input
    }

    output {
        Array[String] str_output = squote(int_input)
    }
}