export interface ProviderConfig {
  host?: string;
  model?: string;
  temperature?: number;
}

export interface OpenRouterConfig extends ProviderConfig {
  api_key_set?: boolean;
}

export interface SettingsResponse {
  gateway: { provider: string };
  ollama: ProviderConfig;
  lmstudio: ProviderConfig;
  openrouter: OpenRouterConfig;
}

export interface SettingsUpdatePayload {
  provider?: string;
  ollama?: Partial<ProviderConfig>;
  lmstudio?: Partial<ProviderConfig>;
  openrouter?: Partial<ProviderConfig> & { api_key?: string };
}

export interface Skill {
  name: string;
  description: string;
  pipeline_stage: string;
  triggers: string[];
}

export interface ProjectsResponse {
  projects: string[];
  active: string | null;
}

export interface McpToolsResponse {
  tools: string[];
}

export interface ProvidersResponse {
  providers: string[];
}

export interface ModelsRequest {
  provider: string;
  host: string;
}

export interface ModelsResponse {
  models: string[];
  error?: string;
}

export interface ProviderTestRequest {
  provider: string;
  host: string;
  model?: string;
  api_key?: string;
}

export interface ProviderTestResponse {
  ok: boolean;
  error?: string;
  latency_ms?: number;
}

export interface ChatResponse {
  response: string;
  needs_clarification: boolean;
  clarifying_question: string;
  iterations: number;
  trace: StageEvent[];
  prompt_tokens: number;
  completion_tokens: number;
  cost_usd: number;
}

export interface StageEvent {
  stage: string;
  detail: string;
}

export interface PreviewData {
  tester_name: string;
  success: boolean;
  summary: string;
  details: string[];
  errors: string[];
  artifacts: string[];
}

export type WsEvent =
  | { type: "stage"; stage: string; detail: string }
  | {
      type: "final";
      response: string;
      needs_clarification: boolean;
      clarifying_question: string;
      iterations: number;
      prompt_tokens: number;
      completion_tokens: number;
      cost_usd: number;
    }
  | { type: "error"; detail: string }
  | { type: "preview" } & PreviewData;

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant" | "clarify";
  content: string;
  timestamp: number;
}

// The ordered stage keys RepromptLoop emits, in the order a single-branch
// run normally passes through them -- drives the Loop Tracker's fixed
// slot layout so it doesn't jump around as different stages arrive.
export const KNOWN_STAGES = [
  "snapshot",
  "intent",
  "complexity",
  "loop_plan",
  "skills",
  "gather",
  "spec",
  "attempt_1",
  "review_1",
  "attempt_2",
  "review_2",
] as const;
