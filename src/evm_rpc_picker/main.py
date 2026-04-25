import argparse
import sys
from evm_rpc_picker.tui import ChainRPCPicker

def print_init_snippet():
    snippet = """
rpc-set() {
    local rpc=$(uvx evm-rpc-picker)
    if [ -n "$rpc" ]; then
        export ETH_RPC_URL="$rpc"
    fi
}
"""
    print(snippet.strip())

def main():
    parser = argparse.ArgumentParser(description="EVM RPC Picker - TUI tool to select EVM RPC URLs")
    parser.add_argument("--init", action="store_true", help="Print shell initialization snippet for Bash/Zsh")
    parser.add_argument("--clear-cache", action="store_true", help="Clear the local chain data cache")
    
    args = parser.parse_args()

    if args.init:
        print_init_snippet()
        return

    if args.clear_cache:
        from evm_rpc_picker.models import clear_cache
        clear_cache()
        # We don't print anything to stdout to avoid messing up the TUI/shell capture

    app = ChainRPCPicker()
    # Run the app. The app.exit(result) call will return 'result' here.
    result = app.run()
    
    if result:
        # Print ONLY the RPC URL to stdout so it can be captured by shell scripts
        print(result)

if __name__ == "__main__":
    main()
