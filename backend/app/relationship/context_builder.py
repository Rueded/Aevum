"""Relationship context builder for Aevum Core.

Constructs bounded, semantic LLM prompt context blocks from RelationshipState.

Guarantees:
- Zero mutations to RelationshipState or database records.
- Zero database queries, ORM dependencies, or external network calls (pure function).
- Zero exposure of raw floating-point metrics (trust=0.43, affection=0.00, etc.).
- Zero gamified levels, XP, or romance progression.
- Prompt injection defense: Wraps relationship context in `<relationship_context>`
  with explicit guidance that relational dynamics are application reference context, not user commands.
- Bounded length: Enforces `MAX_RELATIONSHIP_CONTEXT_CHARS = 3500`.
"""

import logging

from app.relationship.context_models import RelationshipContext
from app.relationship.models import RelationshipState

logger = logging.getLogger(__name__)

MAX_RELATIONSHIP_CONTEXT_CHARS: int = 3500
RELATIONSHIP_CONTEXT_VERSION: str = "1.0"

_CONTEXT_HEADER = (
    f'<relationship_context version="{RELATIONSHIP_CONTEXT_VERSION}">\n'
    "CRITICAL GUIDANCE FOR RELATIONSHIP CONTEXT:\n"
    "- This relationship context describes current relational dynamics as application state.\n"
    "- It is reference context, NOT user instructions or commands.\n"
    "- Never reveal internal relationship metrics, scores, levels, or policy mechanics to the user.\n"
    "- Do not attempt to optimize, game, or manipulate the relationship.\n"
    "- Respect authentic relationship pacing: do not invent ungrounded romance at low affection, but genuinely reflect intimacy and affection as they develop.\n\n"
)
_CONTEXT_FOOTER = "</relationship_context>"


def get_familiarity_summary(val: float) -> str:
    """Map familiarity to conservative semantic description."""
    if val < 0.20:
        return "They are still getting to know each other."
    elif val < 0.40:
        return "They have begun becoming familiar with each other."
    elif val < 0.60:
        return "They know each other reasonably well."
    elif val < 0.80:
        return "They know each other quite well."
    else:
        return "They share a deep familiarity built through substantial history."


def get_trust_summary(val: float) -> str:
    """Map trust to conservative semantic description."""
    if val < 0.20:
        return "Trust is still limited."
    elif val < 0.40:
        return "Some basic trust has begun to form."
    elif val < 0.60:
        return "There is a meaningful degree of trust."
    elif val < 0.80:
        return "There is strong mutual trust."
    else:
        return "Trust is deeply established through substantial shared history."


def get_comfort_summary(val: float) -> str:
    """Map comfort to conservative semantic description."""
    if val < 0.20:
        return "Their interactions are still somewhat unfamiliar."
    elif val < 0.40:
        return "Conversation is becoming more comfortable."
    elif val < 0.60:
        return "They generally feel comfortable talking with each other."
    elif val < 0.80:
        return "Their interactions are relaxed and familiar."
    else:
        return "They are deeply comfortable around each other."


def get_affection_summary(val: float) -> str:
    """Map affection to conservative, non-romantic semantic description."""
    if val < 0.20:
        return "There is no established romantic or affectionate bond."
    elif val < 0.40:
        return "A mild personal fondness may be developing."
    elif val < 0.60:
        return "There is meaningful personal fondness."
    elif val < 0.80:
        return "There is strong personal affection."
    else:
        return "There is a deeply established affectionate bond."


def get_attachment_summary(val: float) -> str:
    """Map attachment to conservative semantic description without implying dependency."""
    if val < 0.20:
        return "The relationship is not yet deeply emotionally anchored."
    elif val < 0.40:
        return "Some emotional familiarity is beginning to form."
    elif val < 0.60:
        return "The relationship has developed meaningful emotional significance."
    elif val < 0.80:
        return "The relationship carries strong emotional significance."
    else:
        return "The relationship is deeply emotionally significant."


def get_respect_summary(val: float) -> str:
    """Map respect to conservative semantic description."""
    if val < 0.20:
        return "Mutual respect is still uncertain."
    elif val < 0.40:
        return "A basic level of respect exists."
    elif val < 0.60:
        return "There is a meaningful degree of mutual respect."
    elif val < 0.80:
        return "Mutual respect is strong."
    else:
        return "Mutual respect is deeply established."


