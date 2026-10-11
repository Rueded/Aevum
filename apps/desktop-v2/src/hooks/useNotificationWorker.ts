import { useEffect, useRef } from "react";
import { desktopApi } from "../api/desktop";
import { useChatStore } from "../stores/useChatStore";

export function useNotificationWorker(characterId = "aevum") {
  const workerIdRef = useRef<string>(`worker-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`);
  const setHighlightedMessageId = useChatStore((s) => s.setHighlightedMessageId);

  useEffect(() => {
    let isCancelled = false;

    // Listen for Tauri native notification clicks
    const setupTauriListener = async () => {
      try {
        if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
          const { listen } = await import("@tauri-apps/api/event");
          const unlisten = await listen<{ id: string; conversation_message_id: string }>(
            "notification_interacted",
            async (event) => {
              if (event.payload?.conversation_message_id) {
                setHighlightedMessageId(event.payload.conversation_message_id);
              }
              if (event.payload?.id) {
                await desktopApi.interactNotification(event.payload.id, "CLICKED", characterId).catch(() => {});
              }
            }
          );
          return unlisten;
        }
      } catch (err) {
        console.warn("Could not setup Tauri notification listener:", err);
      }
      return () => {};
    };

    let cleanupListener: (() => void) | undefined;
    setupTauriListener().then((fn) => {
      cleanupListener = fn;
    });

    const pollNotifications = async () => {
      if (isCancelled) return;
      try {
        const pending = await desktopApi.getPendingNotifications(characterId);
        if (!pending || pending.length === 0 || isCancelled) return;

        for (const notif of pending) {
          if (isCancelled) break;

          // 1. Atomic lease claim
          let claimed = false;
          try {
            const claimRes = await desktopApi.claimNotification(
              notif.id,
              workerIdRef.current,
              characterId,
              60.0
            );
            claimed = claimRes.claimed;
          } catch {
            continue;
          }

          if (!claimed || isCancelled) continue;

          // 2. Dispatch native Windows Toast
          let dispatched = false;
          try {
            if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
              const { invoke } = await import("@tauri-apps/api/core");
              await invoke("send_native_toast", {
                id: notif.id,
                title: notif.title,
                body: notif.body,
              });
              dispatched = true;
            } else {
              console.log("[NotificationWorker] Simulated native toast for browser:", notif.title, notif.body);
              dispatched = true;
            }
          } catch (dispatchErr) {
            console.error("[NotificationWorker] Native toast dispatch failed:", dispatchErr);
            await desktopApi.releaseNotification(notif.id, workerIdRef.current, characterId).catch(() => {});
            continue;
          }

          // 3. Mark delivery as complete
          if (dispatched && !isCancelled) {
            await desktopApi.completeNotification(notif.id, workerIdRef.current, characterId).catch(() => {});
          }
        }
      } catch {
        // Retry on next tick
      }
    };

    const initialTimer = setTimeout(pollNotifications, 2000);
    const intervalId = setInterval(pollNotifications, 12000);

    return () => {
      isCancelled = true;
      clearTimeout(initialTimer);
      clearInterval(intervalId);
      if (cleanupListener) cleanupListener();
    };
  }, [characterId, setHighlightedMessageId]);
}
