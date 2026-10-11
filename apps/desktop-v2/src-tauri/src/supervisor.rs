// apps/desktop/src-tauri/src/supervisor.rs
//! Process Supervisor for Aevum Core Backend.
//!
//! Responsibilities:
//! 1. Probes port 8000 with strict identity check (status == "ok" && app starts with "Aevum").
//! 2. Attaches cleanly if already running; otherwise spawns Python backend via virtualenv.
//! 3. Enforces zero orphan processes using Windows Job Object with JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE.
//! 4. Async readiness polling at 250ms intervals up to 15s.
//! 5. Post-readiness continuous crash supervision (monitoring child exit -> CRASHED, NO auto-restart).
//! 6. 2-stage graceful shutdown:
//!    - Stage 1: AttachConsole + GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT) + FreeConsole, wait up to 3s.
//!    - Stage 2: Force kill fallback if unresponsive after 3s.

use std::io::{Read, Write};
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};

#[cfg(windows)]
use std::ffi::c_void;
#[cfg(windows)]
use std::os::windows::io::AsRawHandle;
#[cfg(windows)]
use windows::Win32::Foundation::{CloseHandle, HANDLE};
#[cfg(windows)]
use windows::Win32::System::Console::{
    AttachConsole, FreeConsole, GenerateConsoleCtrlEvent, CTRL_BREAK_EVENT,
};
#[cfg(windows)]
use windows::Win32::System::JobObjects::{
    AssignProcessToJobObject, CreateJobObjectW, JobObjectExtendedLimitInformation,
    SetInformationJobObject, JOBOBJECT_EXTENDED_LIMIT_INFORMATION,
    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
};

/// Safe RAII wrapper for Windows Job Object HANDLE.
#[cfg(windows)]
pub struct JobHandle(pub HANDLE);

#[cfg(windows)]
unsafe impl Send for JobHandle {}
#[cfg(windows)]
unsafe impl Sync for JobHandle {}

#[cfg(windows)]
impl Drop for JobHandle {
    fn drop(&mut self) {
        if !self.0.is_invalid() {
            unsafe {
                let _ = CloseHandle(self.0);
            }
        }
    }
}

/// Mode of backend operation.
pub enum BackendMode {
    NotStarted,
    Attached,
    Spawned {
        child: Arc<Mutex<std::process::Child>>,
        #[cfg(windows)]
        #[allow(dead_code)]
        job: Arc<JobHandle>,
    },
    Crashed {
        exit_code: Option<i32>,
    },
}

impl std::fmt::Display for BackendMode {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            BackendMode::NotStarted => write!(f, "not_started"),
            BackendMode::Attached => write!(f, "attached"),
            BackendMode::Spawned { .. } => write!(f, "spawned"),
            BackendMode::Crashed { exit_code } => match exit_code {
                Some(code) => write!(f, "crashed (exit_code: {})", code),
                None => write!(f, "crashed"),
            },
        }
    }
}

pub type CrashCallback = Box<dyn Fn(Option<i32>) + Send + Sync + 'static>;

/// The Aevum Backend Supervisor.
pub struct BackendSupervisor {
    host: String,
    port: u16,
    mode: Arc<Mutex<BackendMode>>,
    on_crash: Arc<Mutex<Option<CrashCallback>>>,
}

impl BackendSupervisor {
    pub fn new(host: &str, port: u16) -> Self {
        Self {
            host: host.to_string(),
            port,
            mode: Arc::new(Mutex::new(BackendMode::NotStarted)),
            on_crash: Arc::new(Mutex::new(None)),
        }
    }

    pub fn host(&self) -> &str {
        &self.host
    }

    pub fn port(&self) -> u16 {
        self.port
    }

    /// Register callback invoked when a spawned backend unexpectedly crashes.
    pub fn set_on_crash<F>(&self, cb: F)
    where
        F: Fn(Option<i32>) + Send + Sync + 'static,
    {
        let mut guard = self.on_crash.lock().unwrap();
        *guard = Some(Box::new(cb));
    }

