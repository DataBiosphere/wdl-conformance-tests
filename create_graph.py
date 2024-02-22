#!/usr/bin/env python3
# PYTHON_ARGCOMPLETE_OK
"""
Graph performance testing results.

Either takes a formatted input CSV file with -f from run_performance.py or runs performance testing itself.

By default, it graphs boxplots with a new matplotlib window per 30 tests. Graphtype can be changed with --graph-type
and number of tests per window can be changed with --display-num or --display-all. Runners to display can be altered
with --ignore-runner.

Specifying an input conformance file (ex: conformance.yaml) will allow displaying only certain tests with options -n,
-t, and --id.

Writing the graph to a PNG file works by specifying --output [filename.png] and the image dimensions can be specified
with --dimensions x,y in inches.
"""

import argparse
import os.path
import sys
import uuid
from collections import defaultdict
from typing import List, Optional, Dict, Any

import argcomplete
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
from ruamel import yaml

from lib import get_specific_tests
from run_performance import call_and_write_csv
from run import add_options

default_color_list = plt.rcParams['axes.prop_cycle'].by_key()['color']
colors = {
    "miniwdl": default_color_list[0],
    "cromwell": default_color_list[1],
    "toil-wdl-runner": default_color_list[2]
}

graph_order = ["miniwdl", "toil-wdl-runner", "cromwell"]


def create_bar_graph(all_runtimes: Dict[str, Dict[str, Any]], unique_tests_subset: List[str],
                     include_runners: List[str], iteration: int, precision: int = 0, label: bool = True) -> None:
    """
    Draw the bar graph with error bars representing standard deviation using matplotlib
    :param all_runtimes: all runtimes, each list of runtimes is indexed by all_runtimes[test_id][runner].
    Must be in order
    :param unique_tests_subset: list of test ID names specific to this graph call
    :param include_runners: runners in include in a list of strings
    :param iteration: iteration number
    :param precision: precision for the average runtimes
    :param label: show extra label information on the graph. In this graph, this is the average runtime of each test.
    """
    total_width = 0.9
    number_of_runners = len(include_runners)
    bar_width = total_width / number_of_runners

    fig, ax = plt.subplots()
    # # add some text for labels, title and axes ticks
    ax.set_ylabel('Time in Seconds')
    ax.set_title('WDL Test Runtimes')
    ax.set_xlabel('WDL Test ID')

    single_width = 1

    output_order = sorted(include_runners, key=lambda x: graph_order.index(x))

    def autolabel(rects):
        """
        Attach a text label above each bar displaying its height
        """
        for rect in rects:
            height = rect.get_height()
            height_text = f"{height:.{precision}f}" if height != 0.0 else ""
            ax.text(rect.get_x() + rect.get_width() / 2., 1.05 * height,
                    height_text,
                    ha='center', va='bottom', fontsize='x-small')

    x = 0
    for test_id, runner_runtimes in all_runtimes.items():
        # store the runner name mapped to the data so it can be graphed in a manual order
        runner_name_to_graph_data = {}
        for runner_idx, (runner_name, runtimes) in enumerate(runner_runtimes.items()):
            if len(runtimes) != 0:
                std = np.std(runtimes)
                avg = np.average(runtimes)
            else:
                std = 0
                avg = 0
            width = bar_width * single_width
            color = colors[runner_name]
            runner_name_to_graph_data[runner_name] = {"avg": avg, "width": width, "color": color, "std": std}
        for runner_idx, runner_name in enumerate(output_order):
            x_offset = (runner_idx - number_of_runners / 2) * bar_width + bar_width / 2
            x_pos = x + x_offset
            graph_data = runner_name_to_graph_data[runner_name]
            avg = graph_data["avg"]
            width = graph_data["width"]
            color = graph_data["color"]
            std = graph_data["std"]
            bar = ax.bar(x_pos, avg, width=width, color=color)
            ax.errorbar(x_pos, avg, yerr=std/2, fmt=",-r", ecolor="red")
            if label:
                autolabel(bar)
        x += 1

    # get all runners in runtimes to create a legend
    legend_patch_list = []
    for test_id, runner_runtimes in all_runtimes.items():
        for runner_idx, runner_name in enumerate(runner_runtimes.keys()):
            color = colors[runner_name]
            legend_patch_list.append(mpatches.Patch(color=color, label=runner_name))
        break
    ax.legend(handles=legend_patch_list)
    x_labels = unique_tests_subset
    plt.xticks(range(len(x_labels)), x_labels)
    plt.setp(ax.get_xticklabels(), rotation=45, horizontalalignment='right', fontsize='x-small')
    plt.tight_layout()
    plt.figure(iteration)


