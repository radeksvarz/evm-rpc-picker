# EVM RPC Picker

A powerful TUI (Terminal User Interface) tool to search for EVM chains and manage your RPC URLs securely. It helps you quickly select and set the `ETH_RPC_URL` environment variable with the fastest available RPC, whether it's public, private, or project-specific.

## Features

-   **Instant Search**: Filter over 1000+ chains by name or Chain ID.
-   **Latency Checks**: Real-time ping (using `eth_blockNumber`) to find the most responsive RPC.
-   **Custom RPC Management**: Add, edit, and manage your own RPC endpoints for any chain.
-   **Secure Storage**: Encrypt sensitive RPC URLs and store API keys securely in your system's **Keyring**.
-   **Smart Context Detection**: Automatically detects networks and URLs defined in your `foundry.toml` or `hardhat.config.js`.
-   **Favorites System**:
    *   **Project Level**: Store favorites in `.rpc-picker.toml` within your repository.
    *   **Global Level**: Store favorites in your global user config.
    *   **Favorite RPCs**: Bookmark both public chains and your own custom RPCs to easily access and test them from a dedicated unified dashboard.
-   **Filtering**: 
    *   Toggle between **Mainnet**, **Testnet**, or **All**.
    *   Quickly filter to show only your **Favorite** chains.
-   **Notes**: Attach public notes (saved in config) or secret notes (saved in keyring) to your RPCs.

## Installation

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

```bash
# Run directly without installation
uvx evm-rpc-picker
```

## Shell Integration

Add the following function to your `.bashrc` or `.zshrc` to easily export the selected RPC:

```bash
pick-rpc() {
    local rpc=$(uvx evm-rpc-picker)
    [ -n "$rpc" ] && export ETH_RPC_URL="$rpc"
}
```

After restarting your shell, simply run `pick-rpc`.

## Python Usage

You can also use `evm-rpc-picker` as a module in your own Python scripts:

```python
from evm_rpc_picker import pick_rpc

# This will open the TUI
rpc_url = pick_rpc()

if rpc_url:
    print(f"Selected RPC: {rpc_url}")
```

## Keyboard Shortcuts

### Main Screen
| Key | Action |
|-----|--------|
| `Tab` | **Switch Focus** (Table ↔ Personal RPCs ↔ Env Status) |
| `Enter` | **Select** highlighted chain to see RPCs |
| `Ctrl + F` | **Filter Favorites** toggle |
| `Ctrl + T` | **Filter Network Type** (All ↔ Mainnet ↔ Testnet) |
| `Ctrl + L` | **Toggle Local Favorite** (Project level) |
| `Ctrl + G` | **Toggle Global Favorite** (Global level) |
| `Ctrl + R` | **Refresh** chain data from network |
| `Ctrl + E` | **Use Current ETH_RPC_URL** (select current ENV and exit) |
| `Ctrl + U` | **Personal RPC URLs** (manage and select custom endpoints) |
| `Ctrl + B` | **Favorite RPCs** (view all bookmarked public and custom endpoints) |

### RPC Selection Screen
| Key | Action |
|-----|--------|
| `Enter` | **Select** RPC and exit |
| `Esc` | **Back** to main screen |
| `Ctrl + R` | **Refresh** latencies |
| `Ctrl + L` | **Toggle Local Favorite** (Project level) |
| `Ctrl + G` | **Toggle Global Favorite** (Global level) |

### Personal RPC URLs Screen
| Key | Action |
|-----|--------|
| `Enter` | **Select** RPC and exit |
| `Esc` | **Back** to main screen |
| `a` | **Add** custom RPC |
| `e` | **Edit** highlighted RPC |
| `Delete` | **Delete** highlighted RPC |
| `Ctrl + V` | **Paste & Add** (paste URL from clipboard into Add RPC modal) |
| `Ctrl + B` | **Toggle Favorite** (bookmark/unbookmark the selected custom RPC) |

### Favorite RPCs Screen
| Key | Action |
|-----|--------|
| `Enter` | **Select** RPC and exit |
| `Esc` | **Back** to main screen |
| `Ctrl + R` | **Refresh** latencies |
| `Ctrl + L` | **Toggle Local Favorite** (Project level) |
| `Ctrl + G` | **Toggle Global Favorite** (Global level) |

### Add/Edit Custom RPC Modal
| Key | Action |
|-----|--------|
| `Ctrl + S` | **Save** changes (when editing) |
| `Ctrl + G` | **Add Globally** (when adding) |
| `Ctrl + L` | **Add Locally** (when adding) |
| `Esc` | **Cancel** |

## Configuration

-   **Global Config**: `~/.config/evm-rpc-picker/config.toml`
-   **Project Config**: `.rpc-picker.toml` in your project root.
-   **Cache**: Data from `chainlist.org` is cached for 24 hours in `~/.cache/evm-rpc-picker/chains.json`.

## Development

```bash
git clone https://github.com/radeksvarz/evm-rpc-picker.git
cd evm-rpc-picker
uv sync

# Run normally
uv run evm-rpc-picker
```

### Hot Reloading (TUI Development)

For TUI development with hot reloading, open two terminals.

Terminal 1 (Console output):
```bash
uv run textual console
```

Terminal 2 (App with hot reload):
```bash
uv run textual run --dev evm_rpc_picker.tui:ChainRPCPicker
```

---

Created with 🍻 by **BeerFi Prague** web3 builders community | [Source and updates](https://github.com/radeksvarz/evm-rpc-picker)

