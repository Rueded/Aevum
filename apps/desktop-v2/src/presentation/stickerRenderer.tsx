import React from "react";
import { getStickerById, getCustomStickerById } from "./stickerRegistry";
import { renderTextWithEmojis } from "./emojiRenderer";

const STICKER_REGEX = /\[sticker:([a-zA-Z0-9_]+)\]/g;

/**
 * Mapping of colloquial Chinese bracket tags to official vector sticker IDs.
 * Allows natural conversational expressions like [猫猫问号] and [茶] to render as rich stickers.
 */
export const BRACKET_TO_STICKER_MAP: Record<string, string> = {
  // 猫猫日常
  "[猫猫问号]": "cat_surprised",
  "[问号]": "cat_surprised",
  "[震惊]": "cat_surprised",
  "[猫猫敲头]": "cat_bonk",
  "[敲头]": "cat_bonk",
  "[给你一锤]": "cat_bonk",
  "[摸摸头]": "cat_pat",
  "[摸头]": "cat_pat",
  "[摸摸猫头]": "cat_pat",
  "[傲娇]": "cat_pout",
  "[炸毛]": "cat_pout",
  "[傲娇炸毛]": "cat_pout",
  "[气鼓鼓]": "cat_pout",
  "[委屈]": "cat_crying",
  "[泪目]": "cat_crying",
  "[猫猫流泪]": "cat_crying",
  "[哭]": "cat_crying",
  "[打滚]": "cat_roll",
  "[猫猫打滚]": "cat_roll",
  "[撒娇]": "cat_roll",
  "[炫饭]": "cat_eat",
  "[开饭]": "cat_eat",
  "[快乐炫饭]": "cat_eat",

  // 害羞与心动
  "[脸红]": "cat_blush",
  "[害羞]": "cat_blush",
  "[脸红发烫]": "cat_blush",
  "[心跳加速]": "heart_sparkle",
  "[脸红心跳]": "heart_sparkle",
  "[心动]": "heart_sparkle",
  "[疯狂心动]": "heart_sparkle",
  "[爱心]": "heart_sparkle",
  "[贴贴]": "heart_sparkle",

  // 摸摸与抱抱
  "[摸摸]": "cat_pat",
  "[抱抱]": "cat_pat",

  // 搞怪互怼与捂脸
  "[捂脸]": "cat_facepalm",
  "[Facepalm]": "cat_facepalm",
  "[facepalm]": "cat_facepalm",
  "[没眼看]": "cat_facepalm",
  "[脑壳疼]": "cat_facepalm",

  // 日常摸鱼与搞怪
  "[咸鱼]": "give_up",
  "[摆烂]": "give_up",
  "[咸鱼摆烂]": "give_up",
  "[躺平]": "give_up",
  "[熊猫问号]": "panda_question",
  "[点赞]": "panda_thumbsup",
  "[为你点赞]": "panda_thumbsup",
  "[狗头]": "doge_smirk",
  "[战术狗头]": "doge_smirk",
  "[灵魂出窍]": "ghost_soul",
  "[升天]": "ghost_soul",
  "[茶]": "tea_sip",
  "[喝茶]": "tea_sip",
  "[战术喝茶]": "tea_sip",
  "[芜湖起飞]": "party_cheer",
  "[起飞]": "party_cheer",
  "[庆祝]": "party_cheer",
  "[警告]": "knife_threat",
  "[危险]": "knife_threat",
  "[拔刀]": "knife_threat",
};

export const COMPANION_PHOTOS: Record<string, { title: string; desc: string; url: string }> = {
  orange_cat: {
    title: "小橘的午后睡颜",
    desc: "刚刚在沙发上翻肚皮打呼噜的小橘 🐱",
    url: "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?auto=format&fit=crop&w=600&q=80",
  },
  piano_sheet: {
    title: "视唱练耳与钢琴乐谱",
    desc: "今天正在练的肖邦练习曲乐谱 🎹",
    url: "https://images.unsplash.com/photo-1520523839898-507125cd53c1?auto=format&fit=crop&w=600&q=80",
  },
  sunset_sky: {
    title: "雪隆傍晚的晚霞",
    desc: "阳台望出去的夕阳与晚霞 🌇",
    url: "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=600&q=80",
  },
  latte_art: {
    title: "街角咖啡馆的心形拉花",
    desc: "海边咖啡馆点的热拿铁，拉花挺好看 ☕",
    url: "https://images.unsplash.com/photo-1534778101976-62847782c213?auto=format&fit=crop&w=600&q=80",
  },
};

