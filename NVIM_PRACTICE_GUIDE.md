# Neovim Practice Guide for k8s-slm-log-agent

Your VSCode to Neovim migration cheatsheet. Practice these workflows with this codebase!

## 🎯 Essential Workflows

### 1. Finding Files (Like Ctrl+P in VSCode)

| Action | Keybinding | Description |
|--------|------------|-------------|
| Find files | `Ctrl+p` or `<leader>ff` | Fuzzy find any file in project |
| Recent files | `<leader>fr` | Open recently used files |
| Find buffers | `<leader>fb` | Switch between open files |

**Practice Task**: Try finding `main.go` by typing `Ctrl+p` then `main`

---

### 2. Finding Strings in Code (Like Ctrl+Shift+F in VSCode)

| Action | Keybinding | Description |
|--------|------------|-------------|
| Search in files | `<leader>fg` | Live grep search across project |
| Search word under cursor | `*` (then `<leader>fg`) | Search current word everywhere |

**Navigation in Telescope**:
- `Ctrl+j` / `Ctrl+k` - Move up/down in results
- `Enter` - Open selected file
- `Esc` - Close telescope

**Practice Task**: Search for "logger" in your codebase with `<leader>fg`

---

### 3. LSP: Code Navigation & Intelligence

| Action | Keybinding | Description |
|--------|------------|-------------|
| Go to definition | `gd` | Jump to where function/variable is defined |
| Go to references | `gr` | See all places this is used |
| Hover documentation | `K` | Show docs for symbol under cursor |
| **Enter hover window** | `K` (again) | Press K twice to scroll inside docs |
| **Exit hover window** | `q` | Close hover window |
| Signature help | `Ctrl+k` | Show function signature while typing |
| Rename symbol | `<leader>rn` | Rename variable/function everywhere |
| Code actions | `<leader>ca` | Show quick fixes/refactorings |
| Show errors | `<leader>d` | Show diagnostic details |
| Next error | `]d` | Jump to next error |
| Previous error | `[d` | Jump to previous error |

**Practice Tasks**:
1. Open `workloads/log-analyzer/src/log_analyzer/main.py`
2. Put cursor on a function name and press `gd` to jump to definition
3. Press `Ctrl+o` to jump back (Ctrl+i to jump forward)
4. Try `gr` to see all references to that function
5. Use `K` to see documentation

**📖 Navigating LSP Documentation Windows**:

When you press `K` for hover docs, the window appears but your cursor stays in your code. Here's how to navigate:

1. **Quick view** (cursor stays in code):
   - Press `K` once
   - Read the docs
   - Move cursor or press `Esc` to auto-close

2. **Scroll through long docs** (enter the window):
   - Press `K` once to show docs
   - Press `K` **again** to jump into the docs window
   - Scroll with `j`/`k` or `Ctrl+d`/`Ctrl+u`
   - Press `q` to close and return to code

3. **Alternative method**:
   - Press `K` to show docs
   - Press `Ctrl+w w` to jump to the floating window
   - Navigate, then press `q` to exit

---

### 4. Find & Replace

| Action | Keybinding | Description |
|--------|------------|-------------|
| Replace word in file | `<leader>s` (on word) | Replace current word across file |
| Replace selection | Select text, `<leader>s` | Replace selected text |
| Manual find/replace | `:%s/old/new/gc` | Manual with confirmation |

**How it works**:
1. Put cursor on a word (or select text in visual mode)
2. Press `<leader>s`
3. Type the replacement text
4. Press `Enter`

**Practice Task**:
1. Open any Go file
2. Put cursor on a variable name
3. Press `<leader>s` and try renaming it
4. Press `u` to undo!

---

### 5. File & Directory Creation

| Action | Keybinding | Description |
|--------|------------|-------------|
| New file | `<leader>nf` | Create new file in current directory |
| New directory | `<leader>nd` | Create new directory |
| File explorer | `<leader>e` | Toggle file tree |
| Focus explorer | `<leader>o` | Jump to file tree |

**Practice Task**:
1. Press `<leader>e` to open file tree
2. Navigate with `j/k`
3. Press `a` to create a file/folder
4. Press `d` to delete
5. Press `r` to rename

---

### 6. Window & Buffer Management

| Action | Keybinding | Description |
|--------|------------|-------------|
| Split vertical | `:vsp` | Split window vertically |
| Split horizontal | `:sp` | Split window horizontally |
| Navigate windows | `Ctrl+h/j/k/l` | Move between splits |
| Next buffer | `Tab` | Next file in buffer |
| Previous buffer | `Shift+Tab` | Previous file |
| Close buffer | `<leader>x` | Close current file |
| Save file | `<leader>w` | Save |
| Quit | `<leader>q` | Quit |

**Practice Task**:
1. Open a file with `Ctrl+p`
2. Split window with `:vsp`
3. In the new split, find another file with `Ctrl+p`
4. Navigate between splits with `Ctrl+h` and `Ctrl+l`
5. Close one split with `:q`

---

### 7. Editing Motions (The Vim Way)

