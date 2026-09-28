# Release Roadmap

## Current release boundary

The current application is a Windows desktop forensics GUI for single-investigator case work. It supports case creation, local and remote evidence acquisition, artifact analysis, and report export. It should be treated as an investigator-operated tool: acquisition requires explicit authorization, administrative access where applicable, and independent verification of any generated finding.

## 1.0 release gate

Before calling the current feature set release-ready, complete these checks against harmless fixtures and a disposable Windows VM:

- Exercise case creation, existing-case selection, local evidence registration, and all report export formats.
- Exercise each analyzer with versioned sample inputs and assert its persisted case output.
- Exercise remote connection failure, cancellation, and cleanup paths without collecting real user data.
- Add a CI workflow that installs `requirements.txt`, runs `python -m unittest discover -v`, and compiles the source tree.
- Review the staged and unstaged changes, remove sample case artifacts that should not ship, and tag the tested revision.

## 1.1: Evidence integrity and workflow confidence

- Record source path, acquisition timestamp, size, and SHA-256 in an append-only case manifest.
- Surface acquisition failures and analyzer warnings in the case and report views.
- Add fixture-based tests for web, registry, USB, SRUM, memory, and report services.
- Add a visible run log with tool versions and command outcomes for investigator review.

## 1.2: Operational hardening

- Package the application with a pinned Python runtime and signed dependency manifest.
- Add recovery-safe cancellation and cleanup for long-running local and remote operations.
- Add accessibility and small-display verification for the primary investigator workflows.
- Document supported Windows versions, privileges, tool dependencies, and known forensic limitations.

## Non-goals for this release

Multi-user collaboration, real-time monitoring, cloud deployment, predictive AI, and a replacement for specialist commercial suites are separate product initiatives. They should not block validation of the focused Windows desktop workflow above.
