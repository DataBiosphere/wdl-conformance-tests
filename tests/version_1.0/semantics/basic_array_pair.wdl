version 1.0

workflow arrayPairWorkflow {
    input {
        Int first_int
        Int second_int
    }

    output {
        Array[Pair[Int, Int]] pair_output = [(first_int, second_int)]
    }
}