// igris desktop shell.
//
// Current approach: spawns the already-installed `igris` Python backend
// (via `python -m uvicorn igris.server:app`) as a regular child process on
// app startup, and kills it when the window closes. This assumes the user
// has already run `pip install -e .` in igris-cli, same as the CLI itself
// requires -- there is no bundled Python runtime yet.
//
// A packaged, double-click-to-install build would instead freeze the
// backend with PyInstaller into a real binary and wire it up as a Tauri
// `externalBin` sidecar (see tauri-plugin-shell's Command::sidecar), so
// end users don't need Python on PATH at all. That's a deliberate later
// step, not done here, since it changes how the backend is *shipped*, not
// how it behaves -- everything in igris/server.py stays the same either way.

use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use tauri::Manager;

const BACKEND_PORT: &str = "8765";

struct BackendProcess(Mutex<Option<Child>>);

fn spawn_backend() -> std::io::Result<Child> {
    // Windows-first: relies on `python` resolving on PATH the same way the
    // `igris` CLI itself already does (see igris/cli.py's own PATH notes).
    // No WSL involved -- this runs directly against the Windows Python
    // install, consistent with the rest of the project.
    Command::new("python")
        .args(["-m", "uvicorn", "igris.server:app", "--port", BACKEND_PORT])
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            match spawn_backend() {
                Ok(child) => {
                    app.manage(BackendProcess(Mutex::new(Some(child))));
                }
                Err(e) => {
                    eprintln!(
                        "igris: failed to start Python backend ({e}). \
                         Make sure `pip install -e .` has been run in igris-cli, \
                         and that `python` resolves on PATH."
                    );
                }
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building igris desktop shell");

    app.run(|app_handle, event| {
        // Best-effort cleanup: kill the backend child process once the app
        // is exiting, so a closed window never leaves a stray uvicorn
        // process listening on BACKEND_PORT.
        if let tauri::RunEvent::ExitRequested { .. } = event {
            if let Some(state) = app_handle.try_state::<BackendProcess>() {
                if let Some(mut child) = state.0.lock().unwrap().take() {
                    let _ = child.kill();
                }
            }
        }
    });
}
