"""
Section 2 — Integrated Algorithms Engine.

Hand-rolled insertion sort, binary search, and linear search — plus
comparison-counting wrapper versions used for the benchmark (Task 5).

These are the *only* functions the sort/search endpoints in main.py use.
Never sorted()/list.sort() anywhere in this module or its call sites.
"""
from typing import List, Dict, Any, Optional


# ---------------------------------------------------------------------------
# Task 1: insertion sort
# ---------------------------------------------------------------------------
def insertion_sort(records: List[Dict[str, Any]], key: str) -> None:
    """Sort `records` in place, ascending, by record[key].

    Standard insertion-sort structure: starting from the second element,
    compare against previous elements and shift them right until the
    current element's correct slot is found.
    """
    for i in range(1, len(records)):
        current = records[i]
        current_val = current[key]
        j = i - 1
        while j >= 0 and records[j][key] > current_val:
            records[j + 1] = records[j]
            j -= 1
        records[j + 1] = current


# ---------------------------------------------------------------------------
# Task 2: binary search
# ---------------------------------------------------------------------------
def binary_search(
    sorted_records: List[Dict[str, Any]], target_value: Any, key: str
) -> Optional[int]:
    """Return the index of a record with record[key] == target_value in a
    list already sorted ascending by key, or None if not found."""
    low, high = 0, len(sorted_records) - 1
    while low <= high:
        mid = (low + high) // 2
        mid_val = sorted_records[mid][key]
        if mid_val == target_value:
            return mid
        elif mid_val < target_value:
            low = mid + 1
        else:
            high = mid - 1
    return None


# ---------------------------------------------------------------------------
# Task 3: linear search (baseline)
# ---------------------------------------------------------------------------
def linear_search(
    records: List[Dict[str, Any]], target_value: Any, key: str
) -> Optional[int]:
    """Scan every record in order; return the index of the first match or
    None if the target is absent."""
    for i, record in enumerate(records):
        if record[key] == target_value:
            return i
    return None


# ---------------------------------------------------------------------------
# Task 5: comparison-counting wrapper functions
# ---------------------------------------------------------------------------
def insertion_sort_count(records: List[Dict[str, Any]], key: str) -> int:
    """Same sorting behavior as insertion_sort (mutates records in place),
    but returns only the number of key-comparisons performed."""
    comparisons = 0
    for i in range(1, len(records)):
        current = records[i]
        current_val = current[key]
        j = i - 1
        while j >= 0:
            comparisons += 1
            if records[j][key] > current_val:
                records[j + 1] = records[j]
                j -= 1
            else:
                break
        records[j + 1] = current
    return comparisons


def binary_search_count(
    sorted_records: List[Dict[str, Any]], target_value: Any, key: str
) -> Dict[str, Any]:
    """Same lookup as binary_search but returns {"index": ..., "comparison_count": ...}."""
    comparisons = 0
    low, high = 0, len(sorted_records) - 1
    index = None
    while low <= high:
        mid = (low + high) // 2
        mid_val = sorted_records[mid][key]
        comparisons += 1
        if mid_val == target_value:
            index = mid
            break
        elif mid_val < target_value:
            low = mid + 1
        else:
            high = mid - 1
    return {"index": index, "comparison_count": comparisons}


def linear_search_count(
    records: List[Dict[str, Any]], target_value: Any, key: str
) -> Dict[str, Any]:
    """Same lookup as linear_search but returns {"index": ..., "comparison_count": ...}."""
    comparisons = 0
    index = None
    for i, record in enumerate(records):
        comparisons += 1
        if record[key] == target_value:
            index = i
            break
    return {"index": index, "comparison_count": comparisons}


# ---------------------------------------------------------------------------
# Helper: priority -> comparable rank, used by the /tasks?sort=priority endpoint
# ---------------------------------------------------------------------------
PRIORITY_RANK = {"low": 1, "medium": 2, "high": 3}


def priority_to_rank(priority: str) -> int:
    return PRIORITY_RANK.get(priority, 2)
