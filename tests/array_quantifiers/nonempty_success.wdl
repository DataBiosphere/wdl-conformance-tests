version 1.1

workflow wf {
    input {
    }
    Array[Int]+ array_nonempty = [1,2,3]

    output {
        Int nonempty_length = length(array_nonempty)
        Array[Int] nonempty_out = array_nonempty
    }
}