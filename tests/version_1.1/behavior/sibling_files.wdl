version 1.1

workflow wf {
    input {
        File first
        File second
        String first_as_string = first
        String second_as_string = second
    }
    call t {
        input:
            first=first_as_string,
            second=second_as_string
    }
    output {
        Boolean equal = t.equal
        # String out1 = t.out1
        # String out2 = t.out2
    }
}

task t {
    input {
        String first
        String second
    }

    String first_basename = basename(first)
    String second_basename = basename(second)
    command <<<
        function f {
            FILE=$1
            if [[ $FILE == *"toilfile"* ]]; then
                IFS=":" read -ra ARRAY <<< "$FILE"
                for i in "${ARRAY[@]}"; do
                    :
                done

                variable=$(sed "s/%2F/\//g" <<< ${ARRAY[1]##*%3A})

                basename=$(basename ${variable})
                
                directory=$(sed "s/${basename}\/*//g" <<< ${variable})
                echo ${directory}
            else
                basename=$(basename ${FILE})
                directory=$(sed "s/${basename}\/*//g" <<< ${FILE})
                echo ${directory}
            fi
        }
        f ~{first} > output1.txt
        f ~{second} > output2.txt
    >>>
    output {
        # String out1 = read_string("output1.txt")
        # String out2 = read_string("output2.txt")
        Boolean equal = read_string("output1.txt") == read_string("output2.txt")
    }
}