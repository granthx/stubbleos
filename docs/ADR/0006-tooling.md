# ADR-0006: uv, src layout, strict mypy, ruff

**Status:** accepted

**Decision.** `uv` for environments and locking, `src/` layout with hatchling, `mypy --strict` globally (relaxed only for ORM and API glue), `ruff` for lint and format, pre-commit and GitHub Actions running the same commands as the Makefile.

**Note.** No `uv.lock` is committed yet because the authoring sandbox had no network. Run `uv lock` once and commit it; then change the Dockerfile to `uv sync --frozen`.
