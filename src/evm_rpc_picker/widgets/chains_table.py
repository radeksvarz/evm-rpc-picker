from textual.binding import Binding
from textual.widgets import DataTable


class ChainsTable(DataTable):
    """Custom table for displaying chains."""

    BINDINGS = [
        Binding("home", "cursor_top", "Top", show=False),
        Binding("end", "cursor_bottom", "Bottom", show=False),
        Binding("enter", "select_cursor", "Select", tooltip="Select the highlighted chain"),
        Binding("escape", "app.quit", "Cancel", tooltip="Quit the RPC picker"),
        Binding("ctrl+l", "screen.toggle_favorite", "Fav (Local)", tooltip="Add/remove from local project favorites"),
        Binding("ctrl+g", "screen.toggle_global_favorite", "Fav (Global)", tooltip="Add/remove from global favorites"),
    ]

    def action_cursor_top(self) -> None:
        """Jump to the first row."""
        self.move_cursor(row=0)

    def action_cursor_bottom(self) -> None:
        """Jump to the last row."""
        if self.row_count > 0:
            self.move_cursor(row=self.row_count - 1)