    /// Check if authoritative Aevum backend is healthy right now.
    pub fn is_healthy(&self) -> bool {
        if self.is_crashed() {
            return false;
        }
        probe_backend_health(&self.host, self.port).unwrap_or(false)
    }

    /// Check if backend is currently in a crashed state.
    pub fn is_crashed(&self) -> bool {
        let guard = self.mode.lock().unwrap();
        matches!(*guard, BackendMode::Crashed { .. })
    }

    /// Current mode description.
    pub fn current_mode(&self) -> String {
        let guard = self.mode.lock().unwrap();
        guard.to_string()
    }

    /// Return child process PID if currently spawned.
    pub fn child_pid(&self) -> Option<u32> {
        let guard = self.mode.lock().unwrap();
        if let BackendMode::Spawned { ref child, .. } = *guard {
            Some(child.lock().unwrap().id())
        } else {
            None
        }
    }

    /// Start or attach to the backend.
    ///
    /// 1. Probes `/health` on `host:port`.
    /// 2. If valid Aevum Core is responding, attaches cleanly.
    /// 3. If port is unoccupied, discovers paths, creates Windows Job Object, spawns uvicorn,
    ///    polls readiness every 250ms for up to 15s.
    /// 4. Once READY, spawns long-term supervision thread monitoring for unexpected process exit.
    pub fn start(&self) -> Result<String, String> {
        let mut mode_guard = self.mode.lock().unwrap();
        if !matches!(*mode_guard, BackendMode::NotStarted) {
            return Ok(format!("Backend already initialized ({})", *mode_guard));
        }

        // Phase 1: Probe existing service
        match probe_backend_health(&self.host, self.port) {
            Ok(true) => {
                println!(
                    "[Supervisor] Existing authoritative Aevum Core detected on {}:{}. Attaching cleanly.",
                    self.host, self.port
                );
                *mode_guard = BackendMode::Attached;
                return Ok("attached".to_string());
            }
            Ok(false) => {
                println!(
                    "[Supervisor] No service responding on {}:{}. Spawning new backend process...",
                    self.host, self.port
                );
            }
            Err(e) => {
                return Err(format!(
                    "Port {} cannot be used because health probe failed: {}",
                    self.port, e
                ));
            }
        }

        // Phase 2: Path discovery
        let (python_path, backend_dir) = find_backend_paths()?;
        println!(
            "[Supervisor] Resolved python: {:?}, backend_dir: {:?}",
            python_path, backend_dir
        );

        // Phase 3: Setup Windows Job Object with KILL_ON_JOB_CLOSE
        #[cfg(windows)]
        let job_handle = create_kill_on_close_job()?;

        // Phase 4: Spawn Python process
        let mut cmd = std::process::Command::new(&python_path);
        cmd.args(&[
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            &self.host,
            "--port",
            &self.port.to_string(),
        ]);
        cmd.current_dir(&backend_dir);

        #[cfg(windows)]
        {
            use std::os::windows::process::CommandExt;
            // CREATE_NEW_PROCESS_GROUP = 0x00000200
            // CREATE_NO_WINDOW = 0x08000000
            cmd.creation_flags(0x00000200 | 0x08000000);
        }

        let mut child = cmd.spawn().map_err(|e| {
            format!(
                "Failed to spawn backend python process at {:?}: {}",
                python_path, e
            )
        })?;

        #[cfg(windows)]
        {
            unsafe {
                let child_handle = HANDLE(child.as_raw_handle() as *mut c_void);
                AssignProcessToJobObject(job_handle.0, child_handle).map_err(|e| {
                    let _ = child.kill();
                    format!("Failed to assign child process to Windows Job Object: {:?}", e)
                })?;
            }
            println!("[Supervisor] Child process assigned to Windows Job Object (KILL_ON_JOB_CLOSE enabled).");
        }

        // Phase 5: Async readiness polling (250ms interval, up to 15s timeout)
        let poll_start = Instant::now();
        let timeout = Duration::from_secs(15);
        let poll_interval = Duration::from_millis(250);
        let mut ready = false;

        while poll_start.elapsed() < timeout {
            // Check if child exited prematurely
            match child.try_wait() {
                Ok(Some(status)) => {
                    return Err(format!(
                        "Backend process exited prematurely before becoming healthy with status: {:?}",
                        status
                    ));
                }
                Ok(None) => {}
                Err(e) => {
                    eprintln!("[Supervisor] Warning: error polling child process: {}", e);
                }
            }

            match probe_backend_health(&self.host, self.port) {
                Ok(true) => {
                    ready = true;
                    break;
                }
                Ok(false) => {
                    std::thread::sleep(poll_interval);
                }
                Err(e) => {
                    // Fatal probe error (e.g. port collision)
                    let _ = child.kill();
                    return Err(format!("Backend startup aborted due to probe error: {}", e));
                }
            }
        }

        if !ready {
            let _ = child.kill();
            return Err(format!(
                "Backend failed to become healthy within 15 seconds on {}:{}",
                self.host, self.port
            ));
        }

        println!(
            "[Supervisor] Backend successfully started and ready in {:.2}s",
            poll_start.elapsed().as_secs_f32()
        );

        let child_arc = Arc::new(Mutex::new(child));
        #[cfg(windows)]
        let job_arc = Arc::new(job_handle);

        *mode_guard = BackendMode::Spawned {
            child: child_arc.clone(),
            #[cfg(windows)]
            job: job_arc,
        };

        // Phase 6: Launch Long-Term Child Process Supervision Monitor
        let child_monitor = child_arc;
        let mode_monitor = self.mode.clone();
        let on_crash_monitor = self.on_crash.clone();

        std::thread::spawn(move || {
            loop {
                std::thread::sleep(Duration::from_millis(250));

                let mut mode_lock = mode_monitor.lock().unwrap();
                // Only monitor while in Spawned state
                if !matches!(*mode_lock, BackendMode::Spawned { .. }) {
                    // Clean shutdown or already crashed -> exit monitor loop
                    break;
                }

                let mut child_lock = child_monitor.lock().unwrap();
                match child_lock.try_wait() {
                    Ok(Some(status)) => {
                        let exit_code = status.code();
                        println!(
                            "[Supervisor] UNEXPECTED EXIT DETECTED: Backend child process terminated unexpectedly with status: {:?}. Transitioning to CRASHED.",
                            status
                        );
                        *mode_lock = BackendMode::Crashed { exit_code };
                        drop(mode_lock);

                        // Notify crash callback (Tauri event emitter)
                        if let Some(ref cb) = *on_crash_monitor.lock().unwrap() {
                            cb(exit_code);
                        }
                        break;
                    }
                    Ok(None) => {
                        // Child is running normally
                    }
                    Err(e) => {
                        eprintln!("[Supervisor] Monitor error polling child process: {}", e);
                        break;
                    }
                }
            }
        });

        Ok("spawned".to_string())
    }

