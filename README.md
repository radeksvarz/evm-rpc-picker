# EVM RPC Picker

A TUI (Terminal User Interface) tool to search for EVM chains and select an RPC URL. It helps you quickly set the RPC environment variable for your favourite chain with the fastest available public RPC.

## Features
- **Search**: Instantly filter over 1000+ chains by name or Chain ID.
- **Latency Checks**: Real-time ping (using `eth_blockNumber`) to find the most responsive RPC.
- **Filtering**: Automatically excludes RPCs that require API keys (like Infura or Alchemy) to ensure you get a working public URL.
- **Caching**: Local caching of chain data for near-instant startup.
- **Shell Integration**: Built-in command to export the selected URL directly to your shell environment.

## Installation

Ensure you have [uv](https://github.com/astral-sh/uv) installed.

```bash
# To run directly without installation
uvx evm-rpc-picker
```

## Shell Integration

Add the following function to your `.bashrc` or `.zshrc`:

```bash
set-rpc() {
    local rpc=$(uvx evm-rpc-picker)
    [ -n "$rpc" ] && export ETH_RPC_URL="$rpc"
}
```

After restarting your shell or sourcing the config, use the `set-rpc` command:

```bash
set-rpc
```

## Keyboard Shortcuts

| Key        | Action                                         |
|------------|------------------------------------------------|
| `Tab`      | **Switch Focus** (Search ↔ List ↔ System RPC)  |
| `Enter`    | **Select** highlighted chain or RPC            |
| `Ctrl + T` | **Toggle Filter** (All / Mainnet / Testnet)    |
| `Ctrl + R` | **Refresh** data from network                  |
| `Esc`      | **Exit** or go back from detail screen         |
| `/`        | **Search** (focuses the search input)          |

## Caching Details
The tool fetches data from `https://chainlist.org/rpcs.json` and caches it locally for 24 hours.

- **Cache Location**: `~/.cache/evm-rpc-picker/chains.json`
- **Cache Duration**: 24 hours.
- **Force Refresh**: Press `Ctrl + R` inside the app or run `evm-rpc-picker --clear-cache`.

## Development
```bash
git clone https://github.com/radeksvarz/evm-rpc-picker.git
cd evm-rpc-picker
uv sync
uv run evm-rpc-picker
```

