version 1.0

workflow jointCallingGenotypes {
  input {
    File inputSamplesFile
    Array[Array[File]] inputSamples = read_tsv(inputSamplesFile)
    File gatk
    File refFasta
    File refIndex
    File refDict
  }

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
  scatter (GVCF in HaplotypeCallerERC.GVCF) {
    call GenotypeGVCFs {
      input: GATK=gatk, 
        RefFasta=refFasta, 
        RefIndex=refIndex, 
        RefDict=refDict, 
        sampleName="CEUtrio", 
        GVCF=GVCF
    }
  }

  output {
    Array[File] file_output = GenotypeGVCFs.rawVCF
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
    java -Xmx4g \
        -jar ${GATK} \
        HaplotypeCaller \
        --emit-ref-confidence GVCF \
        --reference ${RefFasta} \
        --input ${bamFile} \
        --output ${sampleName}_rawLikelihoods.g.vcf \
  }
  
  runtime {
    container: "ibmjava:latest"
    memory: "4 GB"
  }

  output {
    File GVCF = "${sampleName}_rawLikelihoods.g.vcf"
  }
}

task GenotypeGVCFs {
  input {
    File GATK
    File RefFasta
    File RefIndex
    File RefDict
    String sampleName
    File GVCF
  }

  command {
    java -Xmx4g \
        -jar ${GATK} \
        GenotypeGVCFs \
        --reference ${RefFasta} \
        --variant ${GVCF} \
        --output ${sampleName}_rawVariants.vcf
  }
  runtime {
    container: "ibmjava:latest"
    memory: "4 GB"
  }

  output {
    File rawVCF = "${sampleName}_rawVariants.vcf"
  }
}








