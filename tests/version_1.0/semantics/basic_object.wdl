version 1.0

workflow objectWorkflow {
    input {
        
    }
    Object f = object {
        a: 10,
        b: "hello"
    }

    output {
        Object obj_output = f
    }
}