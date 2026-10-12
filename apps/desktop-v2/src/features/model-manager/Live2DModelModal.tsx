import React, { useState } from "react";
import { api } from "../../api";

export interface Live2DModelConfig {
  type: "preset" | "custom_live2d" | "custom_image";
  url: string;
  name: string;
  previewUrl?: string;
  description?: string;
}

export const PRESET_MODELS: Live2DModelConfig[] = [
  {
    type: "preset",
    name: "🌸 日和 (Hiyori Live2D 经典元气少女)",
    url: "https://raw.githubusercontent.com/iCharlesL/Live2D-Library/master/hiyori/hiyori_free_t08.model3.json",
    previewUrl: "https://images.unsplash.com/photo-1607604276583-eef5d076aa5f?auto=format&fit=crop&w=400&q=80",
    description: "性格开朗阳光的 Live2D 官方元气少女，支持灵动视线跟随与呼吸律动",
  },
  {
    type: "preset",
    name: "🍃 静久 (Shizuku 经典温婉学姐)",
    url: "https://cdn.jsdelivr.net/gh/fghrsh/live2d_api/model/shizuku/index.json",
    previewUrl: "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=400&q=80",
    description: "温婉知性的二次元校园学姐风格，动作自然细腻",
  },
  {
    type: "preset",
    name: "🎀 春 (Haru 甜美治愈系)",
    url: "https://cdn.jsdelivr.net/gh/guansss/pixi-live2d-display/test/assets/haru/haru_greeter_t03.model3.json",
    previewUrl: "https://images.unsplash.com/photo-1563089145-599997674d42?auto=format&fit=crop&w=400&q=80",
    description: "充满元气的甜美治愈系伴侣，常伴身旁",
  },
  {
    type: "custom_image",
    name: "✨ 苏棠官方概念立绘 (Official Character Portrait)",
    url: "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=600&q=80",
    previewUrl: "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=600&q=80",
    description: "唯美动漫艺术概念立绘，配合环境呼吸光环与语音波形律动",
  },
];

interface Live2DModelModalProps {
  isOpen: boolean;
  onClose: () => void;
  onModelChanged?: () => void;
}

