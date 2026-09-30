use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::State;

pub struct AppState {
    pub memory: Mutex<Vec<MemoryEntry>>,
    pub backend_url: Mutex<Option<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MemoryEntry {
    pub id: String,
    pub key: String,
    pub value: String,
    pub timestamp: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
    pub timestamp: i64,
}

#[tauri::command]
fn get_memory(state: State<AppState>, key: String) -> Result<Option<MemoryEntry>, String> {
    let memory = state.memory.lock().map_err(|e| e.to_string())?;
    Ok(memory.iter().find(|e| e.key == key).cloned())
}

#[tauri::command]
fn set_memory(state: State<AppState>, key: String, value: String) -> Result<MemoryEntry, String> {
    let mut memory = state.memory.lock().map_err(|e| e.to_string())?;
    let entry = MemoryEntry {
        id: uuid::Uuid::new_v4().to_string(),
        key,
        value,
        timestamp: chrono::Utc::now().timestamp(),
    };
    memory.push(entry.clone());
    Ok(entry)
}

#[tauri::command]
fn list_memory(state: State<AppState>) -> Result<Vec<MemoryEntry>, String> {
    let memory = state.memory.lock().map_err(|e| e.to_string())?;
    Ok(memory.clone())
}

#[tauri::command]
fn clear_memory(state: State<AppState>) -> Result<(), String> {
    let mut memory = state.memory.lock().map_err(|e| e.to_string())?;
    memory.clear();
    Ok(())
}

#[tauri::command]
fn set_backend_url(state: State<AppState>, url: String) -> Result<(), String> {
    let mut backend_url = state.backend_url.lock().map_err(|e| e.to_string())?;
    *backend_url = Some(url);
    Ok(())
}

#[tauri::command]
fn get_backend_url(state: State<AppState>) -> Result<Option<String>, String> {
    let backend_url = state.backend_url.lock().map_err(|e| e.to_string())?;
    Ok(backend_url.clone())
}

#[tauri::command]
async fn send_chat_message(
    state: State<'_, AppState>,
    _message: String,
) -> Result<ChatMessage, String> {
    let backend_url = state.backend_url.lock().map_err(|e| e.to_string())?.clone();
    let detail = if backend_url.is_some() {
        "Tauri chat bridge is not implemented; use the FastAPI web bridge"
    } else {
        "Igris backend is offline"
    };
    Err(detail.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .manage(AppState {
            memory: Mutex::new(Vec::new()),
            backend_url: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![
            get_memory, set_memory, list_memory, clear_memory,
            set_backend_url, get_backend_url, send_chat_message,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
