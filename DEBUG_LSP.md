# Debug LSP in Neovim

## Quick Checks to Run in Neovim

Open nvim and run these commands:

### 1. Check if Pyright is running
```vim
:LspInfo
```

You should see:
- Client: pyright (attached)
- Root directory: /Users/treyshanks/workspace/k8s-slm-log-agent/workloads/log-analyzer

### 2. Check Python path being used
```vim
:lua vim.print(vim.lsp.get_clients()[1].config.settings.python)
```

Should show the pythonPath

### 3. Restart LSP
```vim
:LspRestart
```

### 4. Check LSP logs
```vim
:lua vim.cmd('edit ' .. vim.lsp.get_log_path())
```

Look for errors about Python paths or imports

### 5. Check if file is in the right directory
```vim
:lua print(vim.fn.getcwd())
```

Should show your project root

## Manual Python Path Check

From your terminal:
```bash
cd workloads/log-analyzer
.venv/bin/python -c "import fastapi; print('OK')"
```

Should print "OK"

## Force Pyright to Use Specific Python

Create this file in your project root:
```bash
cd workloads/log-analyzer
cat > pyrightconfig.json << 'EOF'
{
  "venvPath": ".",
  "venv": ".venv"
}
EOF
```

Then restart nvim.
