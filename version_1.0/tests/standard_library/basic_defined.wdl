version 1.0

workflow definedWorkflow {
    input {
        String? s
    }

    output {
        Boolean bool_output = defined(s)
    }
}
