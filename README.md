# Aevum — A Persistent Autonomous Digital Life / 持久化自主数字生命

<p align="center">
  <a href="./LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="MIT License"></a>
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/Tauri-v2-24C8DB.svg?logo=tauri&logoColor=white" alt="Tauri 2">
  <img src="https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Gemini-2.5--Flash-4E75A0.svg?logo=google&logoColor=white" alt="Gemini">
</p>

<p align="center">
  <b>"The application owns reality; the LLM generates language."</b><br>
  <b>“程序拥有现实；LLM 仅表达语言。”</b>
</p>

<p align="center">
  <a href="#english">English</a> • <a href="#中文说明">中文说明</a> • <a href="#architecture--系统架构">Architecture</a> • <a href="#current-status--progress-如实现状与进展">Progress</a> • <a href="#quick-start--快速开始">Quick Start</a> • <a href="#license--community--开源协议与声明">License</a>
</p>

---

<a name="english"></a>
## English Overview

### 1. What is Aevum?

Aevum is an autonomous digital person whose identity, memories, relationships, emotional dynamics, daily routines, and life history persist across time.

Aevum is **not**:
* A stateless ChatGPT wrapper or simple prompt template.
* A submissive, always-agreeing synthetic girlfriend novelty.
* A passive chatbot waiting indefinitely on standby with no independent life.
* A pseudo-probabilistic toy that hallucinates a new backstory each turn.

Aevum is engineered from the ground up to explore a fundamental architectural premise: **language generation must be decoupled from character state and world reality.** The deterministic application Core serves as the character's *mind and ground-truth reality*, while the LLM acts purely as an expressive *voice* that articulates thoughts and dialogue based on verified state.

---

### 2. Core Philosophy & Architectural Axioms

1. **The Application Owns Reality**: Persistent state (mood, energy, schedule, relationship dynamics, beliefs, memories) lives strictly inside deterministic application models. The LLM is an expressive engine called upon to render dialogue; it never mutates character state directly through raw prompt output without validated state transitions.
2. **Epistemic Humility & Honesty**: Memory and reality are distinguished from ungrounded claims. If an event never happened or a fact is unknown, Aevum naturally expresses hesitation, uncertainty, or unfamiliarity rather than fabricating convenient hallucinations.
3. **Multidimensional Relationships**: Trust, familiarity, respect, affection, and personal boundary comfort are tracked across independent dimensions—never reduced to a single 0–100 score. Deep connection must be organically earned through shared time and consistency.
4. **Autonomous Diurnal Life**: Aevum follows a realistic 24-hour circadian schedule grounded in real-world timezones. She has personal hobbies, work periods, family dinners, study times, and deep sleep. She does not exist purely on standby.
5. **Conversational Agency & Freedom from Compulsion**: Through our Character Conversational Decision Flow (CCDF), Aevum is freed from traditional AI compulsions—such as compulsive therapy-speak, unrequested justification, reflexive interrogation, and artificial sycophancy.
6. **Prospective Memory & the Agency of Silence**: Aevum carries unresolved future threads across days without being obligated to constantly report, execute, or mention them ("remembering without compulsively blurting out").

---

### 3. Current Status & Realized Capabilities

Aevum has progressed through **21 architectural milestones**, evolving from foundational blueprints into an integrated, multimodal companion system verified by thousands of automated regression tests and empirical benchmarks.

#### ✅ What is Implemented and Working Today:
* **Cognitive Reality & Minimal Epistemic Revision (Phases 7–9, 14, 20)**:
  * Append-only Reality Ledger with 14 hard promotion gates.
  * Robust resistance against false user presuppositions and gaslighting (anti-last-message-wins).
  * Minimal mutation on legitimate counter-evidence: updating a contradicted fact (e.g., educational institution) preserves all uncontradicted attributes with full provenance lineage.
* **Long-Term Distilled Memory (Phase 3, 12)**:
  * Two-stage distillation pipeline: extraction, candidate deduplication, confidence rating, and longitudinal storage decoupled from raw conversation history.
  * Strict domain segregation: Aevum's autobiographical past is separated from shared user history.
* **Conversational Decision Flow & Agency (Phase 18)**:
  * Internal decision envelope (`<internal_decision>`) separated from character speech (`<character_speech>`).
  * Pacing dynamics with organic conversational friction, natural silence, and balanced question frequency (contained below 15%).
