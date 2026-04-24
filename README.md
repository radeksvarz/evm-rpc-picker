# EVM RPC Picker

A modern TUI (Terminal User Interface) tool to search for EVM chains and select an RPC URL. It helps you quickly set your `ETH_RPC_URL` environment variable with the fastest available public RPC.

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

Add the following line to your `.bashrc` or `.zshrc`:

```bash
eval "$(uvx evm-rpc-picker --init)"
```

After restarting your shell or sourcing the config, use the `rpc-set` command:

```bash
rpc-set
```

## Keyboard Shortcuts
| Key | Action |
|-----|--------|
| `f` | Focus the search input |
| `r` | Force refresh chain data from network |
| `q` | Quit the application |
| `Enter` | Select the highlighted chain or RPC |
| `Esc` | Go back or close the RPC selection screen |

## Caching Details
The tool fetches data from `https://chainlist.org/rpcs.json` and caches it locally for 24 hours.

- **Cache Location**: `~/.cache/evm-rpc-picker/chains.json`
- **Cache Duration**: 24 hours.
- **Force Refresh**: Press `r` inside the app or run `evm-rpc-picker --clear-cache`.

## Development
```bash
git clone https://github.com/radek/evm-rpc-picker.git
cd evm-rpc-picker
uv sync
uv run evm-rpc-picker
```

