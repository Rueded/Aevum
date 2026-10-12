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
} from "../../presentation/stickerRegistry";
import styles from "./StickerPickerModal.module.css";

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
  const filteredStickers =
    selectedCategory === "全部"
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
    <>
      <div className={styles.backdrop} onClick={onClose} />
      <div className={styles.popover}>
      <div className={styles.header}>
        <div className={styles.title}>
          <span>🎨 表情包斗图库</span>
          <span className={styles.countBadge}>{displayCount}</span>
        </div>
        <div className={styles.actions}>
          <label className={styles.uploadBtn} title="导入本地图片/GIF作为表情包">
            <span>📁 导入表情</span>
            <input
              type="file"
              accept="image/*"
              style={{ display: "none" }}
              onChange={handleFileUpload}
            />
          </label>
          <button type="button" className={styles.closeBtn} onClick={onClose} title="关闭">
            ✕
          </button>
        </div>
      </div>

      {recentStickerIds.length > 0 && (
        <div className={styles.recentStrip}>
          <span>🕒 常用:</span>
          <div className={styles.recentItems}>
            {recentStickerIds.slice(0, 7).map((id) => {
              const builtin = STICKER_REGISTRY[id];
              const custom = !builtin ? getCustomStickerById(id) : undefined;
              if (!builtin && !custom) return null;
              return (
                <button
                  key={`recent-${id}`}
                  type="button"
                  className={styles.recentBtn}
                  title={builtin ? builtin.name : custom?.name}
                  onClick={() => handlePickSticker(id)}
                >
                  {builtin ? (
                    builtin.renderSvg(24)
                  ) : custom ? (
                    <img src={custom.dataUrl} alt={custom.name} className={styles.recentImg} />
                  ) : null}
                </button>
              );
            })}
          </div>
        </div>
      )}

      <div className={styles.categoryTabs}>
        {STICKER_CATEGORIES.map((cat) => (
          <button
            key={cat}
            type="button"
            className={`${styles.tabPill} ${selectedCategory === cat ? styles.tabPillActive : ""}`}
            onClick={() => setSelectedCategory(cat)}
          >
            {cat} {cat === "我的收藏" && customStickers.length > 0 && `(${customStickers.length})`}
          </button>
        ))}
      </div>

      <div className={styles.gridContainer}>
        {isCustomCategory ? (
          customStickers.length === 0 ? (
            <div className={styles.emptyState}>
              <span style={{ fontSize: 24 }}>📁</span>
              <p>暂无自定义收藏表情</p>
              <p>点击右上角【📁 导入表情】添加本地图片或 GIF！</p>
            </div>
          ) : (
            customStickers.map((custom) => (
              <div key={custom.id} className={styles.gridItem}>
                <div
                  className={styles.thumbWrap}
                  onClick={() => handlePickSticker(custom.id)}
                  title={custom.name}
                >
                  <img src={custom.dataUrl} alt={custom.name} className={styles.customThumb} />
                </div>
                <span className={styles.thumbLabel}>{custom.name}</span>
                <button
                  type="button"
                  className={styles.deleteBadge}
                  title="删除"
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
                <div key={custom.id} className={styles.gridItem}>
                  <div
                    className={styles.thumbWrap}
                    onClick={() => handlePickSticker(custom.id)}
                    title={custom.name}
                  >
                    <img src={custom.dataUrl} alt={custom.name} className={styles.customThumb} />
                  </div>
                  <span className={styles.thumbLabel}>{custom.name}</span>
                  <button
                    type="button"
                    className={styles.deleteBadge}
                    title="删除"
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
              <div
                key={sticker.id}
                className={styles.gridItem}
                onClick={() => handlePickSticker(sticker.id)}
                title={`${sticker.name} (${sticker.description})`}
              >
                <div className={styles.thumbWrap}>{sticker.renderSvg(56)}</div>
                <span className={styles.thumbLabel}>{sticker.name}</span>
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  </>
);
};
