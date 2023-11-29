import argparse
import sys
import uuid
from typing import List

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from performance_testing import call_and_write_csv
from run import add_options


def generate_graphs_from_range(df: pd.DataFrame, start: int, end: int, iteration: int, ignored_runners: List[str],
                               precision: int) -> None:
    """
    Launch a new graph for each range
    """

    header = df.columns.tolist()
    runners = header[1:]
    for runner in ignored_runners:
        try:
            runners.remove(runner)
        except ValueError:
            raise Exception("Invalid runner to ignore: %s", runner)
    total_width = 0.3
    number_of_runners = len(runners)
    bar_width = total_width / number_of_runners
    fig, ax = plt.subplots()
    number_of_entries = df.shape[0]

    # # add some text for labels, title and axes ticks
    ax.set_ylabel('Time in Seconds')
    ax.set_title('WDL Test Runtimes')
    ax.set_xlabel('WDL Test ID')

    # List containing handles for the drawn bars, used for the legend
    bars = []
    # Iterate over all data
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

    end = number_of_entries if end > number_of_entries else end
    all_lowest_time = []
    all_highest_time = []
    all_x = []
    all_y = []
    for i, name in enumerate(runners):
        runner_column = df[name]
        x_offset = (i - number_of_runners / 2) * bar_width + bar_width / 2
        bar = None
        for x, time_str in enumerate(runner_column[start:end]):
            lowest_time = None
            highest_time = None
            if time_str.find("-") > 0:
                # if - is in the string, then the errors are included
                # so clean the time string so that it only has the average time, and store the errors elsewhere
                split_time_str = time_str.split("-")
                time_str = split_time_str[0]
                lowest_time = split_time_str[1]
                highest_time = split_time_str[2]
            all_lowest_time.append(lowest_time)
            all_highest_time.append(highest_time)
            try:
                # cast to float as input is string and I think this messes up with height values
                time_value = float(time_str)
            except ValueError:
                # not a valid input, set to 0 to avoid graphing it as a value
                time_value = 0
            x_pos = x + x_offset
            all_x.append(x_pos)
            all_y.append(time_value)
            bar = ax.bar(x_pos, time_value, width=bar_width * single_width, color=colors[i % len(colors)])
            autolabel(bar)
        if bar is not None:
            bars.append(bar[0])
    # calculate and output errors
    errors = [np.array(all_y) - np.array(all_lowest_time), np.array(all_highest_time) - np.array(all_y)]
    plt.errorbar(all_x, all_y, yerr=errors, fmt="o", ecolor="red")
    ax.legend(bars, runners)
    x_labels = df[header[0]].tolist()[start:end]
    plt.xticks(range(len(x_labels)), x_labels, rotation=45, ha='right')
    plt.subplots_adjust(bottom=0.25)
    plt.figure(iteration)


def create_graph(from_file: str, options: argparse.Namespace) -> None:
    data = pd.read_csv(from_file)
    df = pd.DataFrame(data)
    number_of_entries = df.shape[0]
    display_num = options.display_num
    number_of_entries_per_graph = display_num
    ignored_runners = [] if options.ignore_runner is None else options.ignore_runner.split(",")
    iterations = number_of_entries // number_of_entries_per_graph + (number_of_entries % number_of_entries_per_graph != 0)
    precision = options.precision
    for i in range(iterations):
        generate_graphs_from_range(df, i * number_of_entries_per_graph, i * number_of_entries_per_graph +
                                   number_of_entries_per_graph, i+1, ignored_runners, precision)
    plt.show()


def main(args):
    parser = argparse.ArgumentParser()
    add_options(parser)
    parser.add_argument("--from-file", "-f", dest="file", default=None, help="Specify a csv file to read from.")
    parser.add_argument("--display-num", "-d", default=30, type=int, help="Specify the number of tests to "
                                                                          "display per graph.")
    parser.add_argument("--ignore-runner", default=None, help="Specify a runner(s) to ignore in the graph output.")
    parser.add_argument("--precision", default=1, type=int, help="Specify the precision when outputting float values. "
                                                                 "Ex: Default=1 will result in 0.4 for float value "
                                                                 "0.4...")
    options = parser.parse_args(args)

    if options.file is None:
        new_output_file = f"csv_output_{uuid.uuid4()}.csv"
        options.output = new_output_file
        options.all_runners = True
        print("running")
        call_and_write_csv(options)
        print("creating graph")
        create_graph(new_output_file, options)
    else:
        create_graph(options.file, options)


if __name__ == "__main__":
    main(args=sys.argv[1:])