export const Live2DModelModal: React.FC<Live2DModelModalProps> = ({
  isOpen,
  onClose,
  onModelChanged,
}) => {
  const [selectedPreset, setSelectedPreset] = useState<string>(() => {
    return localStorage.getItem("aevum_live2d_selected_preset") || PRESET_MODELS[0].url;
  });
  const [customModelUrl, setCustomModelUrl] = useState<string>(() => {
    return localStorage.getItem("aevum_custom_live2d_url") || "";
  });
  const [customImageUrl, setCustomImageUrl] = useState<string>(() => {
    const av = localStorage.getItem("aevum_custom_avatar_url") || "";
    if (av.includes("texture_") || av.includes("/textures/") || av.includes("\\textures\\")) {
      return "";
    }
    return av;
  });
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [isUploadingZip, setIsUploadingZip] = useState(false);
  const [localModels, setLocalModels] = useState<
    Array<{
      id: string;
      name: string;
      model_serve_url: string;
      avatar_data_url: string | null;
      is_current: boolean;
    }>
  >([]);

  React.useEffect(() => {
    if (isOpen) {
      api.listAvailableModels().then(setLocalModels).catch(console.warn);
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const safeSetItem = (key: string, value: string) => {
    if (
      key === "aevum_custom_avatar_url" &&
      (value.includes("texture_") || value.includes("/textures/") || value.includes("\\textures\\"))
    ) {
      console.warn("Blocked attempt to store texture atlas sheet as avatar");
      localStorage.removeItem("aevum_custom_avatar_url");
      return;
    }

    try {
      localStorage.setItem(key, value);
    } catch (e) {
      console.warn(`localStorage.setItem("${key}") quota exceeded, running auto-cleanup...`, e);
      try {
        const keysToRemove: string[] = [];
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          if (k) {
            const v = localStorage.getItem(k);
            if (v && v.length > 30000) {
              keysToRemove.push(k);
            }
          }
        }
        for (const k of keysToRemove) {
          console.warn(`Purged bloated localStorage key: ${k}`);
          localStorage.removeItem(k);
        }
        localStorage.setItem(key, value);
      } catch (innerErr) {
        console.warn(`safeSetItem still failed after cleanup:`, innerErr);
      }
    }
  };

  const handleApplyPreset = (preset: Live2DModelConfig) => {
    setSelectedPreset(preset.url);
    safeSetItem("aevum_live2d_selected_preset", preset.url);
    if (preset.type === "custom_image") {
      safeSetItem("aevum_visual_mode", "image");
      safeSetItem("aevum_custom_avatar_url", preset.url);
      safeSetItem("aevum_custom_live2d_url", "");
    } else {
      safeSetItem("aevum_visual_mode", "live2d");
      safeSetItem("aevum_custom_live2d_url", preset.url);
      if (preset.previewUrl) {
        safeSetItem("aevum_custom_avatar_url", preset.previewUrl);
      } else {
        localStorage.removeItem("aevum_custom_avatar_url");
      }
    }
    setStatusMsg(`✅ 已切换为形象: ${preset.name}`);
    window.dispatchEvent(new Event("aevum-avatar-updated"));
    onModelChanged?.();
    setTimeout(() => setStatusMsg(null), 2500);
  };

  const handleApplyLocalModel = async (model: {
    id: string;
    name: string;
    model_serve_url: string;
    avatar_data_url: string | null;
  }) => {
    try {
      await api.setActiveModel(model.id);
      safeSetItem("aevum_visual_mode", "live2d");
      safeSetItem("aevum_custom_live2d_url", model.model_serve_url);
      if (model.avatar_data_url) {
        safeSetItem("aevum_custom_avatar_url", model.avatar_data_url);
      } else {
        localStorage.removeItem("aevum_custom_avatar_url");
      }
      setSelectedPreset("");
      setStatusMsg(`🎉 成功切换并持久化 Live2D 模型 [${model.name}]！`);
      window.dispatchEvent(new Event("aevum-avatar-updated"));
      onModelChanged?.();
      api.listAvailableModels().then(setLocalModels).catch(console.warn);
      setTimeout(() => setStatusMsg(null), 3000);
    } catch (err: unknown) {
      setStatusMsg(`⚠️ 切换失败: ${err instanceof Error ? err.message : String(err)}`);
    }
  };

  const handleZipUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".zip")) {
      setStatusMsg("⚠️ 请选择 .zip 格式的 Live2D 模型压缩包！");
      return;
    }

    try {
      setIsUploadingZip(true);
      setStatusMsg(`⏳ 正在上传并解压模型 [${file.name}]，构建 WebGL 骨骼与物理动力学...`);
      const res = await api.uploadLive2DZip(file);
      if (res.success && res.model_serve_url) {
        safeSetItem("aevum_visual_mode", "live2d");
        safeSetItem("aevum_custom_live2d_url", res.model_serve_url);
        if (res.avatar_data_url) {
          safeSetItem("aevum_custom_avatar_url", res.avatar_data_url);
        } else {
          localStorage.removeItem("aevum_custom_avatar_url");
        }
        setStatusMsg(`🎉 成功导入 Live2D 模型 [${res.name}]！已激活真实 WebGL 骨骼、视线跟随与呼吸律动！`);
        window.dispatchEvent(new Event("aevum-avatar-updated"));
        onModelChanged?.();
        setTimeout(() => setStatusMsg(null), 4000);
      } else {
        setStatusMsg(`⚠️ ${res.message || "未能识别模型结构，请确认压缩包内含有 .model3.json"}`);
      }
    } catch (err: unknown) {
      setStatusMsg(`⚠️ 上传模型失败: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsUploadingZip(false);
      e.target.value = "";
    }
  };

  const handleSaveCustomLive2D = async () => {
    const rawInput = customModelUrl.trim();
    if (!rawInput) return;

    // 1. Check if user typed a local Windows/Unix filesystem path (e.g. D:\... or C:\... or /Users/...)
    const isLocalPath = /^[a-zA-Z]:[\\/]/.test(rawInput) || rawInput.startsWith("/");
    if (isLocalPath) {
      try {
        setStatusMsg("⏳ 正在通过 Aevum 本地服务解析该 Live2D 模型并启动 WebGL 骨骼动力学...");
        const res = await api.resolveLocalModel(rawInput);
        if (res.success) {
          if (res.model_serve_url) {
            safeSetItem("aevum_visual_mode", "live2d");
            safeSetItem("aevum_custom_live2d_url", res.model_serve_url);
            if (res.avatar_data_url) {
              safeSetItem("aevum_custom_avatar_url", res.avatar_data_url);
            } else {
              localStorage.removeItem("aevum_custom_avatar_url");
            }
            setStatusMsg(`🎉 成功加载本地 Live2D 模型 [${res.name}]！已激活真实 WebGL 骨骼、灵动呼吸与眨眼！`);
          } else if (res.avatar_data_url) {
            safeSetItem("aevum_visual_mode", "image");
            safeSetItem("aevum_custom_avatar_url", res.avatar_data_url);
            safeSetItem("aevum_custom_live2d_url", rawInput);
            setStatusMsg(`✅ 成功加载本地角色立绘 [${res.name}]！`);
          }
          window.dispatchEvent(new Event("aevum-avatar-updated"));
          onModelChanged?.();
          setTimeout(() => setStatusMsg(null), 4000);
          return;
        } else {
          setStatusMsg(`⚠️ ${res.message || "未能解析该模型，请检查路径是否正确"}`);
          return;
        }
      } catch (err: unknown) {
        setStatusMsg(`⚠️ 本地解析提示: ${err instanceof Error ? err.message : String(err)}。`);
        return;
      }
    }

    // 2. Check if user typed an image URL (PNG, JPG, WebP, GIF, SVG, DataURL)
    const isImageUrl = /\.(png|jpe?g|webp|gif|svg)($|\?)/i.test(rawInput) || rawInput.startsWith("data:image/");
    if (isImageUrl) {
      safeSetItem("aevum_visual_mode", "image");
      safeSetItem("aevum_custom_avatar_url", rawInput);
      safeSetItem("aevum_custom_live2d_url", rawInput);
      window.dispatchEvent(new Event("aevum-avatar-updated"));
      setStatusMsg("✅ 已成功将图片设置为伴侣形象！正在刷新立绘画布...");
      onModelChanged?.();
      setTimeout(() => setStatusMsg(null), 3000);
      return;
    }

    // 3. Online Live2D Model URL (e.g. https://.../character.model3.json)
    if (rawInput.startsWith("http://") || rawInput.startsWith("https://")) {
      safeSetItem("aevum_visual_mode", "live2d");
      safeSetItem("aevum_custom_live2d_url", rawInput);
      localStorage.removeItem("aevum_custom_avatar_url"); // Prevent texture atlas sheet leak
      window.dispatchEvent(new Event("aevum-avatar-updated"));
      setStatusMsg("✅ 自定义 Live2D 在线模型已保存并应用！");
      onModelChanged?.();
      setTimeout(() => setStatusMsg(null), 3000);
      return;
    }

    setStatusMsg("⚠️ 请输入有效的本地模型路径 (如 D:\\Live2D\\hiyori) 或在线地址！");
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.type.startsWith("image/") || /\.(png|jpe?g|webp|gif)$/i.test(file.name)) {
      const reader = new FileReader();
      reader.onload = (uploadEvent) => {
        const base64 = uploadEvent.target?.result as string;
        setCustomImageUrl(base64);
        safeSetItem("aevum_visual_mode", "image");
        safeSetItem("aevum_custom_avatar_url", base64);
        safeSetItem("aevum_custom_live2d_url", "");
        window.dispatchEvent(new Event("aevum-avatar-updated"));
        setStatusMsg(`✅ 已成功导入并应用角色立绘: ${file.name}！`);
        onModelChanged?.();
        setTimeout(() => setStatusMsg(null), 3000);
      };
      reader.readAsDataURL(file);
    } else {
      setStatusMsg("⚠️ 请选择 PNG、JPG、WebP 格式的高清立绘图片文件！");
    }
  };

  const handleResetToDefault = () => {
    localStorage.removeItem("aevum_custom_avatar_url");
    localStorage.removeItem("aevum_custom_live2d_url");
    localStorage.removeItem("aevum_visual_mode");
    localStorage.removeItem("aevum_live2d_selected_preset");
    window.dispatchEvent(new Event("aevum-avatar-updated"));
    setStatusMsg("已重置为默认呼吸光环模式");
    onModelChanged?.();
    setTimeout(() => setStatusMsg(null), 2000);
  };

  return (
    <div
      className="modal-overlay"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.75)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 2000,
      }}
    >
      <div
        className="modal-container"
        style={{
          width: "580px",
          maxWidth: "92vw",
          maxHeight: "85vh",
          overflowY: "auto",
          background: "#181825",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          borderRadius: "16px",
          padding: "24px",
          boxShadow: "0 20px 50px rgba(0, 0, 0, 0.7)",
          color: "#e2e8f0",
        }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
          <h2 style={{ margin: 0, fontSize: "18px", fontWeight: 700, display: "flex", alignItems: "center", gap: "8px" }}>
            <span>🎨</span>
            <span>伴侣视觉形象与 Live2D 模型管理</span>
          </h2>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "rgba(255,255,255,0.6)",
              fontSize: "20px",
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </div>

        {statusMsg && (
          <div
            style={{
              background: "rgba(16, 185, 129, 0.15)",
              border: "1px solid rgba(16, 185, 129, 0.3)",
              color: "#34d399",
              padding: "10px 14px",
              borderRadius: "8px",
              fontSize: "13px",
              marginBottom: "16px",
              lineHeight: 1.4,
            }}
          >
            {statusMsg}
          </div>
        )}

        {/* 1. 本地已安装 Live2D 模型 */}
        {localModels.length > 0 && (
          <div style={{ marginBottom: "22px" }}>
            <h4 style={{ margin: "0 0 10px 0", fontSize: "14px", color: "#38bdf8", display: "flex", alignItems: "center", gap: "6px" }}>
              <span>💾</span>
              <span>本地已安装 Live2D 伴侣模型 ({localModels.length} 个可用)</span>
            </h4>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: "10px" }}>
              {localModels.map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => handleApplyLocalModel(m)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "10px 12px",
                    background: m.is_current ? "rgba(56, 189, 248, 0.2)" : "rgba(255, 255, 255, 0.04)",
                    border: m.is_current ? "1.5px solid #38bdf8" : "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: "10px",
                    color: "inherit",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.15s ease",
                  }}
                >
                  <span style={{ fontSize: "20px" }}>🎎</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "13px", fontWeight: 600, color: m.is_current ? "#38bdf8" : "#f1f5f9" }}>
                      {m.name}
                    </div>
                    <div style={{ fontSize: "11px", color: m.is_current ? "#7dd3fc" : "rgba(255, 255, 255, 0.5)" }}>
                      {m.is_current ? "● 当前使用中" : "点击切换此模型"}
                    </div>
                  </div>
                </button>
              ))}
            </div>
          </div>
        )}

        {/* 2. Presets */}
        <div style={{ marginBottom: "22px" }}>
          <h4 style={{ margin: "0 0 10px 0", fontSize: "14px", color: "rgba(255,255,255,0.9)" }}>
            2. 精选预设二次元角色模型与立绘
          </h4>
          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            {PRESET_MODELS.map((preset) => (
              <button
                key={preset.url}
                type="button"
                onClick={() => handleApplyPreset(preset)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "10px 14px",
                  background: selectedPreset === preset.url ? "rgba(99, 102, 241, 0.22)" : "rgba(255, 255, 255, 0.04)",
                  border: selectedPreset === preset.url ? "1.5px solid #818cf8" : "1px solid rgba(255, 255, 255, 0.08)",
                  borderRadius: "10px",
                  color: "inherit",
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all 0.15s ease",
                }}
              >
                {preset.previewUrl && (
                  <img
                    src={preset.previewUrl}
                    alt={preset.name}
                    style={{
                      width: "46px",
                      height: "46px",
                      borderRadius: "50%",
                      objectFit: "cover",
                      border: "2px solid rgba(255, 255, 255, 0.2)",
                      flexShrink: 0,
                    }}
                  />
                )}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <span style={{ fontSize: "13.5px", fontWeight: 600 }}>{preset.name}</span>
                    <span
                      style={{
                        fontSize: "11.5px",
                        fontWeight: 500,
                        padding: "2px 8px",
                        borderRadius: "10px",
                        background: selectedPreset === preset.url ? "rgba(99, 102, 241, 0.4)" : "rgba(255, 255, 255, 0.08)",
                        color: selectedPreset === preset.url ? "#a5b4fc" : "rgba(255, 255, 255, 0.5)",
                      }}
                    >
                      {selectedPreset === preset.url ? "● 使用中" : "点击切换"}
                    </span>
                  </div>
                  {preset.description && (
                    <div style={{ fontSize: "11.5px", color: "rgba(255, 255, 255, 0.55)", marginTop: "3px" }}>
                      {preset.description}
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* 2. Live2D Model Import Section */}
        <div style={{ marginBottom: "22px", background: "rgba(255, 255, 255, 0.02)", padding: "14px", borderRadius: "10px", border: "1px solid rgba(255, 255, 255, 0.08)" }}>
          <h4 style={{ margin: "0 0 8px 0", fontSize: "14px", color: "rgba(255,255,255,0.9)", display: "flex", alignItems: "center", gap: "6px" }}>
            <span>💃</span>
            <span>2. 导入自定义 Live2D 模型 (动态骨骼、眨眼、视线跟随)</span>
          </h4>
          <p style={{ margin: "0 0 12px 0", fontSize: "12px", color: "rgba(255,255,255,0.55)", lineHeight: 1.5 }}>
            支持一键上传模型压缩包 (.zip)，或输入本地模型文件夹路径与在线 <code>.model3.json</code> 地址。<br />
            <span style={{ color: "#a5b4fc" }}>💡 提示：Live2D 模型包含骨骼动力学与贴图切片，系统会自动装配。请直接上传压缩包或选择文件夹，无需单独提取内部贴图。</span>
          </p>

          {/* Option A: Zip Upload */}
          <div style={{ marginBottom: "12px" }}>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                padding: "12px",
                background: "rgba(99, 102, 241, 0.08)",
                border: "1.5px dashed rgba(99, 102, 241, 0.4)",
                borderRadius: "8px",
                cursor: isUploadingZip ? "not-allowed" : "pointer",
                fontSize: "13px",
                fontWeight: 600,
                color: "#c7d2fe",
                transition: "all 0.15s ease",
              }}
            >
              <span>{isUploadingZip ? "⏳ 正在上传并解压模型包..." : "📦 点击选择 Live2D 模型压缩包 (.zip)"}</span>
              <input
                type="file"
                accept=".zip"
                disabled={isUploadingZip}
                onChange={handleZipUpload}
                style={{ display: "none" }}
              />
            </label>
          </div>

          {/* Option B: Path or URL */}
          <div style={{ display: "flex", gap: "8px" }}>
            <input
              type="text"
              value={customModelUrl}
              onChange={(e) => setCustomModelUrl(e.target.value)}
              placeholder="或输入本地模型文件夹路径 (如 D:\Live2D\hiyori) 或在线地址"
              style={{
                flex: 1,
                background: "rgba(255,255,255,0.06)",
                border: "1px solid rgba(255,255,255,0.15)",
                borderRadius: "6px",
                padding: "8px 12px",
                color: "inherit",
                fontSize: "13px",
              }}
            />
            <button
              type="button"
              onClick={handleSaveCustomLive2D}
              style={{
                background: "#6366f1",
                color: "white",
                border: "none",
                borderRadius: "6px",
                padding: "8px 14px",
                fontSize: "13px",
                fontWeight: 600,
                cursor: "pointer",
                whiteSpace: "nowrap",
              }}
            >
              解析并加载
            </button>
          </div>
        </div>

        {/* 3. Custom Image Artwork / Portrait Upload */}
        <div style={{ marginBottom: "22px", background: "rgba(255, 255, 255, 0.02)", padding: "14px", borderRadius: "10px", border: "1px solid rgba(255, 255, 255, 0.08)" }}>
          <h4 style={{ margin: "0 0 8px 0", fontSize: "14px", color: "rgba(255,255,255,0.9)", display: "flex", alignItems: "center", gap: "6px" }}>
            <span>🖼️</span>
            <span>3. 导入 2D 静态原画立绘 (PNG / JPG / WebP)</span>
          </h4>
          <p style={{ margin: "0 0 12px 0", fontSize: "12px", color: "rgba(255,255,255,0.55)", lineHeight: 1.5 }}>
            如果您拥有角色的整身立绘或高清插画，可直接在此上传作为伴侣形象（自动附加环境呼吸光环与语音波形律动）。
          </p>
          <label
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "8px",
              padding: "12px",
              background: "rgba(255,255,255,0.04)",
              border: "1px dashed rgba(255,255,255,0.25)",
              borderRadius: "8px",
              cursor: "pointer",
              fontSize: "13px",
              color: "#a5b4fc",
            }}
          >
            <span>📁 点击选择电脑中的高清立绘图片</span>
            <input
              type="file"
              accept=".png,.jpg,.jpeg,.webp"
              onChange={handleImageUpload}
              style={{ display: "none" }}
            />
          </label>
          {customImageUrl && (
            <div style={{ marginTop: "10px", display: "flex", alignItems: "center", gap: "10px" }}>
              <img
                src={customImageUrl}
                alt="Custom Avatar Preview"
                style={{ width: "40px", height: "40px", borderRadius: "50%", objectFit: "cover", border: "1.5px solid #6366f1" }}
              />
              <span style={{ fontSize: "12px", color: "#10b981" }}>已加载当前自定义立绘</span>
            </div>
          )}
        </div>

        {/* Footer controls */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", paddingTop: "14px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
          <button
            type="button"
            onClick={handleResetToDefault}
            style={{
              background: "transparent",
              border: "1px solid rgba(255,255,255,0.2)",
              color: "rgba(255,255,255,0.6)",
              borderRadius: "6px",
              padding: "6px 12px",
              fontSize: "12px",
              cursor: "pointer",
            }}
          >
            还原默认形象
          </button>
          <button
            type="button"
            onClick={onClose}
            style={{
              background: "rgba(255,255,255,0.12)",
              color: "white",
              border: "none",
              borderRadius: "6px",
              padding: "6px 18px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
            }}
          >
            完成
          </button>
        </div>
      </div>
    </div>
  );
};