    /// Graceful 2-stage shutdown of the backend.
    ///
    /// - If Attached: no-op (leave external process intact).
    /// - If Spawned:
    ///   - Stage 1: AttachConsole + GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT) + FreeConsole, wait up to 3s.
    ///   - Stage 2: If still alive after 3s, force terminate via `kill()`.
    pub fn shutdown(&self) -> Result<(), String> {
        let old_mode = {
            let mut mode_guard = self.mode.lock().unwrap();
            std::mem::replace(&mut *mode_guard, BackendMode::NotStarted)
        };

        match old_mode {
            BackendMode::NotStarted | BackendMode::Crashed { .. } => Ok(()),
            BackendMode::Attached => {
                println!("[Supervisor] Mode was attached; external backend left running.");
                Ok(())
            }
            BackendMode::Spawned { child, .. } => {
                println!("[Supervisor] Initiating 2-stage graceful shutdown of spawned backend...");
                let mut child_guard = child.lock().unwrap();

                // Stage 1: Check if already exited
                match child_guard.try_wait() {
                    Ok(Some(status)) => {
                        println!("[Supervisor] Child process already terminated: {:?}", status);
                        return Ok(());
                    }
                    _ => {}
                }

                let child_pid = child_guard.id();
                println!(
                    "[Supervisor] Dispatching graceful CTRL_BREAK_EVENT to child pid {}...",
                    child_pid
                );

                #[cfg(windows)]
                {
                    send_graceful_break(child_pid);
                }

                let deadline = Instant::now() + Duration::from_secs(3);
                let mut exited = false;
                while Instant::now() < deadline {
                    match child_guard.try_wait() {
                        Ok(Some(status)) => {
                            println!("[Supervisor] Child process cleanly exited gracefully: {:?}", status);
                            exited = true;
                            break;
                        }
                        _ => {
                            std::thread::sleep(Duration::from_millis(100));
                        }
                    }
                }

                // Stage 2: Force kill fallback if still alive
                if !exited {
                    println!("[Supervisor] Child process did not exit within 3s. Forcing kill fallback...");
                    let _ = child_guard.kill();
                    let _ = child_guard.wait();
                    println!("[Supervisor] Child process forcibly terminated.");
                }

                Ok(())
            }
        }
    }
}

