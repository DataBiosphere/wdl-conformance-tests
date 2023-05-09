version 1.0

workflow basenameWorkflow {
    input {
        String path
    }

    call get_basename {
        input: path = path
    }

    output {
        String result = get_basename.the_basename
    }
}

task get_basename {
    input {
        String path
    }

    command {
    }

    output {
        String the_basename = basename(path)
    }
}