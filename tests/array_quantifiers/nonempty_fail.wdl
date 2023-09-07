version 1.1

workflow wf {
    input {
    }
    Array[Int]+ array_nonempty_fail = []
    output {
        Int out = select_first(array_nonempty_fail)
    }
}