version 1.1

workflow wf {
    input {
        File first
        File second
    }
    call t {
        input:
            first=first,
            second=second
    }
    output {
        Boolean equal = t.equal
    }
}

task t {
    input {
        File first
        File second
    }

    String first_basename = basename(first)
    String second_basename = basename(second)
    command <<<
        find . -name ~{first_basename} -execdir bash -c 'pwd' {} \; >> output1.txt
        find . -name ~{second_basename} -execdir bash -c 'pwd' {} \; >> output2.txt
    >>>
    output {
        String out1 = read_string("output1.txt")
        String out2 = read_string("output2.txt")
        Boolean equal = read_string("output1.txt") == read_string("output2.txt")
    }
}