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
}
