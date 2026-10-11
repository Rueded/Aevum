// apps/desktop/src-tauri/src/notification.rs
//! Windows Native WinRT Toast Dispatcher for Project Aevum (Phase 8.4 Step 1 PoC).
//!
//! Enforces:
//! - Deterministic protocol activation payload: `aevum://notification/{id}`
//! - XML activationType="protocol" ensuring Windows Shell triggers protocol handler on click.
//! - Direct WinRT API invocation without heuristic wrappers.

#[cfg(windows)]
use windows::core::HSTRING;
#[cfg(windows)]
use windows::Data::Xml::Dom::XmlDocument;
#[cfg(windows)]
use windows::UI::Notifications::{ToastNotification, ToastNotificationManager};

fn quick_xml_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

#[cfg(windows)]
pub fn show_proactive_toast(notification_id: &str, title: &str, body: &str) -> Result<(), String> {
    let escaped_title = quick_xml_escape(title);
    let escaped_body = quick_xml_escape(body);

    let xml = format!(
        r#"<toast launch="aevum://notification/{}" activationType="protocol">
    <visual>
        <binding template="ToastGeneric">
            <text>{}</text>
            <text>{}</text>
        </binding>
    </visual>
</toast>"#,
        notification_id, escaped_title, escaped_body
    );

    let doc = XmlDocument::new().map_err(|e| format!("Failed to create XmlDocument: {e}"))?;
    doc.LoadXml(&HSTRING::from(xml))
        .map_err(|e| format!("Failed to load Toast XML: {e}"))?;

    let toast = ToastNotification::CreateToastNotification(&doc)
        .map_err(|e| format!("Failed to create ToastNotification: {e}"))?;

    // Try creating notifier with official Aevum AUMID, falling back to generic process notifier if not installed
    let notifier = ToastNotificationManager::CreateToastNotifierWithId(&HSTRING::from("com.aevum.desktop"))
        .or_else(|_| ToastNotificationManager::CreateToastNotifier())
        .map_err(|e| format!("Failed to create ToastNotifier: {e}"))?;

    notifier
        .Show(&toast)
        .map_err(|e| format!("Failed to show toast notification: {e}"))?;

    crate::log_step1_event(&format!("[Toast] Dispatched WinRT Toast for notification_id: {}", notification_id));
    Ok(())
}

#[cfg(not(windows))]
pub fn show_proactive_toast(_notification_id: &str, _title: &str, _body: &str) -> Result<(), String> {
    println!("[Toast] Native Windows WinRT Toast is only supported on Windows.");
    Ok(())
}
