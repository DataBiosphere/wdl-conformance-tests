import argparse
import os
import sys
import pandas as pd
import numpy as np
from ruamel import yaml


def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parser = argparse.ArgumentParser()
    parser.add_argument("file1", help="First file")
    parser.add_argument("file2", help="Second file")
    parser.add_argument("--conformance", "-c", default=None, help="Conformance test file. If provided, it will "
                                                                  "preserve the order"
                                                    "according to the conformance file. Default is None.")
    parser.add_argument("--output", "-o", default="csv_output_merged.csv", help="Output path of merged CSV file.")

    options = parser.parse_args(args)

    if not os.path.exists(options.file1):
        raise Exception(f"'{options.file1}' is not a valid file!")
    if not os.path.exists(options.file2):
        raise Exception(f"'{options.file2}' is not a valid file!")

    with open(options.file1, "r") as f:
        data1 = pd.read_csv(f)
    with open(options.file2, "r") as f:
        data2 = pd.read_csv(f)

    df1 = pd.DataFrame(data1)
    df2 = pd.DataFrame(data2)

    unique_tests_1 = df1["Test ID"].unique()
    unique_tests_2 = df2["Test ID"].unique()

    all_runners = ["miniwdl", "toil-wdl-runner", "cromwell"]
    final_df = pd.DataFrame()
    if options.conformance is not None:
        if not os.path.exists(options.conformance):
            raise Exception(f"'{options.conformance}' is not a valid file!")
        with open(options.conformance, "r") as f:
            conformance_data = yaml.safe_load(f)
            test_id_keys = [conformance_test["id"] for conformance_test in conformance_data]
    else:
        test_id_keys = np.unique(np.concatenate((unique_tests_1, unique_tests_2), axis=0)).tolist()
    for test_idx, test_id in enumerate(test_id_keys):
        for runner_idx, runner in enumerate(all_runners):
            # get rows with same Runner and testID
            relevant_rows1 = df1.loc[(df1['Test ID'] == test_id) & (df1["Runner"] == runner)]
            relevant_rows2 = df2.loc[(df2['Test ID'] == test_id) & (df2["Runner"] == runner)]
            final_df = pd.concat([final_df, relevant_rows1, relevant_rows2])
    if options.conformance is None:
        final_df = final_df.sort_index()
    final_df.to_csv(options.output, index=False)


if __name__ == "__main__":
    main()