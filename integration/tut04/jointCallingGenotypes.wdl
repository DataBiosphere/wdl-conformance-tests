version 1.0

workflow jointCallingGenotypes {
  input {
    File inputSamplesBAM
    File inputSamplesBAI
    File gatk
    File refFasta
    File refIndex
    File refDict
    Array[File] compareFiles
  }

  # This is changed from the original tutorial as MiniWDL doesn't support importing files outside of the workflow input without changing its configuration
  Array[Array[File]] inputSamples = [["WDL_tut4a_output", inputSamplesBAM, inputSamplesBAI], ["WDL_tut4b_output", inputSamplesBAM, inputSamplesBAI], ["WDL_tut4c_output", inputSamplesBAM, inputSamplesBAI]]

  scatter (sample in inputSamples) {
    call HaplotypeCallerERC {
      input: GATK=gatk, 
        RefFasta=refFasta, 
        RefIndex=refIndex, 
        RefDict=refDict, 
        sampleName=sample[0],
        bamFile=sample[1], 
        bamIndex=sample[2]
    }
  }
  # this is using the combine step from GATK Tutorial #3 as the tutorial #4 test is broken
  call combine {
    input: GATK=gatk, 
      RefFasta=refFasta, 
      RefIndex=refIndex, 
      RefDict=refDict, 
      sampleName="CEUtrio", 
      GVCFs=HaplotypeCallerERC.GVCF
  }
  call validate_and_gather_the_output {
    input:
      compare_against_files = compareFiles,
      rawVCF = combine.rawVCF
  }
  output {
    String result = validate_and_gather_the_output.validate_success
  }
}

task HaplotypeCallerERC {
  input {
    File GATK
    File RefFasta
    File RefIndex
    File RefDict
    String sampleName
    File bamFile
    File bamIndex
  }

  command {
    java -Xmx4g -jar ${GATK} \
        HaplotypeCaller \
        --emit-ref-confidence GVCF \
        --reference ${RefFasta} \
        --input ${bamFile} \
        --output ${sampleName}_rawLikelihoods.g.vcf
  }
  output {
    File GVCF = "${sampleName}_rawLikelihoods.g.vcf"
  }

  runtime {
    docker: "ibmjava:latest"
    memory: "4 GB"
  }
}

task combine {
  input {
    File GATK
    File RefFasta
    File RefIndex
    File RefDict
    String sampleName
    Array[File] GVCFs

  }

  command <<<
    java -jar ~{GATK} \
      MergeVcfs \
      --INPUT ~{GVCFs[0]} \
      --INPUT ~{GVCFs[1]} \
      --INPUT ~{GVCFs[2]} \
      --OUTPUT ~{sampleName}_combine.vcf
  >>>
  output {
    File rawVCF = "${sampleName}_combine.vcf"
  }

  runtime {
    docker: 'ibmjava:latest'
    memory: "4 GB"
  }
}

task validate_and_gather_the_output {
    input {
        File rawVCF

        Array[File] compare_against_files
    }

    command <<<
        mkdir ./output
        cp ~{rawVCF} ./output

        mkdir ./ref
        cp ~{compare_against_files[0]} ./ref

        python <<CODE
import os
def compare_runs(output_dir, ref_dir):
    """
    Takes two directories and compares all of the files between those two
    directories, asserting that they match.

    - Ignores outputs.txt, which contains a list of the outputs in the folder.
    - Compares line by line, unless the file is a .vcf file.
    - Ignores potentially date-stamped comments (lines starting with '#').
    - Ignores quality scores in .vcf files and only checks that they found
      the same variants.  This is due to assumed small observed rounding
      differences between systems.

    :param ref_dir: The first directory to compare (with output_dir).
    :param output_dir: The second directory to compare (with ref_dir).
    """
    reference_output_files = os.listdir(ref_dir)
    for file in reference_output_files:
        if file not in ('outputs.txt', '__pycache__'):
            test_output_files = os.listdir(output_dir)
            filepath = os.path.join(ref_dir, file)
            with open(filepath) as default_file:
                good_data = []
                for line in default_file:
                    if not line.startswith('#'):
                        good_data.append(line)
                for test_file in test_output_files:
                    if file == test_file:
                        test_filepath = os.path.join(output_dir, file)
                        if file.endswith(".vcf"):
                            compare_vcf_files(filepath1=filepath,
                                              filepath2=test_filepath)
                        else:
                            with open(test_filepath) as test_file:
                                test_data = []
                                for line in test_file:
                                    if not line.startswith('#'):
                                        test_data.append(line)
                            assert good_data == test_data, "File does not match: %r" % file


def compare_vcf_files(filepath1, filepath2):
    """
    Asserts that two .vcf files contain the same variant findings.

    - Ignores potentially date-stamped comments (lines starting with '#').
    - Ignores quality scores in .vcf files and only checks that they found
      the same variants.  This is due to assumed small observed rounding
      differences between systems.

    VCF File Column Contents:
    1: #CHROM
    2: POS
    3: ID
    4: REF
    5: ALT
    6: QUAL
    7: FILTER
    8: INFO

    :param filepath1: First .vcf file to compare.
    :param filepath2: Second .vcf file to compare.
    """
    with open(filepath1) as default_file:
        good_data = []
        for line in default_file:
            line = line.strip()
            if not line.startswith('#'):
                good_data.append(line.split('\t'))

    with open(filepath2) as test_file:
        test_data = []
        for line in test_file:
            line = line.strip()
            if not line.startswith('#'):
                test_data.append(line.split('\t'))

    for i in range(len(test_data)):
        if test_data[i] != good_data[i]:
            for j in range(len(test_data[i])):
                # Only compare chromosome, position, ID, reference, and alts.
                # Quality score may vary (<1%) between systems because of
                # (assumed) rounding differences.  Same for the "info" sect.
                if j < 5:
                    if j == 4:
                        if test_data[i][j].startswith('*,'):
                            test_data[i][j] = test_data[i][j][2:]
                        if good_data[i][j].startswith('*,'):
                            good_data[i][j] = good_data[i][j][2:]
                    assert test_data[i][j] == good_data[i][j], f"\nInconsistent VCFs: {filepath1} != {filepath2}\n" \
                                                               f" - {test_data[i][j]} != {good_data[i][j]}\n" \
                                                               f" - Line: {i} Column: {j}"

try:
    compare_runs(os.path.join(os.getcwd(), "output"), os.path.join(os.getcwd(), "ref"))
    print("success")
except AssertionError as e:
    print("fail", e)
CODE
    >>>

    output {
        String validate_success = read_string(stdout())
    }

    runtime {
        docker: 'python'
    }
}