| Action | Keys | Description |
|--------|------|-------------|
| Delete word | `dw` | Delete word under cursor |
| Delete line | `dd` | Delete entire line |
| Change word | `cw` | Delete word and enter insert mode |
| Delete inside quotes | `di"` | Delete text inside quotes |
| Change inside parens | `ci(` | Change content inside () |
| Visual line mode | `V` | Select entire lines |
| Visual block mode | `Ctrl+v` | Select rectangular blocks |
| Jump to line | `:<number>` | Jump to line number |
| Jump to end of line | `$` | End of line |
| Jump to start | `0` | Start of line |
| Jump to first char | `^` | First non-blank character |

**Practice Task**:
1. Open any file
2. Try `dd` to delete a line
3. Try `u` to undo
4. Try `ci"` with cursor inside quotes
5. Try `V` and select multiple lines, then `d` to delete

---

### 8. Git Integration

| Action | Keybinding | Description |
|--------|------------|-------------|
| Next git hunk | `]c` | Jump to next change |
| Previous git hunk | `[c` | Jump to previous change |
| Preview hunk | `<leader>hp` | Show diff of change |
| Stage hunk | `<leader>hs` | Stage this change |
| Reset hunk | `<leader>hr` | Discard this change |
| Blame line | `<leader>hb` | Show git blame |

**Practice Task**: Make a change to a file and try previewing the diff with `<leader>hp`

---

## 🎓 Your Learning Path

### Week 1: Basic Navigation
- [ ] Use `Ctrl+p` instead of file explorer for 1 day
- [ ] Practice `gd` (go to definition) and `Ctrl+o` (go back)
- [ ] Use `<leader>fg` to search for strings
- [ ] Get comfortable with `hjkl` for movement

### Week 2: Editing Efficiency
- [ ] Practice `dd`, `cc`, `yy` (delete line, change line, yank line)
- [ ] Use `ci"`, `ci(`, `ci{` to change inside delimiters
- [ ] Try visual mode (`v`) to select and edit
- [ ] Use `<leader>s` for find/replace instead of manual search

### Week 3: Advanced Workflows
- [ ] Split windows with `:vsp` and `:sp`
- [ ] Use LSP features: `gr`, `<leader>rn`, `<leader>ca`
- [ ] Navigate errors with `]d` and `[d`
- [ ] Practice git hunks with `]c`, `[c`, `<leader>hp`

---

## 💡 Pro Tips

1. **Don't use arrow keys!** Force yourself to use `hjkl` for a week
2. **Leader key is Space**: When you see `<leader>`, that's the spacebar
3. **Which-key helper**: Press `<leader>` and wait - a popup shows all keybindings!
4. **Use relative line numbers**: Jump with `10j` or `5k` to move 10 lines down or 5 up
5. **Command history**: Press `:` then use arrow up/down to see previous commands
6. **Exit insert mode**: Use `jk` quickly instead of `Esc` (you can add this later)
7. **Jump back/forward**: `Ctrl+o` to go back, `Ctrl+i` to go forward in jump history

---

## 🚀 Quick Start Practice Session

Open this project in nvim and try this sequence:

```bash
cd /Users/treyshanks/workspace/k8s-slm-log-agent
nvim
```

1. Press `<leader>e` to open file tree
2. Press `Ctrl+p` and type "main" to find main.go
3. Press `<leader>fg` and search for "config"
4. Put cursor on a function and press `gd`
5. Press `K` on a Go type to see documentation
6. Press `Ctrl+o` to jump back
7. Press `:q` to quit

---

## 📚 Remember

- **Normal mode**: Default mode, for navigation (press `Esc` to return here)
- **Insert mode**: For typing text (press `i`, `a`, `o` to enter)
- **Visual mode**: For selecting text (press `v`, `V`, or `Ctrl+v`)
- **Command mode**: For commands (press `:`)

**The most important command**: When lost, press `Esc Esc` to get back to normal mode!

---

## ⚡ Your Current Keybindings Summary

### Core (Space is leader)
- `<leader>w` - Save file
- `<leader>q` - Quit
- `<leader>x` - Close buffer
- `Tab` / `Shift+Tab` - Next/previous buffer

### File Operations
- `<leader>e` - Toggle file tree
- `<leader>o` - Focus file tree
- `<leader>nf` - New file
- `<leader>nd` - New directory

### Finding
- `Ctrl+p` or `<leader>ff` - Find files
- `<leader>fg` - Grep search
- `<leader>fb` - Find buffers
- `<leader>fr` - Recent files

### LSP
- `gd` - Go to definition
- `gr` - References
- `K` - Hover docs
- `<leader>rn` - Rename
- `<leader>ca` - Code action
- `<leader>d` - Show diagnostic
- `]d` / `[d` - Next/prev error

### Git
- `]c` / `[c` - Next/prev git hunk
- `<leader>hp` - Preview hunk
- `<leader>hs` - Stage hunk
- `<leader>hr` - Reset hunk
- `<leader>hb` - Blame line

### Edit
- `<leader>s` - Find and replace (word or selection)
- `<` / `>` in visual mode - Indent (stays in visual mode)

Good luck with your Neovim journey! 🎉
