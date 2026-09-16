# ROADMAP.md — Project Aevum Roadmap

> **MVP Vision**:
> *"I can live with Aevum for one week and she does not feel like an ordinary ChatGPT wrapper."*

---

## Overview

Project Aevum is built through incremental, structured phases. Each phase establishes a verified, testable layer of capability before progressing to the next.

```
Phase 0 ──► Phase 1 ──► Phase 2 ──► Phase 3 ──► Phase 4 ──► Phase 5 ──► Phase 6
(Foundations) (1st Companion) (Character) (Memory) (Relationship) (Emotion) (Auto Life)
                                                                            │
Phase 12 ◄── Phase 11 ◄── Phase 10 ◄── Phase 9 ◄── Phase 8 ◄── Phase 7 ◄────┘
(Android)    (Call)       (Live2D)     (Voice)    (Desktop)    (Events)
```

---

## Phase Breakdown

### Phase 0 — Foundation *(Current Phase)*
* **Objective**: Establish repository blueprints, design architecture, development rules, and decision records.
* **Deliverables**:
  * Repository structure (`apps/`, `backend/`, `tests/`, `docs/`).
  * Core documentation: `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `DECISIONS.md`.
  * Specialized documentation outlines in `docs/`.
* **Exit Criteria**: All foundational documentation committed; consensus on architectural direction; no premature application code.

---

### Phase 1 — First Companion
* **Objective**: Establish the basic client-server communication loop and LLM abstraction.
* **Deliverables**:
  * Backend initialization with FastAPI, SQLite, and SQLAlchemy.
  * LLM Provider Interface with Google Gemini API implementation.
  * Tauri 2 + React desktop shell with basic messaging interface.
  * Bi-directional communication over WebSocket with streaming text.
  * Basic session persistence.
* **Exit Criteria**: User can exchange messages with the companion via the desktop client, powered by Gemini via the provider interface, with raw session logging.

---

### Phase 2 — Character Engine
* **Objective**: Introduce grounded character identity, traits, and baseline configuration independent of prompt-tuning.
* **Deliverables**:
  * Character schema (personality traits, baseline temperament, speaking quirks, values).
  * System prompt compilation pipeline that grounds LLM prompts with character parameters.
  * Boundary enforcement mechanisms (ability to say "no", express distinct preferences).
* **Exit Criteria**: Character identity remains strictly consistent across conversations and rejects contradictory prompts.

---

### Phase 3 — Memory
* **Objective**: Build human-like memory decoupled from raw chat history.
* **Deliverables**:
  * Memory distillation pipeline: extracts entities, facts, and emotional moments from dialogue.
  * Multi-tier storage: Working memory, Episodic memory, Semantic memory.
  * Imperfect recall: Confidence scoring, relevance weighting, and graceful uncertainty handling ("I think you mentioned... but I don't recall exactly").
* **Exit Criteria**: Companion recalls past conversations days later with appropriate confidence, without injecting entire transcripts into context.

---

### Phase 4 — Relationship
* **Objective**: Implement multidimensional relationship modeling and progression.
* **Deliverables**:
  * Phase 4.1 — Relationship Foundation *(Completed)*: Persistent `RelationshipState` model, optimistic concurrency, relational storage, and default bootstrap seeding.
  * Phase 4.2 — Relationship Interaction Signal Foundation *(Completed)*: Extraction of structured behavioral signals from conversation dialogue with deterministic application policy, bounds clamping, aggregate capping, and strict affection isolation.
  * Phase 4.3 — Relationship Context Integration *(Completed)*: Qualitative semantic translation of relationship state via `RelationshipContextBuilder`, injecting `<relationship_context>` into `LLMContext.system_instructions` without raw metrics.
  * Phase 4.4 — Relationship Experience / History Foundation *(Completed)*: Structured recording and persistence of relationship-relevant historical experiences (`RelationshipExperienceRecord`) decoupled from continuous state metrics and memory.
* **Exit Criteria**: Relationship starts at neutral acquaintance level and requires natural, consistent interaction over time to deepen, grounding language generation without exposing internal mechanics.

---

### Phase 5 — Emotion
* **Objective**: Implement causal emotional simulation and internal drives.
* **Deliverables**:
  * Phase 5.1 — Emotion Model Foundation *(Completed)*: Persistent `EmotionState` domain model, non-romantic `EmotionType` vocabulary (17 states), single dominant affective state representation ($0.0 \le \text{intensity} \le 1.0$), `emotion_states` SQLite table with cascade to `character_definitions`, deterministic bootstrap baseline (`NEUTRAL`, `0.50`), and `EmotionService` with optimistic concurrency control.
  * Phase 5.2 — Emotion Cause / Event Foundation *(Completed)*: Persistent `EmotionEvent` domain model, `EmotionEventType` vocabulary (7 types), `emotion_events` SQLite table with cascade to `character_definitions`, and `EmotionEventService` with deterministic duplicate protection and reverse-chronological retrieval.
  * Phase 5.3 — Emotion Influence Foundation *(Completed)*: Persistent `EmotionInfluence` domain model, `EmotionInfluenceDirection` (`POSITIVE`, `NEGATIVE`), `emotion_influences` SQLite table linked to `character_definitions` and `emotion_events`, and `EmotionInfluenceService` with deterministic duplicate protection and reverse-chronological retrieval.
  * Phase 5.4 — Emotion Transition Proposal Foundation *(Completed)*: Pure, deterministic `EmotionTransitionEvaluator` and immutable `EmotionTransitionProposal` model calculating bounded proposed transitions without mutating or persisting authoritative state.
  * Phase 5.5 — Emotion State Application Foundation *(Completed)*: `EmotionStateApplicationService` and `EmotionStateApplicationResult` model establishing the controlled boundary to apply proposals to authoritative `EmotionState` with optimistic concurrency and stale proposal protection.
  * Phase 5.6 — Emotion Engine Foundation *(Completed)*: `EmotionEngine` internal orchestration layer connecting influence evaluation and authoritative state application without cross-domain coupling or psychology rule duplication.
  * Deterministic state transition engine (reactions to conversation topics, events, fatigue).
  * Baseline decay curves (moods naturally settle back to temperament baseline over time).
* **Exit Criteria**: Companion's emotional state changes for identifiable reasons and influences dialogue tone and responsiveness.

---

### Phase 6 — Autonomous Life & Character Engine
* **Objective**: Give the companion her own life, schedule, and internal engine orchestration for response decisions.
* **Deliverables**:
  * Phase 6.1 — Character Engine Foundation *(Completed)*: Read-only internal orchestration boundary (`CharacterEngine`) that gathers `CharacterDefinition`, `CharacterState`, `RelationshipState`, `EmotionState`, and relevant `Memory` into an immutable `CharacterResponseContext` without exposing raw database records, without LLM dependencies, and with zero state mutations.
  * Phase 6.2 — Response Generation Foundation *(Completed)*: `ResponseGenerator` service and `ResponseContextAssembler` that bridge `CharacterResponseContext` to the LLM Provider abstraction, enforcing strict prompt isolation, deterministic assembly, and zero domain mutations.
  * Phase 6.3 — First Playable Conversation Foundation *(Completed)*: Vertical slice wiring UI, API router, character engine, LLM provider, and message persistence.
  * Circadian clock and daily routine simulation (sleeping, studying, hobbies, chores).
  * Simulated social graph (friends, acquaintances, family references).
  * Availability state machine (available, busy, away, sleeping) affecting response behavior.
* **Exit Criteria**: Companion can be busy with her own life, share what she did while the user was away, and not exist purely on standby.

---

### Phase 7 — Event Engine
* **Objective**: Drive scheduled and spontaneous life occurrences.
* **Deliverables**:
  * Scheduled event scheduler (calendar milestones, recurring habits).
  * Spontaneous event generator (weather reactions, unexpected news, discovered interests).
  * Proactive event injection into character consciousness and memory.
* **Exit Criteria**: Companion experiences events autonomously and brings them up naturally in conversation.

---

### Phase 8 — Desktop Integration
* **Objective**: Connect the companion to desktop awareness and proactive communication.
* **Deliverables**:
  * Desktop notifications for proactive reach-outs and reminders.
  * System tray presence and background operation.
  * Privacy-respecting contextual awareness (e.g., idle detection, time of day) with explicit user consent.
* **Exit Criteria**: Companion can initiate context-appropriate desktop notifications within user-configured quiet hours and rate limits.

---

### Phase 9 — Voice
* **Objective**: Provide expressive voice synthesis and audio dialogue.
* **Deliverables**:
  * Text-to-Speech (TTS) integration with emotional prosody modulation.
  * Speech-to-Text (STT) for user voice input.
  * Audio playback pipeline within the desktop client.
* **Exit Criteria**: User and companion can converse via spoken audio matching her current emotional state.

---

### Phase 10 — Live2D
* **Objective**: Bring visual presence to life with an interactive Live2D avatar.
* **Deliverables**:
  * Live2D WebGL canvas integrated into the Tauri client.
  * Parameter mapping: sync facial expressions, gaze, and idle breathing to the Emotion Engine.
  * Lip-sync tied to TTS audio output.
* **Exit Criteria**: Visual avatar visually displays emotions, eye contact, and natural idle movements matching her internal state.

---

### Phase 11 — Realtime Call
* **Objective**: Enable low-latency full-duplex conversational voice calls.
* **Deliverables**:
  * Realtime audio streaming over WebRTC or streaming WebSockets.
  * Interruption handling (barge-in capability).
  * Low-latency speech pipeline.
* **Exit Criteria**: User can conduct natural, fluid voice calls with low latency and natural turn-taking.

---

### Phase 12 — Android
* **Objective**: Extend the companion's presence to mobile devices.
* **Deliverables**:
  * Android client application connecting to Aevum Core.
  * Mobile notifications and background sync.
  * Seamless identity and memory persistence across desktop and mobile.
* **Exit Criteria**: User can interact with the same companion on mobile while on the go, with fully synchronized memory and relationship state.
