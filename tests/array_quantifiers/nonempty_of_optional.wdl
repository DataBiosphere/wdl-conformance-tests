version 1.1

workflow wf {
    input {
    }
    Array[Int?]+ array_nonempty = [None,2,3]

    output {
        Array[Int] out = select_all(array_nonempty)
    }
}