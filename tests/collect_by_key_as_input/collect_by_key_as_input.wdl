version 1.1

workflow collectByKeyWorkflow {
  input {
    Array[Pair[String, Int]] in_array = [("a", 1), ("b", 2), ("a", 3)]
  }

  call copy_output {input: in_map=collect_by_key(in_array)}

  output {
    File the_output = copy_output.the_output
  }
}

task copy_output {
  input {
    Map[String, Array[Int]] in_map
  }

  command <<<
    cp ~{write_json(in_map)} output.txt
  >>>

  output {
    File the_output = 'output.txt'
  }
}
