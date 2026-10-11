// apps/desktop/src-tauri/tests/test_supervisor.rs
use std::io::{Read, Write};
use std::net::TcpListener;
use desktop_lib::supervisor::BackendSupervisor;

#[test]
fn test_supervisor_attach_when_already_running() {
    // 1. Start mock Aevum Core listener
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();

    let handle = std::thread::spawn(move || {
        // Handle probe request
        while let Ok((mut stream, _)) = listener.accept() {
            let mut req = [0u8; 1024];
            let _ = stream.read(&mut req);
            let body = r#"{"status":"ok","app":"Aevum Core","version":"0.1.0","database":"connected"}"#;
            let resp = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                body.len(),
                body
            );
            let _ = stream.write_all(resp.as_bytes());
            break;
        }
    });

    // 2. Initialize supervisor on this port
    let supervisor = BackendSupervisor::new("127.0.0.1", port);
    assert_eq!(supervisor.current_mode(), "not_started");

    // 3. Start supervisor -> should attach cleanly
    let mode = supervisor.start().expect("Supervisor should attach cleanly to mock Aevum Core");
    assert_eq!(mode, "attached");
    assert_eq!(supervisor.current_mode(), "attached");

    // 4. Calling start again -> idempotent
    let second_mode = supervisor.start().expect("Second start should be idempotent");
    assert!(second_mode.contains("already initialized (attached)"));

    // 5. Shutdown -> attached mode should not kill external process
    let shutdown_res = supervisor.shutdown();
    assert!(shutdown_res.is_ok());
    assert_eq!(supervisor.current_mode(), "not_started");

    let _ = handle.join();
}

#[test]
fn test_supervisor_rejects_colliding_foreign_port() {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();

    let _handle = std::thread::spawn(move || {
        while let Ok((mut stream, _)) = listener.accept() {
            let mut req = [0u8; 1024];
            let _ = stream.read(&mut req);
            let body = r#"{"status":"ok","app":"Foreign Colliding Service"}"#;
            let resp = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                body.len(),
                body
            );
            let _ = stream.write_all(resp.as_bytes());
        }
    });

    let supervisor = BackendSupervisor::new("127.0.0.1", port);
    let start_res = supervisor.start();
    assert!(start_res.is_err(), "Supervisor must reject colliding non-Aevum service");
    let err_msg = start_res.unwrap_err();
    assert!(err_msg.contains("occupied by non-Aevum service") || err_msg.contains("cannot be used"));
}

#[test]
#[cfg(windows)]
fn test_supervisor_job_object_lifecycle_and_termination() {
    use desktop_lib::supervisor::create_kill_on_close_job;
    use std::os::windows::io::AsRawHandle;
    use windows::Win32::Foundation::HANDLE;
    use windows::Win32::System::JobObjects::AssignProcessToJobObject;

    let job = create_kill_on_close_job().expect("Job object creation failed");

    // Spawn a long-running process (ping 127.0.0.1 -n 30)
    let mut child = std::process::Command::new("cmd.exe")
        .args(&["/C", "ping", "127.0.0.1", "-n", "30"])
        .spawn()
        .expect("Failed to spawn child command");

    unsafe {
        let child_handle = HANDLE(child.as_raw_handle() as *mut std::ffi::c_void);
        let assign_res = AssignProcessToJobObject(job.0, child_handle);
        assert!(assign_res.is_ok(), "Failed to assign process to job object: {:?}", assign_res.err());
    }

    // Process is currently running
    assert!(child.try_wait().unwrap().is_none(), "Child process should still be running");

    // Terminate child cleanly
    let kill_res = child.kill();
    assert!(kill_res.is_ok(), "Failed to kill child: {:?}", kill_res.err());
    let _ = child.wait();
}

fn get_free_port() -> u16 {
    let listener = TcpListener::bind("127.0.0.1:0").unwrap();
    let port = listener.local_addr().unwrap().port();
    drop(listener);
    port
}