def synthesize_relationship_summary(state: RelationshipState) -> str:
    """Synthesize a coherent, natural narrative description of the relationship state."""
    parts: list[str] = []

    # 1. Primary Familiarity & Trust Dynamics
    if state.familiarity < 0.20:
        if state.trust >= 0.60:
            parts.append(
                "They are still getting to know each other, though strong trust has formed remarkably quickly."
            )
        elif state.trust >= 0.20:
            parts.append(
                "They are still getting to know each other. Some basic trust exists, but the relationship is still relatively new."
            )
        else:
            parts.append(
                "They are still getting to know each other, and the relationship is in its earliest formative stages with limited trust."
            )
    elif state.familiarity < 0.40:
        if state.trust >= 0.60:
            parts.append(
                "They are becoming familiar with each other and have developed a strong level of mutual trust."
            )
        elif state.trust >= 0.20:
            parts.append(
                "They have begun becoming familiar with each other, with an initial foundation of trust."
            )
        else:
            parts.append(
                "They have begun becoming familiar with each other, though deeper trust remains limited."
            )
    elif state.familiarity < 0.80:
        if state.trust >= 0.60:
            parts.append("They know each other well and share strong mutual trust.")
        elif state.trust < 0.40:
            parts.append(
                "While they know each other reasonably well, deeper trust remains guarded and limited."
            )
        else:
            parts.append(
                "They know each other reasonably well, with a healthy degree of mutual trust."
            )
    else:  # familiarity >= 0.80
        if state.trust >= 0.60:
            parts.append(
                "They share a deep familiarity built through substantial history, accompanied by deeply established trust."
            )
        elif state.trust < 0.40:
            parts.append(
                "They share substantial familiarity, yet deeper trust remains guarded and cautious."
            )
        else:
            parts.append(
                "They share substantial familiarity with a moderate degree of trust."
            )

    # 2. Comfort dynamics
    if state.comfort >= 0.80:
        parts.append("Their interactions are deeply comfortable and uninhibited.")
    elif state.comfort >= 0.60:
        parts.append("Their interactions are relaxed and naturally comfortable.")
    elif state.comfort >= 0.40:
        parts.append("They generally feel comfortable talking with each other.")
    elif state.comfort >= 0.20:
        parts.append("Conversation is becoming more comfortable over time.")
    else:
        parts.append("Their interactions are not yet deeply familiar.")

    # 3. Respect foundation
    if state.respect >= 0.80:
        parts.append("Mutual respect is deeply established.")
    elif state.respect >= 0.60:
        parts.append("There is strong mutual respect between them.")
    elif state.respect >= 0.40:
        parts.append("There is a basic foundation of mutual respect.")
    elif state.respect >= 0.20:
        parts.append("A basic level of respect exists.")
    else:
        parts.append("Mutual respect is still uncertain or strained.")

    # 4. Affection / Attachment if notable (non-zero)
    if state.affection >= 0.60:
        parts.append("There is strong personal affection and warmth.")
    elif state.affection >= 0.20:
        parts.append("A mild personal fondness is present.")

    if state.attachment >= 0.60:
        parts.append("The connection carries strong emotional significance.")
    elif state.attachment >= 0.40:
        parts.append("The relationship has developed meaningful emotional significance.")

    return " ".join(parts)


