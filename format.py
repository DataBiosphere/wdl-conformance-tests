#!/usr/bin/env python3
"""
format.py: sort the tests in conformance.yaml into conformance_sorted.yaml,
and format them consistently.
"""
import ruamel.yaml


def ruamel_list(*lst):
    output = ruamel.yaml.CommentedSeq(lst)
    output.fa.set_flow_style()
    return output

def sort_order(e):
    # priority order, first to last
    order = ["description", "tags", "versions", "inputs", "outputs", "wdl", "json", "type", "value"]
    try:
        i = order.index(e)
    except ValueError:
        i = 0
    return i

def sort_order_versions(e):
    order = ["draft-2", "1.0", "1.1"]
    try:
        i = order.index(e)
    except ValueError:
        i = 0
    return i

def yaml_sort(d):
    if isinstance(d, dict):
        result = ruamel.yaml.CommentedMap()
        for k in sorted(d.keys(), key=sort_order):
            if k == 'versions':
                result[k] = yaml_sort(ruamel_list(sorted(d[k], key=sort_order_versions)))
            else:
                result[k] = yaml_sort(d[k])
        return result
    if isinstance(d, list):
        for i, item in enumerate(d):
            d[i] = yaml_sort(item)
    return d


def main():
    yaml = ruamel.yaml.YAML()
    with open("conformance.yaml", "rb") as f:
        output = yaml.load(f)
    with open("conformance_sorted.yaml", "wb") as new_f:
        yaml.dump(yaml_sort(output), new_f)


if __name__ == "__main__":
    main()
