# VS Code + VSCodeVim Keyboard Shortcuts Cheat Sheet

> **Philosophy**: Use **Vim motions** for text editing, **VS Code shortcuts** for workspace navigation, **Leader key (Space)** for custom commands

---

## 🚀 The Essential 5 (Master These First)

These eliminate 80% of mouse usage:

| Shortcut | Action | Context |
|----------|--------|---------|
| `Cmd+P` | Fuzzy find files | Anywhere |
| `Space ff` | Find files (same as Cmd+P) | Normal mode |
| `Space fg` | Find in files (grep/search text) | Normal mode |
| `gd` | Go to definition | On symbol |
| `Space e` | Toggle file explorer | Normal mode |

---

## 📁 File Navigation & Management

### Fuzzy Finding
| Shortcut | Action |
|----------|--------|
| `Cmd+P` or `Space ff` | Quick open file (fuzzy search) |
| `Space fg` | Find in files (search text across project) |
| `Space fs` | Find symbol (search functions/classes) |
| `Space fr` | Recent files |
| `Cmd+Shift+.` | Go to symbol in file |

### File Explorer (when focused with `Space e`)
| Key | Action |
|-----|--------|
| `j` / `k` | Move down / up |
| `h` / `l` | Collapse folder / Expand/Open |
| `a` | New file |
| `Shift+A` | New folder |
| `r` | Rename |
| `d` | Delete |
| `x` | Cut |
| `y` | Copy |
| `p` | Paste |
| `gg` | Jump to top |
| `G` | Jump to bottom |

---

## ✏️ Text Editing (Vim Motions)

### Insert Mod
| Shortcut | Action |
|----------|--------|
| `jj` | Escape to normal mode (faster than Esc) |

### Basic Vim Motions (Normal Mode)
| Motion | Action |
|--------|--------|
| `h` `j` `k` `l` | Left, Down, Up, Right |
| `w` / `b` | Next/Previous word |
| `e` | End of word |
| `0` / `$` | Start/End of line |
| `gg` / `G` | Top/Bottom of file |
| `{` / `}` | Previous/Next paragraph |
| `%` | Jump to matching bracket |

### Editing
| Command | Action |
|---------|--------|
| `dd` | Delete line |
| `yy` | Yank (copy) line |
| `p` | Paste |
| `u` | Undo |
| `Ctrl+r` | Redo |
| `ciw` | Change inner word |
| `diw` | Delete inner word |
| `ci"` | Change inside quotes |
| `dat` | Delete around tag (HTML) |

### Visual Mode
| Command | Action |
|---------|--------|
| `v` | Visual mode (character) |
| `V` | Visual line mode |
| `Ctrl+v` | Visual block mode |
| `J` (in visual) | Move selected lines down |
| `K` (in visual) | Move selected lines up |

---

## ⚡ EasyMotion (Jump Anywhere Fast!)

| Shortcut | Action |
|----------|--------|
| `s` + 2 chars | Jump to any visible text (2-char search) |
| `Ctrl+j` | EasyMotion jump down by line |
| `Ctrl+k` | EasyMotion jump up by line |

**How it works**: Press `s`, type 2 characters you see on screen → markers appear → press the highlighted letter to jump instantly!

**Example**: To jump to the word "function":
1. Press `s`
2. Type `fu`
3. Letters appear on all "fu" matches
4. Press the letter to jump there

---

## 🔍 Search & Replace

### Search
| Command | Action |
|---------|--------|
| `/pattern` | Search forward |
| `?pattern` | Search backward |
| `n` / `N` | Next/Previous match |
| `Space h` | Clear search highlight |
| `*` | Search word under cursor |

### Find & Replace
| Shortcut | Action |
|----------|--------|
| `Space fg` | Find in files (workspace search) |
| `Cmd+H` | Find and replace in file |
| `Cmd+Shift+H` | Find and replace in workspace |

---

## 🗂️ Window & Split Management

### Splits
| Shortcut | Action |
|----------|--------|
| `Space v` | Split editor vertically |
| `Ctrl+h` / `Ctrl+l` | Navigate left/right between splits |
| `Cmd+1` / `Cmd+2` | Focus editor group 1/2 |

### Tabs/Editors
| Shortcut | Action |
|----------|--------|
| `Cmd+h` | Previous tab |
| `Cmd+l` | Next tab |
| `Space q` | Close current editor |
| `Space Q` | Close all editors |
| `Space w` | Save file |

### Panels
| Shortcut | Action |
|----------|--------|
| `Space t` | Toggle terminal |
| `Cmd+j` | Focus panel (terminal/output) |
| `Cmd+k` | Focus editor |
| `Space e` | Toggle file explorer |

---

## 🧭 Code Navigation (LSP)

All start with `g` (mnemonic: "Go to...")

| Shortcut | Action |
|----------|--------|
| `gd` | Go to definition |
| `gD` | Go to declaration |
| `gi` | Go to implementation |
| `gr` | Go to references |
| `gh` | Show hover documentation |
| `gp` | Peek definition (inline popup) |
| `Ctrl+o` | Go back (navigation history) |
| `Ctrl+i` | Go forward (navigation history) |