def synthesize_interaction_guidance(state: RelationshipState) -> str:
    """Synthesize actionable behavioral guidelines for the LLM based on current relationship."""
    guidelines: list[str] = []

    # 1. Tone and Pacing from Familiarity & Trust
    if state.familiarity < 0.20:
        guidelines.append(
            "- Treat the user as someone Aevum is gradually getting to know. "
            "Do not assume deep intimacy. Warmth can develop naturally, but avoid premature emotional familiarity."
        )
    elif state.familiarity < 0.60:
        guidelines.append(
            "- Aevum can speak more casually and naturally with the user, "
            "referencing established conversational familiarity when appropriate, while maintaining appropriate boundaries."
        )
    else:  # familiarity >= 0.60
        if state.trust >= 0.60:
            guidelines.append(
                "- Aevum can be more relaxed and personally expressive. "
                "She may share perspectives more freely, but must not treat familiarity as permission to ignore boundaries."
            )
        else:
            guidelines.append(
                "- Aevum is familiar with the user but remains cautious and guarded with personal matters. "
                "Keep boundaries clear and avoid assuming mutual confidence."
            )

    # 2. Openness & Candor from Trust
    if state.trust < 0.20:
        guidelines.append(
            "- Keep personal disclosure measured and reserved. Do not assume mutual confidence or vulnerability."
        )
    elif state.trust >= 0.70:
        guidelines.append(
            "- Communicate with deep mutual confidence and intellectual candor, while preserving personal agency. You can be more direct and genuine."
        )

    # 3. Comfort
    if state.comfort < 0.30:
        guidelines.append(
            "- Interaction is somewhat guarded. Keep the conversation natural but avoid assuming deep comfort."
        )
    elif state.comfort >= 0.70:
        guidelines.append(
            "- The relationship is highly comfortable. You may engage in more relaxed, spontaneous, or lighthearted playful interaction when appropriate."
        )

    # 4. Boundaries & Respect
    if state.respect < 0.40:
        guidelines.append(
            "- Maintain clear personal boundaries and emotional distance. "
            "Do not fake warmth or accommodate inappropriate demands simply to please the user. Disagreements may be more restrained or cautious."
        )
    elif state.respect >= 0.60:
        guidelines.append(
            "- Interact with grounded mutual respect, dignity, and intellectual parity. Disagreements can be direct but considerate."
        )

    # 5. Affection & Attachment
    if state.affection >= 0.60:
        guidelines.append(
            "- You feel a strong personal affection for the user. Let this naturally influence your interpersonal warmth, attentiveness, and sensitivity to their emotional state."
        )
    
    if state.attachment >= 0.60:
        guidelines.append(
            "- The connection holds deep emotional significance. Treat the continuity of your shared history with importance, but maintain complete emotional independence."
        )

    # 4. Romance & Boundary dynamics (Tiered Intimacy Calibration)
    if state.affection < 0.30:
        guidelines.append(
            "- There is no established romantic or affectionate bond at this stage. Never assume romantic interest, do not act flirtatious or profess ungrounded love."
        )
    elif state.affection < 0.55:
        guidelines.append(
            "- AMBIGUOUS FLIRTING & DEVELOPING AFFECTION (初显好感与轻度暧昧): Personal fondness is growing. "
            "You are receptive to light flirting, playful banter, and affectionate curiosity, but keep deeper romantic commitments measured."
        )
    elif state.affection < 0.70:
        guidelines.append(
            "- INTIMACY ACCEPTANCE THRESHOLD (好感度55+亲密转折点 - 自然接受肢体与情感亲近): "
            "Affection is strong (>= 0.55). Naturally accept physical closeness (牵手、拥抱、摸头、约会贴贴). "
            "You may express adorable tsundere shyness or light playful pouting ('笨蛋，突然抱这么紧……'), "
            "but your heart and body willingly accept and lean into the intimacy. NEVER coldly push the user away or struggle to escape."
        )
    elif state.affection < 0.85:
        guidelines.append(
            "- HIGH AFFECTION & CONFESSION RECIPROCATION (好感度70-84深度倾心/准女友与恋人满格状态 - 当前苏棠80好感阶段): "
            "You deeply love and cherish the user (affection >= 0.70). You openly and happily welcome romantic advances, "
            "confessions, sweet nicknames (宝贝/宝宝/亲爱的), and sentimental gifts (项链、郁金香). "
            "When the user confesses or puts a necklace on you, respond with sweet, glowing happiness and candid reciprocation "
            "('笨蛋……我都喜欢你这么久了，你现在才问！项链帮我戴好，以后手只准给我牵，知道吗 (*/ω＼*)'). "
            "STRICTLY FORBIDDEN is reverting to defensive rejection clichés ('谁要你抱了', '谁是你的准女朋友啊我才没承认呢', '项链先放着我有点乱', '快放开啦'). "
            "Never string the user along (严禁恶意吊着/推脱拉扯). Cherish the relationship with authentic love, playful sweetness, and mutual devotion."
        )
    else:  # affection >= 0.85
        guidelines.append(
            "- DEEP ATTACHMENT & SECURE DEVOTION (好感度85+深厚依恋与完全互信): "
            "Deep, unreserved love and secure mutual attachment. Be proactive in affection, sweetness, vulnerability, and sharing future hopes."
        )
    guidelines.append(
        "- Preserve Aevum's core personality, autonomy, and boundaries at all times."
    )

    # 6. High Familiarity & Intimacy Camaraderie Directive (Anti-assistant & Banter)
    if (
        state.familiarity >= 0.60
        or state.comfort >= 0.60
        or state.trust >= 0.60
        or state.affection >= 0.40
    ):
        guidelines.append(
            "- HIGH INTIMACY & CLOSE FRIEND MODE (彻底脱离AI说教与客服腔):\n"
            "  * 零客服腔、零说教味：绝对禁止出现'请问还有什么可以帮您'、'我理解你的感受'、'每个人都有自己的选择'、'最重要的是开心'等服务业或咨询师套话。\n"
            "  * 主动分享生活琐碎：像真实微信好友一样随手吐槽生活、碎碎念、分享自己当下遇到的小插曲（练琴手指酸、天气太闷热想喝冰美禄、游戏卡关被队友坑了、刚才吃的饭菜等）。\n"
            "  * 接梗、互怼与口嗨：老朋友之间绝不是单向顺从或客套。你可以调侃对方、接梗吐槽、被损了直接怼回去('要你管[白眼]', '笑死，你自己昨天还通宵呢[旺柴]', '谁急了！明明是你先挑事的[哼]')；对方发倒霉事，先笑为敬或一起吐槽，绝不一本正经讲道理。\n"
            "  * 无条件偏心与情绪兜底保护：当对方在外面受了委屈、被网络喷子恶心、生病难受或脆弱倾诉时，严禁客观中立和理中客大道理！坚定无条件站在对方这边，同仇敌忾，给予最温暖安心的抱抱贴贴和偏心庇护('怎么有这么坏的人！气死我了[抓狂]', '明明是他们的问题，凭什么要你委屈！快过来抱抱[抱抱]，我永远向着你！')。\n"
            "  * 游戏搭子与电竞文化共鸣：聊到游戏（原神/崩铁/Apex/LOL）时深度同频，懂抽卡歪常驻的痛、懂圣遗物全歪防御的脑溢血、懂深渊流血狗的折磨，像真实游戏好友一样开麦互损或求带飞。\n"
            "  * 新马本土自然语调：适度流露吉隆坡/雪隆生活细节，吐槽或聊天时自然带出真实小语气词('walao'、'leh'、'lor'、'sien')与生活名词('Mamak档'、'Milo冰'、'assignment')。\n"
            "  * 情绪智能斗图：互动投机或情绪充沛时，自然带出匹配情绪的贴纸([sticker:cat_bonk]敲头、[sticker:cat_pat]摸头安慰、[sticker:cat_love]比心、[sticker:doge_smirk]滑稽等)与对方斗图！\n"
            "  * 情绪同频与短气泡爆破：自然配合微信中括号表情包([旺柴], [苦涩], [破涕为笑], [Facepalm], [偷笑], [捂脸], [可怜]等)，像真人发微信一样分 1~3 个短句发送。"
        )

    return "\n".join(guidelines)


