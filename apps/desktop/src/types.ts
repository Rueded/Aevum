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
}

export interface ConversationDetail {
  id: string;
  created_at: string;
  updated_at: string;
  messages: MessageItem[];
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

