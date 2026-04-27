from textual.widgets import DataTable
from textual.binding import Binding

class ChainsTable(DataTable):
    """Custom table for displaying chains."""
    
    BINDINGS = [
        Binding("enter", "select_cursor", "Select", tooltip="Select the highlighted chain"),
        Binding("escape", "app.quit", "Cancel", tooltip="Quit the application"),
        Binding("ctrl+b", "screen.toggle_favorite", "Fav (PROJ)", tooltip="Add/remove from local project favorites"),
        Binding("ctrl+g", "screen.toggle_global_favorite", "Fav (GLOB)", tooltip="Add/remove from global favorites"),
    ]
