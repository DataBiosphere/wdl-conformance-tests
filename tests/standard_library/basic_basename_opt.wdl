version 1.0

workflow basenameWorkflowOpt {
    input {
        String path
        String opt
    }
    call get_basename {input: path = path, opt = opt}
    output {
        String result = get_basename.the_basename
    }
}

task get_basename {
    input {
        String path
        String opt
    }

    command {

    }

    output {
        String the_basename = basename(path, opt)
    }
}