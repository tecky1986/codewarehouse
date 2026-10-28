# User Instruction Memory

This file records user instructions, preferences, and teachings for reference in future interactions.

## Format

### User Instruction Entry
User instruction entries should follow this format:

[User Instruction Summary]
- Date: [YYYY-MM-DD]
- Context: [Mentioned scenario or time]
- Instructions:
  - [Content of user teaching or instruction, described line by line]

### Project Knowledge Entry
Entries discovered by the Agent during task execution should follow this format:

[Project Knowledge Summary]
- Date: [YYYY-MM-DD]
- Context: Discovered by Agent while performing [specific task description]
- Category: [Operations & Deployment|Build Methods|Testing Methods|Troubleshooting & Debugging|Workflow & Collaboration|Environment Configuration]
- Instructions:
  - [Specific knowledge points, described line by line]

## Deduplication Strategy
- Before adding a new entry, check for similar or identical instructions.
- If a duplicate is found, skip the new entry or merge it with the existing one.
- When merging, update the context or date information.
- This helps avoid redundant entries and keeps the memory file tidy.

## Entries

[Build and test commands]
- Date: 2026-10-23
- Context: Discovered by Agent while performing task 1 project scaffold
- Category: Build Methods
- Instructions:
  - Backend tests: `cd /workspace/backend && python3 -m pytest -q`（当前 95 passed）
  - Frontend tests: `cd /workspace/frontend && npm test`；改前端后需 `npm run typecheck && npm run build` 并同步 `frontend/dist` 到 `backend/static/` 再重启 uvicorn
  - Python deps: `pip3 install --break-system-packages -r /workspace/backend/requirements.txt`
  - Frontend deps: `cd /workspace/frontend && npm install`
  - Backend package root is `/workspace/backend` (`pythonpath = .`); API envelope is `{code, message, data}`

[Windows Build Workflow]
- Date: 2026-10-26
- Context: User instructed that local Windows packaging cannot be auto-generated in this environment
- Category: Build Methods
- Instructions:
  - This Linux workspace can run PyInstaller/zip, but its PyInstaller output is a Linux ELF bundle, not a Windows .exe.
  - For a real Windows executable, push Git changes and use the GitHub Windows runner to build the dated zip.
  - Locally, pull the latest Git revision, then download the newest dated Windows zip from the Git/GitHub release.
  - The local Linux `dist/container_packing` bundle can still be used for smoke/regression verification of the same frozen startup and API flow.
  - `build_windows.sh` now supports repacking an existing Windows bundle into a local dated zip via `CP_WINDOWS_PACKAGE=/tmp/win_v021.zip ./build_windows.sh`.
  - Repacking verifies the zip and PE header, but it does not regenerate the `.exe` from the latest source.
  - If the latest Windows artifact already exists as a GitHub artifact for the current HEAD, download it and repackage it locally instead of attempting a local Windows PyInstaller build.
  - For releases, push the source branch first, then tag `vX.Y.Z` on the branch tip; the `Windows executable` workflow on tag push creates the GitHub release and attaches the dated Windows zip.
  - Verify the latest release by checking `releases/latest` assets and the tag-to-branch alignment before reporting completion.
  - 拉取 Windows exe 到本地的标准做法（私有仓库，匿名下载 release 附件返回 404）：
    - 用 git credential fill 取 github.com 的 token：`CRED=$(echo -e "protocol=https\nhost=github.com\n" | git credential fill 2>/dev/null)`，`TOKEN=$(echo "$CRED" | grep '^password=' | cut -d= -f2-)`。
    - 先查 release 的 asset id：`curl -s -H "Authorization: Bearer $TOKEN" https://api.github.com/repos/<owner>/<repo>/releases/tags/<tag>` 取 `assets[0].id`。
    - 走 API asset 端点下载（带 `Accept: application/octet-stream`）：`curl -L -o <dest>.zip -H "Authorization: Bearer $TOKEN" -H "Accept: application/octet-stream" https://api.github.com/repos/<owner>/<repo>/releases/assets/<id>`。
    - 匿名 `curl` 直接打 `releases/download/<tag>/<file>.zip` 会 404（私有仓库对匿名隐藏 release），不要依赖它；token 只用于本次下载，勿写入任何项目文件。
    - 下载后用 `unzip -l` 校验完整性，并用 `head -c 2 <exe> | od -An -tx1` 确认 PE 魔数 `4d 5a`。



