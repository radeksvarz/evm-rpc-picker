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
    
    # If the user is piping or in a non-interactive shell, we might want to handle it,
    # but Textual handles terminal detection.
    
    args = parser.parse_args()

    if args.init:
        print_init_snippet()
        return

    app = ChainRPCPicker()
    # Run the app. The app.exit(result) call will return 'result' here.
    result = app.run()
    
    if result:
        # Print ONLY the RPC URL to stdout so it can be captured by shell scripts
        print(result)

if __name__ == "__main__":
    main()
