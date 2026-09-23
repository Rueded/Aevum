// apps/desktop/src-tauri/src/lib.rs
pub mod notification;
pub mod supervisor;

use std::sync::{Arc, Mutex};
use tauri::menu::{Menu, MenuItem, PredefinedMenuItem};
use tauri::tray::{TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager};

use supervisor::BackendSupervisor;

pub struct SupervisorState(pub Arc<BackendSupervisor>);

#[derive(Default)]
pub struct InitialActivationState(pub Mutex<Option<String>>);

pub fn log_step1_event(msg: &str) {
    println!("{}", msg);
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open("d:\\Aevum\\Aevum\\step1_poc.log")
    {
        use std::io::Write;
        let _ = writeln!(
            file,
            "[{}] {}",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)
                .unwrap_or_default()
                .as_secs(),
            msg
        );
    }
}

/// Deterministically parse notification ID from a protocol activation argument.
/// Strips optional quotes and trailing slashes.
pub fn parse_notification_uri(raw: &str) -> Option<String> {
    let clean = raw.trim().trim_matches('"').trim_end_matches('/');
    if let Some(stripped) = clean.strip_prefix("aevum://notification/") {
        if !stripped.is_empty() {
            return Some(stripped.to_string());
        }
    }
    None
}

#[tauri::command]
fn send_native_toast(id: String, title: String, body: String) -> Result<(), String> {
    notification::show_proactive_toast(&id, &title, &body)
}

#[tauri::command]
fn get_initial_notification_activation(state: tauri::State<InitialActivationState>) -> Option<String> {
    state.0.lock().unwrap().take()
}

#[tauri::command]
fn get_backend_status(state: tauri::State<SupervisorState>) -> serde_json::Value {
    let sup = &state.0;
    serde_json::json!({
        "healthy": sup.is_healthy(),
        "mode": sup.current_mode(),
        "crashed": sup.is_crashed(),
        "host": sup.host(),
        "port": sup.port()
    })
}

