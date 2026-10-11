// apps/desktop/src-tauri/tests/test_winrt_toast.rs
//! Step 1 PoC Tests: Windows WinRT Toast XML & Protocol URI Parsing.

use desktop_lib::notification::show_proactive_toast;
use desktop_lib::parse_notification_uri;

#[test]
fn test_parse_notification_uri_variations() {
    // 1. Standard protocol URI
    assert_eq!(
        parse_notification_uri("aevum://notification/test-123"),
        Some("test-123".to_string())
    );

    // 2. Windows shell quoted URI
    assert_eq!(
        parse_notification_uri("\"aevum://notification/test-123\""),
        Some("test-123".to_string())
    );

    // 3. Trailing slash URI
    assert_eq!(
        parse_notification_uri("aevum://notification/uuid-456-789/"),
        Some("uuid-456-789".to_string())
    );

    // 4. Non-notification URI (should NOT trigger notification activation)
    assert_eq!(parse_notification_uri("aevum://settings"), None);
    assert_eq!(parse_notification_uri("https://aevum.app"), None);

    // 5. Standard CLI flags (Alt+Tab or normal launch without protocol)
    assert_eq!(parse_notification_uri("--flag"), None);
    assert_eq!(parse_notification_uri("desktop.exe"), None);

    // 6. Empty notification ID
    assert_eq!(parse_notification_uri("aevum://notification/"), None);
}

#[test]
#[cfg(windows)]
fn test_show_proactive_toast_winrt_dispatch() {
    // Verifies that Windows WinRT XmlDocument and ToastNotification APIs
    // successfully parse and dispatch the protocol-activation XML.
    let res = show_proactive_toast(
        "poc-test-winrt-uuid",
        "Aevum — Reality Sync",
        "Deterministic WinRT Toast Verification Test",
    );
    assert!(res.is_ok(), "WinRT toast dispatch failed: {:?}", res.err());
}
