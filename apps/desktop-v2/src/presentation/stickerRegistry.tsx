import React from "react";

export interface StickerItem {
  id: string;
  name: string;
  category: "猫猫日常" | "搞怪互怼" | "情绪表达" | "日常摸鱼";
  emojiFallback: string;
  description: string;
  renderSvg: (size?: number) => React.ReactNode;
}

export interface CustomStickerItem {
  id: string;
  name: string;
  dataUrl: string;
  createdAt: number;
}

export const STICKER_CATEGORIES = ["全部", "猫猫日常", "搞怪互怼", "情绪表达", "日常摸鱼", "我的收藏"] as const;

export const STICKER_REGISTRY: Record<string, StickerItem> = {
  cat_bonk: {
    id: "cat_bonk",
    name: "猫猫敲头",
    category: "搞怪互怼",
    emojiFallback: "🐱🔨",
    description: "给你一锤 / 欠揍是不是 / 互怼",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FFF2E8" />
        {/* Cat Head */}
        <circle cx="50" cy="65" r="32" fill="#FFA940" />
        <path d="M26 44L34 22L48 38Z" fill="#FFA940" stroke="#D46B08" strokeWidth="2" strokeLinejoin="round" />
        <path d="M74 44L66 22L52 38Z" fill="#FFA940" stroke="#D46B08" strokeWidth="2" strokeLinejoin="round" />
        {/* Ears inside */}
        <path d="M30 40L35 27L43 36Z" fill="#FFCCC7" />
        <path d="M70 40L65 27L57 36Z" fill="#FFCCC7" />
        {/* Dizzy Eyes (knocked) */}
        <path d="M36 58L46 68M46 58L36 68" stroke="#595959" strokeWidth="3" strokeLinecap="round" />
        <path d="M54 58L64 68M64 58L54 68" stroke="#595959" strokeWidth="3" strokeLinecap="round" />
        {/* Mouth wavy */}
        <path d="M44 76C47 78 53 78 56 76" stroke="#595959" strokeWidth="2.5" strokeLinecap="round" />
        {/* Toy Hammer hitting head */}
        <g transform="rotate(-25 80 30)">
          <rect x="70" y="10" width="28" height="18" rx="5" fill="#FF4D4F" stroke="#CF1322" strokeWidth="2" />
          <rect x="80" y="28" width="8" height="42" rx="3" fill="#8C8C8C" stroke="#595959" strokeWidth="2" />
          {/* Hit stars */}
          <path d="M60 25L64 22L68 25L65 20L68 15L64 18L60 15L63 20Z" fill="#FADB14" />
          <path d="M96 28L100 25L104 28L101 23L104 18L100 21L96 18L99 23Z" fill="#FADB14" />
        </g>
        {/* Caption */}
        <text x="60" y="108" textAnchor="middle" fontSize="11" textLength="80" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#D46B08">给你一锤！</text>
      </svg>
    ),
  },

  cat_surprised: {
    id: "cat_surprised",
    name: "猫猫问号",
    category: "猫猫日常",
    emojiFallback: "🐱❓",
    description: "纳尼？！/ 战术后仰 / 问号脸",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#E6F7FF" />
        {/* Cat Head */}
        <circle cx="56" cy="66" r="32" fill="#BAE7FF" />
        <path d="M30 46L40 24L52 40Z" fill="#BAE7FF" stroke="#1890FF" strokeWidth="2" />
        <path d="M82 46L72 24L60 40Z" fill="#BAE7FF" stroke="#1890FF" strokeWidth="2" />
        {/* Big Shocked Eyes */}
        <ellipse cx="45" cy="62" rx="8" ry="10" fill="#FFFFFF" stroke="#003A8C" strokeWidth="2" />
        <circle cx="45" cy="62" r="4" fill="#003A8C" />
        <ellipse cx="67" cy="62" rx="8" ry="10" fill="#FFFFFF" stroke="#003A8C" strokeWidth="2" />
        <circle cx="67" cy="62" r="4" fill="#003A8C" />
        {/* Open O-Mouth */}
        <ellipse cx="56" cy="78" rx="6" ry="7" fill="#FF85C0" stroke="#C41D7F" strokeWidth="1.5" />
        {/* Big Red Question Marks */}
        <text x="96" y="44" fontSize="26" fontWeight="bold" fill="#FF4D4F" fontFamily="sans-serif">?</text>
        <text x="82" y="28" fontSize="18" fontWeight="bold" fill="#FA8C16" fontFamily="sans-serif">?</text>
        {/* Whiskers */}
        <line x1="26" y1="64" x2="36" y2="66" stroke="#1890FF" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="25" y1="72" x2="36" y2="70" stroke="#1890FF" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="76" y1="66" x2="86" y2="64" stroke="#1890FF" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="76" y1="70" x2="87" y2="72" stroke="#1890FF" strokeWidth="1.5" strokeLinecap="round" />
        <text x="60" y="108" textAnchor="middle" fontSize="11" textLength="80" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#096DD9">真的假的？！</text>
      </svg>
    ),
  },

  cat_pat: {
    id: "cat_pat",
    name: "摸摸猫头",
    category: "情绪表达",
    emojiFallback: "🐱🫂",
    description: "摸摸头 / 不哭不哭 / 顺毛",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FFF0F6" />
        {/* Happy closed-eyes Cat Head */}
        <circle cx="60" cy="70" r="30" fill="#FFD6E7" />
        <path d="M36 50L44 32L54 44Z" fill="#FFD6E7" stroke="#EB2F96" strokeWidth="1.5" />
        <path d="M84 50L76 32L66 44Z" fill="#FFD6E7" stroke="#EB2F96" strokeWidth="1.5" />
        {/* Blushing cheeks */}
        <circle cx="42" cy="74" r="6" fill="#FFA39E" opacity="0.6" />
        <circle cx="78" cy="74" r="6" fill="#FFA39E" opacity="0.6" />
        {/* Happy smiling eyes (curved) */}
        <path d="M44 65C48 60 52 60 56 65" stroke="#780650" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        <path d="M64 65C68 60 72 60 76 65" stroke="#780650" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        {/* Cute triangle nose & mouth */}
        <path d="M60 72L58 75H62Z" fill="#EB2F96" />
        <path d="M56 77C58 79 60 79 60 77C60 79 62 79 64 77" stroke="#780650" strokeWidth="2" strokeLinecap="round" fill="none" />
        {/* Comforting Human Hand */}
        <path d="M38 34C48 26 72 26 82 34C86 37 84 44 78 43C72 42 66 38 60 38C54 38 48 42 42 43C36 44 34 37 38 34Z" fill="#FFE7BA" stroke="#D46B08" strokeWidth="1.5" />
        {/* Floating Sparkle hearts */}
        <path d="M22 28C22 24 26 22 29 25C32 22 36 24 36 28C36 33 29 37 29 37C29 37 22 33 22 28Z" fill="#FF4D4F" />
        <path d="M88 24C88 21 91 19 93 21C95 19 98 21 98 24C98 28 93 31 93 31C93 31 88 28 88 24Z" fill="#FF7875" />
        <text x="60" y="110" textAnchor="middle" fontSize="11" textLength="60" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#C41D7F">摸摸头~</text>
      </svg>
    ),
  },

  cat_pout: {
    id: "cat_pout",
    name: "傲娇炸毛",
    category: "搞怪互怼",
    emojiFallback: "🐱😾",
    description: "哼！/ 不理你了 / 气鼓鼓",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FFF1F0" />
        {/* Cat Head turned slightly */}
        <circle cx="60" cy="65" r="32" fill="#FFCCC7" />
        <path d="M32 44L40 20L52 38Z" fill="#FFCCC7" stroke="#F5222D" strokeWidth="2" />
        <path d="M88 44L80 20L68 38Z" fill="#FFCCC7" stroke="#F5222D" strokeWidth="2" />
        {/* Pouting eyes looking away */}
        <path d="M42 58L54 62" stroke="#820014" strokeWidth="3" strokeLinecap="round" />
        <circle cx="46" cy="65" r="3" fill="#820014" />
        <path d="M66 62L78 58" stroke="#820014" strokeWidth="3" strokeLinecap="round" />
        <circle cx="74" cy="65" r="3" fill="#820014" />
        {/* Puffed cheeks */}
        <circle cx="36" cy="70" r="7" fill="#FFA39E" />
        <circle cx="84" cy="70" r="7" fill="#FFA39E" />
        {/* Pouting mouth */}
        <path d="M54 76C57 74 63 74 66 76" stroke="#820014" strokeWidth="2.5" strokeLinecap="round" />
        {/* Anger mark (vein) */}
        <path d="M86 36L94 44M94 36L86 44M84 40H96M90 34V46" stroke="#F5222D" strokeWidth="2" strokeLinecap="round" />
        {/* Steam puffs */}
        <path d="M24 60C20 58 18 64 22 66" stroke="#8C8C8C" strokeWidth="2" strokeLinecap="round" />
        <text x="60" y="108" textAnchor="middle" fontSize="10.5" textLength="88" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#CF1322">哼！不理你了！</text>
      </svg>
    ),
  },

  cat_crying: {
    id: "cat_crying",
    name: "委屈泪目",
    category: "情绪表达",
    emojiFallback: "🐱😭",
    description: "猫猫流泪 / 怎么这样 / 委屈巴巴",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#F0F5FF" />
        {/* Cat Head */}
        <circle cx="60" cy="64" r="30" fill="#ADC6FF" />
        <path d="M36 44L44 24L54 40Z" fill="#ADC6FF" stroke="#2F54EB" strokeWidth="1.5" />
        <path d="M84 44L76 24L66 40Z" fill="#ADC6FF" stroke="#2F54EB" strokeWidth="1.5" />
        {/* Teary eyes */}
        <ellipse cx="46" cy="58" rx="6" ry="8" fill="#1D39C4" />
        <ellipse cx="74" cy="58" rx="6" ry="8" fill="#1D39C4" />
        <circle cx="48" cy="55" r="2.5" fill="#FFFFFF" />
        <circle cx="76" cy="55" r="2.5" fill="#FFFFFF" />
        {/* Waterfalls of tears */}
        <path d="M46 66C42 74 44 86 42 94" stroke="#40A9FF" strokeWidth="4" strokeLinecap="round" />
        <path d="M74 66C78 74 76 86 78 94" stroke="#40A9FF" strokeWidth="4" strokeLinecap="round" />
        {/* Sad mouth */}
        <path d="M54 75C58 72 62 72 66 75" stroke="#1D39C4" strokeWidth="2.5" strokeLinecap="round" />
        <text x="60" y="110" textAnchor="middle" fontSize="10.5" textLength="90" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#1D39C4">怎么这样啦呜呜</text>
      </svg>
    ),
  },

  cat_roll: {
    id: "cat_roll",
    name: "猫猫打滚",
    category: "猫猫日常",
    emojiFallback: "🐱🐾",
    description: "赖在地上不起来 / 呜呜呜 / 撒娇",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FCFFE6" />
        {/* Rolling oval body */}
        <ellipse cx="60" cy="62" rx="36" ry="24" fill="#FFE58F" stroke="#D48806" strokeWidth="2" />
        {/* Little paws in air */}
        <ellipse cx="44" cy="40" rx="6" ry="10" fill="#FFF1B8" stroke="#D48806" strokeWidth="1.5" />
        <ellipse cx="60" cy="38" rx="6" ry="10" fill="#FFF1B8" stroke="#D48806" strokeWidth="1.5" />
        <ellipse cx="76" cy="40" rx="6" ry="10" fill="#FFF1B8" stroke="#D48806" strokeWidth="1.5" />
        {/* Happy squinting sideways face */}
        <path d="M30 64C32 60 36 60 38 64" stroke="#614700" strokeWidth="2" strokeLinecap="round" />
        <path d="M32 70C34 72 38 72 40 70" stroke="#614700" strokeWidth="2" strokeLinecap="round" />
        {/* Motion dust lines */}
        <path d="M96 68C102 65 106 68 102 74" stroke="#AD8B00" strokeWidth="2" strokeLinecap="round" />
        <path d="M14 68C8 65 6 68 10 74" stroke="#AD8B00" strokeWidth="2" strokeLinecap="round" />
        <text x="60" y="106" textAnchor="middle" fontSize="10.5" textLength="90" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#AD8B00">就赖着不起来！</text>
      </svg>
    ),
  },

  cat_eat: {
    id: "cat_eat",
    name: "快乐炫饭",
    category: "日常摸鱼",
    emojiFallback: "🐱🐟",
    description: "好耶开饭 / 嚼嚼嚼 / 炫饭",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#F6FFED" />
        {/* Cat Head */}
        <circle cx="60" cy="60" r="30" fill="#D9F7BE" />
        <path d="M36 40L44 20L54 36Z" fill="#D9F7BE" stroke="#389E0D" strokeWidth="1.5" />
        <path d="M84 40L76 20L66 36Z" fill="#D9F7BE" stroke="#389E0D" strokeWidth="1.5" />
        {/* Chomping mouth */}
        <ellipse cx="60" cy="68" rx="12" ry="8" fill="#FF7875" />
        {/* Delicious Fish in mouth */}
        <ellipse cx="60" cy="68" rx="18" ry="6" fill="#69C0FF" stroke="#096DD9" strokeWidth="1.5" />
        <polygon points="78,68 86,62 86,74" fill="#69C0FF" stroke="#096DD9" strokeWidth="1.5" />
        <circle cx="48" cy="68" r="2" fill="#002766" />
        {/* Happy squint eyes */}
        <path d="M46 52L52 56L46 60" stroke="#135200" strokeWidth="2" strokeLinecap="round" />
        <path d="M74 52L68 56L74 60" stroke="#135200" strokeWidth="2" strokeLinecap="round" />
        <text x="60" y="108" textAnchor="middle" fontSize="10.5" textLength="88" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#237804">嚼嚼嚼~开饭！</text>
      </svg>
    ),
  },

  give_up: {
    id: "give_up",
    name: "咸鱼摆烂",
    category: "日常摸鱼",
    emojiFallback: "🛌🏳️",
    description: "摆烂了 / 累趴 / 让我静静",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#F5F5F5" />
        {/* Fish pillow */}
        <ellipse cx="60" cy="70" rx="42" ry="16" fill="#D9D9D9" stroke="#8C8C8C" strokeWidth="2" />
        <circle cx="34" cy="68" r="4" fill="#595959" />
        <path d="M34 68L30 72" stroke="#595959" strokeWidth="2" />
        {/* White flag of surrender */}
        <line x1="80" y1="28" x2="80" y2="60" stroke="#595959" strokeWidth="2.5" />
        <polygon points="80,28 104,36 80,44" fill="#FFFFFF" stroke="#8C8C8C" strokeWidth="1.5" />
        {/* Sleep Zzz */}
        <text x="32" y="40" fontSize="14" fontWeight="bold" fill="#8C8C8C">Z</text>
        <text x="44" y="30" fontSize="18" fontWeight="bold" fill="#595959">Z</text>
        <text x="58" y="22" fontSize="22" fontWeight="bold" fill="#262626">Z</text>
        <text x="60" y="108" textAnchor="middle" fontSize="10" textLength="94" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#595959">彻底躺平，别叫我</text>
      </svg>
    ),
  },

  panda_question: {
    id: "panda_question",
    name: "熊猫问号",
    category: "搞怪互怼",
    emojiFallback: "🐼❓",
    description: "小朋友你是否有很多问号 / 真的假的",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FAFAFA" />
        {/* Panda Head */}
        <circle cx="60" cy="64" r="32" fill="#FFFFFF" stroke="#262626" strokeWidth="2.5" />
        <circle cx="34" cy="38" r="10" fill="#262626" />
        <circle cx="86" cy="38" r="10" fill="#262626" />
        {/* Eye patches */}
        <ellipse cx="46" cy="58" rx="8" ry="11" fill="#262626" transform="rotate(-15 46 58)" />
        <circle cx="48" cy="56" r="3" fill="#FFFFFF" />
        <ellipse cx="74" cy="58" rx="8" ry="11" fill="#262626" transform="rotate(15 74 58)" />
        <circle cx="72" cy="56" r="3" fill="#FFFFFF" />
        {/* Nose & weird grin */}
        <ellipse cx="60" cy="68" rx="4" ry="3" fill="#262626" />
        <path d="M50 76C55 80 65 80 70 76" stroke="#262626" strokeWidth="2.5" strokeLinecap="round" />
        {/* Giant Question Mark */}
        <text x="96" y="56" fontSize="30" fontWeight="bold" fill="#F5222D" fontFamily="sans-serif">?</text>
        <text x="60" y="110" textAnchor="middle" fontSize="10.5" textLength="88" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#262626">你在无中生有？</text>
      </svg>
    ),
  },

  panda_thumbsup: {
    id: "panda_thumbsup",
    name: "为你点赞",
    category: "情绪表达",
    emojiFallback: "🐼👍",
    description: "牛逼 / 强啊 / 为你点赞",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#F6FFED" />
        {/* Panda Head */}
        <circle cx="50" cy="64" r="28" fill="#FFFFFF" stroke="#262626" strokeWidth="2" />
        <circle cx="28" cy="42" r="8" fill="#262626" />
        <circle cx="72" cy="42" r="8" fill="#262626" />
        {/* Grinning eyes */}
        <path d="M40 58C43 54 47 54 50 58" stroke="#262626" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M60 58C63 54 67 54 70 58" stroke="#262626" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M48 68C52 74 58 74 62 68" stroke="#262626" strokeWidth="2.5" strokeLinecap="round" />
        {/* Giant Thumbs Up Hand */}
        <g transform="translate(68, 38)">
          <path d="M12 18V6C12 3 15 1 18 1C21 1 23 4 23 7V22L28 24C32 26 32 30 30 33C32 35 32 39 29 42C30 44 29 48 26 50H12V18Z" fill="#FFE58F" stroke="#D48806" strokeWidth="2" />
          <rect x="2" y="18" width="10" height="32" rx="2" fill="#FAAD14" stroke="#D48806" strokeWidth="2" />
        </g>
        <text x="60" y="110" textAnchor="middle" fontSize="10.5" textLength="80" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#389E0D">强！泰裤辣！</text>
      </svg>
    ),
  },

  doge_smirk: {
    id: "doge_smirk",
    name: "战术狗头",
    category: "搞怪互怼",
    emojiFallback: "🐕😏",
    description: "就这？/ 懂的都懂 / 战术微笑",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FFFBE6" />
        {/* Shiba Inu Doge Head */}
        <ellipse cx="60" cy="62" rx="34" ry="30" fill="#E8B86D" stroke="#A86F1A" strokeWidth="2" />
        <polygon points="34,40 40,18 52,34" fill="#E8B86D" stroke="#A86F1A" strokeWidth="2" />
        <polygon points="86,40 80,18 68,34" fill="#E8B86D" stroke="#A86F1A" strokeWidth="2" />
        <ellipse cx="60" cy="72" rx="22" ry="16" fill="#FFF1D6" />
        {/* Shifty Eyes looking sideways */}
        <ellipse cx="46" cy="56" rx="6" ry="8" fill="#FFFFFF" stroke="#5E3E0E" strokeWidth="1.5" />
        <circle cx="50" cy="56" r="3" fill="#382103" />
        <ellipse cx="74" cy="56" rx="6" ry="8" fill="#FFFFFF" stroke="#5E3E0E" strokeWidth="1.5" />
        <circle cx="78" cy="56" r="3" fill="#382103" />
        {/* Smug Smirk */}
        <path d="M52 74C56 78 64 80 72 74" stroke="#5E3E0E" strokeWidth="2.5" strokeLinecap="round" />
        {/* Black nose */}
        <ellipse cx="60" cy="68" rx="4" ry="3" fill="#382103" />
        <text x="60" y="108" textAnchor="middle" fontSize="10.5" textLength="90" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#A86F1A">就这？懂的都懂</text>
      </svg>
    ),
  },

  heart_sparkle: {
    id: "heart_sparkle",
    name: "疯狂心动",
    category: "情绪表达",
    emojiFallback: "💖✨",
    description: "好耶喜欢 / 贴贴 / 发射爱心",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FFF0F6" />
        {/* Giant Main Heart */}
        <path d="M60 92C60 92 20 66 20 42C20 28 32 20 44 24C52 27 58 34 60 38C62 34 68 27 76 24C88 20 100 28 100 42C100 66 60 92 60 92Z" fill="#FF4D4F" />
        {/* Heart Highlight */}
        <path d="M32 36C30 42 32 50 36 56" stroke="#FFA39E" strokeWidth="3" strokeLinecap="round" />
        {/* Sparkles */}
        <path d="M96 22L98 16L100 22L106 24L100 26L98 32L96 26L90 24Z" fill="#FADB14" />
        <path d="M22 22L24 18L26 22L30 24L26 26L24 30L22 26L18 24Z" fill="#FADB14" />
        <text x="60" y="110" textAnchor="middle" fontSize="10.5" textLength="80" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#CF1322">狠狠心动了！</text>
      </svg>
    ),
  },

  ghost_soul: {
    id: "ghost_soul",
    name: "灵魂出窍",
    category: "日常摸鱼",
    emojiFallback: "👻💨",
    description: "加班/赶DDL已升天 / 困麻了",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#F0F5FF" />
        {/* Little Ghost floating up */}
        <path d="M60 20C44 20 36 34 36 52C36 68 40 76 44 72C48 68 54 74 60 70C66 74 72 68 76 72C80 76 84 68 84 52C84 34 76 20 60 20Z" fill="#D6E4FF" stroke="#597EF7" strokeWidth="2" opacity="0.9" />
        {/* Empty hollow eyes */}
        <circle cx="50" cy="42" r="5" fill="#1D39C4" />
        <circle cx="70" cy="42" r="5" fill="#1D39C4" />
        <ellipse cx="60" cy="54" rx="4" ry="7" fill="#1D39C4" />
        {/* Tiny hands waving goodbye */}
        <ellipse cx="28" cy="48" rx="6" ry="4" fill="#D6E4FF" stroke="#597EF7" strokeWidth="1.5" />
        <ellipse cx="92" cy="48" rx="6" ry="4" fill="#D6E4FF" stroke="#597EF7" strokeWidth="1.5" />
        {/* Smoke trail */}
        <path d="M60 76C56 82 64 88 60 94" stroke="#ADC6FF" strokeWidth="3" strokeLinecap="round" />
        <text x="60" y="110" textAnchor="middle" fontSize="10.5" textLength="76" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#2F54EB">已升天，勿念</text>
      </svg>
    ),
  },

  tea_sip: {
    id: "tea_sip",
    name: "战术喝茶",
    category: "日常摸鱼",
    emojiFallback: "🍵😌",
    description: "吃瓜看戏 / 优雅静止 / 喝杯茶冷静下",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#F6FFED" />
        {/* Ceramic Teacup */}
        <path d="M38 52C38 74 50 84 60 84C70 84 82 74 82 52H38Z" fill="#87E8DE" stroke="#006D75" strokeWidth="2" />
        <ellipse cx="60" cy="52" rx="22" ry="7" fill="#5CDBD3" stroke="#006D75" strokeWidth="1.5" />
        {/* Green Tea inside */}
        <ellipse cx="60" cy="53" rx="18" ry="5" fill="#52C41A" />
        {/* Teacup Handle */}
        <path d="M82 56C90 56 94 64 92 72C90 78 82 78 80 76" stroke="#006D75" strokeWidth="2" fill="none" />
        {/* Rising Steam */}
        <path d="M52 42C50 36 54 32 52 26" stroke="#95DE64" strokeWidth="2.5" strokeLinecap="round" />
        <path d="M64 42C62 36 66 32 64 26" stroke="#95DE64" strokeWidth="2.5" strokeLinecap="round" />
        {/* Tea saucer */}
        <ellipse cx="60" cy="86" rx="28" ry="4" fill="#B5F5EC" stroke="#006D75" strokeWidth="1.5" />
        <text x="60" y="108" textAnchor="middle" fontSize="10.5" textLength="88" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#006D75">优雅喝茶，看戏</text>
      </svg>
    ),
  },

  party_cheer: {
    id: "party_cheer",
    name: "芜湖起飞",
    category: "情绪表达",
    emojiFallback: "🎉🥳",
    description: "好耶太棒了 / 庆祝 / 芜湖起飞",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FFF2E8" />
        {/* Party Popper cone */}
        <polygon points="30,86 46,92 74,48 58,42" fill="#FFA940" stroke="#D46B08" strokeWidth="2" />
        <path d="M58 42L74 48" stroke="#D46B08" strokeWidth="2" />
        {/* Confetti Explosion */}
        <circle cx="82" cy="30" r="5" fill="#FF4D4F" />
        <circle cx="94" cy="46" r="4" fill="#52C41A" />
        <circle cx="68" cy="22" r="4" fill="#1890FF" />
        <circle cx="98" cy="24" r="3.5" fill="#FAAD14" />
        <rect x="74" y="38" width="6" height="6" rx="1" fill="#722ED1" transform="rotate(25 77 41)" />
        <rect x="88" y="32" width="6" height="6" rx="1" fill="#FF85C0" transform="rotate(45 91 35)" />
        {/* Ribbons */}
        <path d="M68 34C74 28 80 34 86 28" stroke="#FF4D4F" strokeWidth="2" strokeLinecap="round" fill="none" />
        <path d="M80 44C86 38 92 44 98 38" stroke="#1890FF" strokeWidth="2" strokeLinecap="round" fill="none" />
        <text x="60" y="110" textAnchor="middle" fontSize="10.5" textLength="88" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#D46B08">好耶！芜湖起飞！</text>
      </svg>
    ),
  },

  knife_threat: {
    id: "knife_threat",
    name: "危险警告",
    category: "搞怪互怼",
    emojiFallback: "🗡️⚠️",
    description: "你再说一遍试试？/ 危险发言",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FFF1F0" />
        {/* Warning Triangle sign */}
        <polygon points="60,20 22,82 98,82" fill="#FFA39E" stroke="#CF1322" strokeWidth="2.5" />
        <rect x="57" y="42" width="6" height="20" rx="3" fill="#820014" />
        <circle cx="60" cy="72" r="3.5" fill="#820014" />
        {/* Little shiny plastic toy dagger */}
        <g transform="translate(68, 50) rotate(35)">
          <polygon points="6,0 12,24 0,24" fill="#D9D9D9" stroke="#595959" strokeWidth="1.5" />
          <rect x="-2" y="24" width="16" height="4" fill="#8C8C8C" />
          <rect x="2" y="28" width="8" height="12" fill="#874D00" />
        </g>
        <text x="60" y="108" textAnchor="middle" fontSize="10" textLength="92" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#CF1322">你再说一遍试试？</text>
      </svg>
    ),
  },

  cat_blush: {
    id: "cat_blush",
    name: "害羞脸红",
    category: "情绪表达",
    emojiFallback: "🐱😳",
    description: "心跳加速 / 脸红害羞 / 讨厌啦",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FFF0F6" />
        {/* Cat Head */}
        <circle cx="60" cy="65" r="32" fill="#FFD6E7" />
        <path d="M34 44L42 22L54 38Z" fill="#FFD6E7" stroke="#EB2F96" strokeWidth="2" strokeLinejoin="round" />
        <path d="M86 44L78 22L66 38Z" fill="#FFD6E7" stroke="#EB2F96" strokeWidth="2" strokeLinejoin="round" />
        {/* Inner ears */}
        <path d="M38 40L43 27L50 36Z" fill="#FF85C0" />
        <path d="M82 40L77 27L70 36Z" fill="#FF85C0" />
        {/* Paws covering cheeks shyly */}
        <ellipse cx="38" cy="74" rx="9" ry="12" fill="#FFFFFF" stroke="#EB2F96" strokeWidth="1.5" transform="rotate(20 38 74)" />
        <ellipse cx="82" cy="74" rx="9" ry="12" fill="#FFFFFF" stroke="#EB2F96" strokeWidth="1.5" transform="rotate(-20 82 74)" />
        {/* Blushing rosy cheeks */}
        <circle cx="44" cy="68" r="8" fill="#FF4D4F" opacity="0.6" />
        <circle cx="76" cy="68" r="8" fill="#FF4D4F" opacity="0.6" />
        {/* Shy curved eyes */}
        <path d="M44 56C47 52 52 52 55 56" stroke="#780650" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        <path d="M65 56C68 52 73 52 76 56" stroke="#780650" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        {/* Shy cute mouth */}
        <path d="M57 66C59 68 61 68 63 66" stroke="#780650" strokeWidth="2" strokeLinecap="round" fill="none" />
        {/* Little flutter hearts */}
        <path d="M22 28C22 24 26 22 29 25C32 22 36 24 36 28C36 33 29 37 29 37C29 37 22 33 22 28Z" fill="#FF4D4F" />
        <path d="M92 24C92 21 95 19 97 21C99 19 102 21 102 24C102 28 97 31 97 31C97 31 92 28 92 24Z" fill="#FF7875" />
        {/* Caption */}
        <text x="60" y="108" textAnchor="middle" fontSize="10.5" textLength="90" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#C41D7F">讨厌啦……害羞了</text>
      </svg>
    ),
  },

  cat_facepalm: {
    id: "cat_facepalm",
    name: "猫猫捂脸",
    category: "搞怪互怼",
    emojiFallback: "🐱🤦",
    description: "没眼看 / 捂脸 / 脑壳疼",
    renderSvg: (size = 120) => (
      <svg width={size} height={size} viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="120" height="120" rx="20" fill="#FFFBE6" />
        {/* Cat Head */}
        <circle cx="60" cy="65" r="32" fill="#FFE58F" />
        <path d="M34 44L42 20L54 38Z" fill="#FFE58F" stroke="#D48806" strokeWidth="2" strokeLinejoin="round" />
        <path d="M86 44L78 20L66 38Z" fill="#FFE58F" stroke="#D48806" strokeWidth="2" strokeLinejoin="round" />
        {/* Single visible eye squinting */}
        <path d="M42 60L52 64" stroke="#614700" strokeWidth="2.5" strokeLinecap="round" />
        {/* Cat paw slapped over forehead/eye */}
        <ellipse cx="72" cy="58" rx="14" ry="10" fill="#FFF1B8" stroke="#D48806" strokeWidth="2" transform="rotate(-25 72 58)" />
        {/* Sweat drop */}
        <path d="M28 50C28 50 24 56 24 59C24 61 26 63 28 63C30 63 32 61 32 59C32 56 28 50 28 50Z" fill="#40A9FF" />
        {/* Wavy mouth */}
        <path d="M48 76C52 74 58 74 62 76" stroke="#614700" strokeWidth="2" strokeLinecap="round" />
        {/* Caption */}
        <text x="60" y="108" textAnchor="middle" fontSize="10" textLength="92" lengthAdjust="spacingAndGlyphs" fontWeight="bold" fill="#D48806">没眼看……脑壳疼</text>
      </svg>
    ),
  },
};

