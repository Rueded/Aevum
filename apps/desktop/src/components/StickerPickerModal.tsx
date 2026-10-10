import React, { useState, useEffect } from "react";
import {
  getAllStickers,
  STICKER_CATEGORIES,
  STICKER_REGISTRY,
  StickerItem,
  getCustomStickers,
  saveCustomSticker,
  deleteCustomSticker,
  CustomStickerItem,
  getRecentStickers,
  recordRecentSticker,
  getCustomStickerById,
} from "../presentation/stickerRegistry";

interface StickerPickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectSticker: (stickerId: string) => void;
}

export const StickerPickerModal: React.FC<StickerPickerModalProps> = ({
  isOpen,
  onClose,
  onSelectSticker,
}) => {
  const [selectedCategory, setSelectedCategory] = useState<string>("全部");
  const [customStickers, setCustomStickers] = useState<CustomStickerItem[]>([]);
  const [recentStickerIds, setRecentStickerIds] = useState<string[]>([]);

  useEffect(() => {
    if (isOpen) {
      setCustomStickers(getCustomStickers());
      setRecentStickerIds(getRecentStickers());
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const allStickers = getAllStickers();
  const isCustomCategory = selectedCategory === "我的收藏";
  const filteredStickers = selectedCategory === "全部"
    ? allStickers
    : allStickers.filter((s) => s.category === selectedCategory);

  const displayCount = isCustomCategory
    ? customStickers.length
    : selectedCategory === "全部"
    ? allStickers.length + customStickers.length
    : filteredStickers.length;

  const handlePickSticker = (id: string) => {
    recordRecentSticker(id);
    onSelectSticker(id);
    onClose();
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      alert("表情包图片大小不能超过 5MB 哦！");
      return;
    }

    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target?.result as string;
      if (dataUrl) {
        const newSticker: CustomStickerItem = {
          id: `custom_${Date.now()}`,
          name: file.name.replace(/\.[^/.]+$/, ""),
          dataUrl,
          createdAt: Date.now(),
        };
        saveCustomSticker(newSticker);
        setCustomStickers(getCustomStickers());
        setSelectedCategory("我的收藏");
      }
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  return (
    <div className="sticker-picker-popover">
      <div className="sticker-picker-header">
        <div className="sticker-picker-title">
          <span className="sticker-title-icon">🎨</span>
          <span>表情包斗图库</span>
          <span className="sticker-count-badge">{displayCount}</span>
        </div>
        <div className="sticker-header-actions">
          <label className="sticker-upload-btn" title="导入本地图片/GIF作为表情包">
            <span>📁 导入表情</span>
            <input
              type="file"
              accept="image/*"
              style={{ display: "none" }}
              onChange={handleFileUpload}
            />
          </label>
          <button
            type="button"
            className="sticker-close-btn"
            onClick={onClose}
            title="关闭"
          >
            ✕
          </button>
        </div>
      </div>

      {recentStickerIds.length > 0 && (
        <div className="sticker-recent-strip">
          <span className="sticker-recent-label">🕒 常用:</span>
          <div className="sticker-recent-items">
            {recentStickerIds.slice(0, 7).map((id) => {
              const builtin = STICKER_REGISTRY[id];
              const custom = !builtin ? getCustomStickerById(id) : undefined;
              if (!builtin && !custom) return null;
              return (
                <button
                  key={`recent-${id}`}
                  type="button"
                  className="sticker-recent-btn"
                  title={builtin ? builtin.name : custom?.name}
                  onClick={() => handlePickSticker(id)}
                >
                  {builtin ? (
                    builtin.renderSvg(28)
                  ) : custom ? (
                    <img src={custom.dataUrl} alt={custom.name} className="sticker-recent-img" />
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className="sticker-category-tabs">
        {STICKER_CATEGORIES.map((cat) => (
          <button
            key={cat}
            type="button"
            className={`sticker-tab-pill ${selectedCategory === cat ? "active" : ""}`}
            onClick={() => setSelectedCategory(cat)}
          >
            {cat} {cat === "我的收藏" && customStickers.length > 0 && `(${customStickers.length})`}
          </button>
        ))}
      </div>

      <div className="sticker-grid-container">
        {isCustomCategory ? (
          customStickers.length === 0 ? (
            <div className="sticker-empty-state">
              <span className="empty-icon">📁</span>
              <p>暂无自定义收藏表情</p>
              <p className="empty-sub">点击右上角【📁 导入表情】添加本地图片或 GIF 动图！</p>
            </div>
          ) : (
            customStickers.map((custom) => (
              <div key={custom.id} className="sticker-grid-item custom-sticker-item">
                <button
                  type="button"
                  className="sticker-thumb-btn"
                  onClick={() => handlePickSticker(custom.id)}
                  title={custom.name}
                >
                  <div className="sticker-thumb-wrap">
                    <img src={custom.dataUrl} alt={custom.name} className="sticker-custom-thumb" />
                  </div>
                  <span className="sticker-thumb-label">{custom.name}</span>
                </button>
                <button
                  type="button"
                  className="sticker-delete-badge"
                  title="删除此表情"
                  onClick={(e) => {
                    e.stopPropagation();
                    deleteCustomSticker(custom.id);
                    setCustomStickers(getCustomStickers());
                  }}
                >
                  ✕
                </button>
              </div>
            ))
          )
        ) : (
          <>
            {selectedCategory === "全部" &&
              customStickers.map((custom) => (
                <div key={custom.id} className="sticker-grid-item custom-sticker-item">
                  <button
                    type="button"
                    className="sticker-thumb-btn"
                    onClick={() => handlePickSticker(custom.id)}
                    title={custom.name}
                  >
                    <div className="sticker-thumb-wrap">
                      <img src={custom.dataUrl} alt={custom.name} className="sticker-custom-thumb" />
                    </div>
                    <span className="sticker-thumb-label">{custom.name}</span>
                  </button>
                  <button
                    type="button"
                    className="sticker-delete-badge"
                    title="删除此表情"
                    onClick={(e) => {
                      e.stopPropagation();
                      deleteCustomSticker(custom.id);
                      setCustomStickers(getCustomStickers());
                    }}
                  >
                    ✕
                  </button>
                </div>
              ))}
            {filteredStickers.map((sticker: StickerItem) => (
              <button
                key={sticker.id}
                type="button"
                className="sticker-grid-item"
                onClick={() => handlePickSticker(sticker.id)}
                title={`${sticker.name} (${sticker.description})`}
              >
                <div className="sticker-thumb-wrap">
                  {sticker.renderSvg(76)}
                </div>
                <span className="sticker-thumb-label">{sticker.name}</span>
              </button>
            ))}
          </>
        )}
      </div>

      <div className="sticker-picker-footer">
        <span>💡 点击直接发送真实表情包，开启与 Aevum 的趣味斗图！</span>
      </div>
    </div>
  );
};
