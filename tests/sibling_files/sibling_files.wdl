version 1.0

workflow wf {
    input {
    }
    call make_files as sibling1
    call make_files as sibling2
    call make_files as sibling3

    call check as check1 {
        input:
            first=sibling1.first,
            second=sibling1.second,
            third=sibling2.second
    }
    call check as check2 {
        input:
            first=sibling1.second,
            second=sibling1.first,
            third=sibling2.second
    }
    call check as check3 {
        input:
            first=sibling2.first,
            second=sibling2.second,
            third=sibling1.first
    }
    call check as check4 {
        input:
            first=sibling2.second,
            second=sibling2.first,
            third=sibling1.first
    }
    output {
        Boolean result1 = check1.result
        Boolean result2 = check2.result
        Boolean result3 = check3.result
        Boolean result4 = check4.result
    }
}

task make_files {
    input {
    }

    command <<<
    >>>

    output {
        File first = write_lines(["first file"])
        File second = write_lines(["second file"])
    }
}

task check {
    input {
        File first
        File second
        File third
    }

    command {
        echo ~{first}
        echo ~{second}
        echo ~{third}

        if [[ "$(dirname first)" != "$(dirname second)" ]] ; then
            echo "FAIL" > output.txt
        else
            echo "SUCCESS" > output.txt
        fi
    }

    output {
        Boolean result = read_string("output.txt") == "SUCCESS"
    }
}