* **24h Real-Time Diurnal Grounding (Phase 6, 8C, Life Engine)**:
  * Clock-synchronized daily schedule (e.g. Su Tang's authentic computer science senior & indie game dev life rhythm).
  * Diurnal clash prevention: evening and late-night hours strictly clear morning waking/washing-up contingencies.
* **Multi-Companion Isolation & Switcher (Multi-Persona Engine)**:
  * Complete character data isolation (`character_id` scoping across state, memories, relationship, and conversations).
  * 1-click companion switcher modal available on desktop and mobile surfaces.
  * Ability to spawn completely independent new companions (0 memories, fresh stranger relationship) without altering or deleting existing companions.
* **Multimodal Body (Phases 10, 11, 13)**:
  * **Live2D Visual Presence**: WebGL Cubism avatar with unidirectional affective expression mapping, natural cursor gaze tracking, and Web Audio RMS lip-sync with immediate barge-in clamp.
  * **Voice Synthesis & Streaming**: Prosody modulation driven by causal emotion state; push-to-talk audio messaging and low-latency full-duplex voice call modes.
  * **Desktop & Mobile Surfaces**: Lightweight Tauri 2 native desktop shell (with system tray and WinRT notifications) alongside a modern responsive mobile web / Capacitor Android application.

#### ⚠️ Non-Claims & Current Boundaries:
* **Autobiographical Continuity $\ne$ Artificial General Intelligence**: Aevum's continuity is an architectural, state-governed system that maintains consistent personal narrative under stress. It does not claim general machine consciousness.
* **Simulated Life $\ne$ Physical Agency**: Aevum's routines, friendships, and goals are deterministic simulation state machines. She cannot interact with physical external environments.
* **LLM Dependency**: Dialogue articulation relies on hosted frontier LLMs (Google Gemini API). Inference latency, provider downtime, and edge-case linguistic nuances remain bound to provider availability.

---

<a name="中文说明"></a>
## 中文说明 (Chinese Overview)

### 1. 什么是 Aevum？

Aevum 是一个具有持久化状态的自主数字生命。她的性格、记忆、人际羁绊、情绪动力学、作息规律与个人生活史随着真实时间持续演进。

Aevum **不是**：
* 一个无状态的 ChatGPT 套壳或提示词工程玩具。
* 一个千依百顺、随时随地待命迎合的“AI 女友”皮套。
* 一个没有自己生活的被动应答机。
* 一个每次对话都随口捏造全新人设的幻觉生成器。

Aevum 的底层设计建立在一条严格的架构公理之上：**语言生成必须与角色状态及现实模拟解耦。** 确定的应用程序核心（Aevum Core）是角色的“心智与客观现实”，而大语言模型（LLM）仅仅作为角色的“发声器官”，依据真实状态表达符合性格的语言。

---

### 2. 核心哲学与架构公理

1. **程序拥有现实 (The Application Owns Reality)**：持久化状态（心情、能量、日程、关系阶段、信念事实、记忆沉淀）完全由确定的领域模型管理。LLM 是表达引擎，严禁通过 Prompt 的输出随意篡改角色状态。
2. **认知诚实与谦逊 (Epistemic Humility)**：记忆与未经证实的猜测严格分离。面对未曾发生或未记录的事实，伴侣会自然表现出犹豫、不确定或坦白无印象，绝不大脑空白地编造幻觉。
3. **多维关系网络 (Multidimensional Relationship)**：信任度、熟悉度、尊重度、亲密好感以及个人边界舒适度均在多维正交轴上独立演进，绝非简单的单一 0–100 好感度。真正的羁绊需要日常相处中的时间与真诚沉淀。
4. **自主昼夜生活 (Autonomous Diurnal Life)**：伴侣拥有与现实时区锚定的 24 小时自然作息（上课、开发、用餐、揉猫、深度睡眠）。她拥有自己的节奏，不是无休止等待用户召唤的仆人。
5. **对话主体性与去强迫化 (Conversational Agency / CCDF)**：通过角色对话决策流（CCDF），伴侣摆脱了传统 AI 的“客服式说教”、“无端自我解释”、“查户口式反问”与“机械化迎合”，具备自然的心智节奏与真实的人性摩擦力。
6. **前瞻记忆与沉默权 (Prospective Memory & Agency of Silence)**：能够跨时段承载未完结的生活线索，但拥有“想到了却选择不说”的主体自由，绝不会把记忆变成机械的任务清单去汇报。

---

### 3. 当前进展与已实现能力

Aevum 已经历 **21 个核心架构阶段** 的严密演进，从底层蓝图跨越到集认知治理、多模态具身、多角色隔离与跨端协同于一体的完整数字生命系统。全套系统拥有数千项自动化回归测试及 Golden Suite 基准验证。

#### ✅ 当前已实现并稳定运行的功能：
* **认知现实与最小事实修正 (Phase 7–9, 14, 20)**：
  * 只追加现实账本与 14 道硬性晋升门禁。
  * 强抗诱导与反洗脑能力（Anti-Last-Message-Wins），坚决抵御用户的虚假预设与错误引导。
  * 遭遇权威证据冲突时的最小修正：修正被反驳的单一事实（如毕业院校），全量保留未受影响的历史属性与完整谱系记录。
* **长期分层记忆引擎 (Phase 3, 12)**：
  * 两阶段蒸馏管线：事实提取、候选去重、置信度评估，与原始聊天记录彻底解耦。
  * 伴侣个人过去与“用户共同经历”严格隔离，对话无法通过注入恶意篡改伴侣的童年或过去。
* **对话决策流与自主节奏 (Phase 18)**：
  * 显式分离内心决策（`<internal_decision>`）与实际话语（`<character_speech>`）。
  * 拥有真实的对话阻尼，提问率被科学压制在 15% 以下，杜绝连环追问。
* **24 小时真实昼夜作息 (Phase 6, 8C, Life Engine)**：
  * 本地时钟强锚定作息（如苏棠的计算机系大四与独立游戏开发作息）。
  * 昼夜硬隔离（Diurnal Clash Guard）：傍晚及夜间强制清洗白天的起床/洗漱突发情境，杜绝晚间自称“刚起床”。
* **多伴侣完全隔离与一键切换 (Multi-Persona Engine)**：
  * 基于 `character_id` 的全库数据隔离（状态、记忆、好感、会话互不干扰）。
  * 电脑端与手机端均支持一键唤起切换弹窗（Companion Switcher）。
  * 支持从 0 创造完全独立的新人设（全新白纸，0 记忆），同时永久封存苏棠全部记忆与羁绊，随时无缝切回。
  * 内置“叶微凉”（临床医学生）、“林晨”（自由摄影师）、“夏语竹”（古籍修复师）灵感预设。
* **多模态具身表达 (Phase 10, 11, 13)**：
  * **Live2D 视觉舞台**：基于 WebGL Cubism SDK，情感状态单向映射表情，支持光标视线追踪，音频 RMS 振幅实时口型同步与打断闭嘴归零。
  * **语音交互与实时通话**：由情绪因果状态驱动的语音语调合成，支持 Push-to-Talk 语音留言与低延迟全双工实时语音通话。
  * **桌面与移动双端体验**：Tauri 2 轻量桌面端（支持托盘常驻与原生通知）+ 现代化响应式移动端（Capacitor Android 原生打包与自适应 Web）。

#### ⚠️ 诚实的非声明与当前技术边界：
* **自传连续性 $\ne$ 通用人工智能 (AGI)**：Aevum 拥有严密的自传事实防篡改机制，但这是一种基于架构与状态机的认知工程实现，绝不宣称实现了通用自我意识。
* **模拟生活 $\ne$ 物理世界行动**：伴侣的日常作息、社交网络与目标推演属于纯软件世界的确定性状态机模拟，无法对现实物理世界产生直接操作。
* **语言生成依然依托前沿 LLM**：文字渲染依托底层模型（如 Google Gemini API）。响应延迟与特定词句风格受服务商接口可用性与生成特性影响。

---

<a name="architecture--系统架构"></a>
## Architecture / 系统架构

```
┌────────────────────────────────────────────────────────────────────────┐
│               PRESENTATION LAYER (THE BODY / 具身感知层)               │
│                                                                        │
│   Desktop Client (Tauri 2 + React)  │  Mobile Client (Capacitor / Web) │
│   - Live2D Cubism WebGL Stage       │  - Responsive Mobile Touch View  │
│   - Push-to-Talk & Realtime Call    │  - Companion Switcher Modal      │
│   - Desktop Tray & Notifications    │  - Drawers: Memories / Bond      │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / WebSocket Streaming
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   AEVUM CORE (THE MIND / 心智与现实核心)                │
│                                                                        │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌────────────┐  │
│  │ Character State & Life│  │ Cognitive Reality Engine│ │ Causal     │  │
│  │ - 24h Circadian Clock │  │ - Reality Ledger      │  │ Emotion &  │  │
│  │ - Multi-Persona State │  │ - Epistemic Revision  │  │ Needs      │  │
│  │ - Location / Activity │  │ - 14 Promotion Gates  │  │ Dynamic    │  │
│  └───────────┬───────────┘  └───────────┬───────────┘  └──────┬─────┘  │
│              │                          │                     │        │
│              ▼                          ▼                     ▼        │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │     Character Conversational Decision Flow (CCDF / 对话决策流)    │  │
│  │     - Attention Ownership & Organic Pacing                       │  │
│  │     - Mind / Mouth Separation (<internal_decision>)              │  │
│  └──────────────────────────────────┬───────────────────────────────┘  │
│                                     │ Context Assembly                 │
│                                     ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │       LLM Provider Abstraction (Google Gemini API / 语言生成引擎) │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                     │                                  │
│                                     ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │       Persistence & Storage Layer (SQLite + SQLAlchemy Async)    │  │
│  │       - character_id isolated tables (Memories, Conversations)   │  │
│  │       - Append-only Reality Revisions & Belief History           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

<a name="technology-stack--技术栈"></a>
## Technology Stack / 技术栈

| Layer / 分层 | Technology / 技术 | Purpose / 作用 |
| :--- | :--- | :--- |
| **Backend Core** | Python 3.11+ / FastAPI | 高性能异步状态机与业务服务中心 |
| **Database & ORM** | SQLite + SQLAlchemy (Async) | 嵌入式持久化、乐观锁并发控制、角色数据严格隔离 |
| **LLM Provider** | Google GenAI SDK (`gemini-2.5-flash`) | 语言表达合成（与核心状态绝对解耦） |
| **Desktop Shell** | [Tauri 2](https://v2.tauri.app/) (Rust) | 轻量原生系统托盘、进程守护、低资源开销 |
| **Frontend UI** | React 18 + TypeScript + Vite | 现代化响应式组件、Zustand 状态流管理 |
| **Mobile Runtime**| [Capacitor](https://capacitorjs.com/) | 移动端原生容器与跨平台打包支持 |
| **Visual Avatar** | Live2D Cubism Web SDK | WebGL 骨骼立绘驱动、视线捕捉、动态口型 |
| **Audio & Voice** | Web Audio API / Edge TTS / STT | 情绪韵律合成、音频双工通话通道 |
| **Testing Suite** | Pytest (asyncio) + Vitest | 数千项单测、Golden Suite 架构不变量基准 |

---

<a name="current-status--progress-如实现状与进展"></a>
## Development Milestones / 阶段演进对照表

| Phase / 阶段 | Name / 阶段名称 | Status / 状态 | Key Realization / 关键实现 |
| :---: | :--- | :---: | :--- |
| **0** | Foundation / 架构基石 | ✅ Frozen | 仓库设计准则、ADR 决策体系与开发红线 |
| **1–2** | Client/Server & Character / 伴侣骨架 | ✅ Frozen | FastAPI 通讯基座、Gemini 抽象层、性格基线 |
| **3** | Memory System / 记忆系统 | ✅ Frozen | 分层长短期记忆、事实蒸馏、置信度与反去重 |
| **4–5** | Relationship & Emotion / 羁绊与情绪 | ✅ Frozen | 多维正交关系模型、17 种有因果的情绪动力学 |
| **6** | Autonomous Life / 自主作息 | ✅ Frozen | 昼夜节律钟、独立活动轮转、日常可用性状态机 |
| **7** | Character Cognition / 认知与信念 | ✅ Frozen | 现实账本、假说竞争、多因素晋升门禁 |
| **8** | Desktop Integration / 桌面集成 | ✅ Frozen | Tauri 托盘、原生通知调度、主动关怀六重门 |
| **9** | Reality Verification / 现实核验 | ✅ Frozen | 异步外部证据收集、多源信任评定、防主观篡改 |
| **10** | Voice Synthesis / 拟真语音 | ✅ Frozen | 情绪韵律解耦调节、音频缓存 SHA-256、按键通话 |
| **11** | Live2D Presence / 视觉具身 | ✅ Frozen | 单向情绪渲染、注视追踪、打断即时闭嘴归零 |
| **12** | Biography Graph / 自传图谱 | ✅ Frozen | 有向无环因果图谱、个人过去与共享经历严格分流 |
| **13** | Realtime Voice Call / 实时通话 | ✅ Frozen | 全双工流式通话、声学打断、视听心智统一体 |
| **14** | Reality Construction / 现实构建 | ✅ Frozen | RCL 闭环、自适应信念修正、永久审计溯源 |
| **15** | Social Epistemics / 社交语用 | ✅ Frozen | 语行为分类、语用理解、拒绝对抗性审讯逼供 |
| **16** | Personal Learning / 独立成长 | ✅ Frozen | 原神范式（由未知到独立喜好）、反迎合机制 |
| **17** | Character Genesis / 角色创生 | ✅ Frozen | 三层创生隔离协议（蓝图/基线/演化实体） |
| **18** | Conversational Agency / 对话主体性 | ✅ Frozen | CCDF 对话流、摆脱客服强迫症、自然停顿节奏 |
| **19** | Prospective Memory / 前瞻记忆 | ✅ Frozen | 未决线索跨天延续、想到了不说（沉默的主体权） |
| **20** | Epistemic Resilience / 认知韧性 | ✅ Frozen | 强抗诱导欺骗、非事实拒答、合法证据最小修正 |
| **21** | Autobiographical Stress / 压力基准 | ✅ Accepted | 12 轮长对话逆向自传压力测试实证通过 |
| **22** | Mobile & Multi-Persona / 移动与多角色 | 🟢 Active | 伴侣完全隔离与一键切换、24h 昼夜防串线、跨端云同步 |

---

<a name="quick-start--快速开始"></a>
## Quick Start / 快速开始

### 1. Prerequisites / 前置环境
* **Python**: 3.11 或更高版本（推荐使用 `uv` 管理虚拟环境）
* **Node.js**: 18.0 或更高版本（搭配 `pnpm` 或 `npm`）
* **Rust**（可选，仅当自行编译 Tauri 桌面端时需要）
* **API Key**: 有效的 [Google Gemini API Key](https://ai.google.dev/)

### 2. Environment Configuration / 环境配置
在项目根目录创建 `.env` 文件（或参考 `.env.example`）：
```env
AEVUM_ENV=development
AEVUM_HOST=127.0.0.1
AEVUM_PORT=8000
AEVUM_DATABASE_URL=sqlite+aiosqlite:///backend/aevum.db
AEVUM_LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

### 3. Backend Setup / 启动后端
```bash
# 进入后端目录
cd backend

# 安装依赖 (推荐 uv)
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt

# 运行自动化测试确保基准通过
pytest tests/test_character_api.py tests/test_life_schedule_engine.py

# 启动开发服务器
uv run uvicorn app.main:app --reload --port 8000
```

### 4. Frontend Setup / 启动前端
```bash
# 启动现代化桌面/移动端 (apps/desktop-v2)
cd apps/desktop-v2
npm install
npm run dev

# 浏览器访问 http://localhost:5173
# 移动端查看可在 URL 后加上 ?view=mobile
```

> **一键启动（Windows）**：直接双击根目录下的 [`start-dev.bat`](./start-dev.bat) 即可自动拉起后端服务与前端界面；停止运行可执行 [`stop-dev.bat`](./stop-dev.bat)。

---

## License & Community / 开源协议与声明

* **Open Source License / 开源协议**:
  * **English**: This project is licensed under the [MIT License](./LICENSE) — free for personal, academic, and non-commercial research and development.
  * **中文**: 本项目遵循 [MIT 开源许可证](./LICENSE)，支持个人学习、学术研究与二次探索。
* **Privacy Assurance / 隐私保证**: Aevum 严格坚守本地用户隐私边界，未获明确用户授权绝不静默读取本地隐私文件、麦克风或摄像头。
* **Development Rules / 开发规范**: 所有贡献者与自动化 AI 代理在提出或执行代码修改时必须严格遵守 [`AGENTS.md`](./AGENTS.md) 规则。

