import re

# Text filtering constants
MIN_SNIPPET_LENGTH = 10
SNIPPET_MERGE_DISTANCE = 50
SNIPPET_CONTEXT_WINDOW = 100


def clean_text(text: str) -> str:
    """
    Cleans the text by removing code blocks, HTML tags, and excessive whitespace.
    """
    if not text:
        return ""

    # Remove code blocks (```...```)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # Remove HTML tags (basic)
    text = re.sub(r"<[^>]+>", "", text)

    # Remove non-printable characters (keep newlines and tabs)
    text = re.sub(r"[^\x20-\x7E\n\t]", "", text)

    # Collapse excessive whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _find_matches(text: str, text_lower: str, keyword: str) -> list[tuple[int, str]]:
    snippets = []
    if keyword.startswith("r\\"):
        pattern = keyword[1:]  # Remove 'r' prefix
        for match in re.finditer(pattern, text_lower, re.IGNORECASE):
            start = max(0, match.start() - SNIPPET_CONTEXT_WINDOW)
            end = min(len(text), match.end() + SNIPPET_CONTEXT_WINDOW)
            snippet = text[start:end].strip()
            if snippet and len(snippet) > MIN_SNIPPET_LENGTH:
                snippets.append((start, snippet))
    else:
        pos = 0
        while True:
            pos = text_lower.find(keyword.lower(), pos)
            if pos == -1:
                break
            start = max(0, pos - SNIPPET_CONTEXT_WINDOW)
            end = min(len(text), pos + len(keyword) + SNIPPET_CONTEXT_WINDOW)
            snippet = text[start:end].strip()
            if snippet and len(snippet) > MIN_SNIPPET_LENGTH:
                snippets.append((start, snippet))
            pos += 1
    return snippets


def filter_relevant_text(text: str, max_length: int = 2000) -> str:
    """
    Filter text to extract only relevant snippets around price and stock indicators.

    Args:
        text: Full cleaned webpage text
        max_length: Maximum total length of filtered output

    Returns:
        Filtered text containing only relevant snippets
    """
    if not text:
        return ""

    # Keywords to search for (case-insensitive)
    price_keywords = [
        r"\$\d+\.?\d*",  # $XX.XX pattern
        r"\d+\.\d{2}\s*(usd|eur|gbp|cad)",  # XX.XX USD pattern
        "price:",
        "cost:",
        "sale:",
        "msrp:",
        "save:",
        "discount:",
        r"\$",  # Any dollar sign
    ]

    stock_keywords = [
        "add to cart",
        "buy now",
        "purchase",
        "order now",
        "in stock",
        "out of stock",
        "available",
        "unavailable",
        "sold out",
        "notify me",
        "back in stock",
        "pre-order",
        "ships",
        "delivery",
        "get it by",
    ]

    all_keywords = price_keywords + stock_keywords
    snippets = []

    text_lower = text.lower()

    # Find all matches and extract context
    for keyword in all_keywords:
        snippets.extend(_find_matches(text, text_lower, keyword))

    if not snippets:
        # No matches found, return beginning of text
        if len(text) > max_length:
            return text[:max_length] + "...(truncated)"
        return text

    # Sort by position and deduplicate overlapping snippets
    snippets.sort(key=lambda x: x[0])
    merged_snippets = []
    current_start, current_text = snippets[0]
    current_end = current_start + len(current_text)

    for start, snippet in snippets[1:]:
        end = start + len(snippet)
        # If overlapping or close together, merge
        if start <= current_end + SNIPPET_MERGE_DISTANCE:
            # Extend current snippet
            if end > current_end:
                # Merge overlapping text
                current_text = current_text + " " + snippet[max(0, current_end - start) :]
                current_end = end
        else:
            # Save current and start new
            merged_snippets.append(current_text)
            current_start, current_text = start, snippet
            current_end = end

    merged_snippets.append(current_text)

    # Join snippets with separator and limit total length
    result = " ... ".join(merged_snippets)
    if len(result) > max_length:
        result = result[:max_length] + "...(truncated)"

    return result
