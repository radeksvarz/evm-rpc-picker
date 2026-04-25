from textual.widgets import Input

class SearchInput(Input):
    BINDINGS = [
        ("enter", "submit", "Select"),
        ("escape", "app.quit", "Exit"),
        ("ctrl+r", "app.load_data", "Refresh Data"),
        ("ctrl+t", "app.toggle_filter", "Toggle Filter"),
    ]
