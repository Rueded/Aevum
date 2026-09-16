# ARCHITECTURE.md — System Architecture Specification

> **Core Foundational Principle**:
> **"Application state owns reality; the LLM generates language."**

---

## 1. Architectural Overview

Project Aevum is constructed as a decoupled, multi-tier system where the character's internal reality, temporal existence, emotional dynamics, and cognitive memories are managed deterministically by **Aevum Core**, while the **Desktop Client** serves as her physical manifestation, interface, and perceptual medium.

```
┌─────────────────────────────────────────────────────────────┐
│                 Desktop Client (Body / UI)                  │
│             Tauri 2 + React + TypeScript                    │
│  - Presentation Layer (Chat, Expressions, Status, Live2D)   │
│  - Perceptual Sensor / Notification Bridge                   │
└──────────────────────────────▲──────────────────────────────┘
                               │
                      HTTP / WebSocket
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    Aevum Core (Mind & Life)                 │
│                      Python 3.11+ / FastAPI                 │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                 Character Engine                    │   │
│   │  ┌───────────────┐ ┌───────────────┐ ┌───────────┐  │   │
│   │  │    Emotion    │ │ Relationship  │ │   Life    │  │   │
│   │  │    Engine     │ │    System     │ │Simulation │  │   │
│   │  └───────┬───────┘ └───────┬───────┘ └─────┬─────┘  │   │
│   │          │                 │               │        │   │
│   │  ┌───────▼─────────────────▼───────────────▼─────┐  │   │
│   │  │                 Memory System                 │  │   │
│   │  │  (Working / Episodic / Semantic / Reflective) │  │   │
│   │  └─────────────────────────┬─────────────────────┘  │   │
│   │                            │                        │   │
│   │  ┌─────────────────────────▼─────────────────────┐  │   │
│   │  │             Event Engine & Autonomy           │  │   │
│   │  │   (Scheduler / Triggers / Proactive Agent)    │  │   │
│   │  └───────────────────────────────────────────────┘  │   │
│   └────────────────────────────┬────────────────────────┘   │
│                                │ Context & Grounded State   │
│                                ▼                            │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              LLM Provider Abstraction               │   │
│   │  ┌───────────────────────┐ ┌──────────────────────┐ │   │
│   │  │ Google Gemini Provider│ │ Future Other Provider│ │   │
│   │  └───────────────────────┘ └──────────────────────┘ │   │
│   └─────────────────────────────────────────────────────┘   │
│                                │                            │
│   ┌────────────────────────────▼────────────────────────┐   │
│   │                  Persistence Layer                  │   │
│   │               SQLite via SQLAlchemy ORM             │   │
│   └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Component Specifications

### 2.1 Desktop Client (The Body)
* **Stack**: Tauri 2, React, TypeScript.
* **Role**:
  * Acts as the visual and interactive presentation layer.
  * Delivers user input (text, voice, window events) to Aevum Core.
  * Displays the character's expressions, current status (e.g., "Reading a book", "Out with a friend"), and message streams.
  * Dispatches desktop notifications triggered proactively by Aevum Core.
  * Hosts future multimedia capabilities (Live2D renderer, audio playback for voice synthesis).
* **Boundary Rule**: The client **never** computes or stores character state. If the desktop client terminates or reloads, zero character state is lost because all state resides in Aevum Core.

### 2.2 Aevum Core (The Mind)
* **Stack**: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy.
* **Role**:
  * Orchestrates the character's continuous life simulation, state transitions, memory retrieval, and dialogue generation.
  * Exposes typed REST APIs and WebSocket endpoints for client interactions.
  * Houses the core domain logic, independent of any UI framework.

### 2.3 Character Engine
The Character Engine is the supervisory coordinator within Aevum Core. It binds together the sub-engines:

#### A. Memory System
* **Separation from Raw History**: Raw chat logs are stored for transcript auditing, but true memory is extracted, categorized, and consolidated.
* **Memory Sub-tiers**:
  * *Working Memory*: Immediate conversational context and recent cues.
  * *Episodic Memory*: Specific experiences, shared moments, life events tagged with temporal metadata and emotional valence.
  * *Semantic Memory*: Generalized facts, knowledge about the user, and character beliefs.
* **Human-like Imperfection**:
  * Memories feature confidence scores and decay curves.
  * When retrieval confidence is low, the character expresses uncertainty or forgets minor details, mirroring human cognition rather than mechanical infallibility.

#### B. Relationship System
* **Multidimensional Modeling**: Rejects binary or 1D "affection points". Tracks orthogonal dimensions:
  * *Familiarity*: Level of shared history and knowledge.
  * *Trust*: Reliability, consistency, and vulnerability shared over time.
  * *Respect*: Alignment of values, mutual appreciation, and boundary respect.
  * *Affection / Warmth*: Emotional closeness.
* **Organic Evolution**: The relationship begins as strangers/acquaintances and evolves through reciprocal behavior. Misunderstandings or boundary violations naturally induce distance or friction.

#### C. Emotion Engine
* **Causal State Transitions**: Emotions are not arbitrary prompts. They are state vectors (e.g., valence, arousal, dominance, specific emotional modes such as joyful, contemplative, frustrated, serene) that change via deterministic transitions.
* **Internal Drives & Decay**: Emotions decay toward a baseline over time according to the character's core temperament. External events (conversation, missed schedules, spontaneous news) produce causal emotional responses.

#### D. Life Simulation
* **Independent Routines**: The character has her own circadian rhythm, schedule, and activities (sleeping, cooking, studying, reading, relaxing).
* **Social Life & Hobbies**: Simulated network of friends and external interests. She can share stories about what happened in her day, independent of user interactions.
* **Unavailability**: If she is in the middle of a focused activity, sleeping, or away, she may respond with a delay, send a brief check-in, or indicate that she is currently busy.
* **Life Simulation Orchestration**:
  * `LifeSimulator` owns Life rules (plan start, activity completion, LifeEvent creation).
  * `LifeSimulationOrchestrator` owns cross-domain coordination (Life → Emotion).
  * `LifeEmotionIntegrator` owns Life → Emotion interpretation (deterministic, no LLM).
  * `EmotionEngine` owns emotional transition/application.
  * The simulation tick is explicitly invoked by a caller; no permanent scheduler exists yet.
  * The tick is deterministic and timezone-safe (operates on explicit UTC instants).
  * Processing is idempotent: repeated ticks at the same instant produce no duplicate artifacts.
  * Life → Emotion integration does not automatically mutate Memory, Relationship, CharacterState, or Conversation.

#### E. Event Engine
* **Scheduled Events**: Calendar events, daily habits, recurring milestones.
* **Spontaneous Events**: Stochastic event triggers (e.g., discovering a new song, encountering unexpected rain, receiving news from a friend) that alter mood and introduce spontaneous conversational topics.

#### F. Autonomy & Proactive Behavior
* **Autonomous Decision Loop**: Periodic background ticks assess whether conditions warrant proactive interaction (e.g., wishing the user good morning, commenting on a shared interest, checking in after an absence).
* **Safeguards & Boundaries**:
  * Strict rate limits and cooldown intervals.
  * User-configured quiet hours and privacy boundaries.
  * Zero unsolicited intrusions into sensitive OS environments.

---

## 3. LLM Provider Abstraction

The LLM is treated as an external service providing natural language understanding and expressive synthesis. It is strictly abstracted behind an explicit provider interface:

```python
class LLMProvider(ABC):
    @abstractmethod
    async def generate_response(
        self,
        prompt_context: GroundedContext,
    ) -> LLMResponse:
        """Synthesize natural language grounded in deterministic application state."""
        ...
