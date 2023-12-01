## This WDL maps FASTQ file(s) using ENCODE ChIP-seq mapping pipeline
##
## Requirements/expectations :
## - trimming length parameter (either "native" or length in string format)
## - fastq (either one SE or two PE fastq file(s))
## - reference (tar of reference files for bwa)
##
## example inputs.json would look like:
## {
##      "encode_mapping_workflow.fastqs": ["input_data/rep1-ENCFF000VOL-chr21.fq.gz"],
##      "encode_mapping_workflow.trimming_parameter": "native",
##      "encode_mapping_workflow.reference": "input_data/GRCh38_chr21_bwa.tar.gz"
## }



# TASK DEFINITIONS
version 1.0
task mapping {
    input {

        Array[File] fastq_files
        File reference_file
        String trimming_length
    }

    command {
        python /image_software/pipeline-container/src/encode_map.py \
        ~{reference_file} \
        ~{trimming_length} \
        ~{sep=' ' fastq_files}
    }

    output {
        Array[File] sai_files = glob('*.sai')
        Array[File] unmapped_files = glob('*.gz')
        File mapping_log = glob('mapping.log')[0]
        File mapping_results = glob('mapping.json')[0]
    }

    runtime {
        docker: 'quay.io/encode-dcc/mapping:v1.0'
        cpu: '2'
        memory: '4.1 GB'
        disks: 'local-disk 5 HDD'
    }
}


task post_processing {
    input {

        Array[File] initial_fastqs
        File reference_file
        Array[File] sai_files
        String trimming_length
        Array[File] unmapped_fastqs

    }
    command {

        python /image_software/pipeline-container/src/encode_post_map.py \
         ~{trimming_length} \
         ~{reference_file} \
         ~{sep=' ' unmapped_fastqs} \
         ~{sep=' ' sai_files} \
         ~{sep=' ' initial_fastqs}
    }

    output {
        File unfiltered_bam = glob('*.raw.srt.bam')[0]
        File unfiltered_flagstats = glob('*.raw.srt.bam.flagstat.qc')[0]
        File post_mapping_log = glob('post_mapping.log')[0]
        File post_mapping_results = glob('post_mapping.json')[0]
    }

    runtime {
        docker: 'quay.io/encode-dcc/post_mapping:v1.0'
        cpu: '2'
        memory: '4.1 GB'
        disks: 'local-disk 5 HDD'
    }
}


task filter_qc {
    input {
        File bam_file
        Array[File] fastq_files
    }


    command {

        python /image_software/pipeline-container/src/filter_qc.py \
         ~{bam_file} \
         ~{sep=' ' fastq_files}
    }

    output {
        File dup_file_qc = glob('*.dup.qc')[0]
        File filtered_bam = glob('*final.bam')[0]
        File filtered_bam_bai = glob('*final.bam.bai')[0]
        File filtered_map_stats = glob('*final.flagstat.qc')[0]
        File pbc_file_qc = glob('*.pbc.qc')[0]
        File filter_qc_log = glob('filter_qc.log')[0]
        File filter_qc_results = glob('filter_qc.json')[0]
    }

    runtime {
        docker: 'quay.io/encode-dcc/filter:v1.0'
        cpu: '2'
        memory: '4.1 GB'
        disks: 'local-disk 5 HDD'
    }
}


task xcor {
    input {
        File bam_file
        Array[File] fastq_files
    }

    command {

        python /image_software/pipeline-container/src/xcor.py \
         ~{bam_file} \
         ~{sep=' ' fastq_files}
    }

    output {
        File cc_file = glob('*.cc.qc')[0]
        File cc_plot = glob('*.cc.plot.pdf')[0]
        Array[File] tag_align = glob('*tagAlign.gz')
        File xcor_log = glob('xcor.log')[0]
        File xcor_results = glob('xcor.json')[0]
    }

    runtime {
        docker: 'quay.io/encode-dcc/xcor:v1.0'
        cpu: '2'
        memory: '4.1 GB'
        disks: 'local-disk 5 HDD'
    }
}


task validate_and_gather_the_output {
    input {
        File unfiltered_bam
        File filtered_bam
        File unfiltered_flagstat
        File filtered_flagstat
        File dup_qc
        File pbc_qc
        File mapping_log
        File post_mapping_log
        File filter_qc_log
        File xcor_log
        File mapping_results
        File post_mapping_results
        File filter_qc_results
        File xcor_results
        File cc
        File cc_pdf
        Array[File] tag_align

        Array[File] compare_against_files
    }

    command <<<
        mkdir ./output
        cp ~{unfiltered_bam} ./output
        cp ~{filtered_bam} ./output
        cp ~{unfiltered_flagstat} ./output
        cp ~{filtered_flagstat} ./output
        cp ~{dup_qc} ./output
        cp ~{pbc_qc} ./output
        cp ~{mapping_log} ./output
        cp ~{post_mapping_log} ./output
        cp ~{filter_qc_log} ./output
        cp ~{xcor_log} ./output
        cp ~{mapping_results} ./output
        cp ~{post_mapping_results} ./output
        cp ~{filter_qc_results} ./output
        cp ~{xcor_results} ./output
        cp ~{cc} ./output
        cp ~{cc_pdf} ./output
        cp ~{sep=' ' tag_align} ./output

        mkdir ./ref
        cp ~{compare_against_files[0]} ./ref
        cp ~{compare_against_files[1]} ./ref
        cp ~{compare_against_files[2]} ./ref
        cp ~{compare_against_files[3]} ./ref
        cp ~{compare_against_files[4]} ./ref

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

# WORKFLOW DEFINITION

workflow encode_mapping_workflow {
    input {

        String trimming_parameter
        Array[File] fastqs
        File reference
        Array[File] compare_against_files
    }
    call mapping  {
        input: fastq_files=fastqs,
          reference_file=reference,
          trimming_length=trimming_parameter
    }

    call post_processing  {
        input: initial_fastqs=fastqs,
          reference_file=reference,
          sai_files=mapping.sai_files,
          trimming_length=trimming_parameter,
          unmapped_fastqs=mapping.unmapped_files
    }

    call filter_qc  {
        input: bam_file=post_processing.unfiltered_bam,
          fastq_files=fastqs
    }


    call xcor  {
        input: bam_file=filter_qc.filtered_bam,
          fastq_files=fastqs
    }

    call validate_and_gather_the_output {
        input: cc = xcor.cc_file,
          cc_pdf = xcor.cc_plot,
          dup_qc = filter_qc.dup_file_qc,
          filter_qc_log = filter_qc.filter_qc_log,
          filter_qc_results = filter_qc.filter_qc_results,
          filtered_bam = filter_qc.filtered_bam,
          filtered_flagstat = filter_qc.filtered_map_stats,
          mapping_log = mapping.mapping_log,
          mapping_results = mapping.mapping_results,
          pbc_qc = filter_qc.pbc_file_qc,
          post_mapping_log = post_processing.post_mapping_log,
          post_mapping_results = post_processing.post_mapping_results,
          tag_align = xcor.tag_align,
          unfiltered_bam = post_processing.unfiltered_bam,
          unfiltered_flagstat = post_processing.unfiltered_flagstats,
          xcor_log = xcor.xcor_log,
          xcor_results = xcor.xcor_results,
        compare_against_files = compare_against_files
    }
    output {
        String result = validate_and_gather_the_output.validate_success
    }
}
