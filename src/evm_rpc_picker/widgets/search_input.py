"""Custom search input widget with specialized focus handling."""

from textual.widgets import Input


class SearchInput(Input):
    """Input widget for searching chains with custom focus behavior."""

    can_focus = False
