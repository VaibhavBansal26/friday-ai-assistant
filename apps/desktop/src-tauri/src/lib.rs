use std::net::{SocketAddr, TcpStream};
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::Manager;

struct BackendProcess(Mutex<Option<Child>>);

fn backend_is_running() -> bool {
    let address: SocketAddr = "127.0.0.1:8000".parse().expect("valid Friday API address");
    TcpStream::connect_timeout(&address, Duration::from_millis(250)).is_ok()
}

fn start_backend() -> Result<Option<Child>, String> {
    if backend_is_running() {
        return Ok(None);
    }

    // The native app is built from apps/desktop/src-tauri, three levels below the
    // repository root. Keeping the backend tied to the app lifecycle prevents a
    // stale terminal-launched uvicorn process from causing conversation failures.
    let project_root = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .ancestors()
        .nth(3)
        .ok_or("Could not locate the Friday project root")?;
    let uvicorn = project_root.join(".venv/bin/uvicorn");
    if !uvicorn.exists() {
        return Err(format!("Friday API runtime is missing at {}", uvicorn.display()));
    }

    Command::new(uvicorn)
        .args([
            "friday.main:app",
            "--app-dir",
            "apps/api/src",
            "--host",
            "127.0.0.1",
            "--port",
            "8000",
        ])
        .current_dir(project_root)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map(Some)
        .map_err(|error| format!("Could not start Friday API: {error}"))
}

#[tauri::command]
fn desktop_health() -> &'static str { "ok" }

#[tauri::command]
fn open_external_url(url: String) -> Result<(), String> {
    if !(url.starts_with("https://") || url.starts_with("http://127.0.0.1:")) {
        return Err("Friday only opens HTTPS or local authorization URLs".into());
    }
    std::process::Command::new("open")
        .arg(url)
        .spawn()
        .map(|_| ())
        .map_err(|error| format!("Could not open the authorization page: {error}"))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(BackendProcess(Mutex::new(None)))
        .setup(|app| {
            let child = start_backend().map_err(|error| {
                eprintln!("{error}");
                error
            })?;
            *app.state::<BackendProcess>().0.lock().expect("backend state lock") = child;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![desktop_health, open_external_url])
        .run(tauri::generate_context!())
        .expect("error while running Friday");
}