#[tauri::command]
fn shutdown_backend(state: tauri::State<SupervisorState>) -> Result<(), String> {
    state.0.shutdown()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    log_step1_event(&format!("[Thread] run() thread: {:?}", std::thread::current().id()));
    let supervisor = Arc::new(BackendSupervisor::new("127.0.0.1", 8000));

    tauri::Builder::default()
        .manage(InitialActivationState::default())
        .manage(SupervisorState(supervisor.clone()))
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
                log_step1_event("[WindowEvent] Close requested -> intercepted: window hidden to tray");
            }
        })
        .plugin(tauri_plugin_single_instance::init(|app, args, _cwd| {
            log_step1_event(&format!("[SingleInstance] Secondary instance triggered with args: {:?}", args));
            for arg in &args {
                if let Some(notification_id) = parse_notification_uri(arg) {
                    log_step1_event(&format!("[SingleInstance] Deterministic notification activation: {}", notification_id));
                    let _ = app.emit("notification-activated", serde_json::json!({ "notificationId": notification_id }));
                }
            }
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.unminimize();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_deep_link::init())
        .invoke_handler(tauri::generate_handler![
            send_native_toast,
            get_initial_notification_activation,
            get_backend_status,
            shutdown_backend
        ])
        .setup({
            let supervisor = supervisor.clone();
            move |app| {
                log_step1_event(&format!("[Thread] setup() thread: {:?}", std::thread::current().id()));
                let id = &app.config().identifier;
                log_step1_event(&format!("[Config] App identifier: {}", id));

                // 1. Build System Tray Menu
                let show_i = MenuItem::with_id(app, "show", "Show Aevum", true, None::<&str>)?;
                let sep1 = PredefinedMenuItem::separator(app)?;
                let dnd_1h = MenuItem::with_id(app, "dnd_1h", "Do Not Disturb (1 Hour)", true, None::<&str>)?;
                let dnd_off = MenuItem::with_id(app, "dnd_off", "Do Not Disturb (Off)", true, None::<&str>)?;
                let sep2 = PredefinedMenuItem::separator(app)?;
                let quit_i = MenuItem::with_id(app, "quit", "Quit Aevum", true, None::<&str>)?;
                let menu = Menu::with_items(app, &[&show_i, &sep1, &dnd_1h, &dnd_off, &sep2, &quit_i])?;

                let icon = tauri::include_image!("icons/32x32.png");
                let sup_for_tray = supervisor.clone();

                let _tray = TrayIconBuilder::with_id("main-tray")
                    .icon(icon)
                    .menu(&menu)
                    .tooltip("Aevum")
                    .on_menu_event(move |app, event| {
                        match event.id().as_ref() {
                            "show" => {
                                if let Some(w) = app.get_webview_window("main") {
                                    let _ = w.show();
                                    let _ = w.unminimize();
                                    let _ = w.set_focus();
                                }
                            }
                            "dnd_1h" => {
                                log_step1_event("[Tray] DND 1 hour clicked");
                                let _ = app.emit("tray-dnd-toggle", serde_json::json!({ "enabled": true, "duration_minutes": 60 }));
                            }
                            "dnd_off" => {
                                log_step1_event("[Tray] DND Off clicked");
                                let _ = app.emit("tray-dnd-toggle", serde_json::json!({ "enabled": false }));
                            }
                            "quit" => {
                                log_step1_event("[Tray] Quit clicked -> initiating supervisor shutdown");
                                let _ = sup_for_tray.shutdown();
                                app.exit(0);
                            }
                            _ => {}
                        }
                    })
                    .on_tray_icon_event(|tray, event| {
                        if let TrayIconEvent::Click {
                            button: tauri::tray::MouseButton::Left,
                            button_state: tauri::tray::MouseButtonState::Up,
                            ..
                        } = event
                        {
                            let app = tray.app_handle();
                            if let Some(w) = app.get_webview_window("main") {
                                let _ = w.show();
                                let _ = w.unminimize();
                                let _ = w.set_focus();
                            }
                        }
                    })
                    .build(app)?;

                #[cfg(windows)]
                unsafe {
                    use windows::core::HSTRING;
                    use windows::Win32::UI::WindowsAndMessaging::FindWindowW;
                    let class_name = HSTRING::from(format!("{id}-sic"));
                    let window_name = HSTRING::from(format!("{id}-siw"));
                    let hwnd = FindWindowW(&class_name, &window_name);
                    log_step1_event(&format!("[SingleInstanceCheck] FindWindowW result: {:?}", hwnd));
                }

                // Check cold start arguments
                for arg in std::env::args() {
                    if let Some(notification_id) = parse_notification_uri(&arg) {
                        log_step1_event(&format!("[ColdStart] Found notification activation arg: {}", notification_id));
                        let state = app.state::<InitialActivationState>();
                        *state.0.lock().unwrap() = Some(notification_id);
                    }
                }

                #[cfg(desktop)]
                {
                    use tauri_plugin_deep_link::DeepLinkExt;
                    if let Err(e) = app.deep_link().register("aevum") {
                        eprintln!("[DeepLink] Failed to register aevum protocol: {}", e);
                    } else {
                        println!("[DeepLink] Successfully registered aevum:// protocol");
                    }
                }

                // 2. Wire Long-Term Crash Supervision Event Emitter
                let app_handle_for_crash = app.handle().clone();
                supervisor.set_on_crash(move |exit_code| {
                    log_step1_event(&format!("[Supervisor] Emitting backend crash event (exit_code: {:?})", exit_code));
                    let _ = app_handle_for_crash.emit(
                        "backend-status-changed",
                        serde_json::json!({
                            "ready": false,
                            "crashed": true,
                            "exit_code": exit_code,
                            "mode": "crashed"
                        }),
                    );
                });

                // 3. Launch Supervisor start in background thread unless explicitly skipped
                if std::env::var("AEVUM_SKIP_BACKEND_SPAWN").unwrap_or_default() != "1" {
                    let app_handle = app.handle().clone();
                    let sup = supervisor.clone();
                    std::thread::spawn(move || {
                        log_step1_event("[Supervisor] Starting background supervisor lifecycle probe/spawn...");
                        match sup.start() {
                            Ok(mode) => {
                                log_step1_event(&format!("[Supervisor] Backend ready in mode: {}", mode));
                                let _ = app_handle.emit(
                                    "backend-status-changed",
                                    serde_json::json!({
                                        "ready": true,
                                        "mode": mode,
                                        "host": sup.host(),
                                        "port": sup.port()
                                    }),
                                );
                            }
                            Err(e) => {
                                log_step1_event(&format!("[Supervisor] Backend startup error: {}", e));
                                let _ = app_handle.emit(
                                    "backend-status-changed",
                                    serde_json::json!({
                                        "ready": false,
                                        "error": e
                                    }),
                                );
                            }
                        }
                    });
                }

                Ok(())
            }
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