---

## 🛠️ Code Actions & Refactoring

| Shortcut | Action |
|----------|--------|
| `Space rn` | Rename symbol |
| `Space rf` | Format document |
| `Space ca` | Code actions / Quick fix |
| `Space /` | Toggle comment |

---

## 🔧 Terminal

### Open/Close
| Shortcut | Action |
|----------|--------|
| `Space t` | Toggle terminal |
| `Ctrl+` ` | Native VS Code toggle terminal |

### Navigation (when terminal focused)
| Shortcut | Action |
|----------|--------|
| `Ctrl+h` / `Ctrl+l` | Navigate between terminal panes |
| `Ctrl+j` / `Ctrl+k` | Scroll terminal up/down |

---

## 📋 Quick Open / Lists Navigation

When in Quick Open (`Cmd+P`), autocomplete, or any list:

| Shortcut | Action |
|----------|--------|
| `Ctrl+j` | Next item |
| `Ctrl+k` | Previous item |
| `j` / `k` | Next/Previous (in sidebar lists) |
| `gg` / `G` | First/Last item (in lists) |
| `o` | Select item (in lists) |

---

## 🎯 Leader Key Commands (Space)

Press `Space` in normal mode, then:

### Files
- `Space w` - Save
- `Space q` - Close editor
- `Space Q` - Close all editors
- `Space e` - File explorer

### Find
- `Space f f` - Find files
- `Space f g` - Find in files (grep)
- `Space f s` - Find symbol
- `Space f r` - Recent files

### Refactor
- `Space r n` - Rename
- `Space r f` - Format

### Code
- `Space c a` - Code actions

### Other
- `Space h` - Clear highlight
- `Space t` - Terminal
- `Space v` - Split vertical

---

## 💡 Pro Tips

### Workflow Patterns

1. **Open a file fast**:
   - `Space ff` → type partial filename → Enter
   - Example: `Space ff` → "cont" → finds "controller.py"

2. **Search for code**:
   - `Space fg` → type search term → Enter
   - Jump through results with `F4` (next) / `Shift+F4` (prev)

3. **Jump to definition and back**:
   - Place cursor on function → `gd` → view definition
   - `Ctrl+o` to jump back

4. **Navigate file explorer without mouse**:
   - `Space e` → `j/k` to move → `l` to open → `h` to close folder

5. **Quick file creation**:
   - `Space e` → navigate to folder → `a` → type filename → Enter

6. **Search and jump with EasyMotion**:
   - `s` + 2 chars → press letter marker → instant jump
   - Faster than counting lines for `5j`

### Muscle Memory Builder

**Week 1**: Master the Essential 5
**Week 2**: Add file explorer navigation (hjkl + a)
**Week 3**: Add LSP navigation (gd, gr, gh)
**Week 4**: Add leader key commands (Space + ...)

### Hybrid Philosophy

- **Editing text**: Use Vim motions (`ciw`, `dd`, `yy`)
- **Navigating workspace**: Use VS Code shortcuts (`Cmd+P`, `Cmd+Shift+F`)
- **Custom actions**: Use leader key (`Space + ...`)

### VS Code Native Shortcuts Still Available

These are delegated to VS Code (not Vim):

- `Cmd+S` - Save (but `Space w` also works!)
- `Cmd+F` - Find in file
- `Cmd+W` - Close tab
- `Cmd+N` - New file
- `Cmd+Z` - Undo
- `Cmd+C/V/X` - Copy/Paste/Cut (but `yy` and `p` work too!)

---

## 🎨 Customization

All settings are in:
- `~/Library/Application Support/Code/User/settings.json` - VSCodeVim config
- `~/Library/Application Support/Code/User/keybindings.json` - Custom keybindings

To modify leader key bindings, edit the `vim.normalModeKeyBindingsNonRecursive` section in settings.json.

---

## 🐛 Troubleshooting

**Vim mode feels stuck?**
- Press `Esc` or `jj` to return to normal mode
- Check bottom left corner for mode indicator

**Keys not working?**
- Reload VS Code: `Cmd+Shift+P` → "Reload Window"
- Check for keybinding conflicts: `Cmd+K Cmd+S` → search for the key

**EasyMotion not showing markers?**
- Make sure `vim.easymotion` is `true` in settings
- Try `s` followed by two characters that exist on screen

**File explorer keys not working?**
- Make sure file explorer is focused: `Space e`
- The sidebar must have focus (blue highlight)

---

## 📚 Resources

- [VSCodeVim GitHub](https://github.com/VSCodeVim/Vim)
- [VS Code Keyboard Shortcuts PDF](https://code.visualstudio.com/shortcuts/keyboard-shortcuts-macos.pdf)
- [Vim Cheat Sheet](https://vim.rtorr.com/)

---

**Remember**: Keyboard efficiency is built through repetition. Pick 2-3 new shortcuts each week and force yourself to use them until they become muscle memory. Don't try to learn everything at once!