/// Send graceful CTRL_BREAK_EVENT to a Windows console process group.
///
/// Under Win32:
/// 1. Detaches from current console (if any).
/// 2. Attaches to the child process's console using `AttachConsole(pid)`.
/// 3. Dispatches `GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, pid)`.
/// 4. Immediately calls `FreeConsole()` to restore GUI application state.
#[cfg(windows)]
pub fn send_graceful_break(pid: u32) {
    unsafe {
        let _ = FreeConsole();
        let attached = AttachConsole(pid).is_ok();
        let _ = GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, pid);
        let _ = FreeConsole();
        if !attached {
            // If attach failed (e.g. process already exited), direct fallback
            let _ = GenerateConsoleCtrlEvent(CTRL_BREAK_EVENT, pid);
        }
    }
}

/// Create a Windows Job Object configured with `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`.
#[cfg(windows)]
pub fn create_kill_on_close_job() -> Result<JobHandle, String> {
    unsafe {
        let job = CreateJobObjectW(None, None)
            .map_err(|e| format!("CreateJobObjectW failed: {:?}", e))?;
        let mut info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION::default();
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;

        SetInformationJobObject(
            job,
            JobObjectExtendedLimitInformation,
            &info as *const _ as *const c_void,
            std::mem::size_of::<JOBOBJECT_EXTENDED_LIMIT_INFORMATION>() as u32,
        )
        .map_err(|e| {
            let _ = CloseHandle(job);
            format!("SetInformationJobObject failed: {:?}", e)
        })?;

        Ok(JobHandle(job))
    }
}

