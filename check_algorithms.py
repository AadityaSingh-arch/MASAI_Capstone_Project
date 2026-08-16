"""
Section 2, Task 7 — automated checks for the algorithms engine.

Plain if/else PASS/FAIL checks (no assert/pytest/unittest). Run:
    python3 check_algorithms.py
"""
from backend.algorithms import (
    insertion_sort,
    binary_search,
    linear_search,
    insertion_sort_count,
    binary_search_count,
    linear_search_count,
)


def check(case_name, result, expected):
    if result == expected:
        print(f"PASS: {case_name}")
    else:
        print(f"FAIL: {case_name} — expected {expected}, got {result}")


def main():
    # --- Case 1: insertion_sort on empty list leaves it empty, no error ---
    empty = []
    try:
        insertion_sort(empty, "key")
        check("insertion_sort empty list", empty, [])
    except Exception as e:
        print(f"FAIL: insertion_sort empty list — expected [], got exception {e}")

    # --- Case 2: insertion_sort on single-element list unchanged ---
    single = [{"key": 5}]
    insertion_sort(single, "key")
    check("insertion_sort single element", single, [{"key": 5}])

    # --- Case 3: binary_search finds first / last / middle of sorted distinct list ---
    sorted_list = [{"key": v} for v in [1, 3, 5, 7, 9, 11, 13]]
    check("binary_search first index", binary_search(sorted_list, 1, "key"), 0)
    check("binary_search last index", binary_search(sorted_list, 13, "key"), 6)
    check("binary_search middle index", binary_search(sorted_list, 7, "key"), 3)

    # --- Case 4: binary_search returns not-found (None) for an absent target ---
    check("binary_search absent value", binary_search(sorted_list, 100, "key"), None)

    # --- Case 5: insertion_sort_count sorts correctly and returns a plain int > 0 ---
    small = [{"key": 3}, {"key": 1}, {"key": 2}]
    count = insertion_sort_count(small, "key")
    sorted_correctly = small == [{"key": 1}, {"key": 2}, {"key": 3}]
    is_positive_int = isinstance(count, int) and count > 0
    check("insertion_sort_count sorts correctly", sorted_correctly, True)
    check("insertion_sort_count returns positive int", is_positive_int, True)

    # --- Case 6: binary_search_count on a sorted list, value present at known index ---
    known_sorted = [{"key": v} for v in [10, 20, 30, 40, 50]]
    result = binary_search_count(known_sorted, 30, "key")
    index_correct = result["index"] == 2
    count_positive_int = isinstance(result["comparison_count"], int) and result["comparison_count"] > 0
    check("binary_search_count index correct", index_correct, True)
    check("binary_search_count comparison_count positive int", count_positive_int, True)

    # --- Case 7: linear_search_count for an absent value: index=not-found, count=len ---
    absent_target_list = [{"key": v} for v in [1, 2, 3, 4]]
    result2 = linear_search_count(absent_target_list, 999, "key")
    check("linear_search_count absent index", result2["index"], None)
    check("linear_search_count absent comparison_count", result2["comparison_count"], len(absent_target_list))


if __name__ == "__main__":
    main()
