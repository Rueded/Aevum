export interface HealthData {
  status: string;
  app: string;
  version: string;
  database: string;
}

export interface MessageItem {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  audio_cache_key?: string | null;
  audio_status?: string | null;
  speech_bubbles?: string[];
  internal_decision?: Record<string, any> | null;
}

export interface ConversationDetail {
  id: string;
  created_at: string;
  updated_at: string;
  messages: MessageItem[];
}

export interface ConversationListItem {
  id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  last_message_preview?: string | null;
}

export interface MessageCreateResponse {
  message: MessageItem;
  assistant_response: MessageItem | null;
  assistant_status: string;
}

export interface CharacterStateResponse {
  name: string;
  age: number;
  occupation: string;
  background: string;
  mood: string;
  natural_mood: string;
  energy: number;
  stress: number;
  social_energy: number;
  current_activity: string;
  current_location: string;
  emotion: {
    type: string;
    intensity: number;
    summary: string;
  };
  status: string;
}

export interface RelationshipResponse {
  summary: string;
  familiarity: number;
  trust: number;
  comfort: number;
  affection: number;
  attachment: number;
  respect: number;
  familiarity_label: string;
  trust_label: string;
  comfort_label: string;
  affection_label: string;
  attachment_label: string;
}

export interface RelationshipUpdateRequest {
  familiarity?: number;
  trust?: number;
  comfort?: number;
  respect?: number;
  affection?: number;
  attachment?: number;
}

export interface LifeEventItem {
  id: string;
  title: string;
  description: string;
  event_type: string;
  occurred_at: string;
  significance: number;
}

export interface LifeGoalItem {
  id: string;
  title: string;
  description: string;
  status: string;
  progress?: number | null;
}

export interface LifeResponse {
  current_activity: string;
  current_location: string;
  status: string;
  recent_events: LifeEventItem[];
  active_goals: LifeGoalItem[];
}

export interface MemoryItem {
  id: string;
  category: string;
  subject_entity: "USER" | "AEVUM" | string;
  content: string;
  importance: number;
  confidence: number;
  emotional_weight: number;
  created_at: string;
  times_recalled: number;
}

export interface CharacterDebugResponse {
  character_id: string;
  state_version: number;
  relationship_version: number;
  raw_state: Record<string, any>;
  raw_relationship: Record<string, number>;
  raw_emotion: Record<string, any>;
  total_memories: number;
  total_events: number;
  decision_trace?: Record<string, any> | null;
  reality_history?: Array<{
    slot_key?: string;
    previous_value?: any;
    revised_value?: any;
    revision_reason?: string;
  }>;
}

export type FactAuthority = "USER_LOCKED" | "USER_CONFIGURED" | "AEVUM_CANONICAL" | "SYSTEM_BASELINE";
export type FactStatus = "CANONICAL" | "CANDIDATE" | "DISPUTED" | "FALSIFIED" | "EPHEMERAL";
export type FactSource = "USER_CONFIGURED" | "AEVUM_INFERRED" | "CONVERSATION" | "SYSTEM_BASELINE";
export type LedgerTier = "USER_EDITABLE" | "AEVUM_EMERGENT" | "SYSTEM_INTEGRITY";

