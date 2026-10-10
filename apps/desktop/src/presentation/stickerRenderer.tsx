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
 * Renders text containing [sticker:id] tokens and [bracket] emojis.
 * Stickers can be rendered on their own dedicated row (standaloneLine = true)
 * rather than being squished inline with text.
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

  // 3. Mixed content with stickers and text
  const parts = processedContent.split(STICKER_REGEX);
  if (parts.length === 1) {
    return renderTextWithEmojis(processedContent, emojiEnabled, showEmojiLabel);
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
