# Project Instructions

## Project Goal

Build the investment analysis system in this order:

1. Single LLM-based analysis
2. Financial data integration
3. RAG
4. Tools
5. Agent workflows
6. LangGraph
7. Multi-agent architecture

Do not introduce later-stage technologies before they are needed.

## File Rules

* Keep all prompt definitions in `bull_prompt.py`.
* Do not rename existing files unless explicitly requested.
* Preserve existing function names and return formats when possible.
* Save generated outputs in `results/`.
* Do not read, modify, or expose `.env` or API keys unless explicitly requested.

## Coding Rules

* Use Python type hints for new functions.
* Add appropriate error handling for external API calls.
* Make the smallest necessary change.
* Avoid unnecessary refactoring or dependency additions.
* Do not modify any code without explicit user approval.

## Git Rules

* Write commit messages in English only.
* Do not commit, push, create branches, or open pull requests unless explicitly requested.
* Suggest an English commit message after completing a meaningful unit of work.

## Token and Context Usage

* Read only files relevant to the current task.
* Start with targeted searches instead of scanning the entire repository.
* Do not repeatedly read files whose contents are already known.
* Do not inspect `.env`, `venv/`, `__pycache__/`, `results/`, cache directories, generated files, model files, datasets, or binary files unless required.
* Do not repeat large code blocks when a diff or partial snippet is sufficient.
* Keep explanations concise and focused on the issue, proposed changes, affected files, and test results.
* Reuse existing project conventions and known context instead of rediscovering them.

## Required Working Process

### Before Editing

1. Inspect only the files relevant to the request.
2. Explain the current problem or code behavior.
3. Describe the proposed changes and why they are needed.
4. List the files that would be modified.
5. Ask for explicit user approval.
6. Do not edit files, run formatting tools, install dependencies, or execute commands that modify the project before approval.

### After Approval

* Apply only the approved changes.
* Do not make additional unapproved changes.
* If another change becomes necessary, stop and ask for approval again.
* Run relevant tests after editing when possible.

### After Editing

* Summarize the modified files and key changes.
* Report the tests or commands executed and their results.
* Mention remaining issues, assumptions, or unverified behavior.
* Suggest an appropriate English commit message.

## Approval Rule

A request to analyze, review, explain, debug, or identify a problem is not permission to modify code.

Only modify code after the user clearly approves the proposed changes with a response such as:

* “수정해”
* “진행해”
* “적용해”
* “승인”
* “고쳐줘”

When approval is unclear, explain the proposed changes and wait without modifying any files.
