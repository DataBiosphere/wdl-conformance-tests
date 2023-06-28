version 1.0

workflow SimpleVariantSelection {
  input {
    File gatk
    File refFasta
    File refIndex
    File refDict
    String name
  }

  call haplotypeCaller {
    input: 
      sampleName=name, 
      RefFasta=refFasta, 
      GATK=gatk, 
      RefIndex=refIndex, 
      RefDict=refDict
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

  output {
    File selectSNPs_rawSubset = selectSNPs.rawSubset
    File selectIndels_rawSubset = selectIndels.rawSubset
    File haplotypeCaller_rawVCF = haplotypeCaller.rawVCF
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

  command {
    java -jar ${GATK} \
        HaplotypeCaller \
        --reference ${RefFasta} \
        --input ${inputBAM} \
        --output ${sampleName}.raw.indels.snps.vcf
  }
  runtime {
    container: "ibmjava:latest"
    memory: "4 GB"
  }
  output {
    File rawVCF = "${sampleName}.raw.indels.snps.vcf"
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

  command {
    java -jar ${GATK} \
      SelectVariants \
      --reference ${RefFasta} \
      --variant ${rawVCF} \
      --select-type-to-include ${type} \
      --output ${sampleName}_raw.${type}.vcf
  }
  runtime {
    container: "ibmjava:latest"
    memory: "4 GB"
  }
  output {
    File rawSubset = "${sampleName}_raw.${type}.vcf"
  }
}