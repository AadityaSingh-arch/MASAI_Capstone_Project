"""
Section 3 — AI Quick-Add mock parser.

Deterministic, rule-based, zero-network, zero-API-key parser that simulates
what an LLM would return for a "turn this sentence into a task" prompt.
Given the exact algorithm in the brief, any two correct implementations must
produce identical output for the same input.

Also builds the role-based "prompt" (system + user messages) that would be
sent to a real LLM if the optional USE_REAL_LLM path were enabled — the mock
consumes only the user-role text, but the message list is constructed the
same way regardless of which backend answers it.
"""
import re
from typing import Optional, TypedDict


class ParsedTask(TypedDict):
    title: str
    priority: str
    due_date_hint: Optional[str]


# Step (b): priority keyword groups, checked in this exact order.
HIGH_PRIORITY_KEYWORDS = ["urgent", "asap"]
LOW_PRIORITY_KEYWORDS = ["whenever", "low priority"]

# Step (c): date-phrase keywords, checked in this exact order.
SIMPLE_DATE_KEYWORDS = ["today", "tomorrow", "next week"]
NEXT_WEEKDAY_PHRASES = [
    "next monday",
    "next tuesday",
    "next wednesday",
    "next thursday",
    "next friday",
    "next saturday",
    "next sunday",
]
BARE_WEEKDAYS = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

UNTITLED_PLACEHOLDER = "Untitled task"


def build_prompt_messages(description: str) -> list:
    """Role-based message structure (Section 3, Task 2). Used regardless of
    whether the mock (default) or a real LLM (optional, feature-flagged)
    produces the actual parse."""
    system_message = {
        "role": "system",
        "content": (
            "You are a task-parsing assistant for TaskFlow. Given a free-text "
            "task description, extract: (1) a priority of exactly 'low', "
            "'medium', or 'high' based on urgency cues in the text, (2) a "
            "due-date hint phrase if one is present in the text, and (3) a "
            "cleaned-up title with those cues removed. Respond with only the "
            "extracted fields."
        ),
    }
    user_message = {"role": "user", "content": description}
    return [system_message, user_message]


def _find_all_occurrences(haystack_lower: str, needle: str) -> list:
    """Return start indices of every non-overlapping occurrence of `needle`
    in `haystack_lower` (both already lower-cased)."""
    indices = []
    start = 0
    while True:
        idx = haystack_lower.find(needle, start)
        if idx == -1:
            break
        indices.append(idx)
        start = idx + len(needle)
    return indices


def _strip_spans(original: str, lower: str, needles: list) -> str:
    """Remove every occurrence of every needle (matched case-insensitively
    via the lower-cased copy, but the removal happens on `original` so
    casing elsewhere in the title is preserved)."""
    spans = []
    for needle in needles:
        for idx in _find_all_occurrences(lower, needle):
            spans.append((idx, idx + len(needle)))

    if not spans:
        return original

    # Remove from right to left so earlier indices stay valid.
    spans.sort(key=lambda s: s[0], reverse=True)
    result = original
    for start, end in spans:
        result = result[:start] + result[end:]
    return result


def mock_parse_task(description: str) -> ParsedTask:
    """Deterministic rule-based parser implementing the exact algorithm from
    the brief (Section 3, Task 3, steps a-d)."""
    # (a) lower-cased working copy for matching; original stays untouched
    # for the title step.
    original = description
    lower = description.lower()

    # (b) priority — check group (i) then group (ii), first match wins.
    matched_priority_keywords = []
    priority = "medium"
    high_hit = any(kw in lower for kw in HIGH_PRIORITY_KEYWORDS)
    low_hit = any(kw in lower for kw in LOW_PRIORITY_KEYWORDS)

    if high_hit:
        priority = "high"
    elif low_hit:
        priority = "low"
    else:
        priority = "medium"

    # Title-stripping note: strip every occurrence of every group (i)/(ii)
    # keyword found anywhere in the text, not just the deciding one.
    for kw in HIGH_PRIORITY_KEYWORDS + LOW_PRIORITY_KEYWORDS:
        if kw in lower:
            matched_priority_keywords.append(kw)

    # (c) due-date hint — simple keywords, then "next <weekday>" phrases
    # (whole two-word span), then bare weekdays. First match wins.
    due_date_hint = None
    matched_date_phrase = None

    for kw in SIMPLE_DATE_KEYWORDS:
        if kw in lower:
            due_date_hint = kw
            matched_date_phrase = kw
            break

    if due_date_hint is None:
        for phrase in NEXT_WEEKDAY_PHRASES:
            if phrase in lower:
                due_date_hint = phrase
                matched_date_phrase = phrase
                break

    if due_date_hint is None:
        for day in BARE_WEEKDAYS:
            if day in lower:
                due_date_hint = day
                matched_date_phrase = day
                break

    # (d) title — strip matched priority keyword spans + the matched date
    # phrase (if any) from the ORIGINAL-cased description, then trim.
    strip_needles = list(matched_priority_keywords)
    if matched_date_phrase:
        strip_needles.append(matched_date_phrase)

    title = _strip_spans(original, lower, strip_needles)
    # Collapse leftover double spaces created by removing an inner word,
    # then trim. (Collapsing interior whitespace is a light cleanup, not a
    # change to which spans were removed.)
    title = re.sub(r"[ \t]{2,}", " ", title).strip()

    if not title:
        title = UNTITLED_PLACEHOLDER

    return {"title": title, "priority": priority, "due_date_hint": due_date_hint}
