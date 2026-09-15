# Development Documentation

This directory contains development guidelines, environment setup procedures, testing practices, and workflow standards for Project Aevum.

## Standards & Tooling
* **Package Management**:
  * Python: Managed with `uv`.
  * Frontend: Managed with `pnpm`.
* **Testing Philosophy**:
  * Unit tests for all business logic, state machines, and persistence models.
  * External dependencies (LLM APIs, OS services) must be mocked in automated test suites.
  * Integration tests use test dependency overrides (e.g. `FakeLLMProvider`) to ensure hermetic, deterministic test execution without live API keys.
* **Agent Guidelines**:
  * All AI agents and human contributors must comply with [`AGENTS.md`](../../AGENTS.md).
