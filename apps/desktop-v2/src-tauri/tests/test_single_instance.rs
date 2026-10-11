// apps/desktop/src-tauri/tests/test_single_instance.rs
use windows_sys::Win32::Foundation::{CloseHandle, GetLastError, ERROR_ALREADY_EXISTS};
use windows_sys::Win32::System::Threading::CreateMutexW;
use windows_sys::Win32::UI::WindowsAndMessaging::{
    CreateWindowExW, DefWindowProcW, DestroyWindow, FindWindowW, RegisterClassExW,
    WNDCLASSEXW, WS_EX_LAYERED, WS_EX_NOACTIVATE, WS_EX_TOOLWINDOW, WS_EX_TRANSPARENT,
    WS_OVERLAPPED,
};
use windows_sys::Win32::System::LibraryLoader::GetModuleHandleW;

fn encode_wide(s: &str) -> Vec<u16> {
    s.encode_utf16().chain(std::iter::once(0)).collect()
}

#[test]
fn test_single_instance_mutex_and_window() {
    let class_name = encode_wide("com.aevum.desktop-sic");
    let window_name = encode_wide("com.aevum.desktop-siw");
    let mutex_name = encode_wide("com.aevum.desktop-sim");

    unsafe {
        // 1. Create mutex
        let hmutex1 = CreateMutexW(std::ptr::null(), 1, mutex_name.as_ptr());
        assert!(!hmutex1.is_null());
        assert_ne!(GetLastError(), ERROR_ALREADY_EXISTS);

        // 2. Register class & create hidden event window
        let class = WNDCLASSEXW {
            cbSize: std::mem::size_of::<WNDCLASSEXW>() as u32,
            style: 0,
            lpfnWndProc: Some(DefWindowProcW),
            cbClsExtra: 0,
            cbWndExtra: 0,
            hInstance: GetModuleHandleW(std::ptr::null()),
            hIcon: std::ptr::null_mut(),
            hCursor: std::ptr::null_mut(),
            hbrBackground: std::ptr::null_mut(),
            lpszMenuName: std::ptr::null(),
            lpszClassName: class_name.as_ptr(),
            hIconSm: std::ptr::null_mut(),
        };
        let atom = RegisterClassExW(&class);
        println!("Atom: {}", atom);

        let hwnd = CreateWindowExW(
            WS_EX_NOACTIVATE | WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW,
            class_name.as_ptr(),
            window_name.as_ptr(),
            WS_OVERLAPPED,
            0,
            0,
            0,
            0,
            std::ptr::null_mut(),
            std::ptr::null_mut(),
            GetModuleHandleW(std::ptr::null()),
            std::ptr::null(),
        );
        println!("Created hwnd: {:?}", hwnd);
        assert!(!hwnd.is_null(), "CreateWindowExW failed");

        // 3. Second instance attempts CreateMutexW:
        let hmutex2 = CreateMutexW(std::ptr::null(), 1, mutex_name.as_ptr());
        assert_eq!(GetLastError(), ERROR_ALREADY_EXISTS);

        // 4. Second instance calls FindWindowW:
        let found = FindWindowW(class_name.as_ptr(), window_name.as_ptr());
        println!("Found hwnd: {:?}", found);
        assert_eq!(found, hwnd, "FindWindowW must find the target window");

        // Cleanup
        DestroyWindow(hwnd);
        CloseHandle(hmutex1);
        CloseHandle(hmutex2);
    }
}
