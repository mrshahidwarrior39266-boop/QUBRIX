"""
core/visualizer.py
------------------
Purpose: Format student text into safe, beautiful HTML with inline color-coded <mark> tags
         highlighting verbatim evidence quotes tied to specific rubric criteria.
Inputs:  Raw student text and itemized criterion evaluations.
Outputs: Sanitized HTML markup ready for display in Streamlit or web interfaces.
"""

import html
import logging
import re
from typing import Any, Dict, List

# Configure logging
logger = logging.getLogger(__name__)

# Color styling for evidence badges
BADGE_STYLES = {
    "FULL": {
        "bg": "#d1e7dd",      # Soft pastel green
        "text": "#0f5132",    # Deep forest green
        "border": "#badbcc"
    },
    "PARTIAL": {
        "bg": "#fff3cd",      # Soft pastel amber
        "text": "#664d03",    # Deep amber brown
        "border": "#ffecb5"
    }
}


def highlight_student_evidence(
    student_answer: str,
    criterion_evaluations: List[Dict[str, Any]]
) -> str:
    """
    Wrap verbatim evidence quotes in styled HTML <mark> tags while preserving
    unhighlighted student prose and preventing HTML injection / XSS vulnerabilities.

    Args:
        student_answer: Raw text submitted by the student.
        criterion_evaluations: List of criterion evaluation dicts containing
                               'evidence_quote', 'status', and 'criterion_id'.

    Returns:
        str: Styled HTML string ready for st.markdown(..., unsafe_allow_html=True).
    """
    if not student_answer:
        return "<em>No response provided.</em>"

    # HTML-escape raw text to block injection vulnerabilities
    escaped_answer = html.escape(student_answer)

    # Collect valid quotes to highlight
    spans_to_highlight = []
    for c in criterion_evaluations:
        status = c.get("status", "NONE").upper()
        quote = c.get("evidence_quote", "").strip()
        cid = c.get("criterion_id", "")

        if status in BADGE_STYLES and quote:
            escaped_quote = html.escape(quote)
            if escaped_quote.lower() in escaped_answer.lower():
                spans_to_highlight.append({
                    "quote": escaped_quote,
                    "cid": cid,
                    "status": status,
                    "style": BADGE_STYLES[status]
                })

    # Sort spans by length descending to prevent shorter sub-phrases from breaking longer quotes
    spans_to_highlight.sort(key=lambda x: len(x["quote"]), reverse=True)

    highlighted_html = escaped_answer

    for item in spans_to_highlight:
        q = item["quote"]
        cid = item["cid"]
        status = item["status"]
        st = item["style"]

        # Case-insensitive replacement pattern using regex
        pattern = re.compile(re.escape(q), re.IGNORECASE)

        # Replacement styled tag
        replacement = (
            f'<mark style="background-color: {st["bg"]}; color: {st["text"]}; '
            f'border: 1px solid {st["border"]}; border-radius: 4px; padding: 2px 6px; '
            f'margin: 0 1px; font-weight: 500; display: inline-block;">'
            f'{q} '
            f'<span style="font-size: 0.72em; background: rgba(255,255,255,0.7); '
            f'border-radius: 3px; padding: 1px 4px; margin-left: 2px; font-weight: 600;">'
            f'{cid}: {status}'
            f'</span>'
            f'</mark>'
        )

        # Replace first occurrence to prevent duplicate replacements
        highlighted_html = pattern.sub(replacement, highlighted_html, count=1)

    return f'<div style="font-size: 1.05rem; line-height: 1.7; padding: 14px; background: #fdfdfe; border-radius: 8px; border: 1px solid #e2e8f0;">{highlighted_html}</div>'