def create_box_graph(all_runtimes: Dict[str, Dict[str, Any]], unique_tests_subset: List[str],
                     include_runners: List[str], iteration: int, precision: int = 0, label: bool = True) -> None:
    """
    Draw the boxplot graph with matplotlib
    :param all_runtimes: all runtimes, each list of runtimes is indexed by all_runtimes[test_id][runner].
        Must be in order
    :param unique_tests_subset: list of test ID names specific to this graph call
    :param include_runners: runners in include in a list of strings
    :param iteration: iteration number
    :param precision: precision for the median labels
    :param label: whether to draw labels as well. In this graph, the labels are the medians of each entry
    """
    fig, ax = plt.subplots()
    ax.set_ylabel('Time in Seconds')
    ax.set_title('WDL Test Runtimes')
    ax.set_xlabel('WDL Test ID')
    x = 0
    test_ids = unique_tests_subset
    total_width = 0.9
    number_of_runners = len(include_runners)
    box_width = total_width / number_of_runners

    output_order = sorted(include_runners, key=lambda x: graph_order.index(x))

    def autolabel(box_obj):
        """
        Attach a label above the median line of each box displaying its height
        """
        _, y = box_obj['medians'][0].get_xydata()[0]
        # add some labels at the medians of the boxplots with the corresponding times
        if not np.isnan(y) and not y == 0:
            annot = ax.annotate("a", xy=(x_pos, y), xytext=(x_pos, y))
            annot.set_visible(False)
            ax.text(x_pos, y, f"{y:.{precision}f}",
                    horizontalalignment='center', verticalalignment='baseline', size='x-small')

    def autocolor(box_obj, runner_color):
        """
        Color the boxes, fliers, medians, means, whiskers, and caps of a boxplot to the corresponding color
        according to the `colors` object in the global scope
        """
        for item in ['boxes', 'fliers', 'medians', 'means']:
            for sub_item in box_obj[item]:
                plt.setp(sub_item, color=runner_color)
        for item in ['whiskers', 'caps']:
            for sub_items in zip(box_obj[item][::2], box_obj[item][1::2]):
                plt.setp(sub_items, color=runner_color)

    for test_id, runner_runtimes in all_runtimes.items():
        # store the runner name mapped to the data so it can be graphed in a manual order
        runner_name_to_graph_data = {}
        for runner_idx, (runner_name, runtimes) in enumerate(runner_runtimes.items()):
            color = colors[runner_name]
            runner_name_to_graph_data[runner_name] = {"runtimes": runtimes, "notch": 0, "sym": "", "widths": box_width,
                                                      "color": color}
        for runner_idx, runner_name in enumerate(output_order):
            x_offset = (runner_idx - number_of_runners / 2) * box_width + box_width / 2
            x_pos = x + x_offset
            graph_data = runner_name_to_graph_data[runner_name]
            runtimes = graph_data["runtimes"]
            notch = graph_data["notch"]
            sym = graph_data["sym"]
            widths = graph_data["widths"]
            color = graph_data["color"]
            box = ax.boxplot(runtimes, notch, sym, positions=[x_pos], widths=widths)
            if label:
                autolabel(box)
            autocolor(box, color)
        x += 1
    x_labels = test_ids
    # get all runners in runtimes to create a legend
    legend_patch_list = []
    for test_id, runner_runtimes in all_runtimes.items():
        for runner_idx, runner_name in enumerate(runner_runtimes.keys()):
            color = colors[runner_name]
            legend_patch_list.append(mpatches.Patch(color=color, label=runner_name))
        break
    ax.legend(handles=legend_patch_list)
    ax.set_ylim(bottom=0)
    plt.xticks(range(len(x_labels)), x_labels)
    plt.setp(ax.get_xticklabels(), rotation=45, horizontalalignment='right', fontsize='x-small')
    plt.tight_layout()
    plt.figure(iteration)


