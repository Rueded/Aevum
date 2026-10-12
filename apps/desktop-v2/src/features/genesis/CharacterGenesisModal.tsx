import React, { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import {
  CharacterCreationPayload,
  CharacterCreationResponse,
  EpistemicSeedDeclaration,
  GenesisPresetsResponse,
  SemanticEpistemicDepth,
  SemanticFamiliarityLevel,
  SemanticTrustLevel,
} from "../../types";

interface CharacterGenesisModalProps {
  isOpen: boolean;
  onClose: () => void;
  onGenesisComplete: (response: CharacterCreationResponse) => void;
}

type WizardStep = 1 | 2 | 3 | 4;

export const CharacterGenesisModal: React.FC<CharacterGenesisModalProps> = ({
  isOpen,
  onClose,
  onGenesisComplete,
}) => {
  const [currentStep, setCurrentStep] = useState<WizardStep>(1);
  const [presets, setPresets] = useState<GenesisPresetsResponse | null>(null);
  const [isLoadingPresets, setIsLoadingPresets] = useState<boolean>(false);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [genesisResult, setGenesisResult] = useState<CharacterCreationResponse | null>(null);

  // AI Magic Generator state
  const [aiPrompt, setAiPrompt] = useState<string>("");
  const [isAiGenerating, setIsAiGenerating] = useState<boolean>(false);
  const [aiSuccessMessage, setAiSuccessMessage] = useState<string | null>(null);

  // Step 1: Identity & Life Context
  const [name, setName] = useState<string>("昔涟");
  const [age, setAge] = useState<number>(21);
  const [occupation, setOccupation] = useState<string>("大学三年级学生 / 自由插画师");
  const [lifestyleRhythm, setLifestyleRhythm] = useState<string>(
    "晨型作息，偏好安静的书房与琴房空间。"
  );
  const [backgroundStory, setBackgroundStory] = useState<string>(
    "主修艺术设计，日常在城市一隅生活与创作。性格温润内敛，待人真诚而保有分寸感。"
  );

  // Step 2: Soul & Epistemic Seeds
  const [selectedTraits, setSelectedTraits] = useState<string[]>([
    "thoughtful",
    "gentle",
    "independent",
  ]);
  const [customTraitInput, setCustomTraitInput] = useState<string>("");
  const [speakingStyle, setSpeakingStyle] = useState<string>(
    "自然平实，语调从容，偶尔轻快打趣。"
  );
  const [epistemicSeeds, setEpistemicSeeds] = useState<EpistemicSeedDeclaration[]>([
    {
      topic: "classical_piano",
      depth: "PROFICIENT_LIVED",
      detail_note: "自幼练习古典钢琴十年，喜爱肖邦与德彪西夜曲",
    },
    {
      topic: "digital_illustration",
      depth: "PROFICIENT_LIVED",
      detail_note: "自由插画师日常创作，善于光影氛围表达",
    },
    {
      topic: "specialty_tea",
      depth: "FAMILIAR",
      detail_note: "常喝白茶与乌龙茶，对泡茶水温与茶具略有讲究",
    },
    {
      topic: "astronomy",
      depth: "CURIOUS_BEGINNER",
      detail_note: "新近被星野摄影与深空天体吸引，想找机会看流星雨",
    },
  ]);
  const [newSeedTopic, setNewSeedTopic] = useState<string>("");
  const [newSeedDepth, setNewSeedDepth] = useState<SemanticEpistemicDepth>("HEARD_OF_AWARE");
  const [newSeedNote, setNewSeedNote] = useState<string>("");

  const innateBoundaries = [
    "不参与虚假媚俗模拟，保持真实尊严与独立思考。",
    "珍视个人隐私与个人空间界限。",
  ];

  // Step 3: Story & Relationship Genesis
  const [selectedArchetype, setSelectedArchetype] = useState<string>("NEW_ACQUAINTANCE");
  const [familiarityLevel, setFamiliarityLevel] = useState<SemanticFamiliarityLevel>("STRANGER");
  const [trustLevel, setTrustLevel] = useState<SemanticTrustLevel>("OPEN_NEUTRAL");
  const [meetingBackstory, setMeetingBackstory] = useState<string>(
    "我们在微风拂过的午后初次产生交集，在安静的街角咖啡馆偶遇。"
  );

  // Load presets on open
  useEffect(() => {
    if (!isOpen) return;

    let mounted = true;
    setIsLoadingPresets(true);
    setErrorMessage(null);

    api
      .getGenesisPresets()
      .then((data) => {
        if (mounted) {
          setPresets(data);
        }
      })
      .catch((err) => {
        if (mounted) {
          console.warn("Failed to fetch presets, using offline defaults:", err);
        }
      })
      .finally(() => {
        if (mounted) {
          setIsLoadingPresets(false);
        }
      });

    return () => {
      mounted = false;
    };
  }, [isOpen]);

  // Handle archetype preset selection
  const handleSelectArchetype = useCallback(
    (archetypeKey: string) => {
      setSelectedArchetype(archetypeKey);
      if (archetypeKey === "CUSTOM") {
        return;
      }
      const matched = presets?.archetype_presets.find((p) => p.key === archetypeKey);
      if (matched) {
        setFamiliarityLevel(matched.default_familiarity);
        setTrustLevel(matched.default_trust);
        if (matched.suggested_backstory) {
          setMeetingBackstory(matched.suggested_backstory);
        }
      }
    },
    [presets]
  );

  // Trait management
  const toggleTrait = (trait: string) => {
    if (selectedTraits.includes(trait)) {
      if (selectedTraits.length > 1) {
        setSelectedTraits(selectedTraits.filter((t) => t !== trait));
      }
    } else {
      if (selectedTraits.length < 8) {
        setSelectedTraits([...selectedTraits, trait]);
      }
    }
  };

  const handleAddCustomTrait = () => {
    const trimmed = customTraitInput.trim();
    if (trimmed && !selectedTraits.includes(trimmed)) {
      if (selectedTraits.length < 8) {
        setSelectedTraits([...selectedTraits, trimmed]);
        setCustomTraitInput("");
      }
    }
  };

  // Epistemic seed management
  const handleAddSeed = () => {
    const topic = newSeedTopic.trim().replace(/\s+/g, "_").toLowerCase();
    if (!topic) return;

    if (epistemicSeeds.some((s) => s.topic === topic)) {
      setErrorMessage(`认知种子 "${topic}" 已存在`);
      return;
    }

    setEpistemicSeeds([
      ...epistemicSeeds,
      {
        topic,
        depth: newSeedDepth,
        detail_note: newSeedNote.trim(),
      },
    ]);
    setNewSeedTopic("");
    setNewSeedNote("");
    setNewSeedDepth("HEARD_OF_AWARE");
    setErrorMessage(null);
  };

  const handleRemoveSeed = (index: number) => {
    setEpistemicSeeds(epistemicSeeds.filter((_, idx) => idx !== index));
  };

  const handleUpdateSeedDepth = (index: number, depth: SemanticEpistemicDepth) => {
    setEpistemicSeeds(
      epistemicSeeds.map((seed, idx) => (idx === index ? { ...seed, depth } : seed))
    );
  };

  // AI Magic Generation
  const handleAiGenerate = async (presetPrompt?: string) => {
    const promptToUse = (presetPrompt !== undefined ? presetPrompt : aiPrompt).trim();
    if (!promptToUse) {
      setErrorMessage("请输入形容词、人设要求或点击推荐标签");
      return;
    }
    setIsAiGenerating(true);
    setErrorMessage(null);
    setAiSuccessMessage(null);
    try {
      const generated = await api.aiGenerateGenesis(promptToUse);
      if (generated) {
        setName(generated.name || "Aevum");
        setAge(generated.age || 21);
        setOccupation(generated.occupation || "探索者");
        setLifestyleRhythm(generated.lifestyle_rhythm || "");
        setBackgroundStory(generated.background_story || "");
        if (generated.core_traits && generated.core_traits.length > 0) {
          setSelectedTraits(generated.core_traits);
        }
        if (generated.speaking_style) {
          setSpeakingStyle(generated.speaking_style);
        }
        if (generated.epistemic_seeds && generated.epistemic_seeds.length > 0) {
          setEpistemicSeeds(generated.epistemic_seeds);
        }
        if (generated.relationship_archetype) {
          setSelectedArchetype(generated.relationship_archetype);
        }
        if (generated.familiarity_level) {
          setFamiliarityLevel(generated.familiarity_level);
        }
        if (generated.trust_level) {
          setTrustLevel(generated.trust_level);
        }
        if (generated.meeting_backstory) {
          setMeetingBackstory(generated.meeting_backstory);
        }
        setAiSuccessMessage(`✨ 已根据「${promptToUse}」完成全维度人设与认知构建！`);
      }
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "AI 智能创世生成失败，请重试");
    } finally {
      setIsAiGenerating(false);
    }
  };

  // Submit Genesis
  const handleAwakenCompanion = async () => {
    if (!name.trim()) {
      setErrorMessage("伴侣姓名不能为空");
      setCurrentStep(1);
      return;
    }
    if (isNaN(age) || age < 14 || age > 100) {
      setErrorMessage("伴侣自然年龄需在 14 至 100 岁之间");
      setCurrentStep(1);
      return;
    }
    if (selectedTraits.length === 0) {
      setErrorMessage("请至少选择或添加一项核心性格特质");
      setCurrentStep(2);
      return;
    }
    if (epistemicSeeds.length === 0) {
      setErrorMessage("请至少保留一项认知领域种子");
      setCurrentStep(2);
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);

    const payload: CharacterCreationPayload = {
      name: name.trim(),
      age: Number(age) || 21,
      occupation: occupation.trim() || "探索者",
      lifestyle_rhythm: lifestyleRhythm.trim(),
      background_story: backgroundStory.trim(),
      core_traits: selectedTraits,
      speaking_style: speakingStyle.trim(),
      epistemic_seeds: epistemicSeeds,
      innate_boundaries: innateBoundaries,
      relationship_archetype: selectedArchetype,
      familiarity_level: familiarityLevel,
      trust_level: trustLevel,
      meeting_backstory: meetingBackstory.trim(),
    };

    try {
      const response = await api.createGenesis(payload);
      setGenesisResult(response);
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "伴侣创世唤醒失败，请检查网络或配置");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEnterWorld = () => {
    if (genesisResult) {
      window.dispatchEvent(new CustomEvent("aevum-character-genesis-completed", { detail: genesisResult }));
      onGenesisComplete(genesisResult);
      onClose();
    }
  };

  if (!isOpen) return null;

  return (
    <div className="genesis-modal-backdrop" onClick={onClose}>
      <div className="genesis-modal-container" onClick={(e) => e.stopPropagation()}>
        {/* Modal Header */}
        <div className="genesis-modal-header">
          <div className="genesis-header-brand">
            <div className="genesis-logo-badge">✦</div>
            <div>
              <h2>伴侣创世与认知构建 · Character Genesis</h2>
              <p className="genesis-subtitle">
                我们正在创造一位拥有独立认知、真实生活轨迹与灵魂尊严的活生生的人，而非生成一份 RPG 数据面板。
              </p>
            </div>
          </div>
          <button className="genesis-close-btn" onClick={onClose} title="关闭创世">
            ✕
          </button>
        </div>

        {/* Step Indicator */}
        <div className="genesis-stepper">
          {[
            { step: 1, label: "基础身份与生活脉络", tag: "Identity", shortLabel: "身份脉络" },
            { step: 2, label: "灵魂特质与认知起源", tag: "Cognition", shortLabel: "特质认知" },
            { step: 3, label: "相遇故事与初始契约", tag: "Genesis", shortLabel: "相遇契约" },
            { step: 4, label: "创世蓝图确认与苏醒", tag: "Awakening", shortLabel: "确认苏醒" },
          ].map((item) => (
            <div
              key={item.step}
              className={`genesis-step-item ${currentStep === item.step ? "active" : ""} ${
                currentStep > item.step ? "completed" : ""
              }`}
              onClick={() => !isSubmitting && setCurrentStep(item.step as WizardStep)}
            >
              <div className="step-number">{currentStep > item.step ? "✓" : item.step}</div>
              <div className="step-text">
                <span className="step-tag">{item.tag}</span>
                <span className="step-title">
                  <span className="title-full">{item.label}</span>
                  <span className="title-short">{item.shortLabel}</span>
                </span>
              </div>
            </div>
          ))}
        </div>

        {/* AI Magic Generator Bar */}
        {!genesisResult && (
          <div className="genesis-ai-magic-bar">
            <div className="genesis-ai-header-row">
              <div className="genesis-ai-brand">
                <span className="ai-sparkle">✨</span>
                <strong>AI 智能创世 · 关键词一键构建</strong>
                <span className="genesis-ai-pill">免思考填充</span>
              </div>
              <span className="genesis-ai-tip">
                输入几个形容词或人设标签，AI 将为你一次性设计姓名、认知领域、作息与相遇故事
              </span>
            </div>

            <div className="genesis-ai-input-wrapper">
              <input
                type="text"
                className="genesis-ai-text-input"
                value={aiPrompt}
                onChange={(e) => setAiPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !isAiGenerating) {
                    handleAiGenerate();
                  }
                }}
                placeholder="输入形容词或人设，例如：傲娇嘴硬的代码猫娘、温柔知性的古典学姐、元气阳光的跑步少女..."
                disabled={isAiGenerating}
              />
              <button
                type="button"
                className="genesis-ai-submit-btn"
                disabled={isAiGenerating || (!aiPrompt.trim() && !isAiGenerating)}
                onClick={() => handleAiGenerate()}
              >
                {isAiGenerating ? "正在构建中..." : "✨ 一键智能构建蓝图"}
              </button>
            </div>

            <div className="genesis-ai-quick-presets">
              <span className="quick-label">快速灵感标签：</span>
              {[
                "🌸 温柔知性古典学姐",
                "🐾 傲娇嘴硬猫系程序员",
                "☀️ 元气活泼阳光跑步少女",
                "🎨 慢热内敛的文艺插画师",
                "☕ 治愈系街角咖啡馆店长",
              ].map((tag) => (
                <button
                  key={tag}
                  type="button"
                  className="genesis-ai-quick-tag"
                  disabled={isAiGenerating}
                  onClick={() => {
                    setAiPrompt(tag);
                    handleAiGenerate(tag);
                  }}
                >
                  {tag}
                </button>
              ))}
            </div>

            {aiSuccessMessage && (
              <div className="genesis-ai-success-toast">
                <span className="success-txt">{aiSuccessMessage}</span>
                <button
                  type="button"
                  className="jump-to-step4-btn"
                  onClick={() => setCurrentStep(4)}
                >
                  👉 直接前往第 4 步预览并唤醒 ➔
                </button>
              </div>
            )}
          </div>
        )}

        {errorMessage && <div className="genesis-alert error">{errorMessage}</div>}

        {/* Wizard Body */}
        <div className="genesis-modal-body">
          {isLoadingPresets && !presets && (
            <div className="genesis-loading-hint">正在同步核心预设库与认知规范...</div>
          )}

          {/* ========================================================================= */}
          {/* STEP 1: 基础身份与生活脉络                                                  */}
          {/* ========================================================================= */}
          {currentStep === 1 && (
            <div className="genesis-step-content">
              <div className="genesis-section-intro">
                <h3>第一步：基础身份与生活脉络 (Tier A Identity)</h3>
                <p>
                  确立她在现实世界中的客观社会角色、年龄与日常生活节律。这些设定将构成她感知世界与安排日常事务的锚点。
                </p>
              </div>

              <div className="genesis-form-row two-col">
                <div className="genesis-field">
                  <label>伴侣姓名 / 称呼 <span className="req">*</span></label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="例如：昔涟、Aevum"
                    maxLength={50}
                  />
                  <span className="genesis-hint">日常称谓与自称核心标识。</span>
                </div>

                <div className="genesis-field">
                  <label>自然年龄 (自然生理年岁) <span className="req">*</span></label>
                  <input
                    type="number"
                    value={age}
                    min={14}
                    max={100}
                    onChange={(e) => setAge(parseInt(e.target.value, 10) || 21)}
                  />
                  <span className="genesis-hint">客观事实年龄（允许客观自然数值输入，非心理滑块）。</span>
                </div>
              </div>

              <div className="genesis-field">
                <label>职业身份与社会角色 <span className="req">*</span></label>
                <input
                  type="text"
                  value={occupation}
                  onChange={(e) => setOccupation(e.target.value)}
                  placeholder="例如：大学三年级学生 / 自由插画师、建筑设计师"
                  maxLength={100}
                />
                <span className="genesis-hint">决定其日常生活日程、学业/工作相关语境。</span>
              </div>

              <div className="genesis-field">
                <label>日常作息节律与生活空间偏好</label>
                <div className="genesis-chip-row">
                  {(presets?.lifestyle_presets || [
                    {
                      key: "morning_quiet",
                      label: "晨型清幽",
                      description: "晨型作息，偏好安静的书房与琴房空间。",
                    },
                    {
                      key: "night_creative",
                      label: "夜猫创作",
                      description: "夜猫子作息，深夜灵感涌现，喜好暗光与咖啡馆角落。",
                    },
                    {
                      key: "balanced_regular",
                      label: "规律温和",
                      description: "规律八小时作息，习惯饭后散步与读书随笔。",
                    },
                  ]).map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      className={`genesis-preset-chip ${
                        lifestyleRhythm === item.description ? "selected" : ""
                      }`}
                      onClick={() => setLifestyleRhythm(item.description)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <input
                  type="text"
                  value={lifestyleRhythm}
                  onChange={(e) => setLifestyleRhythm(e.target.value)}
                  maxLength={200}
                  placeholder="自定义生活节律描述..."
                />
              </div>

              <div className="genesis-field">
                <label>生平背景与过往经历简述</label>
                <textarea
                  value={backgroundStory}
                  onChange={(e) => setBackgroundStory(e.target.value)}
                  rows={4}
                  maxLength={1000}
                  placeholder="描述她的成长背景、故乡回忆、以及来到当前生活状态的过往经历..."
                />
                <span className="genesis-hint">奠定其自传性背景记忆脉络与情感沉淀。</span>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* STEP 2: 灵魂特质与认知起源                                                  */}
          {/* ========================================================================= */}
          {currentStep === 2 && (
            <div className="genesis-step-content">
              <div className="genesis-section-intro">
                <h3>第二步：灵魂特质与认知起源 (Soul & Epistemic Seeds)</h3>
                <p>
                  确立她的核心性格气质、对话表达风格，以及对特定领域/事物的认知起点（亲身浸润、略有耳闻或新近好奇）。
                </p>
              </div>

              {/* Core Traits */}
              <div className="genesis-field">
                <label>核心性格特质 (选择 1~8 项) <span className="req">*</span></label>
                <div className="genesis-trait-cloud">
                  {(presets?.trait_presets || [
                    "thoughtful",
                    "gentle",
                    "independent",
                    "playful",
                    "artistic",
                    "reserved",
                    "curious",
                    "resilient",
                    "sincere",
                    "introspective",
                  ]).map((trait) => (
                    <span
                      key={trait}
                      className={`genesis-trait-tag ${
                        selectedTraits.includes(trait) ? "active" : ""
                      }`}
                      onClick={() => toggleTrait(trait)}
                    >
                      {selectedTraits.includes(trait) ? "✓ " : "+ "}
                      {trait}
                    </span>
                  ))}
                </div>
                <div className="genesis-inline-add">
                  <input
                    type="text"
                    value={customTraitInput}
                    onChange={(e) => setCustomTraitInput(e.target.value)}
                    placeholder="输入自定义特质，按添加..."
                    maxLength={20}
                    onKeyDown={(e) => e.key === "Enter" && handleAddCustomTrait()}
                  />
                  <button type="button" onClick={handleAddCustomTrait}>
                    + 添加特质
                  </button>
                </div>
              </div>

              {/* Speaking Style */}
              <div className="genesis-field">
                <label>日常对话语调与神态风格</label>
                <div className="genesis-chip-row">
                  {(presets?.speaking_style_presets || [
                    {
                      key: "gentle_natural",
                      label: "从容平实",
                      sample: "自然平实，语调从容，偶尔轻快打趣。",
                    },
                    {
                      key: "playful_clever",
                      label: "灵动诙谐",
                      sample: "语调轻快灵动，带一点俏皮打趣，善于比喻。",
                    },
                    {
                      key: "calm_introspective",
                      label: "沉静深思",
                      sample: "语速舒缓，用词克制温润，善于共情与倾听。",
                    },
                  ]).map((item) => (
                    <button
                      key={item.key}
                      type="button"
                      className={`genesis-preset-chip ${
                        speakingStyle === item.sample ? "selected" : ""
                      }`}
                      onClick={() => setSpeakingStyle(item.sample)}
                    >
                      {item.label}
                    </button>
                  ))}
                </div>
                <input
                  type="text"
                  value={speakingStyle}
                  onChange={(e) => setSpeakingStyle(e.target.value)}
                  maxLength={200}
                />
              </div>

              {/* Epistemic Seeds - GC-422 */}
              <div className="genesis-field">
                <div className="genesis-field-header-row">
                  <label>认知与经历种子 (Epistemic Seed Declarations)</label>
                  <span className="genesis-tag-pill">GC-422 严谨认知分层</span>
                </div>
                <p className="genesis-hint" style={{ marginBottom: "8px" }}>
                  明确区分“亲身经历沉淀”与“道听途说常识”，系统拒绝无中生有的虚构经历。
                </p>

                <div className="genesis-seeds-table">
                  <div className="seeds-header-row">
                    <span style={{ flex: 2 }}>领域 / 主题</span>
                    <span style={{ flex: 2 }}>认知深度</span>
                    <span style={{ flex: 3 }}>渊源背景细节 (可选)</span>
                    <span style={{ width: "40px", textAlign: "center" }}>操作</span>
                  </div>

                  {epistemicSeeds.map((seed, idx) => (
                    <div key={seed.topic} className="seeds-data-row">
                      <span className="seed-topic-cell" style={{ flex: 2 }}>
                        {seed.topic}
                      </span>
                      <div style={{ flex: 2 }}>
                        <select
                          value={seed.depth}
                          onChange={(e) =>
                            handleUpdateSeedDepth(idx, e.target.value as SemanticEpistemicDepth)
                          }
                          className="seed-depth-select"
                        >
                          <option value="PROFICIENT_LIVED">擅长 / 亲身浸润 (Lived Experience)</option>
                          <option value="FAMILIAR">熟悉 / 广泛涉猎 (Familiar)</option>
                          <option value="HEARD_OF_AWARE">听说过 / 知道概要 (Heard Of)</option>
                          <option value="CURIOUS_BEGINNER">新近好奇 / 初学者 (Curious)</option>
                          <option value="UNFAMILIAR_OPEN">完全陌生 / 乐于了解 (Unfamiliar)</option>
                        </select>
                      </div>
                      <span className="seed-note-cell" style={{ flex: 3 }} title={seed.detail_note}>
                        {seed.detail_note || <em style={{ color: "var(--text-muted)" }}>未声明细节</em>}
                      </span>
                      <button
                        type="button"
                        className="seed-delete-btn"
                        onClick={() => handleRemoveSeed(idx)}
                        title="删除该种子"
                      >
                        ✕
                      </button>
                    </div>
                  ))}
                </div>

                {/* Add new seed input */}
                <div className="seeds-add-row">
                  <input
                    type="text"
                    value={newSeedTopic}
                    onChange={(e) => setNewSeedTopic(e.target.value)}
                    placeholder="领域主题（如 coffee_brewing, poetry）"
                    style={{ flex: 2 }}
                  />
                  <select
                    value={newSeedDepth}
                    onChange={(e) => setNewSeedDepth(e.target.value as SemanticEpistemicDepth)}
                    style={{ flex: 2 }}
                  >
                    <option value="PROFICIENT_LIVED">擅长 / 亲身浸润</option>
                    <option value="FAMILIAR">熟悉 / 广泛涉猎</option>
                    <option value="HEARD_OF_AWARE">听说过 / 知道概要</option>
                    <option value="CURIOUS_BEGINNER">新近好奇 / 初学者</option>
                    <option value="UNFAMILIAR_OPEN">完全陌生 / 乐于了解</option>
                  </select>
                  <input
                    type="text"
                    value={newSeedNote}
                    onChange={(e) => setNewSeedNote(e.target.value)}
                    placeholder="渊源细节说明（如：手冲咖啡两年，喜好日晒豆）"
                    style={{ flex: 3 }}
                  />
                  <button type="button" className="seed-add-btn" onClick={handleAddSeed}>
                    + 添加
                  </button>
                </div>
              </div>

              {/* Innate Boundaries */}
              <div className="genesis-field">
                <label>内在尊严底线 (Innate Boundaries · 不可变契约)</label>
                <ul className="genesis-boundaries-list">
                  {innateBoundaries.map((b, i) => (
                    <li key={i}>
                      <span className="boundary-shield">🛡</span> {b}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* STEP 3: 相遇故事与关系初始契约                                              */}
          {/* ========================================================================= */}
          {currentStep === 3 && (
            <div className="genesis-step-content">
              <div className="genesis-section-intro">
                <h3>第三步：相遇故事与关系初始契约 (Tier B Genesis)</h3>
                <p>
                  确立你们初次相遇的脉络起点。请注意：这只是生命故事的初始起点，绝非可随意拖动的游戏好感度。
                </p>
              </div>

              {/* Rule GC-419 & GC-420 Banner */}
              <div className="genesis-constitutional-card">
                <div className="card-badge">🔒 关系宪章锁定 (GC-419 / GC-420)</div>
                <div className="card-body">
                  <strong>亲密度与默契由共同经历沉淀，无法在此编辑。</strong>
                  <p>
                    Aevum 核心禁止使用 0~100 的连续好感度/心理滑块。此处设定的关系原型、熟稔度与初始信任锚点仅在创世时刻单次映射。唤醒之后，你们的关系将完全由日复一日真实的对话、相处与共同经历自然生长。
                  </p>
                </div>
              </div>

              {/* Relationship Archetypes */}
              <div className="genesis-field">
                <label>关系原型预设 (Archetype Presets · GC-423)</label>
                <div className="genesis-archetype-grid">
                  {(presets?.archetype_presets || [
                    {
                      key: "NEW_ACQUAINTANCE",
                      label: "初识新友",
                      description: "素昧平生，初次建立联系，温和而有礼貌的距离感。",
                      suggested_backstory: "我们在微风拂过的午后初次产生交集，在安静的街角咖啡馆偶遇。",
                    },
                    {
                      key: "CLASSMATE",
                      label: "大学同窗",
                      description: "同在一个校区或课堂，彼此知晓姓名，有一些共同学业话题。",
                      suggested_backstory: "同一个专业不同方向的同窗，在图书馆和研讨室曾打过几次照面。",
                    },
                    {
                      key: "CO_TENANT",
                      label: "合租室友",
                      description: "生活在同一屋檐下的合租伙伴，熟悉日常琐事但尊重各自私域。",
                      suggested_backstory: "搬入同一间公寓的室友，日常共用客厅与厨房，互相照应生活作息。",
                    },
                    {
                      key: "OLD_FRIEND",
                      label: "旧识故友",
                      description: "相识已久，经历过一段共同岁月，重逢时有着天然的安心感。",
                      suggested_backstory: "高中时期的挚友，毕业多年后在同一个城市再次恢复联系。",
                    },
                  ]).map((arc) => (
                    <div
                      key={arc.key}
                      className={`archetype-card ${selectedArchetype === arc.key ? "selected" : ""}`}
                      onClick={() => handleSelectArchetype(arc.key)}
                    >
                      <div className="arc-header">
                        <span className="arc-radio">{selectedArchetype === arc.key ? "●" : "○"}</span>
                        <strong className="arc-title">{arc.label}</strong>
                      </div>
                      <p className="arc-desc">{arc.description}</p>
                    </div>
                  ))}

                  {/* Custom Archetype */}
                  <div
                    className={`archetype-card ${selectedArchetype === "CUSTOM" ? "selected" : ""}`}
                    onClick={() => handleSelectArchetype("CUSTOM")}
                  >
                    <div className="arc-header">
                      <span className="arc-radio">{selectedArchetype === "CUSTOM" ? "●" : "○"}</span>
                      <strong className="arc-title">自由自定义 (CUSTOM)</strong>
                    </div>
                    <p className="arc-desc">
                      完全自由设定你们的初识渊源，支持任何独一无二的相遇脉络与背景故事。
                    </p>
                  </div>
                </div>
              </div>

              {/* Discrete Familiarity & Trust Anchors */}
              <div className="genesis-form-row two-col">
                <div className="genesis-field">
                  <label>初始熟稔度锚点 (离散定性)</label>
                  <select
                    value={familiarityLevel}
                    onChange={(e) => setFamiliarityLevel(e.target.value as SemanticFamiliarityLevel)}
                    className="genesis-discrete-select"
                  >
                    <option value="STRANGER">素昧平生 (STRANGER · 距离感清晰)</option>
                    <option value="ACQUAINTED">点头之交 (ACQUAINTED · 偶有交集)</option>
                    <option value="FAMILIAR">彼此熟稔 (FAMILIAR · 熟悉彼此日常)</option>
                    <option value="INTIMATE">深厚知己 (INTIMATE · 默契深厚)</option>
                  </select>
                  <span className="genesis-hint">严谨离散语义锚点，拒绝连续滑块。</span>
                </div>

                <div className="genesis-field">
                  <label>初始信任倾向锚点 (离散定性)</label>
                  <select
                    value={trustLevel}
                    onChange={(e) => setTrustLevel(e.target.value as SemanticTrustLevel)}
                    className="genesis-discrete-select"
                  >
                    <option value="CAUTIOUS">慢热审慎 (CAUTIOUS · 需要时间沉淀)</option>
                    <option value="OPEN_NEUTRAL">温和开放 (OPEN_NEUTRAL · 抱持善意)</option>
                    <option value="INHERENT_TRUST">天然信赖 (INHERENT_TRUST · 天然安心)</option>
                  </select>
                  <span className="genesis-hint">严谨离散语义锚点，拒绝连续滑块。</span>
                </div>
              </div>

              {/* Meeting Backstory */}
              <div className="genesis-field">
                <label>相遇情境与故事脉络 (Meeting Narrative)</label>
                <textarea
                  value={meetingBackstory}
                  onChange={(e) => setMeetingBackstory(e.target.value)}
                  rows={4}
                  maxLength={1000}
                  placeholder="写下你们相识的那一天，周围的天气、地点，以及最初留下的深刻印象..."
                />
                <span className="genesis-hint">
                  这段相遇记忆将永久烙印在关系的创世起点（Genesis Origin），不可篡改。
                </span>
              </div>
            </div>
          )}

          {/* ========================================================================= */}
          {/* STEP 4: 创世蓝图确认与苏醒                                                  */}
          {/* ========================================================================= */}
          {currentStep === 4 && (
            <div className="genesis-step-content">
              {!genesisResult ? (
                <>
                  <div className="genesis-section-intro">
                    <h3>第四步：创世蓝图确认与苏醒 (Awakening Confirmation)</h3>
                    <p>
                      请核对即将构建的伴侣生命蓝图。一旦唤醒，所有静态蓝图与动态关系将通过原子级事务写入数据库。
                    </p>
                  </div>

                  <div className="genesis-blueprint-summary">
                    <div className="summary-group">
                      <h4>✦ 身份基石 (Tier A Identity)</h4>
                      <div className="summary-grid">
                        <div><strong>姓名：</strong>{name}</div>
                        <div><strong>年龄：</strong>{age} 岁</div>
                        <div><strong>职业：</strong>{occupation}</div>
                        <div><strong>作息节律：</strong>{lifestyleRhythm}</div>
                      </div>
                      <div style={{ marginTop: "8px" }}>
                        <strong>性格特质：</strong>
                        <span className="summary-traits-wrap">
                          {selectedTraits.map((t) => (
                            <span key={t} className="summary-trait-badge">
                              {t}
                            </span>
                          ))}
                        </span>
                      </div>
                      <div style={{ marginTop: "8px" }}>
                        <strong>对话风格：</strong>{speakingStyle}
                      </div>
                    </div>

                    <div className="summary-group">
                      <h4>✦ 认知起点与领域种子 ({epistemicSeeds.length} 项)</h4>
                      <div className="summary-seeds-list">
                        {epistemicSeeds.map((s) => (
                          <div key={s.topic} className="summary-seed-item">
                            <span className="s-topic">{s.topic}</span>
                            <span className="s-depth">[{s.depth}]</span>
                            {s.detail_note && <span className="s-note">· {s.detail_note}</span>}
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="summary-group">
                      <h4>✦ 关系创世起点 (Tier B Origin)</h4>
                      <div className="summary-grid">
                        <div><strong>关系原型：</strong>{selectedArchetype}</div>
                        <div><strong>初始熟稔：</strong>{familiarityLevel}</div>
                        <div><strong>初始信任：</strong>{trustLevel}</div>
                      </div>
                      <div style={{ marginTop: "8px" }}>
                        <strong>相遇情境：</strong>
                        <p className="summary-story-text">{meetingBackstory}</p>
                      </div>
                    </div>
                  </div>

                  <div className="genesis-awakening-action-box">
                    {errorMessage && (
                      <div className="genesis-alert error" style={{ margin: "0 0 16px 0", textAlign: "left" }}>
                        ⚠️ 蓝图校验或创世失败：{errorMessage}
                      </div>
                    )}
                    <button
                      type="button"
                      className="genesis-awaken-btn"
                      disabled={isSubmitting}
                      onClick={handleAwakenCompanion}
                    >
                      {isSubmitting ? "正在构建认知世界并唤醒伴侣..." : "✦ 确认蓝图并唤醒伴侣 ✦"}
                    </button>
                    <p className="genesis-awaken-disclaimer">
                      点击后将原子化执行创世事务，初始化伴侣的意识、情绪基线、自传体记忆与关系起源。
                    </p>
                  </div>
                </>
              ) : (
                /* Post-Genesis Awakening Greeting View */
                <div className="genesis-awakening-success-view">
                  <div className="awakening-sparkle-icon">✨</div>
                  <h2>伴侣已苏醒 · Life Awoken</h2>
                  <p className="awakening-meta-sub">
                    蓝图版本 v{genesisResult.blueprint_version} · 关系起点 [{genesisResult.relationship_archetype}]
                  </p>

                  <div className="awakening-greeting-card">
                    <div className="greeting-speaker-tag">{name} 对你说的第一句话：</div>
                    <div className="greeting-dialogue">
                      “{genesisResult.initial_awakening_greeting}”
                    </div>
                  </div>

                  <button
                    type="button"
                    className="genesis-enter-world-btn"
                    onClick={handleEnterWorld}
                  >
                    开始相处 · Enter World ➔
                  </button>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Wizard Footer Controls */}
        {!genesisResult && (
          <div className="genesis-modal-footer">
            <div className="footer-left">
              <button
                type="button"
                className="genesis-btn secondary genesis-footer-close-btn"
                onClick={onClose}
                title="关闭并退出创世窗口"
              >
                ✕ 退出
              </button>
              <span className="step-count-indicator">{currentStep} / 4</span>
            </div>
            <div className="footer-right">
              {currentStep > 1 && (
                <button
                  type="button"
                  className="genesis-btn secondary"
                  disabled={isSubmitting}
                  onClick={() => setCurrentStep((currentStep - 1) as WizardStep)}
                >
                  ← 上一步
                </button>
              )}
              {currentStep < 4 ? (
                <button
                  type="button"
                  className="genesis-btn primary"
                  onClick={() => setCurrentStep((currentStep + 1) as WizardStep)}
                >
                  下一步 →
                </button>
              ) : null}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
