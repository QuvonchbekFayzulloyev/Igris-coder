import { invoke } from '@tauri-apps/api/core';

// Types matching Rust structs
export interface MemoryEntry {
  id: string;
  key: string;
  value: string;
  timestamp: number;
}

export interface ChatMessage {
  role: string;
  content: string;
  timestamp: number;
}

// Memory commands
export async function getMemory(key: string): Promise<MemoryEntry | null> {
  return invoke('get_memory', { key });
}

export async function setMemory(key: string, value: string): Promise<MemoryEntry> {
  return invoke('set_memory', { key, value });
}

export async function listMemory(): Promise<MemoryEntry[]> {
  return invoke('list_memory');
}

export async function clearMemory(): Promise<void> {
  return invoke('clear_memory');
}

// Backend integration commands
export async function setBackendUrl(url: string): Promise<void> {
  return invoke('set_backend_url', { url });
}

export async function getBackendUrl(): Promise<string | null> {
  return invoke('get_backend_url');
}

export async function sendChatMessage(message: string): Promise<ChatMessage> {
  return invoke('send_chat_message', { message });
}
