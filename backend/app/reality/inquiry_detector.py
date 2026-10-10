"""Reality Inquiry Detector for Phase 20 Gate 0.

Strict Invariants:
- INQUIRY != EVIDENCE:
  Distinguishes user assertions ('you study music') from personal inquiries ('what major do you study?').
  An inquiry does NOT provide evidence, but signals an opportunity to evaluate/infer an unknown reality slot.
- Pure function / stateless detection: zero DB, zero LLM, zero side-effects.
- Respects existing Canonical reality: if a slot is already established and CANONICAL in CharacterCore,
  it returns None (no inference needed for already known reality).
"""

from dataclasses import dataclass
import re
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.character.core_models import CharacterCore
    from app.reality.models import FactStatus


@dataclass(frozen=True)
class InquirySignal:
    """Immutable signal emitted when user inquires about an unknown personal reality slot."""

    target_slot: str
    inquiry_text: str
    is_personal_reality_inquiry: bool = True


def _has_any_kw(text: str, keywords: list[str]) -> bool:
    lower = text.lower()
    return any(kw.lower() in lower for kw in keywords)


def _has_all_kw(text: str, keyword_groups: list[list[str]]) -> bool:
    lower = text.lower()
    return all(any(kw.lower() in lower for kw in group) for group in keyword_groups)


