# Installing LSP Servers in Neovim

## Quick Fix for Python LSP

You need to install Pyright (Python language server). Here's how:

### Option 1: Install via Neovim (Recommended)

1. Open nvim:
   ```bash
   nvim
   ```

2. Type this command:
   ```
   :MasonInstall pyright
   ```

3. Wait for installation to complete (you'll see a progress window)

4. Quit nvim with `:q` and reopen

### Option 2: Install via Command Line

```bash
# Using npm (if you have Node.js)
npm install -g pyright

# Or using Mason from command line
nvim --headless -c "MasonInstall pyright" -c "qall"
```

### Verify Installation

After installing, open nvim and check:

```
:Mason
```

You should see `pyright` in the list with a checkmark ✓

---

## What This Fixes

- `K` (hover) will show proper type information like `app: FastAPI` instead of `Unknown`
- Auto-completion will suggest methods from your imports
- Error detection will work for undefined variables
- Go to definition (`gd`) will work for external packages

---

## Next: Configure Virtual Environment Detection

After Pyright is installed, I'll create a config file so it knows about your `.venv` folder!
