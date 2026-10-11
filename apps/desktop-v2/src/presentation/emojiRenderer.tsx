import React from "react";

// Mapping of common WeChat Bracket Emojis to symbolic representations & themes
export const WECHAT_EMOJI_MAP: Record<string, { icon: string; name: string; color: string }> = {
  "[旺柴]": { icon: "🐕", name: "旺柴", color: "#e6a23c" },
  "[苦涩]": { icon: "🥺", name: "苦涩", color: "#909399" },
  "[破涕为笑]": { icon: "😂", name: "破涕为笑", color: "#f56c6c" },
  "[囧]": { icon: "😣", name: "囧", color: "#e6a23c" },
  "[Facepalm]": { icon: "🤦", name: "捂脸", color: "#409eff" },
  "[捂脸]": { icon: "🤦", name: "捂脸", color: "#409eff" },
  "[撇嘴]": { icon: "😒", name: "撇嘴", color: "#909399" },
  "[害羞]": { icon: "😳", name: "害羞", color: "#f56c6c" },
  "[脸红]": { icon: "😳", name: "脸红", color: "#f56c6c" },
  "[笑哭]": { icon: "😂", name: "笑哭", color: "#f56c6c" },
  "[没眼看]": { icon: "🤦", name: "没眼看", color: "#409eff" },
  "[脑壳疼]": { icon: "🤕", name: "脑壳疼", color: "#e6a23c" },
  "[摸摸头]": { icon: "🫂", name: "摸摸头", color: "#e6a23c" },
  "[摸摸]": { icon: "🫂", name: "摸摸", color: "#e6a23c" },
  "[奸笑]": { icon: "😏", name: "奸笑", color: "#e6a23c" },
  "[偷笑]": { icon: "🤭", name: "偷笑", color: "#e6a23c" },
  "[捂脸哭]": { icon: "🤣", name: "捂脸哭", color: "#f56c6c" },
  "[流泪]": { icon: "😭", name: "流泪", color: "#409eff" },
  "[大哭]": { icon: "😭", name: "大哭", color: "#409eff" },
  "[发怒]": { icon: "😡", name: "发怒", color: "#f56c6c" },
  "[发呆]": { icon: "😶", name: "发呆", color: "#909399" },
  "[擦汗]": { icon: "😅", name: "擦汗", color: "#409eff" },
  "[再见]": { icon: "🙋", name: "再见", color: "#67c23a" },
  "[哼]": { icon: "😤", name: "哼", color: "#e6a23c" },
  "[右哼哼]": { icon: "😤", name: "哼哼", color: "#e6a23c" },
  "[左哼哼]": { icon: "😤", name: "左哼哼", color: "#e6a23c" },
  "[微笑]": { icon: "🙂", name: "微笑", color: "#e6a23c" },
  "[疑问]": { icon: "❓", name: "疑问", color: "#e6a23c" },
  "[思考]": { icon: "🤔", name: "思考", color: "#409eff" },
  "[Doge]": { icon: "🐶", name: "Doge", color: "#e6a23c" },
  "[Hurt]": { icon: "💔", name: "心痛", color: "#f56c6c" },
  "[Broken]": { icon: "🩹", name: "破碎", color: "#909399" },
  "[Sigh]": { icon: "😮‍💨", name: "叹气", color: "#909399" },
  "[Lol]": { icon: "😆", name: "大笑", color: "#67c23a" },
  "[可怜]": { icon: "🥺", name: "可怜", color: "#e6a23c" },
  "[抓狂]": { icon: "😫", name: "抓狂", color: "#f56c6c" },
  "[白眼]": { icon: "🙄", name: "白眼", color: "#909399" },
  "[得意]": { icon: "😎", name: "得意", color: "#e6a23c" },
  "[难过]": { icon: "😞", name: "难过", color: "#909399" },
  "[困]": { icon: "🥱", name: "困", color: "#909399" },
  "[睡]": { icon: "😴", name: "睡", color: "#909399" },
  "[吃惊]": { icon: "😮", name: "吃惊", color: "#e6a23c" },
  "[调皮]": { icon: "😜", name: "调皮", color: "#e6a23c" },
  "[愉快]": { icon: "😊", name: "愉快", color: "#67c23a" },
  "[汗]": { icon: "😓", name: "汗", color: "#909399" },
  "[晕]": { icon: "💫", name: "晕", color: "#e6a23c" },
  "[鼓掌]": { icon: "👏", name: "鼓掌", color: "#e6a23c" },
  "[强]": { icon: "👍", name: "强", color: "#e6a23c" },
  "[握手]": { icon: "🤝", name: "握手", color: "#e6a23c" },
  "[胜利]": { icon: "✌️", name: "胜利", color: "#67c23a" },
  "[加油]": { icon: "💪", name: "加油", color: "#f56c6c" },
  "[心]": { icon: "❤️", name: "心", color: "#f56c6c" },
  "[爱心]": { icon: "❤️", name: "爱心", color: "#f56c6c" },
  "[心碎]": { icon: "💔", name: "心碎", color: "#909399" },
  "[咖啡]": { icon: "☕", name: "咖啡", color: "#a06030" },
  "[奶茶]": { icon: "🧋", name: "奶茶", color: "#a06030" },
  "[月亮]": { icon: "🌙", name: "月亮", color: "#e6a23c" },
  "[太阳]": { icon: "☀️", name: "太阳", color: "#e6a23c" },
  "[礼物]": { icon: "🎁", name: "礼物", color: "#f56c6c" },
  "[emo]": { icon: "🌧️", name: "emo", color: "#909399" },
  "[摸头]": { icon: "🫂", name: "摸头", color: "#e6a23c" },
  "[抱抱]": { icon: "🫂", name: "抱抱", color: "#f56c6c" },
  "[猫猫问号]": { icon: "🐱❓", name: "猫猫问号", color: "#e6a23c" },
  "[茶]": { icon: "🍵", name: "喝茶", color: "#67c23a" },
  "[喝茶]": { icon: "🍵", name: "喝茶", color: "#67c23a" },
  "[战术喝茶]": { icon: "🍵", name: "喝茶", color: "#67c23a" },
  "[滑稽]": { icon: "😏", name: "滑稽", color: "#e6a23c" },
  "[狗头]": { icon: "🐶", name: "狗头", color: "#e6a23c" },
  "[敲头]": { icon: "🔨", name: "敲头", color: "#e6a23c" },
  "[打滚]": { icon: "🐾", name: "打滚", color: "#e6a23c" },
  "[炫饭]": { icon: "🍚", name: "炫饭", color: "#67c23a" },
  "[咸鱼]": { icon: "🐟", name: "咸鱼", color: "#909399" },
  "[摆烂]": { icon: "🛌", name: "摆烂", color: "#909399" },
};