export interface CoreFactItem {
  key: string;
  category: string;
  value: any;
  source: FactSource;
  authority: FactAuthority;
  status: FactStatus;
  epistemic_confidence: number;
  locked: boolean;
  explanation?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LedgerItem {
  key: string;
  category: string;
  value: any;
  tier: LedgerTier;
  source: FactSource;
  authority: FactAuthority;
  status: FactStatus;
  confidence: number;
  locked: boolean;
  explanation?: string | null;
  created_at: string;
  updated_at: string;
}

export interface RealityLedgerProjection {
  character_id: string;
  green_user_editable: LedgerItem[];
  yellow_aevum_emergent: LedgerItem[];
  red_system_integrity: LedgerItem[];
  total_facts: number;
  locked_count: number;
  candidate_count: number;
  average_confidence: number;
}

export interface CharacterCoreData {
  character_id: string;
  facts: Record<string, CoreFactItem>;
}

export interface ProfileResponse {
  character_id: string;
  core: CharacterCoreData;
  bible_version: number;
  behavioral_guidelines: string[];
  reasoning_guidelines: string[];
  flaws: string[];
  ledger: RealityLedgerProjection;
}

export interface UpdateCoreRequest {
  updates: Record<string, any>;
}

export interface FactMutationResponse {
  status: string;
  fact_key: string;
  fact?: CoreFactItem | null;
}

// =============================================================================
// Phase 8: Desktop Integration & Settings Types
// =============================================================================

export interface DesktopSettings {
  character_id: string;
  proactive_enabled: boolean;
  timezone: string;
  quiet_hours_enabled: boolean;
  quiet_hours_start: string | null;
  quiet_hours_end: string | null;
  max_daily_reach_outs: number;
  min_cooldown_minutes: number;
  idle_awareness_enabled: boolean;
  idle_threshold_seconds: number;
  user_country?: string;
  dnd_until: string | null;
  updated_at: string | null;
}

export interface DesktopSettingsUpdate {
  proactive_enabled?: boolean;
  timezone?: string;
  quiet_hours_enabled?: boolean;
  quiet_hours_start?: string;
  quiet_hours_end?: string;
  max_daily_reach_outs?: number;
  min_cooldown_minutes?: number;
  idle_awareness_enabled?: boolean;
  idle_threshold_seconds?: number;
  user_country?: string;
}

export interface SetDNDPayload {
  duration_minutes?: number;
  clear?: boolean;
}

export interface NotificationHistoryItem {
  id: string;
  character_id: string;
  conversation_message_id: string;
  trigger_type: string;
  idempotency_key: string;
  title: string;
  body: string;
  status: string;
  claimed_by: string | null;
  claimed_at: string | null;
  suppression_reason: string | null;
  created_at: string;
  delivered_at: string | null;
  interacted_at: string | null;
}

export interface NotificationItem {
  id: string;
  character_id: string;
  conversation_message_id: string;
  trigger_type: string;
  idempotency_key: string;
  title: string;
  body: string;
  status: string;
  claimed_by?: string | null;
  claimed_at?: string | null;
  suppression_reason?: string | null;
  context_metadata?: string | null;
  created_at: string;
  delivered_at?: string | null;
  interacted_at?: string | null;
}

export interface HeartbeatPayload {
  client_id: string;
  client_timestamp: string;
  is_idle: boolean;
  idle_seconds: number;
  window_focused: boolean;
  app_active?: boolean;
}

export interface HeartbeatResponse {
  status: string;
  awareness_enabled: boolean;
  observed_at: string;
  server_time: string;
}

// =============================================================================
// Phase 10: Voice & Audio Types
// =============================================================================

export interface VoiceMessageCreate {
  audio_base64: string;
  format?: string;
  sample_rate_hz?: number;
  channels?: string;
  duration_ms?: number;
  user_consent_granted: boolean;
  input_mode?: string;
  synthesize_reply_audio?: boolean;
  voice_id?: string | null;
}

export interface VoiceMessageResponse {
  message: MessageItem;
  transcribed_text: string;
  assistant_response: MessageItem | null;
  assistant_status: string;
  audio_data_base64: string | null;
  audio_cache_key: string | null;
  audio_status: "success" | "failed" | "unavailable" | "skipped" | string;
}

export interface VoiceTTSRequest {
  text: string;
  voice_id?: string | null;
  desired_format?: string;
  epistemic_cue?: string;
  character_id?: string;
}

export interface VoiceTTSResponse {
  status: string;
  audio_base64: string | null;
  cache_key: string | null;
  duration_ms: number;
  error_message: string | null;
}

export interface VoiceSTTRequest {
  audio_base64: string;
  format?: string;
  sample_rate_hz?: number;
  channels?: string;
  duration_ms?: number;
  user_consent_granted: boolean;
  input_mode?: string;
}

export interface VoiceSTTResponse {
  status: string;
  transcribed_text: string | null;
  error_message: string | null;
}

export interface BiographicalFactProjection {
  id: string;
  domain: string;
  attribute_key: string;
  attribute_value: string;
  era: string;
  canonical_status: string;
  recall_level: string;
  provenance: string;
}

export interface LifeEventProjection {
  id: string;
  era: string;
  domain: string;
  headline: string;
  summary: string;
  canonical_status: string;
  recall_level: string;
  qualia_ids: string[];
}

export interface PersonalPreferenceProjection {
  id: string;
  category: string;
  object_name: string;
  affinity: string;
  era_acquired: string;
  causal_state: string;
  causal_relation_id?: string | null;
}

export interface QualiaAnchorProjection {
  id: string;
  sensory_modality: string;
  description: string;
  emotional_coloring?: string | null;
}

export interface SocialContactProjection {
  id: string;
  display_name: string;
  relation_role: string;
  era_first_met: string;
  is_user: boolean;
}

export interface SharedHistoryEpisodeProjection {
  id: string;
  episode_type: string;
  title: string;
  summary: string;
  session_anchor: string;
  key_learnings: string[];
  recall_level: string;
  created_at_era: string;
}

export interface LongitudinalMemoryResponse {
  facts: BiographicalFactProjection[];
  life_events: LifeEventProjection[];
  preferences: PersonalPreferenceProjection[];
  qualia: QualiaAnchorProjection[];
  contacts: SocialContactProjection[];
  shared_episodes: SharedHistoryEpisodeProjection[];
  relational_dynamics: Record<string, number>;
}

// =============================================================================
// Phase 13: Realtime Voice Call & Product Shell Types (ADR-024)
// =============================================================================

export type CallMode = "IDLE" | "CONNECTING" | "ACTIVE" | "RECONNECTING" | "ENDED";

export interface CallSessionResponse {
  session_id: string;
  conversation_id: string;
  status: string;
  active_generation_id: number;
  created_monotonic_at: number;
}

export interface CreateCallSessionRequest {
  conversation_id: string;
  session_id?: string | null;
}

export type RealtimeControlEventType =
  | "SESSION_STARTED"
  | "SESSION_RECONNECT"
  | "SESSION_CLOSED"
  | "TRANSCRIPT_EVENT"
  | "TURN_EVENT"
  | "BARGE_IN"
  | "INTERRUPT_FLUSH"
  | "AUDIO_FRAME"
  | "VISUAL_DIRECTIVE"
  | "ERROR_EVENT"
  | "HEARTBEAT";

export interface TranscriptEventPayload {
  event_type: "TRANSCRIPT_EVENT";
  session_id: string;
  turn_id: string;
  lifecycle_state: "PARTIAL" | "FINAL_PENDING_COMMIT" | "COMMITTED";
  text: string;
  is_final: boolean;
  utterance_boundary_confirmed: boolean;
  provider_name: string;
}

export interface VisualDirectivePayload {
  event_type: "VISUAL_DIRECTIVE";
  session_id: string;
  expression_archetype: string;
  intensity: number;
  transition_duration_ms: number;
  mouth_open_override?: number | null;
  is_speaking: boolean;
}

export interface InterruptFlushPayload {
  event_type: "INTERRUPT_FLUSH";
  session_id: string;
  generation_id: number;
  reason: string;
}

export interface RealtimeErrorPayload {
  event_type: "ERROR_EVENT";
  session_id: string;
  error_kind: string;
  message: string;
  recoverable: boolean;
  affected_generation_id?: number | null;
}

// =============================================================================
// Phase 17: Character Genesis & Blueprint Types
// =============================================================================

export type SemanticEpistemicDepth =
  | "PROFICIENT_LIVED"
  | "FAMILIAR"
  | "HEARD_OF_AWARE"
  | "CURIOUS_BEGINNER"
  | "UNFAMILIAR_OPEN";

export interface EpistemicSeedDeclaration {
  topic: string;
  depth: SemanticEpistemicDepth;
  detail_note?: string;
}

export type SemanticFamiliarityLevel =
  | "STRANGER"
  | "ACQUAINTED"
  | "FAMILIAR"
  | "INTIMATE";

export type SemanticTrustLevel =
  | "CAUTIOUS"
  | "OPEN_NEUTRAL"
  | "INHERENT_TRUST";

export interface CharacterCreationPayload {
  name: string;
  age: number;
  occupation: string;
  lifestyle_rhythm: string;
  background_story: string;
  core_traits: string[];
  speaking_style: string;
  epistemic_seeds: EpistemicSeedDeclaration[];
  innate_boundaries: string[];
  relationship_archetype: string;
  familiarity_level: SemanticFamiliarityLevel;
  trust_level: SemanticTrustLevel;
  meeting_backstory: string;
}

export interface CharacterCreationResponse {
  success: boolean;
  character_id: string;
  blueprint_version: number;
  relationship_archetype: string;
  initial_awakening_greeting: string;
  snapshot: Record<string, unknown>;
}

export interface GenesisPresetsResponse {
  archetype_presets: Array<{
    key: string;
    label: string;
    default_familiarity: SemanticFamiliarityLevel;
    default_trust: SemanticTrustLevel;
    description: string;
    suggested_backstory: string;
  }>;
  trait_presets: string[];
  speaking_style_presets: Array<{
    key: string;
    label: string;
    description: string;
    sample: string;
  }>;
  lifestyle_presets: Array<{
    key: string;
    label: string;
    description: string;
  }>;
  epistemic_depth_options: Array<{
    key: SemanticEpistemicDepth;
    label: string;
    description: string;
  }>;
  familiarity_options: Array<{
    key: SemanticFamiliarityLevel;
    label: string;
    description: string;
  }>;
  trust_options: Array<{
    key: SemanticTrustLevel;
    label: string;
    description: string;
  }>;
}

export interface CharacterBlueprintResponse {
  character_id: string;
  version: number;
  display_name: string;
  identity_summary: string;
  lifestyle_rhythm: string;
  core_traits: string[];
  communication_style: string[];
  speaking_style?: string | string[];
  innate_boundaries: string[];
  created_at: string;
  updated_at: string;
}

export interface BlueprintUpdateRequest {
  display_name?: string;
  identity_summary?: string;
  lifestyle_rhythm?: string;
  core_traits?: string[];
  communication_style?: string[];
  speaking_style?: string[] | string;
  innate_boundaries?: string[];
}

export interface ResolveLocalModelResponse {
  success: boolean;
  name: string;
  avatar_data_url?: string | null;
  model_json_path?: string | null;
  model_serve_url?: string | null;
  message: string;
}

