"""Custom search input widget that looks like an Input but shows a constant cursor."""

from textual.reactive import reactive
from textual.widgets import Static


class SearchInput(Static):
    """A search box that mimics an Input widget but displays a static cursor."""

    value = reactive("")
    placeholder = reactive("Search by name or chain ID...")

    def render(self) -> str:
        """Render the search value with a static cursor."""
        if not self.value:
            # Use a dimmed color for placeholder
            return f"█ [grey37]{self.placeholder}[/]"
        return f"{self.value}█"