export function getStickerById(id: string): StickerItem | undefined {
  return STICKER_REGISTRY[id];
}

export function getAllStickers(): StickerItem[] {
  return Object.values(STICKER_REGISTRY);
}

const CUSTOM_STICKERS_KEY = "aevum_custom_stickers";

export function getCustomStickers(): CustomStickerItem[] {
  if (typeof window === "undefined" || !window.localStorage) return [];
  try {
    const raw = localStorage.getItem(CUSTOM_STICKERS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (err) {
    console.error("Failed to read custom stickers:", err);
    return [];
  }
}

export function saveCustomSticker(item: CustomStickerItem): void {
  try {
    const existing = getCustomStickers();
    const updated = [item, ...existing.filter((s) => s.id !== item.id)];
    localStorage.setItem(CUSTOM_STICKERS_KEY, JSON.stringify(updated));
  } catch (err) {
    console.error("Failed to save custom sticker:", err);
  }
}

export function deleteCustomSticker(id: string): void {
  try {
    const existing = getCustomStickers();
    const updated = existing.filter((s) => s.id !== id);
    localStorage.setItem(CUSTOM_STICKERS_KEY, JSON.stringify(updated));
  } catch (err) {
    console.error("Failed to delete custom sticker:", err);
  }
}

export function getCustomStickerById(id: string): CustomStickerItem | undefined {
  const customs = getCustomStickers();
  return customs.find((s) => s.id === id);
}

const RECENT_STICKERS_KEY = "aevum_recent_stickers";

export function getRecentStickers(): string[] {
  if (typeof window === "undefined" || !window.localStorage) return [];
  try {
    const raw = localStorage.getItem(RECENT_STICKERS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function recordRecentSticker(id: string): void {
  if (typeof window === "undefined" || !window.localStorage) return;
  try {
    const existing = getRecentStickers().filter((s) => s !== id);
    const updated = [id, ...existing].slice(0, 8);
    localStorage.setItem(RECENT_STICKERS_KEY, JSON.stringify(updated));
  } catch (err) {
    console.error("Failed to record recent sticker:", err);
  }
}
