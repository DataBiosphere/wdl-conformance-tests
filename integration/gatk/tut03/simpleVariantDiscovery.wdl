version 1.0

workflow SimpleVariantDiscovery {
  input {
    File gatk
    File refFasta
    File refIndex
    File refDict
    String name
    File inputBAM
    File bamIndex
    Array[File] compareFiles
  }

  call haplotypeCaller {
    input:
      sampleName=name,
      RefFasta=refFasta,
      GATK=gatk,
      RefIndex=refIndex,
      RefDict=refDict,
      inputBAM=inputBAM,
      bamIndex=bamIndex
  }
  call select as selectSNPs {
    input:
      sampleName=name,
      RefFasta=refFasta,
      GATK=gatk,
      RefIndex=refIndex,
      RefDict=refDict,
      type="SNP",
      rawVCF=haplotypeCaller.rawVCF
  }
  call select as selectIndels {
    input:
      sampleName=name,
      RefFasta=refFasta,
      GATK=gatk,
      RefIndex=refIndex,
      RefDict=refDict,
      type="INDEL",
      rawVCF=haplotypeCaller.rawVCF
  }
  call hardFilterSNP {
    input: sampleName=name,
      RefFasta=refFasta,
      GATK=gatk,
      RefIndex=refIndex,
      RefDict=refDict,
      rawSNPs=selectSNPs.rawSubset
  }
  call hardFilterIndel {
    input: sampleName=name,
      RefFasta=refFasta,
      GATK=gatk,
      RefIndex=refIndex,
      RefDict=refDict,
      rawIndels=selectIndels.rawSubset
  }
  call combine {
    input: sampleName=name,
      RefFasta=refFasta,
      GATK=gatk,
      RefIndex=refIndex,
      RefDict=refDict,
      filteredSNPs=hardFilterSNP.filteredSNPs,
      filteredIndels=hardFilterIndel.filteredIndels
  }

  call validate_and_gather_the_output {
    input:
      haplotype=haplotypeCaller.rawVCF,
      selectSNPs=selectSNPs.rawSubset,
      selectIndels=selectIndels.rawSubset,
      hardFilterIndel=hardFilterIndel.filteredIndels,
      hardFilterSNP=hardFilterSNP.filteredSNPs,
      combine=combine.filteredVCF,
      compare_against_files=compareFiles
  }

  output {
    String result = validate_and_gather_the_output.validate_success
  }
}

task haplotypeCaller {
  input {
    File GATK
    File RefFasta
    File RefIndex
    File RefDict
    String sampleName
    File inputBAM
    File bamIndex
  }

  command <<<
    java -jar ~{GATK} \
        HaplotypeCaller \
        --reference ~{RefFasta} \
        --input ~{inputBAM} \
        --output ~{sampleName}.raw.indels.snps.vcf
  >>>
  output {
    File rawVCF = "${sampleName}.raw.indels.snps.vcf"
  }
  runtime {
    docker: "ibmjava:latest"
  }
}

task select {
  input {
    File GATK
    File RefFasta
    File RefIndex
    File RefDict
    String sampleName
    String type
    File rawVCF
  }

  command <<<
    java -jar ~{GATK} \
      SelectVariants \
      --reference ~{RefFasta} \
      --variant ~{rawVCF} \
      --select-type-to-include ~{type} \
      --output ~{sampleName}_raw.~{type}.vcf
  >>>
  output {
    File rawSubset = "${sampleName}_raw.${type}.vcf"
  }
  runtime {
    docker: "ibmjava:latest"
  }
}

task hardFilterSNP {
  input {
    File GATK
    File RefFasta
    File RefIndex
    File RefDict
    String sampleName
    File rawSNPs
  }


  command <<<
    java -jar ~{GATK} \
      VariantFiltration \
      --reference ~{RefFasta} \
      --variant ~{rawSNPs} \
      --filter-expression "FS > 60.0" \
      --filter-name "snp_filter" \
      --output ~{sampleName}.filtered.snps.vcf
  >>>
  output {
    File filteredSNPs = "${sampleName}.filtered.snps.vcf"
  }
  runtime {
    docker: "ibmjava:latest"
  }
}

task hardFilterIndel {
  input {
    File GATK
    File RefFasta
    File RefIndex
    File RefDict
    String sampleName
    File rawIndels
  }

  command <<<
    java -jar ~{GATK} \
      VariantFiltration \
      --reference ~{RefFasta} \
      --variant ~{rawIndels} \
      --filter-expression "FS > 200.0" \
      --filter-name "indel_filter" \
      --output ~{sampleName}.filtered.indels.vcf
  >>>
  output {
    File filteredIndels = "${sampleName}.filtered.indels.vcf"
  }
  runtime {
    docker: "ibmjava:latest"
  }
}

task combine {
  input {
    File GATK
    File RefFasta
    File RefIndex
    File RefDict
    String sampleName
    File filteredSNPs
    File filteredIndels
  }

  command <<<
    java -jar ~{GATK} \
      MergeVcfs \
      --INPUT ~{filteredSNPs} \
      --INPUT ~{filteredIndels} \
      --OUTPUT ~{sampleName}.filtered.snps.indels.vcf
  >>>
  output {
    File filteredVCF = "${sampleName}.filtered.snps.indels.vcf"
  }

  runtime {
    docker: "ibmjava:latest"
  }
}


task validate_and_gather_the_output {
    input {
        File haplotype
        File selectSNPs
        File selectIndels
        File hardFilterIndel
        File hardFilterSNP
        File combine
        Array[File] compare_against_files
    }

    command <<<
        mkdir ./output
        cp ~{haplotype} ./output
        cp ~{selectSNPs} ./output
        cp ~{selectIndels} ./output
        cp ~{hardFilterIndel} ./output
        cp ~{hardFilterSNP} ./output
        cp ~{combine} ./output

        mkdir ./ref
        cp ~{compare_against_files[0]} ./ref
        cp ~{compare_against_files[1]} ./ref
        cp ~{compare_against_files[2]} ./ref
        cp ~{compare_against_files[3]} ./ref
        cp ~{compare_against_files[4]} ./ref
        cp ~{compare_against_files[5]} ./ref

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