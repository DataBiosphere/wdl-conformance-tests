import argparse
import sys
import uuid
from collections import defaultdict
from typing import List, Optional

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd

from performance_testing import call_and_write_csv, add_performance_testing_args
from run import add_options


def create_bar_graph(all_runtimes, unique_tests_subset, include_runners, iteration, precision=1):
    test_ids = unique_tests_subset
    total_width = 0.3
    number_of_runners = len(include_runners)
    bar_width = total_width / number_of_runners

    fig, ax = plt.subplots()
    # # add some text for labels, title and axes ticks
    ax.set_ylabel('Time in Seconds')
    ax.set_title('WDL Test Runtimes')
    ax.set_xlabel('WDL Test ID')

    # List containing handles for the drawn bars, used for the legend
    bars = []
    single_width = 1
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']

    def autolabel(rects):
        """
        Attach a text label above each bar displaying its height
        """
        for rect in rects:
            height = rect.get_height()
            height_text = f"{height:.{precision}f}" if height != 0.0 else ""
            ax.text(rect.get_x() + rect.get_width() / 2., 1.05 * height,
                    height_text,
                    ha='center', va='bottom')

    x = 0
    for test_id, runner_runtimes in all_runtimes.items():
        bar = None
        for runner_idx, (runner_name, runtimes) in enumerate(runner_runtimes.items()):
            x_offset = (runner_idx - number_of_runners / 2) * bar_width + bar_width / 2
            std = np.std(runtimes)
            avg = np.average(runtimes)
            x_pos = x + x_offset
            bar = ax.bar(x_pos, avg, width=bar_width * single_width, color=colors[runner_idx % len(colors)])
            ax.errorbar(x_pos, avg, yerr=std, fmt=",-r", ecolor="red")
            autolabel(bar)
        if bar is not None:
            bars.append(bar[0])
        x += 1
    ax.legend(bars, include_runners)
    x_labels = unique_tests_subset
    plt.xticks(range(len(x_labels)), x_labels, rotation=45, ha='right')
    plt.subplots_adjust(bottom=0.25)
    plt.figure(iteration)


def create_box_graph(all_runtimes, unique_tests_subset, include_runners, iteration):
    """
    Draw the boxplot graph with matplotlib
    :param all_runtimes: all runtimes, each list of runtimes is indexed by all_runtimes[test_id][runner].
    Must be in order
    :param unique_tests_subset: list of test ID names specific to this graph call
    :param include_runners: runners in include in a list of strings
    :param iteration: iteration number
    """
    fig, ax = plt.subplots()
    ax.set_ylabel('Time in Seconds')
    ax.set_title('WDL Test Runtimes')
    ax.set_xlabel('WDL Test ID')
    x = 0
    test_ids = unique_tests_subset
    total_width = 0.3
    number_of_runners = len(include_runners)
    box_width = total_width / number_of_runners
    colors = plt.rcParams['axes.prop_cycle'].by_key()['color']
    for test_id, runner_runtimes in all_runtimes.items():
        for runner_idx, (runner_name, runtimes) in enumerate(runner_runtimes.items()):
            color = colors[runner_idx % len(colors)]
            x_offset = (runner_idx - number_of_runners / 2) * box_width + box_width / 2
            x_pos = x + x_offset
            box = ax.boxplot(runtimes, 0, positions=[x_pos], widths=box_width)
            for item in ['boxes', 'fliers', 'medians', 'means']:
                for sub_item in box[item]:
                    plt.setp(sub_item, color=color)
            for item in ['whiskers', 'caps']:
                for sub_items in zip(box[item][::2], box[item][1::2]):
                    plt.setp(sub_items, color=color)
        x += 1
    x_labels = test_ids
    # get labels
    legend_patch_list = []
    for test_id, runner_runtimes in all_runtimes.items():
        for runner_idx, runner_name in enumerate(runner_runtimes.keys()):
            color = colors[runner_idx % len(colors)]
            legend_patch_list.append(mpatches.Patch(color=color, label=runner_name))
        break
    ax.legend(handles=legend_patch_list)
    plt.xticks(range(len(x_labels)), x_labels, rotation=45, ha='right')
    plt.figure(iteration)


def generate_graphs_from_range(df: pd.DataFrame, start: int, end: int, iteration: int,
                               ignored_runners: Optional[List[str]] = None,
                               precision: int = 1, graph_type="box") -> None:
    """
    Launch a new graph for each range
    """

    unique_runners = df["Runner"].unique()
    unique_tests = df["Test ID"].unique()
    unique_tests_subset = unique_tests[start:end]
    all_runtimes = defaultdict(lambda: defaultdict(list))
    for test_idx, test_id in enumerate(unique_tests_subset):
        for runner_idx, runner in enumerate(unique_runners):
            if runner in (ignored_runners or []):
                continue
            # get rows with same Runner and testID
            relevant_rows = df.loc[(df['Test ID'] == test_id) & (df["Runner"] == runner)]
            runtimes = relevant_rows['Runtime'].tolist()
            for runtimes_idx, time in enumerate(runtimes):
                try:
                    runtimes[runtimes_idx] = float(time)
                except ValueError:
                    # the value is SKIPPED or FAILED, so set to 0 to indicate failure to run
                    runtimes[runtimes_idx] = 0
            all_runtimes[test_id][runner] = runtimes
    include_runners = unique_runners.tolist()
    for runner_to_ignore in (ignored_runners or []):
        include_runners.remove(runner_to_ignore)
    if graph_type == "box":
        create_box_graph(all_runtimes, unique_tests_subset.tolist(), include_runners, iteration + 1)
    if graph_type == "bar":
        create_bar_graph(all_runtimes, unique_tests_subset.tolist(), include_runners, iteration + 1)


def create_graph(from_file: str, options: argparse.Namespace) -> None:
    data = pd.read_csv(from_file)
    df = pd.DataFrame(data)
    display_num = options.display_num
    number_of_entries_per_graph = display_num
    ignored_runners = None if options.ignore_runner is None else options.ignore_runner.split(",")

    unique_tests = df["Test ID"].unique()
    num_unique_tests = len(unique_tests)
    iterations = num_unique_tests // number_of_entries_per_graph + (
            num_unique_tests % number_of_entries_per_graph != 0)
    for iteration in range(iterations):
        start, end = iteration * number_of_entries_per_graph, iteration * number_of_entries_per_graph + number_of_entries_per_graph
        generate_graphs_from_range(df, start, end, iteration, ignored_runners, graph_type=options.graph_type)
    plt.show()


def add_create_graph_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--from-file", "-f", dest="file", default=None, help="Specify a csv file to read from.")
    parser.add_argument("--display-num", "-d", default=30, type=int, help="Specify the number of tests to "
                                                                          "display per graph.")
    parser.add_argument("--ignore-runner", default=None, help="Specify a runner(s) to ignore in the graph output.")
    parser.add_argument("--precision", default=1, type=int, help="Specify the precision when outputting float values. "
                                                                 "Ex: Default=1 will result in 0.4 for float value "
                                                                 "0.4...")
    parser.add_argument("--graph-type", default="box")


def main(args):
    parser = argparse.ArgumentParser()
    add_options(parser)
    add_performance_testing_args(parser)
    add_create_graph_args(parser)
    options = parser.parse_args(args)

    if options.file is None:
        new_output_file = f"csv_output_{uuid.uuid4()}.csv"
        options.output = new_output_file
        print("running")
        call_and_write_csv(options)
        print("creating graph")
        create_graph(new_output_file, options)
    else:
        create_graph(options.file, options)


if __name__ == "__main__":
    main(args=sys.argv[1:])
