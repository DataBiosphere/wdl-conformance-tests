workflow definedWorkflow {
    String? s

    call get_defined {input: s = s}

    output {
        Boolean bool_output = get_defined.is_defined
    }
}

task get_defined {
    String? s
    command {}
    output {
        Boolean is_defined = defined(s)
    }
}