export interface ResolvedPhotoMeta {
  url: string;
  title: string;
  desc?: string;
  styleBadge?: string;
}

export function resolvePhotoMeta(token: string): ResolvedPhotoMeta | null {
  const trimmed = token.trim();

  // 1. Static presets
  if (COMPANION_PHOTOS[trimmed]) {
    return { ...COMPANION_PHOTOS[trimmed], styleBadge: "📷 生活随手拍" };
  }

  // 2. Dynamic AI generation: anime, real, art, ai, web
  const colonIdx = trimmed.indexOf(":");
  if (colonIdx > 0) {
    const type = trimmed.slice(0, colonIdx).toLowerCase();
    const payload = trimmed.slice(colonIdx + 1);
    const parts = payload.split("|").map((p) => p.trim());
    const prompt = parts[0];
    const title = parts[1] || "苏棠的生活随手拍";
    const desc = parts[2] || prompt;

    if (type === "web" || type === "http" || type === "https") {
      const fullUrl = type === "web" ? parts[0] : `${type}:${parts[0]}`;
      return { url: fullUrl, title, desc, styleBadge: "🌐 网络图片" };
    }

    let model = "flux-anime";
    let styleBadge = "🎨 二次元动漫";
    let finalPrompt = prompt;

    if (type === "real" || type === "realistic" || type === "photo") {
      model = "flux";
      styleBadge = "📷 真实日常抓拍";
      finalPrompt = `${prompt}, realistic photography, candid photo snapshot, 4k`;
    } else if (type === "art" || type === "midjourney") {
      model = "midjourney";
      styleBadge = "✨ 艺术电影风";
    } else if (type === "anime" || type === "2d" || type === "manga") {
      model = "flux-anime";
      styleBadge = "🎨 二次元动漫";
    }

    const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(finalPrompt)}?model=${model}&width=768&height=576&nologo=true`;
    return { url, title, desc, styleBadge };
  }

  // 3. Fallback: if it starts with http
  if (trimmed.startsWith("http://") || trimmed.startsWith("https://")) {
    return { url: trimmed, title: "随手拍照片", styleBadge: "🌐 网络图片" };
  }

  // 4. Fallback: treat unrecognized token as prompt for flux-anime
  const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(trimmed)}?model=flux-anime&width=768&height=576&nologo=true`;
  return { url, title: trimmed, styleBadge: "🎨 AI 随手拍" };
}

