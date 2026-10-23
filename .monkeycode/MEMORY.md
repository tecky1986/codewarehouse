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
