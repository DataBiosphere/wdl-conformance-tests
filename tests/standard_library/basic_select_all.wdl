workflow selectAllWorkflow {
    Int? maybe_four
    Int? maybe_five
    Int? maybe_six
    Int? maybe_seven
    Int? maybe_eight

    call get_select_all {
        input: arr_int = [maybe_four, maybe_five, maybe_six, maybe_seven, maybe_eight]
    }

    output {
        Array[Int] result = get_select_all.all_defined
    }
}

task get_select_all {
    Array[Int?] arr_int

    command {

    }

    output {
        Array[Int] all_defined = select_all(arr_int)
    }
}