/* ---------------------------------------------------------------------
   Shared constants for all variants
   Based on interface-designer skill, GUI model
   --------------------------------------------------------------------- */

export const STAGES = ['Plan', 'Read', 'Edit', 'Test', 'Review'] as const;
export type Stage = (typeof STAGES)[number];

export const ROOTS = ['agent_workspace'] as const;

export interface TreeNode {
  type: 'folder' | 'file';
  name: string;
  special?: boolean;
  status?: 'modified' | 'new';
  children?: TreeNode[];
}

export const INITIAL_TREE: TreeNode[] = [
  {
    type: 'folder',
    name: '.agent',
    special: true,
    children: [
      { type: 'file', name: 'config.yaml' },
      { type: 'file', name: 'memory.db' },
    ],
  },
  {
    type: 'folder',
    name: 'src',
    children: [
      { type: 'file', name: 'index.ts', status: 'modified' },
      {
        type: 'folder',
        name: 'agent',
        children: [
          { type: 'file', name: 'planner.ts' },
          { type: 'file', name: 'executor.ts', status: 'new' },
        ],
      },
      {
        type: 'folder',
        name: 'tools',
        children: [
          { type: 'file', name: 'fs.ts' },
          { type: 'file', name: 'shell.ts' },
        ],
      },
      {
        type: 'folder',
        name: 'ui',
        children: [{ type: 'file', name: 'Button.tsx', status: 'new' }],
      },
    ],
  },
  {
    type: 'folder',
    name: 'tests',
    children: [{ type: 'file', name: 'planner.test.ts' }],
  },
  { type: 'file', name: 'package.json' },
  { type: 'file', name: 'README.md' },
];

export const COMMANDS = [
  { label: 'New session', hint: '', action: 'newChat' },
  { label: 'Open 2nd Brain', hint: '', action: 'openBrain' },
  { label: 'Open Web AI Bridge', hint: '', action: 'openWebAI' },
  { label: 'Open settings', hint: '', action: 'openSettings' },
];

/* NOTE: KIND_COLOR has been moved to platform-specific files:
   - web/colors.ts (Tailwind CSS classes)
   - cli/colors.ts (Ink colors)
   Use the appropriate one based on your platform.
*/

export type NodeKind = 'fact' | 'session' | 'pattern' | 'architecture';

export interface BrainNode {
  id: string;
  label: string;
  kind: NodeKind;
  x: number;
  y: number;
}

export interface ChatMessage {
  role?: 'user' | 'agent';
  kind?: 'toolcall' | 'human' | 'drawing' | 'log' | 'clarify' | 'agent_state' | 'task_result';
  text?: string;
  name?: string;
  status?: 'running' | 'done' | 'error';
  detail?: string;
  diff?: string[];
  engine?: string;
  model?: string;
  duration_ms?: number;
  /** structure_check fail — javob buzilgan bo'lishi mumkinligi haqida ogohlantirish. */
  warning?: string;
  runId?: string;
  /** Token-ustali chat — javob hali yozilmoqda (jonli kursor ko'rsatiladi). */
  streaming?: boolean;
  /** Agentning fikrlash (thinking/reasoning) matni — stream davomida jonli to'ldiriladi. */
  thinking?: string;
  /** Live-build preview: workspace path of the drawing (SVG/PNG) to render. */
  path?: string;
  /** Optional caption shown under the live-build preview card. */
  caption?: string;
  /** AGENTIK completion — zarurat turiga qarab qurilgan pipeline ish yakuni
   * (qaysi pipeline, bosqichlar, tool'lar, dvigatel...). Konversatsiya shu
   * ma'lumotlar bilan to'ldiriladi. */
  completion?: ChatCompletion;
}

/** Agentik work completion record — chat yakunida konversatsiyaga to'ldiriladi. */
export interface ChatCompletion {
  /** Tanlangan pipeline turi (chat/math/weather/draw/ui_build/web/code/...). */
  pipeline?: string;
  /** Pipeline nomi (odam o'qiydigan). */
  label?: string;
  /** Pipeline bosqichlari (plan/read/edit/test/review). */
  stages?: string[];
  /** Bajarilgan dvigatel (llm+tools / math-quick / weather-quick / cag / ...). */
  engine?: string;
  /** Bajarilgan tool'lar ro'yxati. */
  tools?: string[];
  /** So'rovdan aniqlangan mavzu obyekti (masalan 'olma', 'dashboard'). */
  subject?: string;
  /** Kod so'rovida aniqlangan framework (masalan 'React', 'Django'). */
  framework?: string;
  /** Kod so'rovida aniqlangan dasturlash tili. */
  language?: string;
  /** Kod so'rovida aniqlangan ma'lumotlar bazasi (masalan 'PostgreSQL', 'MongoDB'). */
  database?: string;
  /** Klassifikatsiya paytida rejalangan tool'lar (actual emas, reja). */
  planned_tools?: string[];
  /** Ish yakuni statusi (ok / refused). */
  status?: string;
  /** Davomiylik (ms). */
  duration_ms?: number;
  /** Chizma/rasm yaratilgan bo'lsa — workspace'dagi nisbiy yo'li. */
  image?: string;
  /** Birlashgan zaruratlar uchun qo'shimcha pipeline'lar (foydalanuvchi pipeline birinchi). */
  sub_pipelines?: string[];
}

export type MainView = 'chat' | 'preview' | 'brain';
export type SidebarMode = 'chats' | 'workspace' | 'agent';

// ── Agent state types ─────────────────────────────────────────────
export type AgentStateType = 'idle' | 'thinking' | 'planning' | 'executing' | 'verifying' | 'error' | 'paused';

export interface AgentTask {
  id: string;
  title: string;
  description: string;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'paused';
  priority: 'low' | 'normal' | 'high';
  created_at: number;
  started_at?: number;
  completed_at?: number;
  steps: AgentTaskStep[];
  result?: string;
  error?: string;
  tools_used: string[];
  duration_ms?: number;
}

export interface AgentTaskStep {
  id: number;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped';
  tool?: string;
  result?: string;
  duration_ms?: number;
}

export interface AgentCapability {
  name: string;
  icon: string;
  description: string;
  enabled: boolean;
  tools: string[];
}

export interface AgentState {
  state: AgentStateType;
  current_task?: string;
  current_step?: string;
  capabilities: AgentCapability[];
  task_queue: AgentTask[];
  completed_today: number;
  tools_available: number;
  memory_entries: number;
  uptime_seconds: number;
  auto_mode: boolean;
}

/* Sidebar chat item — real /api/chat/history'dan to'ldiriladi (mock yo'q). */
export interface SidebarChatItem {
  id: string;
  title: string;
  time: string;
  starred?: boolean;
  unread?: boolean;
  kind: 'chat' | 'artifact' | 'project';
}
