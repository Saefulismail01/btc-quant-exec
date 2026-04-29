---
description: Obsidian + GitHub CLI Workflow Integration for btc-quant-exec project
---

# Obsidian + GitHub CLI Workflow

## Quick Start

1. **Check tasks**: Run `gh issue list --assignee=@me`
2. **Create issue**: Run `gh issue create --title "..." --label="..."`
3. **Create PR**: Run `gh pr create --title "..." --body "Closes #X"`

## Daily Routine

### Morning
- Open Obsidian Daily Note
- Run `gh issue list --assignee=@me --state=open`
- Prioritize tasks in Obsidian

### Work
- Research/analysis → Obsidian
- Implementation → GitHub Issues/PRs
- Update progress in Obsidian

### Evening
- Close completed: `gh issue close X`
- Update Obsidian with learnings
- Plan tomorrow

## Folder Structure

```
📁 Obsidian Vault/
├── 📁 00 - Inbox/        # Quick capture
├── 📁 01 - Projects/     # Project docs
├── 📁 02 - Research/     # Hypothesis, backtest
├── 📁 03 - GitHub/       # Sync issues/PRs
└── 📁 04 - Daily/        # Daily notes
```

## Useful Aliases (PowerShell)

```powershell
function ghmy { gh issue list --assignee=@me @args }
function ghic($title) { gh issue create --title $title @args }
function ghpc($title) { gh pr create --title $title @args }
function ghiv($num) { gh issue view $num }
function ghpv($num) { gh pr view $num }
```

## Bi-directional Linking

### Obsidian to GitHub
```markdown
**GitHub Issue:** [[GitHub/Issue-45]]
**PR:** [[GitHub/PR-67]]
```

### GitHub to Obsidian
```markdown
See research doc: [Entry Timing Proposal](obsidian://open?vault=...&file=...)
```

## Research → Implementation Flow

1. **Research Phase** (Obsidian)
   - Document hypothesis
   - Run analysis/backtest
   - Record results

2. **Execution Phase** (GitHub CLI)
   - `gh issue create` for implementation
   - Code and test
   - `gh pr create` and merge

3. **Documentation Phase** (Obsidian)
   - Update docs with results
   - Link to GitHub issue/PR
   - Archive learnings

## Templates

### Daily Note Template
```markdown
# {{date}}

## GitHub Tasks
- [ ] Task 1 (Issue #X)
- [ ] Task 2 (PR #Y)

## Research
- 

## Learnings
- 

## Blockers
- 
```

### Research Doc Template
```markdown
# {{title}}

**Status:** research/implemented/deployed
**GitHub Issue:** [[GitHub/Issue-X]]

## Hypothesis

## Methodology

## Results

## Conclusions

## Next Steps
```
