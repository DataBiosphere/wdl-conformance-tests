version 1.1

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