const EMOJI_REGEX = /(\[[a-zA-Z\u4e00-\u9fa5]+\])/g;

/**
 * Parses a single text line, replacing supported WeChat bracket emojis with icons or badges.
 * showLabel: when false (default), renders pure emoji icon without badge text.
 */
export function renderTextWithEmojis(
  text: string,
  enabled: boolean = true,
  showLabel: boolean = false
): React.ReactNode {
  if (!enabled || !text) {
    return text;
  }

  const parts = text.split(EMOJI_REGEX);
  if (parts.length === 1) {
    return text;
  }

  return parts.map((part, index) => {
    const meta = WECHAT_EMOJI_MAP[part];
    if (meta) {
      if (!showLabel) {
        return (
          <span
            key={index}
            className="wechat-emoji-item"
            title={meta.name}
            style={{
              display: "inline-block",
              margin: "0 2px",
              fontSize: "1.2em",
              verticalAlign: "middle",
              lineHeight: "1",
            }}
          >
            {meta.icon}
          </span>
        );
      }
      return (
        <span
          key={index}
          className="wechat-emoji-pill"
          title={meta.name}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "3px",
            padding: "1px 5px",
            margin: "0 2px",
            borderRadius: "6px",
            fontSize: "0.92em",
            backgroundColor: "rgba(255, 255, 255, 0.08)",
            border: "1px solid rgba(255, 255, 255, 0.12)",
            verticalAlign: "middle",
            lineHeight: "1.3",
          }}
        >
          <span style={{ fontSize: "1.1em" }}>{meta.icon}</span>
          <span style={{ fontSize: "0.85em", opacity: 0.85 }}>{meta.name}</span>
        </span>
      );
    }
    return part;
  });
}
