workflow helloHaplotypeCaller {
  call haplotypeCaller

#  output {
#    File rawVCF = haplotypeCaller.rawVCF
#  }
}

task haplotypeCaller {
  File GATK
  File RefFasta
  File RefIndex
  File RefDict
  String sampleName
  File inputBAM
  File bamIndex
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
