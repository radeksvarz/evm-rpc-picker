from textual.widgets import DataTable


class ChainsTable(DataTable):
    BINDINGS = [
        ("enter", "select_cursor", "Select"),
        ("escape", "app.quit", "Cancel"),
    ]
