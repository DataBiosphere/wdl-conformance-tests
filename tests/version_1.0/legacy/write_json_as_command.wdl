version 1.0
workflow writeJsonWorkflow {
  input {
    Map[String, String] in_map
  }

  call write_json {input: in_map=in_map}
}

task write_json {
  input {
    Map[String, String] in_map
  }

  command {
    cp ${write_json(in_map)} output.txt
  }

  output {
    File the_output = 'output.txt'
  }
}