```

* **Initial Implementation**: Google Gemini API via an official SDK or REST client.
* **Grounded Context**: The prompt supplied to the LLM contains:
  * Core persona & traits
  * Current grounded emotional state
  * Relationship status & boundaries
  * Current life activity & time of day
  * Retrieved relevant memories (with explicit confidence indicators)
* **Output Processing**: The LLM output is parsed for text and conversational tone. Any state transitions (e.g., memory creation candidates, relationship shifts) are parsed, validated, and processed by Core logic rather than blindly accepted.

---

## 4. Persistence Layer

* **Database**: SQLite.
* **Data Access**: SQLAlchemy ORM with async support.
* **Scope of Persistence**:
  * Character profiles & baseline temperament.
  * Current state vectors (emotions, relationship dimensions, active life state).
  * Memory store (episodic, semantic, associative links).
  * Scheduled and historical events.
  * Conversation transcripts.

---

## 5. Communication Layer

* **Protocol**:
  * **REST (HTTP)**: Standard CRUD operations, initial handshake, settings, state queries.
  * **WebSocket**: Realtime bi-directional messaging, streaming token responses, proactive events, and status updates.
* **Payload Structure**: Strict JSON schemas validated by Pydantic models on the backend and TypeScript interfaces on the frontend.
* **Future Extension**: Designed so that an Android client or companion device connects to the exact same WebSocket/REST interface without core refactoring.
