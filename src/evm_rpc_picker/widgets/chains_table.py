from textual.widgets import DataTable

class ChainsTable(DataTable):
    BINDINGS = [
        ("enter", "select_cursor", "Select"),
        ("escape", "app.quit", "Exit"),
        ("ctrl+r", "app.load_data", "Refresh Data"),
        ("ctrl+t", "app.toggle_filter", "Toggle Filter"),
    ]
