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
  - Backend tests: `cd /workspace/backend && python3 -m pytest -q`
  - Frontend tests: `cd /workspace/frontend && npm test`
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



