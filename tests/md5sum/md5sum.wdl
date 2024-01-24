version 1.1

task md5 {
  input {
    File inputFile
  }
  command {
    md5sum ${inputFile} >> md5sum.txt
  }

 output {
    File value = "md5sum.txt"
 }

 runtime {
   docker: "ubuntu:22.04"
   cpu: 1
   memory: "512 MB"
   disks: "local-disk 10 HDD"
 }
}

workflow ga4ghMd5 {
  input {
    File inputFile
  }
  call md5 { input: inputFile=inputFile }
  output {
    File value = md5.value
  }
}
