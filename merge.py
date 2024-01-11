"""
Tool to merge two or more CSV files into one while keeping data sorted by ID
"""

import argparse
import os
import sys
import pandas as pd
import numpy as np
from ruamel import yaml


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", help="Specify files.", nargs="+")
    # parser.add_argument("file1", help="First file")
    # parser.add_argument("file2", help="Second file")
    parser.add_argument("--conformance", "-c", default=None, help="Conformance test file. If provided, it will "
                                                                  "preserve the order"
                                                                  "according to the conformance file. Default is None.")
    parser.add_argument("--output", "-o", default="csv_output_merged.csv", help="Output path of merged CSV file.")

    options = parser.parse_args(args)

    for file in options.file:
        if not os.path.exists(file):
            raise Exception(f"'{file}' doesn't exist!")

    data_list = []
    dataframe_list = []
    unique_test_list = []
    for file in options.file:
        with open(file, "r") as f:
            data = pd.read_csv(f)
            data_list.append(data)
        dataframe = pd.DataFrame(data)
        dataframe_list.append(dataframe)
        unique_test_list.append(dataframe["Test ID"].unique())

    all_runners = ["miniwdl", "toil-wdl-runner", "cromwell"]
    final_df = pd.DataFrame()
    if options.conformance is not None:
        if not os.path.exists(options.conformance):
            raise Exception(f"'{options.conformance}' is not a valid file!")
        with open(options.conformance, "r") as f:
            conformance_data = yaml.safe_load(f)
            test_id_keys = [conformance_test["id"] for conformance_test in conformance_data]
    else:
        all_test_ids = np.concatenate(unique_test_list, axis=0)
        test_id_keys = np.unique(all_test_ids).tolist()
    for test_idx, test_id in enumerate(test_id_keys):
        for runner_idx, runner in enumerate(all_runners):
            # get rows with same Runner and testID
            relevant_row_list = []
            for df in dataframe_list:
                relevant_row_list.append(df.loc[(df["Test ID"] == test_id) & (df["Runner"] == runner)])
            final_df = pd.concat([final_df, *relevant_row_list])
    if options.conformance is None:
        final_df = final_df.sort_index()
    final_df.to_csv(options.output, index=False)


if __name__ == "__main__":
    main()
