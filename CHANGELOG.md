# Changelog

All notable changes to this project are documented here.

## 1.1.0 - 2026-08-08

- Added a complete mocked-API integration test across all nine pipeline stages.
- Added an honest, reproducible offline validation benchmark and machine-readable result.
- Added a synthetic downloadable sample vault.
- Documented pipeline, concurrency, privacy, recovery, model, and cost decisions in ADR-001.
- Added coverage reporting and a minimum CI quality gate.

## 1.0.0 - 2026-07-28

- Added stable import paths for the pipeline agents.
- Fixed package discovery so the `agents` package ships with the CLI.
- Corrected the shell wrapper to use the documented Click subcommand.
- Added Python 3.10–3.12 CI, CLI tests, import tests, and a synthetic sample export.
- Replaced illustrative performance claims with reproducible validation guidance.
