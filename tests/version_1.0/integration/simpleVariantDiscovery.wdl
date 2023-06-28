version 1.0

workflow SimpleVariantDiscovery {
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
  output {
    File combine_filteredVCF = combine.filteredVCF
    File hardFilterSNP_filteredSNPs = hardFilterSNP.filteredSNPs
    File selectIndels_rawSubset = selectIndels.rawSubset
    File selectSNPs_rawSubset = selectSNPs.rawSubset
    File haplotypeCaller_rawVCF = haplotypeCaller.rawVCF
    File hardFilterIndel_filteredIndels = hardFilterIndel.filteredIndels
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

task hardFilterSNP {
  input {
    File GATK
    File RefFasta
    File RefIndex
    File RefDict
    String sampleName
    File rawSNPs
  }

  command {
    java -jar ${GATK} \
      VariantFiltration \
      --reference ${RefFasta} \
      --variant ${rawSNPs} \
      --filter-expression "FS > 60.0" \
      --filter-name "snp_filter" \
      --output ${sampleName}.filtered.snps.vcf
  }
  runtime {
    container: "ibmjava:latest"
    memory: "4 GB"
  }
  output {
    File filteredSNPs = "${sampleName}.filtered.snps.vcf"
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

  command {
    java -jar ${GATK} \
      VariantFiltration \
      --reference ${RefFasta} \
      --variant ${rawIndels} \
      --filter-expression "FS > 200.0" \
      --filter-name "indel_filter" \
      --output ${sampleName}.filtered.indels.vcf
  }
  runtime {
    container: "ibmjava:latest"
    memory: "4 GB"
  }
  output {
    File filteredIndels = "${sampleName}.filtered.indels.vcf"
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

  command {
    java -jar ${GATK} \
      MergeVcfs \
      --INPUT ${filteredSNPs} \
      --INPUT ${filteredIndels} \
      --OUTPUT ${sampleName}.filtered.snps.indels.vcf
  }
  runtime {
    container: "ibmjava:latest"
    memory: "4 GB"
  }
  output {
    File filteredVCF = "${sampleName}.filtered.snps.indels.vcf"
  }
}
