# Agent Instructions (mandatory)

## 1. Safety & Critical Rules
- **Explicit Permission Required**: Always ask before `rm`, changing constants (URLs, timeouts), or adding new dependencies.

## 2. Language Policy
- English only.

## 3. TUI (Textual)
- **Events**: Use `@on(DataTable.RowSelected)` for table selection (Enter is consumed by widget).
- **Navigation**: Handle key bubbling in `MainScreen` so shortcuts work even when `SearchInput` is focused.
- **Workers**: Prefer standard `async` methods for logic that needs to be awaited in tests.
- **UX**: Every action must have a visible keyboard shortcut (e.g., `[Ctrl+S]`).

## 4. Quality & Workflow
- 100% coverage for config/logic layers. Use `uv run pytest`.
- Use `pilot.pause(0.5)` and mock network (via `respx`) and filesystem (via `tmp_path`) for isolation.
- Run `uv run ruff check --fix .`, `uv run ruff format .` and `uv run mypy src/evm_rpc_picker` before finishing for linting and types.

## 5. Architecture
- **Layout**: `src/evm_rpc_picker/`.
- **Config**: Global (`~/.config/evm-rpc-picker/config.toml`), Local (`.rpc-picker.toml`).
- **Security**: Keyring or encrypted password via `EncryptionManager`.
- **Data**: Fetched from `chainlist.org` and cached locally.

## 6. PR Instructions
- **Title format**: `[evm-rpc-picker] <Title>`
- **Checklist**: Ensure all checks in [Quality & Workflow](#4-quality--workflow) pass before committing.
