from typing import Optional

import jaro


def compute_similarity(name1: Optional[str], name2: Optional[str]) -> float:
    """
    Compute author name similarity using Jaro-Winkler metric.

    Handles common name variations:
    - Case differences: "John Doe" vs "john doe"
    - Extra whitespace
    - Name order inversion: "John Doe" vs "Doe John"
    - Reversed strings

    Args:
        name1: First author name
        name2: Second author name

    Returns:
        Similarity score from 0.0 to 1.0.
        Score > 0.9 is typically considered same person.
    """
    if not name1 or not name2:
        return 0.0

    inverted1 = 0.0
    inverted2 = 0.0
    inverted3 = 0.0

    inverted_name1 = name1
    inverted_name2 = name2

    # Invert name order if space present
    if " " in name1:
        inverted_name1 = _invert_name(name1)

    if " " in name2:
        inverted_name2 = _invert_name(name2)

    # Try inverted comparisons
    if " " in name1 or " " in name2:
        inverted1 = jaro.jaro_winkler_metric(
            inverted_name1, name2.replace(" ", "").lower()
        )
        inverted2 = jaro.jaro_winkler_metric(
            name1.replace(" ", "").lower(), inverted_name2
        )
        inverted3 = jaro.jaro_winkler_metric(inverted_name1, inverted_name2)

    # Remove space and convert to lowercase
    n1 = name1.replace(" ", "").lower()
    n2 = name2.replace(" ", "").lower()

    # Forward comparison
    forward = jaro.jaro_winkler_metric(n1, n2)

    # Backward (reverse both strings)
    backward = jaro.jaro_winkler_metric(n1[::-1], n2[::-1])

    # Return maximum similarity
    return max(forward, backward, inverted1, inverted2, inverted3)


def _invert_name(name: str) -> str:
    """Invert first/last name order."""
    parts = name.split(" ")
    if len(parts) >= 2:
        return (parts[1] + parts[0]).lower()
    return name.lower()
