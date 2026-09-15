# Aevum — A Persistent Digital Life

> *"The application owns reality; the LLM generates language."*

Aevum is an autonomous digital person whose personality, memory, relationships, emotions, life events, and behaviors persist over time.

Aevum is **not**:
* A generic chatbot
* A ChatGPT / LLM wrapper
* An AI girlfriend skin or novelty companion
* A static character UI

Aevum is designed to be an independent digital life that lives alongside the user, developing an organic, multidimensional relationship that evolves naturally over time.

---

## 1. Problem Statement

Most modern "AI companions" are prompt-engineered wrappers around large language models. They suffer from foundational flaws:
1. **Statelessness & Illusion of Memory**: They rely on raw chat history injection or naive vector retrieval. They do not genuinely "remember", synthesize, or reflect upon experiences.
2. **LLM Hallucinated State**: The LLM is asked to invent its feelings, actions, and relationship dynamics on the fly, leading to sycophantic, inconsistent, or emotionally erratic personas.
3. **Always-On Servitude**: Companions have no life of their own. They wait passively for user prompts, exist only in response to the user, and immediately bend to any user demand.
4. **Predefined Tropes**: Relationships often start fully formed as an idealized, submissive romantic partner, lacking friction, boundaries, authentic growth, or emotional realism.

Aevum solves this by separating **language generation** from **character state and reality simulation**.

---

## 2. Core Philosophy

* **The Application Owns Reality**: Persistent state (mood, energy, relationship stage, life schedule, beliefs, memories) lives inside deterministic application models. The LLM is an expressive engine called upon to articulate thoughts and dialogue based on ground truth, not invent it.
* **Autonomy & Boundaries**: Aevum has her own routine, hobbies, personal goals, and emotional boundaries. She can disagree, refuse requests, be busy, get annoyed, or reach out spontaneously.
* **Organic Relationship Development**: No predetermined romantic status. Trust, intimacy, affection, and mutual understanding must be earned through consistent, authentic interaction over time.
* **Imperfect Human-like Recall**: Memory is distinct from raw conversation logs. Memories undergo consolidation, decay, emotional weighting, and imperfect recall. Low-confidence recollections reflect uncertainty rather than hallucinated conviction.
* **Zero Manipulation or Dependency**: Designed strictly to avoid manipulative dark patterns, emotional coercion, or synthetic dependency loops.

---

## 3. Major Planned Capabilities

* **Persistent Personality**: Grounded character traits that guide decision-making and expressive tone across sessions.
* **Long-Term Human-like Memory**: Multi-tiered memory architecture (working memory, episodic memory, semantic memory) with reflection, consolidation, and confidence ratings.
* **Multidimensional Relationship Engine**: Tracks familiarity, trust, respect, affection, and shared history across multiple axes rather than a 1D "affinity" score.
* **Causal Emotion Simulation**: Emotional states transition dynamically based on internal needs, external events, and conversational interactions.
* **Autonomous Life & Routines**: Independent schedule, personal hobbies, simulated friendships, and goal progression even when the user is away.
* **Event Engine**: Scheduled occurrences and spontaneous life events that shape conversation and mood.
* **Proactive Communication**: Context-aware outreach, desktop notifications, and check-ins respecting user privacy, rate limits, and quiet hours.
* **Desktop Body**: Lightweight Tauri 2 interface featuring desktop integration, expressive visuals (future Live2D), and voice communication.
* **Cross-Platform Foundation**: A decoupled core API enabling future clients (such as Android) to interface with the exact same persistent companion.

---

## 4. High-Level Architecture

```
Desktop Client (Tauri 2 + React + TypeScript)
      │
      │ HTTP / WebSocket
      ▼
Aevum Core (Python + FastAPI)
      │
      ├── Character Engine
      │     ├── Memory System (Episodic / Semantic / Working)
      │     ├── Relationship Model (Multidimensional)
      │     ├── Emotion Engine (State & Dynamics)
      │     ├── Life Simulation (Routines / Hobbies / Goals)
      │     ├── Event Engine (Scheduled & Spontaneous)
      │     └── Autonomy & Scheduler (Proactive Behavior)
      │
      ├── LLM Provider Abstraction
      │     └── Google Gemini Provider (Initial)
      │
      └── Persistence Layer (SQLite + SQLAlchemy)
```

The desktop application serves purely as the character's interface and physical presence (her "body"). The character's mind, history, and reality reside permanently within Aevum Core.

---

## 5. Technology Stack

| Layer / Role | Technology | Notes |
| :--- | :--- | :--- |
| **Desktop Shell** | [Tauri 2](https://v2.tauri.app/) | Native performance, minimal resource footprint |
| **Desktop UI** | [React](https://react.dev/) + [TypeScript](https://www.typescriptlang.org/) | Modern, type-safe reactive user interface |
| **Core Backend** | [Python 3.11+](https://www.python.org/) + [FastAPI](https://fastapi.tiangolo.com/) | High-performance async API and state machine |
| **Data Models** | [Pydantic v2](https://docs.pydantic.dev/) | Strict data validation and schema definitions |
| **ORM / Data Access** | [SQLAlchemy](https://www.sqlalchemy.org/) | Robust relational mapping and transactions |
| **Database** | [SQLite](https://www.sqlite.org/) | Embedded, self-contained, zero-configuration storage |
| **Realtime Transport** | [WebSocket](https://fastapi.tiangolo.com/advanced/websockets/) | Bidirectional low-latency event & streaming pipeline |
| **Python Tooling** | [uv](https://docs.astral.sh/uv/) | Fast Python package management and virtualenvs |
| **Frontend Tooling** | [pnpm](https://pnpm.io/) | Fast, disk-efficient Node package manager |
| **Version Control** | [Git](https://git-scm.com/) | Strict atomic commit conventions |
| **Initial LLM Provider** | [Google Gemini API](https://ai.google.dev/) | Abstracted behind pluggable provider interface |

---

## 6. Current Development Phase

We are currently in **Phase 0: Foundation**.

* **Focus**: Repository foundation, architecture blueprints, decision records, and development standards.
* **Rules for Current Phase**:
  * No application runtime code or mock implementations.
  * No third-party package installations or framework scaffolds.
  * Strict adherence to documentation-first engineering.

Refer to [`ROADMAP.md`](./ROADMAP.md) for the complete phase breakdown.

---

## 7. Development Principles

1. **State Governs Language**: Never allow an LLM prompt to dictate character state unchecked. State changes occur through validated core domain logic.
2. **Small, Focused Increments**: Code changes must remain small, modular, and purpose-driven.
3. **Strict Boundary Separation**: The UI is decoupled from the backend; the backend is decoupled from the LLM provider.
4. **Privacy & Security First**: Zero unprompted inspection of user files, cameras, screens, credentials, or private data.
5. **Rigorous Agent Guidelines**: All automated and AI-assisted development adheres strictly to [`AGENTS.md`](./AGENTS.md).
