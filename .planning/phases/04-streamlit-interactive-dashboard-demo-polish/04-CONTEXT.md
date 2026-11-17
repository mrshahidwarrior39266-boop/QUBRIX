# Phase 4 Context: Streamlit Interactive Dashboard & Demo Polish

## Phase Goal
Deliver an executive-grade Streamlit web interface with subject tabs, inline color-coded `<mark>` highlighted text spans, dynamic rubric sliders with live Before-and-After score diffing, persistent disk caching for 100% offline safety, and CSV report export.

## Requirements Covered
- **UI-01**: Interactive Streamlit dashboard with multi-subject tabs and responsive grading views.
- **UI-02**: Visual inline color-coded `<mark>` highlighting of evidence spans directly on student answers.
- **CACHE-01**: Persistent local disk cache for evaluations ensuring 100% demo uptime and API rate-limit resilience.
- **EXPORT-01**: Downloadable CSV report export containing grades, itemized criteria points, and feedback.

## Key Technical Decisions
- **Safe HTML Highlighting**: Raw student text is HTML-escaped before injecting sanitized `<mark>` tags to prevent XSS issues in Streamlit.
- **Disk Cache Warming**: Pre-populates `data/cache/evaluations.json` so the demo loads and regrades in milliseconds even with zero internet connection.
- **All-in-One Dashboard Layout**: Tab 1 for Grading & Evidence, Tab 2 for Dynamic Regrading Diffing, Tab 3 for Reliability & Borderline Review Queue.

## Plans in this Phase
1. `04-01-PLAN.md` (Wave 1): HTML evidence highlighter in `core/visualizer.py` and interactive Streamlit UI in `app.py`.
2. `04-02-PLAN.md` (Wave 2): Disk cache in `core/cache_manager.py`, CSV export, and production `README.md`.
