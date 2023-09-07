version 1.1

workflow wf {
    input {
        
    }

    Array[Int]+? nonempty_optional1
    Array[Int]+? nonempty_optional2 = [1, 2]

    output {
        Boolean out1 = nonempty_optional1 == None
        Boolean out2 = nonempty_optional2 == [1, 2]
    }
}