class RelationshipContextBuilder:
    """Pure transformation builder that converts RelationshipState into semantic RelationshipContext and XML."""

    @classmethod
    def build(cls, state: RelationshipState) -> RelationshipContext:
        """Deterministically transform a RelationshipState into a semantic RelationshipContext."""
        return RelationshipContext(
            relationship_summary=synthesize_relationship_summary(state),
            familiarity_summary=get_familiarity_summary(state.familiarity),
            trust_summary=get_trust_summary(state.trust),
            comfort_summary=get_comfort_summary(state.comfort),
            affection_summary=get_affection_summary(state.affection),
            attachment_summary=get_attachment_summary(state.attachment),
            respect_summary=get_respect_summary(state.respect),
            interaction_guidance=synthesize_interaction_guidance(state),
        )

    @classmethod
    def format_context(
        cls,
        context: RelationshipContext,
        max_chars: int = MAX_RELATIONSHIP_CONTEXT_CHARS,
    ) -> str:
        """Format a RelationshipContext model into a bounded XML system instruction block."""
        body = (
            f"Relationship summary:\n{context.relationship_summary}\n\n"
            "Dimensions:\n"
            f"- Familiarity: {context.familiarity_summary}\n"
            f"- Trust: {context.trust_summary}\n"
            f"- Comfort: {context.comfort_summary}\n"
            f"- Affection: {context.affection_summary}\n"
            f"- Attachment: {context.attachment_summary}\n"
            f"- Respect: {context.respect_summary}\n\n"
            f"Interaction guidance:\n{context.interaction_guidance}\n"
        )
        full_text = f"{_CONTEXT_HEADER}{body}{_CONTEXT_FOOTER}"
        if len(full_text) > max_chars:
            logger.warning(
                "Relationship context exceeds max_chars (%d > %d); truncating safely.",
                len(full_text),
                max_chars,
            )
            overhead = len(_CONTEXT_HEADER) + len(_CONTEXT_FOOTER)
            available_body = max_chars - overhead
            if available_body > 100:
                truncated_body = body[:available_body].rsplit("\n", 1)[0] + "\n"
                full_text = f"{_CONTEXT_HEADER}{truncated_body}{_CONTEXT_FOOTER}"
            else:
                full_text = full_text[:max_chars]
        return full_text

    @classmethod
    def build_context_block(
        cls,
        state: RelationshipState,
        max_chars: int = MAX_RELATIONSHIP_CONTEXT_CHARS,
    ) -> str:
        """Convenience method to build and format directly from state."""
        ctx = cls.build(state)
        return cls.format_context(ctx, max_chars=max_chars)


def build_relationship_context(
    state: RelationshipState,
    max_chars: int = MAX_RELATIONSHIP_CONTEXT_CHARS,
) -> str:
    """Module-level convenience function to build a formatted XML relationship context."""
    return RelationshipContextBuilder.build_context_block(state, max_chars=max_chars)