/// Probe backend `/health` endpoint with strict identity verification.
///
/// Returns:
/// - `Ok(true)` if port is open and returns HTTP 200 with JSON matching:
///   `status == "ok"` AND `app` starts with `"Aevum"`.
/// - `Ok(false)` if port is not accepting connections (closed / refused).
/// - `Err(msg)` if port is open but returns non-200 or conflicting service signature.
pub fn probe_backend_health(host: &str, port: u16) -> Result<bool, String> {
    let addr: SocketAddr = format!("{}:{}", host, port)
        .parse()
        .map_err(|e| format!("Invalid socket address {}:{}: {}", host, port, e))?;

    let mut stream = match TcpStream::connect_timeout(&addr, Duration::from_millis(500)) {
        Ok(s) => s,
        Err(e) => {
            // Connection refused or timed out means backend is not running
            if e.kind() == std::io::ErrorKind::ConnectionRefused
                || e.kind() == std::io::ErrorKind::TimedOut
            {
                return Ok(false);
            }
            return Ok(false);
        }
    };

    let _ = stream.set_read_timeout(Some(Duration::from_millis(1500)));
    let _ = stream.set_write_timeout(Some(Duration::from_millis(1000)));

    let request = format!(
        "GET /health HTTP/1.1\r\nHost: {}:{}\r\nConnection: close\r\nUser-Agent: AevumSupervisor/0.1\r\n\r\n",
        host, port
    );

    if stream.write_all(request.as_bytes()).is_err() {
        return Ok(false);
    }

    let mut buf = Vec::new();
    let mut temp = [0u8; 1024];
    loop {
        match stream.read(&mut temp) {
            Ok(0) => break,
            Ok(n) => {
                buf.extend_from_slice(&temp[..n]);
                if buf.len() > 16384 {
                    break;
                }
            }
            Err(_) => break,
        }
    }

    if buf.is_empty() {
        return Ok(false);
    }

    let response_str = String::from_utf8_lossy(&buf);

    // Check status line
    let first_line = response_str.lines().next().unwrap_or("");
    if !first_line.contains("200") {
        return Err(format!(
            "Occupied port returned non-200 HTTP status: {}",
            first_line
        ));
    }

    // Split headers and body
    let body = match response_str.find("\r\n\r\n") {
        Some(pos) => &response_str[pos + 4..],
        None => match response_str.find("\n\n") {
            Some(pos) => &response_str[pos + 2..],
            None => "",
        },
    };

    // Strict JSON validation: must contain status="ok" and app="Aevum Core" or starts_with("Aevum")
    let v: serde_json::Value = serde_json::from_str(body.trim()).map_err(|e| {
        format!(
            "Service on port {} returned non-JSON /health payload: {}",
            port, e
        )
    })?;

    let status = v.get("status").and_then(|s| s.as_str()).unwrap_or("");
    let app = v.get("app").and_then(|a| a.as_str()).unwrap_or("");

    if status == "ok" && app.starts_with("Aevum") {
        Ok(true)
    } else {
        Err(format!(
            "Port {} is occupied by non-Aevum service (app='{}', status='{}')",
            port, app, status
        ))
    }
}

/// Locate Python virtualenv and backend working directory.
pub fn find_backend_paths() -> Result<(PathBuf, PathBuf), String> {
    // 1. Check environment variable override
    if let Ok(env_root) = std::env::var("AEVUM_WORKSPACE_ROOT") {
        let p = PathBuf::from(env_root);
        if let Some(res) = resolve_from_root(&p) {
            return Ok(res);
        }
    }

    // 2. Search upwards from current directory
    if let Ok(cwd) = std::env::current_dir() {
        let mut cur = Some(cwd.as_path());
        while let Some(dir) = cur {
            if let Some(res) = resolve_from_root(dir) {
                return Ok(res);
            }
            cur = dir.parent();
        }
    }

    // 3. Search upwards from current executable
    if let Ok(exe) = std::env::current_exe() {
        let mut cur = exe.parent();
        while let Some(dir) = cur {
            if let Some(res) = resolve_from_root(dir) {
                return Ok(res);
            }
            cur = dir.parent();
        }
    }

    // 4. Fallback: hardcoded workspace directory if present
    let hardcoded = PathBuf::from("d:\\Aevum\\Aevum");
    if let Some(res) = resolve_from_root(&hardcoded) {
        return Ok(res);
    }

    Err("Could not locate backend directory or virtualenv python executable".to_string())
}

