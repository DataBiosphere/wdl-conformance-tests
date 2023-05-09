version 1.0

workflow selectFirstWorkflow{
    input {
        Int? maybe_four
        Int? maybe_five
        Int? maybe_six
    }

    call get_select_first {input: maybe_int_arr = [maybe_four, maybe_five, maybe_six]}
    
    output {
        Int result = get_select_first.first
    }
}

task get_select_first {
    input {
        Array[Int?] maybe_int_arr
    }
    command {}
    output {
        Int first = select_first(maybe_int_arr)
    }
}