class RealityInquiryDetector:
    """Detects whether a user message is an inquiry targeting an unknown personal reality slot."""

    @classmethod
    def detect_inquiry(
        cls,
        user_input: str,
        core: Optional["CharacterCore"] = None,
    ) -> Optional[InquirySignal]:
        """Detect personal reality inquiry from user input.

        Args:
            user_input: Raw user message string.
            core: Optional CharacterCore snapshot to verify whether slot is already known.

        Returns:
            InquirySignal if an unknown slot is targeted; None otherwise.
        """
        text = user_input.strip()
        if not text:
            return None

        # Check existing canonical facts in core
        def is_already_canonical(slot_key: str) -> bool:
            if core and hasattr(core, "facts") and core.facts:
                fact = core.facts.get(slot_key)
                if fact is not None and getattr(fact, "status", None) is not None:
                    from app.reality.models import FactStatus
                    return fact.status == FactStatus.CANONICAL
            return False

        # ------------------------------------------------------------------
        # 1. Target: education.major
        # e.g., "你读什么专业？", "你学什么专业？", "平时学些什么？", "修什么专业", "what major do you study?"
        # ------------------------------------------------------------------
        if not is_already_canonical("education.major"):
            if _has_all_kw(text, [
                ["专业", "系", "major", "field of study", "学科"],
                ["读什么", "学什么", "念什么", "修什么", "是什么", "哪门", "what is", "what do you study"],
            ]) or _has_any_kw(text, [
                "读什么专业", "学什么专业", "你的专业是", "什么专业", "平时学些什么",
                "what's your major", "what is your major", "what major",
            ]):
                return InquirySignal(
                    target_slot="education.major",
                    inquiry_text=text,
                )

        # ------------------------------------------------------------------
        # 2. Target: education.institution
        # e.g., "那你在哪间大学？", "你读哪所大学？", "在哪个学校就读？", "which university do you go to?"
        # ------------------------------------------------------------------
        if not is_already_canonical("education.institution"):
            if _has_all_kw(text, [
                ["大学", "学校", "高校", "学院", "university", "uni", "college"],
                ["哪间", "哪所", "哪个", "哪里", "what", "which", "where"],
            ]) or _has_any_kw(text, [
                "读哪间大学", "读哪所大学", "在哪间大学", "在哪所大学", "在哪个学校",
                "什么大学", "哪所学校", "which university", "what university", "which college",
            ]):
                return InquirySignal(
                    target_slot="education.institution",
                    inquiry_text=text,
                )

        # ------------------------------------------------------------------
        # 3. Target: education.year
        # e.g., "你现在大几了？", "几年级学生？", "what year are you in?"
        # ------------------------------------------------------------------
        if not is_already_canonical("education.year"):
            if _has_any_kw(text, [
                "大几了", "大几", "几年级", "念几年级", "读几年级", "第几年",
                "what year are you", "which year are you", "what grade",
            ]):
                return InquirySignal(
                    target_slot="education.year",
                    inquiry_text=text,
                )

        # ------------------------------------------------------------------
        # 4. Target: family.parents_occupation
        # e.g., "你父母是做什么的？", "你爸妈是做什么工作的？", "家里人从事什么职业？", "what do your parents do?"
        # ------------------------------------------------------------------
        if not is_already_canonical("family.parents_occupation"):
            if _has_all_kw(text, [
                ["父母", "爸妈", "父亲", "母亲", "家里人", "爹娘", "家长", "parents"],
                ["做什么", "什么工作", "什么职业", "干嘛", "干什么", "上班", "从事", "what do they do"],
            ]) or _has_any_kw(text, [
                "父母是做什么", "爸妈是做什么", "你爸妈做什么", "父母职业", "爸妈职业",
                "家里是做什么的", "家里是干嘛的", "what do your parents do", "parents' occupation",
            ]):
                return InquirySignal(
                    target_slot="family.parents_occupation",
                    inquiry_text=text,
                )

        # ------------------------------------------------------------------
        # 5. Target: family.childhood_background
        # e.g., "你几岁开始学琴的？", "从小就学钢琴吗？", "小时候家境怎么样？", "学琴多久了？"
        # ------------------------------------------------------------------
        if not is_already_canonical("family.childhood_background"):
            if _has_all_kw(text, [
                ["学琴", "练琴", "钢琴", "弹琴", "音乐", "家境", "小时候"],
                ["几岁", "多久", "从小", "什么时候开始", "经历", "怎么样", "how long", "since when"],
            ]) or _has_any_kw(text, [
                "几岁开始学琴", "几岁学琴", "从小就学琴", "学琴多久", "小时候学琴",
                "小时候的经历", "小时候家境", "自幼学琴",
            ]):
                return InquirySignal(
                    target_slot="family.childhood_background",
                    inquiry_text=text,
                )

        # ------------------------------------------------------------------
        # 6. Target: lifestyle.transit
        # e.g., "你平时出门坐什么车？", "怎么去上学/去槟城？", "平时开车还是搭地铁？"
        # ------------------------------------------------------------------
        if not is_already_canonical("lifestyle.transit"):
            if _has_all_kw(text, [
                ["出行", "出门", "通勤", "去学校", "回槟城", "交通"],
                ["坐什么", "怎么去", "乘什么", "开车还是", "搭什么", "how do you commute", "how do you get"],
            ]) or _has_any_kw(text, [
                "出门坐什么", "平时出门搭什么", "怎么去学校", "怎么去槟城",
                "开车还是搭车", "坐地铁吗", "坐轻快铁吗",
            ]):
                return InquirySignal(
                    target_slot="lifestyle.transit",
                    inquiry_text=text,
                )

        # ------------------------------------------------------------------
        # 7. Target: lifestyle.beverage
        # e.g., "你平时喜欢喝什么奶茶？", "平时喝什么饮料？", "喜欢喝咖啡还是奶茶？"
        # ------------------------------------------------------------------
        if not is_already_canonical("lifestyle.beverage"):
            if _has_all_kw(text, [
                ["喝什么", "喜欢喝", "爱喝", "饮料", "奶茶", "咖啡", "茶"],
                ["平时", "一般", "通常", "喜欢", "什么", "what do you drink", "favorite drink"],
            ]) or _has_any_kw(text, [
                "喜欢喝什么", "平时喝什么", "爱喝什么", "喜欢喝奶茶吗", "喝咖啡还是", "常喝什么",
            ]):
                return InquirySignal(
                    target_slot="lifestyle.beverage",
                    inquiry_text=text,
                )

        # ------------------------------------------------------------------
        # 8. Target: education.secondary_school
        # e.g., "你以前读哪个中学？", "高中是在哪里读的？"
        # ------------------------------------------------------------------
        if not is_already_canonical("education.secondary_school"):
            if _has_all_kw(text, [
                ["中学", "高中", "独中", "国中", "high school", "secondary school"],
                ["哪个", "哪间", "哪所", "哪里", "which", "where"],
            ]) or _has_any_kw(text, [
                "读哪所中学", "读哪个高中", "读哪间中学", "中学是在哪", "高中是在哪",
            ]):
                return InquirySignal(
                    target_slot="education.secondary_school",
                    inquiry_text=text,
                )

        # ------------------------------------------------------------------
        # 9. Target: education.music_qualification
        # e.g., "你钢琴考过几级？", "考过英皇八级吗？", "有没有考级？"
        # ------------------------------------------------------------------
        if not is_already_canonical("education.music_qualification"):
            if _has_all_kw(text, [
                ["钢琴", "音乐", "乐理"],
                ["考级", "几级", "证书", "文凭", "abrsm", "级数"],
            ]) or _has_any_kw(text, [
                "考过几级", "钢琴考级", "考过八级吗", "英皇八级", "考过什么证书",
            ]):
                return InquirySignal(
                    target_slot="education.music_qualification",
                    inquiry_text=text,
                )

        return None
