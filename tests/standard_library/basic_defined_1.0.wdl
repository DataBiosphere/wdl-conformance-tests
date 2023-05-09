version 1.0

workflow definedWorkflow {
    input {
        String? s
    }

    call get_defined {input: s = s}

    output {
        Boolean result = get_defined.is_defined
    }
}

task get_defined {
    input {
        String? s
    }

    command {}

    output {
        Boolean is_defined = defined(s)
    }
}