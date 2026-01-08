# Advanced Virtual Environment Detection

## Adding Poetry Support

If you use Poetry, add to your `get_python_path` function in `~/.config/nvim/lua/plugins/lsp.lua`:

```lua
local function get_python_path(workspace)
  -- Poetry venv detection
  local poetry_venv = vim.fn.system('cd ' .. workspace .. ' && poetry env info -p 2>/dev/null'):gsub('\n', '')
  if poetry_venv ~= '' and vim.fn.isdirectory(poetry_venv) == 1 then
    return poetry_venv .. '/bin/python'
  end

  -- Standard venv patterns
  local venv_patterns = {
    workspace .. '/.venv/bin/python',
    workspace .. '/venv/bin/python',
    workspace .. '/.env/bin/python',
    workspace .. '/env/bin/python',
  }

  for _, path in ipairs(venv_patterns) do
    if vim.fn.executable(path) == 1 then
      return path
    end
  end

  return vim.fn.exepath('python3') or vim.fn.exepath('python')
end
```

## Adding Pipenv Support

```lua
local function get_python_path(workspace)
  -- Pipenv venv detection
  local pipenv_venv = vim.fn.system('cd ' .. workspace .. ' && pipenv --venv 2>/dev/null'):gsub('\n', '')
  if pipenv_venv ~= '' and vim.fn.isdirectory(pipenv_venv) == 1 then
    return pipenv_venv .. '/bin/python'
  end

  -- Rest of the function...
end
```

## Adding Conda Support

```lua
local function get_python_path(workspace)
  -- Conda environment detection
  local conda_env = os.getenv('CONDA_PREFIX')
  if conda_env and conda_env ~= '' then
    return conda_env .. '/bin/python'
  end

  -- Rest of the function...
end
```

## Complete Function (All Tools)

```lua
local function get_python_path(workspace)
  -- 1. Check for Poetry
  local poetry_venv = vim.fn.system('cd ' .. workspace .. ' && poetry env info -p 2>/dev/null'):gsub('\n', '')
  if poetry_venv ~= '' and vim.fn.isdirectory(poetry_venv) == 1 then
    return poetry_venv .. '/bin/python'
  end

  -- 2. Check for Pipenv
  local pipenv_venv = vim.fn.system('cd ' .. workspace .. ' && pipenv --venv 2>/dev/null'):gsub('\n', '')
  if pipenv_venv ~= '' and vim.fn.isdirectory(pipenv_venv) == 1 then
    return pipenv_venv .. '/bin/python'
  end

  -- 3. Check for Conda
  local conda_env = os.getenv('CONDA_PREFIX')
  if conda_env and conda_env ~= '' then
    return conda_env .. '/bin/python'
  end

  -- 4. Check standard venv locations
  local venv_patterns = {
    workspace .. '/.venv/bin/python',
    workspace .. '/venv/bin/python',
    workspace .. '/.env/bin/python',
    workspace .. '/env/bin/python',
  }

  for _, path in ipairs(venv_patterns) do
    if vim.fn.executable(path) == 1 then
      return path
    end
  end

  -- 5. Fallback to system Python
  return vim.fn.exepath('python3') or vim.fn.exepath('python')
end
```

## Debugging

To see which Python path Pyright is using:

```vim
:lua print(vim.lsp.get_clients()[1].config.settings.python.pythonPath)
```

Or check LSP logs:

```vim
:lua vim.lsp.set_log_level('debug')
:e ~/.local/state/nvim/lsp.log
```
