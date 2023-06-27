version 1.0

workflow pairWorkflow {
    input {
        Int first_int
        Int second_int
    }

    output {
        Pair[Int, Int] pair_output = (first_int, second_int)
    }
}