def generate_graphs_from_range(df: pd.DataFrame, iteration: int, ignored_runners: Optional[List[str]] = None,
                               test_ids_to_graph: Optional[List[str]] = None, graph_type="box",
                               start: Optional[int] = None, end: Optional[int] = None, label: bool = True,
                               precision: int = 0, ignore_skipped: bool = False) -> None:
    """
    Launch a new graph for each range
    :param df: pandas dataframe of csv
    :param iteration: iteration call number
    :param ignored_runners: optional; runner(s) to ignore when graphing
    :param test_ids_to_graph: optional; list of test ids to graph
    :param graph_type: type of graph to create, default box
    :param start: optional, start index in df to graph
    :param end: optional, end index in df to graph
    :param label: optional, whether to graph with labels
    :param precision: number of decimal points to display in the labels
    :param ignore_skipped: ignore skipped tests
    """

    unique_runners = df["Runner"].unique()
    unique_tests = df["Test ID"].unique()
    if test_ids_to_graph is None:
        unique_tests_subset = unique_tests[start:end]
    else:
        unique_tests_subset = test_ids_to_graph
    if ignore_skipped:
        # remove all tests that are skipped from the graph
        parsed_ids = df.query('Runtime == "SKIPPED"')['Test ID'].unique()
        test_ids_to_skip = set()
        for test_id in parsed_ids:
            # in case the csv has other valid runtimes
            # as of now this will not happen, but it may be useful to add this functionality later
            # ex: object is not and will never be supported in miniwdl/toil-wdl-runner, that could be considered skipped
            if len(df.query('`Test ID` == "{test_id}" & Runtime != "SKIPPED"')) == 0:
                test_ids_to_skip.add(test_id)
        unique_tests_subset = [test_id for test_id in unique_tests_subset if test_id not in test_ids_to_skip]
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
        create_box_graph(all_runtimes, unique_tests_subset if test_ids_to_graph is None else test_ids_to_graph,
                         include_runners, iteration + 1, label=label, precision=precision)
    if graph_type == "bar":
        create_bar_graph(all_runtimes, unique_tests_subset if test_ids_to_graph is None else test_ids_to_graph,
                         include_runners, iteration + 1, label=label, precision=precision)


def create_graph(from_file: str, options: argparse.Namespace) -> None:
    data = pd.read_csv(from_file)
    df = pd.DataFrame(data)
    number_of_entries_per_graph = options.display_num if not options.display_all else sys.maxsize
    ignored_runners = None if options.ignore_runner is None else options.ignore_runner.split(",")
    label = not options.no_labels

    unique_tests = df["Test ID"].unique()
    if options.conformance_file is None:
        # if test IDs are specified on command line, graph those only
        test_ids_to_graph = options.id.split(",") if options.id is not None else None

        num_unique_tests_to_display = len(test_ids_to_graph or unique_tests)
        iterations = num_unique_tests_to_display // number_of_entries_per_graph + (
                num_unique_tests_to_display % number_of_entries_per_graph != 0)
        for iteration in range(iterations):
            start, end = (iteration * number_of_entries_per_graph, iteration *
                          number_of_entries_per_graph + number_of_entries_per_graph)
            generate_graphs_from_range(df, iteration, ignored_runners, graph_type=options.graph_type, start=start,
                                       end=end, label=label, precision=options.precision,
                                       test_ids_to_graph=test_ids_to_graph, ignore_skipped=options.ignore_skipped)
    else:
        # graph tests in order according to conformance.yaml
        with open(options.conformance_file, "r") as f:
            data = yaml.safe_load(f)
            # this also allows specifying which tests to graph by tag/id/numbers
            all_test_idx_to_graph = get_specific_tests(conformance_tests=data, tag_argument=options.tags,
                                                       number_argument=options.numbers,
                                                       exclude_number_argument=options.exclude_numbers,
                                                       id_argument=options.id)
            all_test_ids_to_graph = list_of_idx_to_ids(data, all_test_idx_to_graph)
        num_unique_tests_to_display = len(all_test_ids_to_graph)
        iterations = num_unique_tests_to_display // number_of_entries_per_graph + (
                num_unique_tests_to_display % number_of_entries_per_graph != 0)
        for iteration in range(iterations):
            start, end = (iteration * number_of_entries_per_graph, iteration *
                          number_of_entries_per_graph + number_of_entries_per_graph)
            test_ids_to_graph = all_test_ids_to_graph[start:end]
            generate_graphs_from_range(df, iteration, ignored_runners, graph_type=options.graph_type,
                                       test_ids_to_graph=test_ids_to_graph, label=label, precision=options.precision,
                                       ignore_skipped=options.ignore_skipped)
    if options.output is None:
        plt.show()
    else:
        # else write to a file
        img_filename, img_ext = os.path.splitext(options.output)
        figure_numbers = plt.get_fignums()
        width_size = 0
        height_size = 0

        if options.dimensions == "default":
            width_size = num_unique_tests_to_display * 0.25
            height_size = 10
        elif options.dimensions is not None:
            # user supplied custom dimensions
            provided_width, provided_height = map(int, options.dimensions.split(","))
            width_size = provided_width
            height_size = provided_height

        # minimum dimensions so the graph won't be cut off
        min_width = 5
        min_height = 5
        for i in figure_numbers:
            figure = plt.figure(i)
            # default size of figure is too small, so expand
            figure.set_size_inches(max(width_size, min_width), max(height_size, min_height))
            filepath = img_filename + str(i) + img_ext if len(figure_numbers) > 1 else options.output
            plt.savefig(filepath, dpi=plt.figure(i).dpi * 2)


