import { useEffect, useRef } from "react";
import { desktopApi } from "../api/desktop";
import { useSettingsStore } from "../stores/useSettingsStore";

export function useHeartbeatWorker(characterId = "aevum") {
  const lastActiveRef = useRef<number>(Date.now());
  const settings = useSettingsStore((s) => s.settings);

  useEffect(() => {
    const handleActivity = () => {
      lastActiveRef.current = Date.now();
    };

    window.addEventListener("mousemove", handleActivity, { passive: true });
    window.addEventListener("keydown", handleActivity, { passive: true });
    window.addEventListener("click", handleActivity, { passive: true });

    const interval = setInterval(async () => {
      const now = Date.now();
      const idleSeconds = Math.round((now - lastActiveRef.current) / 1000);
      const threshold = settings?.idle_threshold_seconds || 180;
      const isIdle = idleSeconds >= threshold;
      const windowFocused = document.hasFocus();

      try {
        await desktopApi.sendHeartbeat(
          {
            client_id: "desktop-v2-main",
            client_timestamp: new Date().toISOString(),
            is_idle: isIdle,
            idle_seconds: idleSeconds,
            window_focused: windowFocused,
            app_active: !isIdle,
          },
          characterId
        );
      } catch {
        // Heartbeat failure ignored gracefully
      }
    }, 30000);

    return () => {
      clearInterval(interval);
      window.removeEventListener("mousemove", handleActivity);
      window.removeEventListener("keydown", handleActivity);
      window.removeEventListener("click", handleActivity);
    };
  }, [characterId, settings]);
}