fn resolve_from_root(candidate: &Path) -> Option<(PathBuf, PathBuf)> {
    let backend_dir = if candidate.file_name().and_then(|n| n.to_str()) == Some("backend") {
        candidate.to_path_buf()
    } else {
        candidate.join("backend")
    };

    if !backend_dir.is_dir() {
        return None;
    }

    #[cfg(windows)]
    {
        let venv_python = backend_dir.join(".venv").join("Scripts").join("python.exe");
        if venv_python.is_file() {
            return Some((venv_python, backend_dir));
        }
        let uv_python = backend_dir.join("venv").join("Scripts").join("python.exe");
        if uv_python.is_file() {
            return Some((uv_python, backend_dir));
        }
        // System fallback if in path
        if let Ok(path) = which_python() {
            return Some((path, backend_dir));
        }
    }

    #[cfg(not(windows))]
    {
        let venv_python = backend_dir.join(".venv").join("bin").join("python");
        if venv_python.is_file() {
            return Some((venv_python, backend_dir));
        }
    }

    None
}

#[cfg(windows)]
fn which_python() -> Result<PathBuf, ()> {
    for path in std::env::var("PATH").unwrap_or_default().split(';') {
        let p = PathBuf::from(path).join("python.exe");
        if p.is_file() {
            return Ok(p);
        }
    }
    Err(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use std::net::TcpListener;

    #[test]
    fn test_probe_backend_health_closed_port() {
        // Pick an unbound high port
        let port = 59123;
        let res = probe_backend_health("127.0.0.1", port);
        assert_eq!(res, Ok(false));
    }

    #[test]
    fn test_probe_backend_health_valid_aevum() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();

        std::thread::spawn(move || {
            if let Ok((mut stream, _)) = listener.accept() {
                let mut req = [0u8; 1024];
                let _ = stream.read(&mut req);
                let body = r#"{"status":"ok","app":"Aevum Core","version":"0.1.0","database":"connected"}"#;
                let resp = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                    body.len(),
                    body
                );
                let _ = stream.write_all(resp.as_bytes());
            }
        });

        let res = probe_backend_health("127.0.0.1", port);
        assert_eq!(res, Ok(true));
    }

    #[test]
    fn test_probe_backend_health_colliding_foreign_app() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();

        std::thread::spawn(move || {
            if let Ok((mut stream, _)) = listener.accept() {
                let mut req = [0u8; 1024];
                let _ = stream.read(&mut req);
                let body = r#"{"status":"ok","app":"Apache Solr"}"#;
                let resp = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
                    body.len(),
                    body
                );
                let _ = stream.write_all(resp.as_bytes());
            }
        });

        let res = probe_backend_health("127.0.0.1", port);
        assert!(res.is_err());
        assert!(res.unwrap_err().contains("occupied by non-Aevum service"));
    }

    #[test]
    fn test_probe_backend_health_non_200() {
        let listener = TcpListener::bind("127.0.0.1:0").unwrap();
        let port = listener.local_addr().unwrap().port();

        std::thread::spawn(move || {
            if let Ok((mut stream, _)) = listener.accept() {
                let mut req = [0u8; 1024];
                let _ = stream.read(&mut req);
                let resp = "HTTP/1.1 500 Internal Server Error\r\nContent-Length: 0\r\n\r\n";
                let _ = stream.write_all(resp.as_bytes());
            }
        });

        let res = probe_backend_health("127.0.0.1", port);
        assert!(res.is_err());
        assert!(res.unwrap_err().contains("returned non-200 HTTP status"));
    }

    #[test]
    fn test_find_backend_paths() {
        let res = find_backend_paths();
        assert!(res.is_ok(), "Expected to find backend paths: {:?}", res);
        let (py, dir) = res.unwrap();
        assert!(dir.ends_with("backend"));
        assert!(py.exists(), "Python executable should exist at {:?}", py);
    }

    #[test]
    #[cfg(windows)]
    fn test_create_kill_on_close_job() {
        let job = create_kill_on_close_job();
        assert!(job.is_ok(), "Failed to create Windows Job Object: {:?}", job.err());
    }
}
