"""
Section 2, Task 5 — benchmark the real algorithms engine (algorithms.py)
against synthetic task data shaped like the app's real fields, at three
sizes, using the comparison-counting wrapper functions.

Run:
    python3 benchmark.py

Writes raw counted numbers to benchmark_results.txt as well as printing
them, so the README can quote real numbers rather than a verbal claim.
"""
import copy
import random

from backend.algorithms import (
    insertion_sort_count,
    binary_search_count,
    linear_search_count,
)
from seed import generate_synthetic_tasks

SIZES = [10, 500, 3000]


def run_benchmark():
    lines = []
    lines.append("TaskFlow Section 2 benchmark — comparison counts\n")
    lines.append(f"{'size':>6} | {'insertion_sort (title)':>24} | {'binary_search (title)':>22} | {'linear_search (title)':>22}\n")
    lines.append("-" * 90 + "\n")

    for size in SIZES:
        random.seed(42)  # reproducible synthetic data per run
        base_records = generate_synthetic_tasks(size)

        # --- insertion sort comparisons, sorting by title ---
        records_for_sort = copy.deepcopy(base_records)
        sort_comparisons = insertion_sort_count(records_for_sort, "title")

        # records_for_sort is now sorted by title; pick a real target that exists.
        target_index = size // 2
        target_title = records_for_sort[target_index]["title"]

        # --- binary search comparisons on the now-sorted list ---
        binary_result = binary_search_count(records_for_sort, target_title, "title")

        # --- linear search comparisons on an UNsorted copy (fresh order) ---
        unsorted_records = copy.deepcopy(base_records)
        linear_result = linear_search_count(unsorted_records, target_title, "title")

        lines.append(
            f"{size:>6} | {sort_comparisons:>24} | "
            f"{binary_result['comparison_count']:>22} | {linear_result['comparison_count']:>22}\n"
        )

    output = "".join(lines)
    print(output)
    with open("benchmark_results.txt", "w") as f:
        f.write(output)
    print("Raw results written to benchmark_results.txt")


if __name__ == "__main__":
    run_benchmark()
