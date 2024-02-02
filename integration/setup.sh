#!/bin/bash
dir_path="datasets/"
download_urls=("http://toil-datasets.s3.amazonaws.com/ENCODE_data.zip" "http://toil-datasets.s3.amazonaws.com/wdl_templates.zip" "http://toil-datasets.s3.amazonaws.com/GATK_data.zip")
for download_url in "${download_urls[@]}"
do
  file_basename=$(basename "${download_url}" .zip)
  subdir_path=$dir_path$file_basename
  download_zip_path=$dir_path$(basename "$download_url")
  if [ ! -d "${dir_path}" ]; then
    mkdir "${dir_path}"
  fi
  if [ ! -d "${subdir_path}" ]; then
    curl "${download_url}" -o "${download_zip_path}"
    unzip "${download_zip_path}" -d "${dir_path}"
    rm "$download_zip_path"
  fi
done