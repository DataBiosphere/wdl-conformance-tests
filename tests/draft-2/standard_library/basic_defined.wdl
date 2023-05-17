workflow definedWorkflow {
    String? s1
    String? s2

    output {
        Boolean bool_output = defined(s1)
        Boolean bool_output_none = defined(s2)
    }
}
