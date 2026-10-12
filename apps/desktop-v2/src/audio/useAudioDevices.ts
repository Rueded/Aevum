import { useCallback, useEffect, useRef, useState } from "react";

export interface AudioDeviceInfo {
  deviceId: string;
  label: string;
  groupId: string;
}

export function useAudioDevices() {
  const [inputDevices, setInputDevices] = useState<AudioDeviceInfo[]>([]);
  const [outputDevices, setOutputDevices] = useState<AudioDeviceInfo[]>([]);
  const [selectedInputId, setSelectedInputId] = useState<string>(() => {
    return localStorage.getItem("aevum_selected_audio_input_id") || "default";
  });
  const [selectedOutputId, setSelectedOutputId] = useState<string>(() => {
    return localStorage.getItem("aevum_selected_audio_output_id") || "default";
  });
  const [hasPermission, setHasPermission] = useState<boolean>(false);
  const [micVolume, setMicVolume] = useState<number>(0);
  const [isTestingMic, setIsTestingMic] = useState<boolean>(false);

  const testAudioCtxRef = useRef<AudioContext | null>(null);
  const testStreamRef = useRef<MediaStream | null>(null);
  const testAnimFrameRef = useRef<number | null>(null);

  const enumerate = useCallback(async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
      return;
    }
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const inputs: AudioDeviceInfo[] = [];
      const outputs: AudioDeviceInfo[] = [];

      const hasRealLabels = devices.some((d) => Boolean(d.label && d.label.trim().length > 0));
      if (hasRealLabels) {
        setHasPermission(true);
      } else if (navigator.permissions && navigator.permissions.query) {
        try {
          const status = await navigator.permissions.query({ name: "microphone" as PermissionName });
          if (status.state === "granted") {
            setHasPermission(true);
          }
        } catch {
          // Ignore unsupported permission name queries
        }
      }

      devices.forEach((dev, index) => {
        if (dev.kind === "audioinput") {
          inputs.push({
            deviceId: dev.deviceId || `input-${index}`,
            label: dev.label || `麦克风输入设备 ${inputs.length + 1}${hasRealLabels ? "" : " (待授权读取型号)"}`,
            groupId: dev.groupId,
          });
        } else if (dev.kind === "audiooutput") {
          outputs.push({
            deviceId: dev.deviceId || `output-${index}`,
            label: dev.label || `扬声器 / 耳机输出设备 ${outputs.length + 1} (系统音频 · 正常可用)`,
            groupId: dev.groupId,
          });
        }
      });

      setInputDevices(inputs);
      setOutputDevices(outputs);
    } catch (err) {
      console.warn("[useAudioDevices] Enumerate error:", err);
    }
  }, []);

  const requestPermission = useCallback(async () => {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("getUserMedia is not supported in this browser");
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      setHasPermission(true);
      // Stop the test stream right after granting permission
      stream.getTracks().forEach((track) => track.stop());
      await enumerate();
    } catch (err) {
      console.warn("[useAudioDevices] Permission denied or failed:", err);
      throw err;
    }
  }, [enumerate]);

  const selectInput = (deviceId: string) => {
    setSelectedInputId(deviceId);
    localStorage.setItem("aevum_selected_audio_input_id", deviceId);
  };

  const selectOutput = (deviceId: string) => {
    setSelectedOutputId(deviceId);
    localStorage.setItem("aevum_selected_audio_output_id", deviceId);
  };

  // Test microphone live volume level
  const startMicTest = async () => {
    if (isTestingMic) return;
    try {
      const constraints: MediaStreamConstraints = {
        audio: selectedInputId && selectedInputId !== "default"
          ? { deviceId: { exact: selectedInputId } }
          : true,
      };
      const stream = await navigator.mediaDevices.getUserMedia(constraints);
      testStreamRef.current = stream;

      const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      testAudioCtxRef.current = audioCtx;

      const source = audioCtx.createMediaStreamSource(stream);
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);

      const bufferLength = analyser.frequencyBinCount;
      const dataArray = new Uint8Array(bufferLength);

      setIsTestingMic(true);

      const checkVolume = () => {
        analyser.getByteFrequencyData(dataArray);
        let sum = 0;
        for (let i = 0; i < bufferLength; i++) {
          sum += dataArray[i];
        }
        const average = sum / bufferLength;
        const normalized = Math.min(100, Math.round((average / 128) * 100));
        setMicVolume(normalized);
        testAnimFrameRef.current = requestAnimationFrame(checkVolume);
      };

      checkVolume();
    } catch (err) {
      console.warn("[useAudioDevices] Failed to start mic test:", err);
      setIsTestingMic(false);
    }
  };

  const stopMicTest = () => {
    if (testAnimFrameRef.current) {
      cancelAnimationFrame(testAnimFrameRef.current);
      testAnimFrameRef.current = null;
    }
    if (testStreamRef.current) {
      testStreamRef.current.getTracks().forEach((t) => t.stop());
      testStreamRef.current = null;
    }
    if (testAudioCtxRef.current) {
      testAudioCtxRef.current.close().catch(() => {});
      testAudioCtxRef.current = null;
    }
    setIsTestingMic(false);
    setMicVolume(0);
  };

  // Test speaker with pleasant soft synth chime
  const testSpeaker = async () => {
    try {
      const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();

      osc.type = "sine";
      osc.frequency.setValueAtTime(523.25, audioCtx.currentTime); // C5
      osc.frequency.exponentialRampToValueAtTime(659.25, audioCtx.currentTime + 0.15); // E5
      osc.frequency.exponentialRampToValueAtTime(783.99, audioCtx.currentTime + 0.3); // G5

      gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.6);

      osc.connect(gain);
      gain.connect(audioCtx.destination);

      osc.start();
      osc.stop(audioCtx.currentTime + 0.6);

      setTimeout(() => {
        audioCtx.close().catch(() => {});
      }, 700);
    } catch (err) {
      console.warn("[useAudioDevices] Speaker test error:", err);
    }
  };

  useEffect(() => {
    enumerate();
    const handleDeviceChange = () => {
      enumerate();
    };
    navigator.mediaDevices?.addEventListener("devicechange", handleDeviceChange);
    return () => {
      stopMicTest();
      navigator.mediaDevices?.removeEventListener("devicechange", handleDeviceChange);
    };
  }, [enumerate]);

  return {
    inputDevices,
    outputDevices,
    selectedInputId,
    selectedOutputId,
    hasPermission,
    requestPermission,
    selectInput,
    selectOutput,
    micVolume,
    isTestingMic,
    startMicTest,
    stopMicTest,
    testSpeaker,
    refreshDevices: enumerate,
  };
}
