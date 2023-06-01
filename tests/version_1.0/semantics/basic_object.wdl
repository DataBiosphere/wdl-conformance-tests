version 1.0

workflow objectWorkflow {
    input {
        
    }
    Object f = object {
        a: 10,
        b: "hello",
        f: "tests/version_1.0/semantics/basic_object.wdl"
    }

    output {
        Object obj_output = f
    }
}