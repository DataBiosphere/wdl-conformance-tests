version 1.1

workflow wf {
    input {
    }
    call make_files as files_made

    call check as check1 {
        input:
            files = files_made.found
    }
    output {
        Boolean success = check1.success
    }
}

task make_files {
    input {
    }

    command <<<
        touch 'GRCh38#0#chm1.fa'
        touch 'GRCh38%230%23chm1.fa'
        touch "'"'"!@#$%^&*()_[]{};<>~`+=?—🌍'.fa
    >>>

    output {
        Array[File] found = glob("*.fa") 
    }
}

task check {
    input {
        Array[File] files
    }

    command <<<
        set -e
        cp ~{sep=" " files} .
        stat 'GRCh38#0#chm1.fa'
        stat 'GRCh38%230%23chm1.fa'
        stat "'"'"!@#$%^&*()_[]{};<>~`+=?—🌍'.fa
        echo "SUCCESS" >"output.txt"
    >>>

    output {
        Boolean success = read_string("output.txt") == "SUCCESS"
    }
}
