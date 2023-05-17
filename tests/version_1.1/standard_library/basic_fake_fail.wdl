version 1.1

workflow fakeFailWorkflow {
    input {
        Int int_input
    }

    output {
        Array[String] str_output = squote(int_input)
    }
}