def list_of_idx_to_ids(conformance_tests, list_of_idx):
    return [conformance_tests[idx]["id"] for idx in list_of_idx]


def add_create_graph_args(parser: argparse.ArgumentParser) -> None:
    graph_args = parser.add_argument_group("Arguments for graphing runtimes of WDL tests")
    graph_args.add_argument("--from-file", "-f", dest="file", default=None, help="Specify a csv file to read from.")
    graph_args.add_argument("--display-num", "-d", default=30, type=int, help="Specify the number of tests to "
                                                                              "display per graph.")
    graph_args.add_argument("--display-all", "-a", default=False, action="store_true",
                            help="Display all tests on a single graph. Overrides --display-num.")
    graph_args.add_argument("--ignore-runner", default=None, help="Specify a runner(s) to ignore in the graph output.")
    graph_args.add_argument("--precision", default=0, type=int,
                            help="Specify the precision when outputting float values. "
                                 "Ex: Default=0 will result in 1 for float value "
                                 "1.4...")
    graph_args.add_argument("--no-labels", default=False, action="store_true", help="Specify to not display extra "
                                                                                    "labels on the graph.")
    graph_args.add_argument("--graph-type", default="box")
    graph_args.add_argument("--conformance-file", default=None, const="conformance.yaml", action="store",
                            nargs="?",
                            help="Specify the conformance file to read from. This will specify whether to grab/graph "
                                 "tests by conformance file or by CSV file test IDs only. Specifying this will make "
                                 "the graph accept -n, -t, -id and other related arguments.")
    graph_args.add_argument("--ignore-skipped", default=False, action="store_true", help="Specify whether to not graph "
                                                                                        "skipped conformance tests in "
                                                                                        "the graph.")
    output_args = parser.add_argument_group("Arguments for specifying how to write the graph to a file.")
    output_args.add_argument("--output", "-o", default=None,
                             help="Instead of displaying the graphs, output it into an image. If --display-num is set "
                                  "to a number less than the total amount of tests in the CSV file, then multiple "
                                  "images will be created with the naming scheme: [filename][iteration].["
                                  "fileextension]. For example, if wdl_graph.png is passed, then the first file created"
                                  " will be wdl_graph1.png.")
    # "default" is a marker as the default will be generated at runtime
    output_args.add_argument("--dimensions", const="default", default=None, nargs="?", action="store",
                             help="If custom dimensions are needed, this can be called with input format x_size,y_size "
                                  "in inches. Calling this with no value will size the graph accordingly.")


def main(args):
    parser = argparse.ArgumentParser(description=__doc__)
    add_options(parser)
    add_create_graph_args(parser)
    argcomplete.autocomplete(parser)
    options = parser.parse_args(args)

    if options.file is None:
        new_output_file = f"csv_output_{uuid.uuid4()}.csv"
        options.output = new_output_file
        call_and_write_csv(options)
        create_graph(new_output_file, options)
    else:
        create_graph(options.file, options)


if __name__ == "__main__":
    main(args=sys.argv[1:])
