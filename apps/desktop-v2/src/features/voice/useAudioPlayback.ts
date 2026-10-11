import { useRef, useCallback, useEffect } from "react";
import { useChatStore } from "../../stores/useChatStore";
import { useVisualStore } from "../../stores/useVisualStore";
import { voiceApi } from "../../api/voice";
import { LipSyncAnalyzer } from "../../visual/lipSyncAnalyzer";
import type { MessageItem } from "../../types";

export function useAudioPlayback() {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const analyzerRef = useRef<LipSyncAnalyzer | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const setPlayingMessageId = useChatStore((s) => s.setPlayingMessageId);
  const setLipSyncState = useVisualStore((s) => s.setLipSyncState);

  const stopAudio = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    if (analyzerRef.current) {
      analyzerRef.current.triggerBargeIn();
      analyzerRef.current.detachAudioElement();
    }
    setPlayingMessageId(null);
    setLipSyncState({
      mouth_open_y: 0.0,
      mouth_form: 0.0,
      is_speaking: false,
    });
  }, [setPlayingMessageId, setLipSyncState]);

  const playAudio = useCallback(
    async (message: MessageItem) => {
      if (!message.audio_cache_key) return;

      stopAudio();

      const audioUrl = voiceApi.getCachedAudioUrl(message.audio_cache_key);
      const audio = new Audio(audioUrl);
      audio.crossOrigin = "anonymous";
      audioRef.current = audio;

      // Route to user-configured speaker output if supported
      const selectedOutputId = localStorage.getItem("aevum_selected_audio_output_id");
      if (selectedOutputId && selectedOutputId !== "default" && "setSinkId" in audio) {
        try {
          await (audio as any).setSinkId(selectedOutputId);
        } catch (e) {
          console.warn("Could not set audio sinkId:", e);
        }
      }

      const analyzer = new LipSyncAnalyzer();
      analyzerRef.current = analyzer;
      try {
        analyzer.attachAudioElement(audio);
      } catch (err) {
        console.warn("Could not attach audio to LipSyncAnalyzer:", err);
      }

      const loop = () => {
        if (analyzerRef.current) {
          const state = analyzerRef.current.updateFrame();
          setLipSyncState(state);
        }
        animFrameRef.current = requestAnimationFrame(loop);
      };

      audio.onplay = () => {
        setPlayingMessageId(message.id);
        loop();
      };

      audio.onended = () => {
        stopAudio();
      };

      audio.onerror = () => {
        console.error("Audio playback error for message:", message.id);
        stopAudio();
      };

      try {
        await audio.play();
      } catch (err) {
        console.error("Failed to start audio playback:", err);
        stopAudio();
      }
    },
    [stopAudio, setPlayingMessageId, setLipSyncState]
  );

  useEffect(() => {
    return () => {
      stopAudio();
    };
  }, [stopAudio]);

  return { playAudio, stopAudio };
}