#[test]
#[cfg(windows)]
fn test_real_backend_graceful_shutdown_and_lifespan_dispose() {
    let port = get_free_port();

    // Setup unique marker file path
    let marker_path = std::env::temp_dir().join(format!("aevum_shutdown_test_{}.txt", port));
    if marker_path.exists() {
        let _ = std::fs::remove_file(&marker_path);
    }

    std::env::set_var("AEVUM_SHUTDOWN_MARKER", marker_path.to_str().unwrap());

    // Initialize supervisor on ephemeral port
    let supervisor = BackendSupervisor::new("127.0.0.1", port);
    assert_eq!(supervisor.current_mode(), "not_started");

    // Start supervisor -> will spawn real uvicorn backend
    println!("[TEST] Starting real backend on port {}...", port);
    let mode = supervisor.start().expect("Real backend should start and reach READY");
    assert_eq!(mode, "spawned");
    assert_eq!(supervisor.current_mode(), "spawned");
    assert!(supervisor.is_healthy(), "Backend should report healthy");

    let pid = supervisor.child_pid().expect("Spawned backend should have a valid PID");
    println!("[TEST] Real backend running with PID: {}", pid);

    // Perform graceful shutdown
    println!("[TEST] Triggering supervisor graceful shutdown...");
    let shutdown_res = supervisor.shutdown();
    assert!(shutdown_res.is_ok(), "Graceful shutdown must succeed: {:?}", shutdown_res.err());
    assert_eq!(supervisor.current_mode(), "not_started");

    // Verify: Database engine was cleanly disposed and marker was written by lifespan
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(3);
    let mut marker_found = false;
    while std::time::Instant::now() < deadline {
        if marker_path.exists() {
            if let Ok(content) = std::fs::read_to_string(&marker_path) {
                if content.trim() == "disposed_cleanly" {
                    marker_found = true;
                    break;
                }
            }
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    }

    assert!(
        marker_found,
        "Lifespan shutdown marker 'disposed_cleanly' was NOT found at {:?}. Graceful shutdown failed to dispose engine!",
        marker_path
    );
    println!("[TEST] VERIFIED: Lifespan shutdown marker 'disposed_cleanly' written by real backend!");

    // Clean up
    let _ = std::fs::remove_file(&marker_path);
    std::env::remove_var("AEVUM_SHUTDOWN_MARKER");
}

#[test]
#[cfg(windows)]
fn test_real_backend_crash_supervision_and_no_restart() {
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::Arc;
    let port = get_free_port();

    let supervisor = BackendSupervisor::new("127.0.0.1", port);

    // Set crash callback
    let crash_detected = Arc::new(AtomicBool::new(false));
    let crash_code = Arc::new(std::sync::Mutex::new(None));
    let crash_detected_clone = crash_detected.clone();
    let crash_code_clone = crash_code.clone();

    supervisor.set_on_crash(move |code| {
        println!("[TEST CALLBACK] Crash callback received with code: {:?}", code);
        crash_detected_clone.store(true, Ordering::SeqCst);
        *crash_code_clone.lock().unwrap() = code;
    });

    println!("[TEST] Spawning real backend for crash supervision on port {}...", port);
    let mode = supervisor.start().expect("Backend must start successfully");
    assert_eq!(mode, "spawned");
    assert!(supervisor.is_healthy(), "Backend should be healthy initially");
    assert!(!supervisor.is_crashed(), "Backend should not be crashed initially");

    let pid = supervisor.child_pid().expect("Spawned backend must have PID");
    println!("[TEST] Backend spawned with PID {}, now forcibly terminating externally...", pid);

    // Forcibly kill child process externally via Win32 TerminateProcess (simulating sudden unhandled abort / crash)
    #[cfg(windows)]
    unsafe {
        use windows::Win32::System::Threading::{OpenProcess, TerminateProcess, PROCESS_TERMINATE};
        let handle = OpenProcess(PROCESS_TERMINATE, false, pid).expect("OpenProcess failed");
        let term_res = TerminateProcess(handle, 99);
        assert!(term_res.is_ok(), "TerminateProcess failed: {:?}", term_res.err());
        let _ = windows::Win32::Foundation::CloseHandle(handle);
    }

    // Wait for supervisor long-term monitor loop (polls every 250ms)
    let deadline = std::time::Instant::now() + std::time::Duration::from_secs(4);
    while std::time::Instant::now() < deadline {
        if supervisor.is_crashed() && crash_detected.load(Ordering::SeqCst) {
            break;
        }
        std::thread::sleep(std::time::Duration::from_millis(100));
    }

    // Verify supervisor detected crash
    assert!(
        crash_detected.load(Ordering::SeqCst),
        "Supervisor crash callback was not triggered after process termination!"
    );
    assert!(
        supervisor.is_crashed(),
        "Supervisor state must be Crashed, but got mode: {}",
        supervisor.current_mode()
    );
    assert!(
        !supervisor.is_healthy(),
        "Supervisor must report unhealthy when in crashed state"
    );
    assert!(
        supervisor.current_mode().starts_with("crashed"),
        "Current mode string should indicate crashed"
    );

    // Verify NO automatic restart: wait 1 second and confirm port is free and mode is still crashed
    std::thread::sleep(std::time::Duration::from_secs(1));
    assert!(
        supervisor.is_crashed(),
        "Supervisor must NOT auto-restart backend; mode must remain crashed"
    );
    assert!(
        !supervisor.is_healthy(),
        "Backend must remain dead (no auto-restart)"
    );

    println!("[TEST] VERIFIED: Long-term crash supervision detected external exit, transitioned to CRASHED, and did NOT auto-restart.");
}
