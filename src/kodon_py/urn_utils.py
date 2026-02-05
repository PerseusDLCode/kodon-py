"""Utilities for parsing and decomposing CTS URNs.

CTS URN structure:
    Document:   urn:cts:greekLit:tlg0001.tlg001.test-grc1
    Textpart:   urn:cts:greekLit:tlg0001.tlg001.test-grc1:1.2.3
    Element:    urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@<p>[0]
    Token:      urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@word[1]
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# Stephanus notation: letters a-e map to integers 1-5
# This is called `STEPHANUS_MAP` but it works for Bekker
# pages and sub-lines in, e.g., tragedy as well.
STEPHANUS_MAP = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}


@dataclass
class ParsedURN:
    """Represents a fully decomposed CTS URN."""

    # Full URN string
    urn: str

    # Namespace components
    collection: Optional[str] = None  # e.g., "greekLit"

    # Work component parts
    work_component: Optional[str] = None  # e.g., "tlg0001.tlg001.test-grc1"
    text_group: Optional[str] = None  # e.g., "tlg0001"
    work: Optional[str] = None  # e.g., "tlg001"
    version: Optional[str] = None  # e.g., "test-grc1"
    exemplar: Optional[str] = None  # Optional 4th work component

    # Passage component
    passage_component: Optional[str] = None  # e.g., "1.2.3" or "1.1-1.2"

    # Parsed citations
    citations: list[str] = field(
        default_factory=list
    )  # e.g., ["1.2.3"] or ["1.1", "1.2"]
    integer_citations: list[list[int]] = field(
        default_factory=list
    )  # e.g., [[1,2,3]] or [[1,1], [1,2]]

    # Subreference fields (for Element and Token URNs)
    token_strings: list[str] = field(default_factory=list)  # e.g., ["Rage", "Achilles"]
    token_indexes: list[int] = field(default_factory=list)  # e.g., [1, 1]


def parse_alphanumeric(citation_part: str) -> list[int]:
    """Parse a single citation part that may contain Stephanus notation.

    Examples:
        "327a" -> [327, 1]
        "1" -> [1]
        "2" -> [2]

    Args:
        citation_part: A single part of a citation (e.g., "327a" or "1")

    Returns:
        List of integers representing the parsed citation part
    """
    # Check if the last character is a letter
    if citation_part and citation_part[-1].lower() in STEPHANUS_MAP:
        letter = citation_part[-1].lower()
        number_part = citation_part[:-1]
        if number_part.isdigit():
            return [int(number_part), STEPHANUS_MAP[letter]]

    # Plain integer
    if citation_part.isdigit():
        return [int(citation_part)]

    # Try to handle mixed alphanumeric by keeping as-is
    # This shouldn't normally happen with valid CTS citations
    return []


def parse_single_citation(citation: str) -> list[int]:
    """Parse a single citation string into a list of integers.

    Examples:
        "1.2.3" -> [1, 2, 3]
        "327a" -> [327, 1]

    Args:
        citation: A citation string like "1.2.3" or "327a"

    Returns:
        List of integers
    """
    parts = citation.split(".")
    result = []
    for part in parts:
        parsed = parse_alphanumeric(part)
        result.extend(parsed)
    return result


def parse_passage(passage: str) -> tuple[list[str], list[list[int]]]:
    """Parse a passage component, handling ranges and Stephanus notation.

    Args:
        passage: The passage component, e.g., "1.2.3" or "1.1-1.2" or "327a-327c"

    Returns:
        Tuple of (citations, integer_citations) where:
            - citations is a list of citation strings (1 for single, 2 for range)
            - integer_citations is the parsed integer representation
    """
    if not passage:
        return [], []

    # Check for range (contains "-" that's not part of a negative number)
    # CTS ranges use "-" to separate start and end citations
    if "-" in passage:
        # Split on "-" but be careful about edge cases
        # A range like "1.1-1.2" should split into ["1.1", "1.2"]
        # But "test-grc1" in work component is not a range (that's handled elsewhere)
        parts = passage.split("-")
        if len(parts) == 2:
            start, end = parts
            citations = [start, end]
            integer_citations = [
                parse_single_citation(start),
                parse_single_citation(end),
            ]
            return citations, integer_citations

    # Single citation
    citations = [passage]
    integer_citations = [parse_single_citation(passage)]
    return citations, integer_citations


def parse_work_component(work_str: str) -> tuple[str, str, str, Optional[str]]:
    """Parse the work component of a CTS URN.

    The work component has the form: textgroup.work.version[.exemplar]

    Args:
        work_str: The work component string, e.g., "tlg0001.tlg001.test-grc1"

    Returns:
        Tuple of (text_group, work, version, exemplar)
    """
    parts = work_str.split(".")
    text_group = parts[0] if len(parts) > 0 else ""
    work = parts[1] if len(parts) > 1 else ""
    version = parts[2] if len(parts) > 2 else ""
    exemplar = parts[3] if len(parts) > 3 else None
    return text_group, work, version, exemplar


def extract_subreference(
    passage_with_subref: str,
) -> tuple[str, Optional[str], Optional[int]]:
    """Extract subreference (@-notation) from a passage component.

    Args:
        passage_with_subref: Passage that may contain subreference, e.g., "1.1@Rage[1]"

    Returns:
        Tuple of (passage_without_subref, token_string, token_index)
        If no subreference, returns (original_passage, None, None)
    """
    if "@" not in passage_with_subref:
        return passage_with_subref, None, None

    # Split on @ to get passage and subreference
    parts = passage_with_subref.split("@", 1)
    passage = parts[0]
    subref = parts[1]

    # Parse subreference: could be "word[1]" or "<tagname>[0]"
    # Pattern: token_string[index]
    match = re.match(r"(.+)\[(\d+)\]$", subref)
    if match:
        token_string = match.group(1)
        token_index = int(match.group(2))
        return passage, token_string, token_index

    # Malformed subreference - return as-is
    return passage_with_subref, None, None


def parse_urn(urn: str) -> ParsedURN:
    """Parse a CTS URN into its component parts.

    Supports:
        - Document URNs: urn:cts:greekLit:tlg0001.tlg001.test-grc1
        - Textpart URNs: urn:cts:greekLit:tlg0001.tlg001.test-grc1:1.2.3
        - Element URNs: urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@<p>[0]
        - Token URNs: urn:cts:greekLit:tlg0001.tlg001.test-grc1:1@word[1]
        - Range URNs: urn:cts:greekLit:tlg0001.tlg001.test-grc1:1.1-1.2

    Args:
        urn: The full CTS URN string

    Returns:
        ParsedURN with all components populated
    """
    result = ParsedURN(urn=urn)

    if not urn or not urn.startswith("urn:cts:"):
        return result

    # Remove "urn:cts:" prefix
    remainder = urn[8:]

    # Split into parts by ":"
    parts = remainder.split(":")

    if len(parts) >= 1:
        result.collection = parts[0]

    if len(parts) >= 2:
        result.work_component = parts[1]
        text_group, work, version, exemplar = parse_work_component(parts[1])
        result.text_group = text_group
        result.work = work
        result.version = version
        result.exemplar = exemplar

    if len(parts) >= 3:
        passage_raw = parts[2]

        # Check for range with subreferences (e.g., "1.1@Rage[1]-1.2@Achilles[1]")
        # or simple range (e.g., "1.1-1.2")
        # or single with subreference (e.g., "1@word[1]")

        # First, try to detect if this is a range by looking for "-" between citations
        # A range with subreferences: passage1@token[idx]-passage2@token[idx]

        token_strings = []
        token_indexes = []

        # Check if it's a range (contains "-" not inside brackets)
        # Simple heuristic: split on "-" and check if we get valid citation patterns
        range_parts = passage_raw.split("-")

        if len(range_parts) == 2 and not passage_raw.startswith("-"):
            # Likely a range
            start_raw, end_raw = range_parts

            start_passage, start_token, start_idx = extract_subreference(start_raw)
            end_passage, end_token, end_idx = extract_subreference(end_raw)

            result.passage_component = f"{start_passage}-{end_passage}"
            result.citations = [start_passage, end_passage]
            result.integer_citations = [
                parse_single_citation(start_passage),
                parse_single_citation(end_passage),
            ]

            if start_token is not None:
                token_strings.append(start_token)
                token_indexes.append(start_idx)
            if end_token is not None:
                token_strings.append(end_token)
                token_indexes.append(end_idx)
        else:
            # Single citation (possibly with subreference)
            passage, token_string, token_index = extract_subreference(passage_raw)
            result.passage_component = passage
            result.citations, result.integer_citations = parse_passage(passage)

            if token_string is not None:
                token_strings.append(token_string)
                token_indexes.append(token_index)

        result.token_strings = token_strings
        result.token_indexes = token_indexes

    return result
