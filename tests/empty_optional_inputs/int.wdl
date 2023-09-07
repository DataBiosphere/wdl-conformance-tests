version 1.0

workflow wf {
    input {
        Int a
        Int b
        Int? c
    }

    output {
        Array[Int] out = select_all([a, b, c])
    }
}