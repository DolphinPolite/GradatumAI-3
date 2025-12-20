Quick steps to prepare and upload this repository to GitHub

1) Prepare local repository and create a commit (PowerShell):

```powershell
cd "path\to\GradatumAI-3-main"
./scripts/prepare_git.ps1 -Message "My initial commit message"
```

2) Create a remote and push

Using `gh` (GitHub CLI) — recommended:

```powershell
gh repo create <owner>/<repo> --public --source=. --remote=origin --push
```

Or manually add a remote and push:

```powershell
git remote add origin https://github.com/<owner>/<repo>.git
git branch -M main
git push -u origin main
```

Notes:
- `.gitignore` is included; it currently ignores common Python artifacts. If you want to include model weights under `models/`, remove the `models/*.pth` rule from `.gitignore`.
- If you prefer a different commit message, edit `COMMIT_MESSAGE.txt` or pass `-Message` to the script.
