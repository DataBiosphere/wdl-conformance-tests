workflow basenameWorkflow {
    String path

    call get_basename {
        input: path = path
    }

    output {
        String result = get_basename.the_basename
    }
}

task get_basename {
    String path

    command {
    }

    output {
        String the_basename = basename(path)
    }
}