export const CompanionPhotoCard: React.FC<ResolvedPhotoMeta> = ({ url, title, desc, styleBadge }) => {
  const [loaded, setLoaded] = React.useState(false);
  const [error, setError] = React.useState(false);

  return (
    <div style={{ margin: "10px 0", maxWidth: "280px" }}>
      <div
        style={{
          background: "rgba(255, 255, 255, 0.08)",
          backdropFilter: "blur(12px)",
          border: "1px solid rgba(255, 255, 255, 0.15)",
          borderRadius: "14px",
          overflow: "hidden",
          boxShadow: "0 6px 20px rgba(0, 0, 0, 0.35)",
          position: "relative",
        }}
      >
        <div style={{ position: "relative", minHeight: "180px", background: "rgba(0,0,0,0.25)" }}>
          {!loaded && !error && (
            <div
              style={{
                position: "absolute",
                inset: 0,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                color: "rgba(255,255,255,0.6)",
                fontSize: "12px",
                gap: "6px",
              }}
            >
              <span style={{ fontSize: "22px" }}>📸</span>
              <span>正在冲洗照片...</span>
            </div>
          )}
          {error ? (
            <div
              style={{
                height: "180px",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "rgba(255,255,255,0.5)",
                fontSize: "12px",
              }}
            >
              [照片加载超时]
            </div>
          ) : (
            <img
              src={url}
              alt={title}
              onLoad={() => setLoaded(true)}
              onError={() => setError(true)}
              style={{
                width: "100%",
                height: "180px",
                objectFit: "cover",
                display: "block",
                opacity: loaded ? 1 : 0,
                transition: "opacity 0.4s ease",
                cursor: "pointer",
              }}
              onClick={() => window.open(url, "_blank")}
              title="点击查看大图"
            />
          )}
          {styleBadge && (
            <span
              style={{
                position: "absolute",
                top: "8px",
                right: "8px",
                background: "rgba(0, 0, 0, 0.65)",
                backdropFilter: "blur(6px)",
                color: "#e2e8f0",
                fontSize: "10px",
                padding: "2px 7px",
                borderRadius: "10px",
                border: "1px solid rgba(255,255,255,0.2)",
              }}
            >
              {styleBadge}
            </span>
          )}
        </div>
        <div style={{ padding: "8px 12px" }}>
          <div style={{ fontWeight: 600, fontSize: "13px", color: "#fff" }}>📸 {title}</div>
          {desc && (
            <div style={{ fontSize: "11px", color: "rgba(255, 255, 255, 0.7)", marginTop: "2px" }}>
              {desc}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const PHOTO_REGEX = /\[photo:([^\]]+)\]/g;
const MARKDOWN_IMAGE_REGEX = /!\[(.*?)\]\(((?:data:image\/[a-zA-Z0-9]+;base64,[A-Za-z0-9+/=]+|https?:\/\/[^\s)]+))\)/g;

export interface RenderContentOptions {
  emojiEnabled?: boolean;
  showEmojiLabel?: boolean;
  stickersEnabled?: boolean;
  standaloneLine?: boolean;
}

/**
 * Check if the text consists solely of a single sticker tag.
 */
export function isStandaloneSticker(text: string): string | null {
  const trimmed = text.trim();
  const match = trimmed.match(/^\[sticker:([a-zA-Z0-9_]+)\]$/);
  if (match) return match[1];

  const bracketMapped = BRACKET_TO_STICKER_MAP[trimmed];
  return bracketMapped || null;
}

/**
 * Renders text containing [sticker:id] tokens, [photo:id] cards, markdown images, and [bracket] emojis.
 */
export function renderContentWithStickersAndEmojis(
  content: string,
  optionsOrEmojiEnabled: boolean | RenderContentOptions = true
): React.ReactNode {
  if (!content) return content;

  const options: RenderContentOptions =
    typeof optionsOrEmojiEnabled === "boolean"
      ? { emojiEnabled: optionsOrEmojiEnabled }
      : optionsOrEmojiEnabled;

  const emojiEnabled = options.emojiEnabled ?? true;
  const showEmojiLabel = options.showEmojiLabel ?? false;
  const stickersEnabled = options.stickersEnabled ?? true;
  const standaloneLine = options.standaloneLine ?? true;

  // 1. If stickers are enabled, convert mapped bracket tags to [sticker:id]
  let processedContent = content;
  if (stickersEnabled) {
    for (const [bracketTag, stickerId] of Object.entries(BRACKET_TO_STICKER_MAP)) {
      if (processedContent.includes(bracketTag)) {
        processedContent = processedContent.split(bracketTag).join(`[sticker:${stickerId}]`);
      }
    }
  }

  // 2. Check for pure standalone sticker
  const standaloneId = isStandaloneSticker(processedContent);
  if (standaloneId && stickersEnabled) {
    const sticker = getStickerById(standaloneId);
    if (sticker) {
      return (
        <div className="standalone-sticker-card" title={sticker.name}>
          <div className="sticker-media-wrap">{sticker.renderSvg(140)}</div>
        </div>
      );
    }
    const custom = getCustomStickerById(standaloneId);
    if (custom) {
      return (
        <div className="standalone-sticker-card" title={custom.name}>
          <div className="sticker-media-wrap custom-sticker-media">
            <img src={custom.dataUrl} alt={custom.name} className="custom-sticker-img" />
          </div>
        </div>
      );
    }
  }

  // 3. Render Markdown Images and Photos
  const renderItemWithMedia = (textChunk: string, keyPrefix: string): React.ReactNode => {
    // Check for companion photo snapshots: [photo:id]
    if (textChunk.includes("[photo:")) {
      const photoParts = textChunk.split(PHOTO_REGEX);
      return photoParts.map((sub, sIdx) => {
        if (sIdx % 2 === 1) {
          const photoMeta = resolvePhotoMeta(sub);
          if (photoMeta) {
            return (
              <CompanionPhotoCard
                key={`${keyPrefix}-photo-${sIdx}`}
                url={photoMeta.url}
                title={photoMeta.title}
                desc={photoMeta.desc}
                styleBadge={photoMeta.styleBadge}
              />
            );
          }
          return `[photo:${sub}]`;
        }
        return renderItemWithMedia(sub, `${keyPrefix}-sub-${sIdx}`);
      });
    }

    // Check for inline markdown images: ![alt](url)
    if (MARKDOWN_IMAGE_REGEX.test(textChunk)) {
      const imgParts = textChunk.split(MARKDOWN_IMAGE_REGEX);
      const res: React.ReactNode[] = [];
      let i = 0;
      while (i < imgParts.length) {
        if (i % 3 === 0) {
          if (imgParts[i]) {
            res.push(renderTextWithEmojis(imgParts[i], emojiEnabled, showEmojiLabel));
          }
          i++;
        } else if (i % 3 === 1) {
          const altText = imgParts[i];
          const imgUrl = imgParts[i + 1];
          res.push(
            <div
              key={`${keyPrefix}-mdimg-${i}`}
              style={{
                margin: "8px 0",
                maxWidth: "260px",
                borderRadius: "12px",
                overflow: "hidden",
                border: "1px solid rgba(255,255,255,0.15)",
                boxShadow: "0 4px 14px rgba(0,0,0,0.3)",
              }}
            >
              <img
                src={imgUrl}
                alt={altText || "用户分享图片"}
                style={{ width: "100%", maxHeight: "240px", objectFit: "cover", display: "block" }}
              />
            </div>
          );
          i += 2;
        }
      }
      return <>{res}</>;
    }

    return renderTextWithEmojis(textChunk, emojiEnabled, showEmojiLabel);
  };

  // 4. Mixed content with stickers and text
  const parts = processedContent.split(STICKER_REGEX);
  if (parts.length === 1) {
    return renderItemWithMedia(processedContent, "root");
  }

  const nodes: React.ReactNode[] = [];
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) {
      // Sticker ID captured group
      const stickerId = parts[i];
      if (stickersEnabled) {
        const sticker = getStickerById(stickerId);
        if (sticker) {
          if (standaloneLine) {
            nodes.push(
              <div key={`sticker-line-${i}`} className="message-sticker-row">
                <div className="standalone-sticker-card" title={sticker.name}>
                  <div className="sticker-media-wrap">{sticker.renderSvg(120)}</div>
                </div>
              </div>
            );
          } else {
            nodes.push(
              <span key={`sticker-inline-${i}`} className="inline-sticker-card" title={sticker.name}>
                {sticker.renderSvg(100)}
              </span>
            );
          }
          continue;
        }

        const custom = getCustomStickerById(stickerId);
        if (custom) {
          if (standaloneLine) {
            nodes.push(
              <div key={`sticker-line-${i}`} className="message-sticker-row">
                <div className="standalone-sticker-card" title={custom.name}>
                  <div className="sticker-media-wrap custom-sticker-media">
                    <img src={custom.dataUrl} alt={custom.name} className="custom-sticker-img" />
                  </div>
                </div>
              </div>
            );
          } else {
            nodes.push(
              <span key={`sticker-inline-${i}`} className="inline-sticker-card" title={custom.name}>
                <img src={custom.dataUrl} alt={custom.name} className="custom-sticker-img inline-custom" />
              </span>
            );
          }
          continue;
        }
      }

      nodes.push(`[sticker:${stickerId}]`);
    } else {
      // Text chunk
      const textChunk = parts[i];
      if (textChunk) {
        if (standaloneLine && nodes.length > 0) {
          nodes.push(
            <div key={`text-seg-${i}`} className="message-text-segment">
              {renderTextWithEmojis(textChunk, emojiEnabled, showEmojiLabel)}
            </div>
          );
        } else {
          nodes.push(renderTextWithEmojis(textChunk, emojiEnabled, showEmojiLabel));
        }
      }
    }
  }

  return <>{nodes}</>;
}
