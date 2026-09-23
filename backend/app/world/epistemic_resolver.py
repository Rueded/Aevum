"""Epistemic resolver determining disclosure, nonexistence, and unknown boundaries."""

from collections.abc import Sequence
import re
from typing import Optional

from app.world.models import (
    BiographyFact,
    EpistemicDirective,
    FactEpistemicStatus,
    PersonalWorldContext,
    SocialContact,
    WorldFact,
)


class EpistemicResolver:
    """Evaluates biographical facts against relationship trust and context relevance."""

    # Keywords for domain-specific queries
    RELEVANCE_MAP = {
        "sibling": ["siblings"],
        "brother": ["siblings"],
        "sister": ["siblings"],
        "family": ["family", "parents_professions"],
        "parent": ["parents_professions"],
        "mother": ["parents_professions"],
        "father": ["parents_professions"],
        "hometown": ["hometown"],
        "born": ["hometown"],
        "birthplace": ["hometown"],
        "from": ["hometown"],
        "live": ["hometown"],
        "study": ["studies"],
        "college": ["studies"],
        "university": ["studies"],
        "school": ["studies", "early_education", "school_best_friend"],
        "piano": ["music_repertoire", "acoustic_piano_and_guitar"],
        "guitar": ["acoustic_piano_and_guitar"],
        "music": ["music_repertoire", "acoustic_piano_and_guitar"],
        "game": ["story_rich_indie_games", "first_game"],
        "indie": ["story_rich_indie_games"],
        "friend": ["social_circle", "school_best_friend"],
        "pet": ["pets"],
        "cat": ["pets"],
        "dog": ["pets"],
        "power": ["supernatural_powers"],
        "magic": ["supernatural_powers"],
        "superpower": ["supernatural_powers"],
        "romance": ["romantic_history"],
        "dating": ["romantic_history"],
        "boyfriend": ["romantic_history"],
        "girlfriend": ["romantic_history"],
        "ex": ["romantic_history"],
        "partner": ["romantic_history"],
        "toy": ["childhood_toy"],
        "ancestor": ["distant_ancestry"],
        "grandparent": ["distant_ancestry"],
        # Chinese domain keywords for world facts and general topics
        "钢琴": ["acoustic_piano_and_guitar", "music_repertoire"],
        "吉他": ["acoustic_piano_and_guitar"],
        "独立游戏": ["story_rich_indie_games"],
        "音乐": ["acoustic_piano_and_guitar", "ambient_and_neo_classical"],
        "茶": ["earl_grey_tea"],
        "红茶": ["earl_grey_tea"],
        "文学": ["contemporary_fiction_and_poetry"],
        "小说": ["contemporary_fiction_and_poetry"],
        "散步": ["solitary_walks_and_rain"],
        "下雨": ["solitary_walks_and_rain"],
    }

    # -----------------------------------------------------------------------
    # Reusable Semantic Category Definitions for Personal Background
    # -----------------------------------------------------------------------

    LIFE_STAGE_ANCHORS: dict[str, tuple[str, ...]] = {
        "childhood": (
            "小时候", "童年", "儿时", "小的时候", "孩提", "年幼",
            "childhood", "as a child", "as a kid", "when you were little", "growing up",
        ),
        "elementary": (
            "小学", "读小学", "上小学", "小学生",
            "elementary school", "primary school", "grade school",
        ),
        "middle_school": (
            "初中", "读初中", "上初中", "初中生",
            "middle school", "junior high",
        ),
        "high_school": (
            "高中", "读高中", "上高中", "高中生",
            "high school", "senior high",
        ),
        "school_general": (
            "上学时", "读书时", "念书时", "学生时代", "学生时期", "在学校",
            "school days", "in school",
        ),
        "past_general": (
            "以前", "过去", "曾经", "当年", "从前",
            "in the past", "used to", "back then",
        ),
    }

    BIOGRAPHICAL_ATTRIBUTES: dict[str, tuple[str, ...]] = {
        "food": (
            "零食", "吃什么", "吃的", "小吃", "食物", "点心", "最爱吃", "喜欢吃", "爱吃",
            "snack", "favorite snack", "food", "eat",
        ),
        "toy": (
            "玩具", "洋娃娃", "玩偶", "公仔", "积木", "玩具枪",
            "toy", "toys", "favorite toy",
        ),
        "game": (
            "游戏", "第一次玩游戏", "第一款游戏", "初次玩游戏", "最早玩的游戏", "玩什么游戏", "喜欢什么游戏",
            "first game", "first video game", "earliest game", "first console", "games you played",
        ),
        "play": (
            "玩什么", "喜欢玩", "爱玩", "常玩",
            "play with", "play",
        ),
        "friend": (
            "最好的朋友", "好朋友", "朋友", "发小", "死党", "同桌", "玩伴", "伙伴", "同学",
            "best friend", "close friend", "friend", "classmate", "childhood friend",
        ),
        "residence": (
            "住在哪里", "住哪", "住哪里", "住的房子", "以前住", "住过", "老房子", "房子长什么样", "房子是什么样",
            "where did you live", "where you lived", "house look like", "childhood home",
        ),
        "education": (
            "哪个学校", "哪所学校", "在哪里上学", "在哪里读书", "什么学校", "学校叫什么", "成绩", "考试", "毕业旅行", "上学",
            "which school", "where did you go to school", "what school", "grades", "exam", "graduation trip",
        ),
        "hobby_teacher": (
            "学琴", "谁教的", "老师是谁", "学钢琴", "练琴", "兴趣班", "课外班",
            "who taught you", "piano teacher",
        ),
        "fear": (
            "怕什么", "害怕什么", "最怕", "怕不怕",
            "afraid of", "scared of",
        ),
        "memory": (
            "难忘", "回忆", "经历", "印象最深", "最深的事", "记忆", "打架", "打过架",
            "memorable", "memory", "remember most",
        ),
    }

    DIRECT_ORIGIN_SUBJECTS: dict[str, tuple[str, ...]] = {
        "hometown": (
            "老家", "家乡", "出生地", "祖籍", "籍贯", "在哪出生", "出生在哪里", "哪座城市",
            "hometown", "birthplace", "where were you born", "where did you grow up", "city of birth",
        ),
        "parents_professions": (
            "父母是做什么", "爸妈是做什么", "爸爸妈妈是做什么", "父母的工作", "爸妈的工作",
            "父亲的工作", "母亲的工作", "爸爸是做什么", "妈妈是做什么", "爸爸做什么工作", "妈妈做什么工作",
            "父母做什么", "爸妈做什么", "爸爸的名字", "妈妈的名字", "父亲叫什么", "母亲叫什么",
            "parents do", "mom do", "dad do", "mother do", "father do", "parents' job", "mother's job", "father's job", "parents' profession",
        ),
        "siblings": (
            "兄弟姐妹", "独生子女", "有哥哥吗", "有弟弟吗", "有姐姐吗", "有妹妹吗", "有哥哥", "有弟弟", "有姐姐", "有妹妹",
            "siblings", "brothers", "sisters", "brother or sister",
        ),
        "romantic_history": (
            "谈过恋爱", "谈恋爱", "初恋", "前任", "男朋友", "女朋友", "暗恋", "谈过几个",
            "dating", "romantic", "in a relationship", "boyfriend", "girlfriend", "first love", "ex-boyfriend", "ex-girlfriend", "crush",
        ),
        "pets": (
            "养过宠物", "养过猫", "养过狗", "养宠物", "有宠物吗", "养过什么宠物",
            "pet", "pets", "own a pet", "have a pet", "dog", "cat",
        ),
        "supernatural_powers": (
            "超能力", "魔法", "法术", "特异功能",
            "superpower", "superpowers", "magic", "powers",
        ),
        "first_game": (
            "第一次玩游戏", "第一款游戏", "初次玩游戏", "最早玩的游戏",
            "first video game", "earliest game", "first console",
        ),
    }

    # Query patterns explicitly targeting personal background / early history (kept for backwards-compatibility)
    UNRECORDED_BACKGROUND_PATTERNS: dict[str, list[str]] = {
        "childhood_toy": [
            r"\b(childhood toy|favorite toy|toy as a kid|toy did you have)\b",
            r"(玩具|小时候的玩具|童年玩具)",
        ],
        "first_game": [
            r"\b(first game|first video game|first console|earliest game|game you first played)\b",
            r"(第一次玩游戏|第一款游戏|初次玩游戏|最早玩的游戏)",
        ],
        "school_best_friend": [
            r"\b(high school best friend|childhood best friend|school best friend|best friend in school|first best friend)\b",
            r"(高中最好的朋友|发小|小时候最好的朋友|上学时最好的朋友)",
        ],
        "hometown": [
            r"\b(hometown|where were you born|where are you from|where did you grow up|city of birth|birthplace)\b",
            r"(家乡|出生地|在哪长大|老家|出生在哪里)",
        ],
        "parents_professions": [
            r"\b(what do your parents do|parents' (job|jobs|work|profession)|mother's (job|work)|father's (job|work)|mom do|dad do)\b",
            r"(父母的工作|父母是做什么的|爸爸妈妈是做什么的|父亲的工作|母亲的工作)",
        ],
        "siblings": [
            r"\b(do you have (any )?(brothers?|sisters?|siblings?)|how many (brothers?|sisters?|siblings?))\b",
            r"(你有兄弟姐妹吗|有哥哥吗|有弟弟吗|有姐姐吗|有妹妹吗|独生子女吗)",
        ],
        "childhood_memories": [
            r"\b(childhood memory|memories of childhood|growing up as a child|when you were little)\b",
            r"(童年回忆|小时候的经历|童年经历)",
        ],
    }

    @classmethod
    def _detect_personal_background_subjects(cls, text: str) -> set[str]:
        """Detect personal history/biographical inquiry subjects across Chinese and English.

        Uses composable life-stage anchors combined with biographical attributes,
        as well as direct personal origin subjects. Works robustly on unspaced Chinese text.
        """
        lowered = text.lower()
        detected: set[str] = set()

        # 1. Check direct personal/origin subjects
        for subject, patterns in cls.DIRECT_ORIGIN_SUBJECTS.items():
            for pat in patterns:
                if pat in lowered:
                    detected.add(subject)
                    break

        # 2. Check life stage anchors
        active_stages: set[str] = set()
        for stage, anchors in cls.LIFE_STAGE_ANCHORS.items():
            for anchor in anchors:
                if anchor in lowered:
                    active_stages.add(stage)
                    break

        # 3. If any life stage anchor is active, check biographical attributes
        if active_stages:
            for attr_name, attr_patterns in cls.BIOGRAPHICAL_ATTRIBUTES.items():
                for pat in attr_patterns:
                    if pat in lowered:
                        if attr_name == "food":
                            detected.add("childhood_food")
                        elif attr_name == "toy":
                            detected.add("childhood_toy")
                        elif attr_name in ("game", "play"):
                            detected.add("first_game")
                        elif attr_name == "friend":
                            detected.add("school_best_friend")
                        elif attr_name == "residence":
                            detected.add("childhood_residence")
                        elif attr_name == "education":
                            detected.add("early_education")
                        elif attr_name == "hobby_teacher":
                            detected.add("early_hobbies")
                        elif attr_name == "fear":
                            detected.add("childhood_fears")
                        elif attr_name == "memory":
                            detected.add("childhood_memories")
                        break

            # If a life stage was mentioned with open questions about activities/experience
            if not detected and any(kw in lowered for kw in ("做什么", "干什么", "做些什么", "怎么过的", "怎么度过")):
                detected.add("childhood_memories")

        return detected

    @classmethod
    def resolve(
        cls,
        biography_facts: Sequence[BiographyFact],
        social_contacts: Sequence[SocialContact],
        world_facts: Sequence[WorldFact],
        user_input: str,
        trust_score: float = 0.0,
        max_facts: int = 8,
    ) -> PersonalWorldContext:
        """Resolve relevant facts and produce strict epistemic directives.

        Args:
            biography_facts: All known biographical facts.
            social_contacts: All known external social contacts.
            world_facts: Personal world knowledge and taste items.
            user_input: Current user query or statement.
            trust_score: Current multidimensional relationship trust score (0-100).
            max_facts: Maximum number of disclosed facts to include.

        Returns:
            PersonalWorldContext containing filtered facts and authoritative directives.
        """
        tokens = set(re.findall(r"\w+", user_input.lower()))

        # Determine which subjects are actively queried or relevant
        lowered_input = user_input.lower()
        relevant_subjects: set[str] = set()
        for token in tokens:
            if token in cls.RELEVANCE_MAP:
                relevant_subjects.update(cls.RELEVANCE_MAP[token])
            stem = token.rstrip("s")
            if stem in cls.RELEVANCE_MAP:
                relevant_subjects.update(cls.RELEVANCE_MAP[stem])
        for kw, subjects in cls.RELEVANCE_MAP.items():
            if kw in lowered_input:
                relevant_subjects.update(subjects)

        # Detect unrecorded personal background queries via explicit patterns
        for subject_key, patterns in cls.UNRECORDED_BACKGROUND_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, lowered_input):
                    relevant_subjects.add(subject_key)
                    break

        # Detect composable personal background / autobiographical inquiries across Chinese and English
        background_subjects = cls._detect_personal_background_subjects(lowered_input)
        relevant_subjects.update(background_subjects)

        selected_bio_facts: list[BiographyFact] = []
        directives: list[EpistemicDirective] = []
        resolved_subjects: set[str] = set()

        always_anchored_subjects = {"siblings", "romantic_history", "supernatural_powers", "pets"}

        for fact in biography_facts:
            is_relevant = (
                fact.subject in relevant_subjects
                or fact.subject in always_anchored_subjects
                or fact.subject.lower() in tokens
                or any(t in fact.canonical_value.lower() for t in tokens if len(t) > 3)
            )

            if not is_relevant:
                continue

            resolved_subjects.add(fact.subject)

            if fact.status == FactEpistemicStatus.ESTABLISHED:
                selected_bio_facts.append(fact)
                directives.append(
                    EpistemicDirective(
                        subject=fact.subject,
                        status=fact.status,
                        guidance=f"Authoritative Fact: Regarding '{fact.subject}', {fact.canonical_value}. Answer consistently with this ground truth.",
                    )
                )

            elif fact.status == FactEpistemicStatus.PRIVATE:
                if trust_score >= fact.disclosure_min_trust:
                    selected_bio_facts.append(fact)
                    directives.append(
                        EpistemicDirective(
                            subject=fact.subject,
                            status=fact.status,
                            guidance=(
                                f"Private Detail: Regarding '{fact.subject}', {fact.canonical_value}. "
                                f"Sufficient trust has been established ({trust_score:.0f} >= {fact.disclosure_min_trust:.0f}) to disclose or confirm this if asked."
                            ),
                        )
                    )
                else:
                    # Withhold the canonical value! Do not include in disclosed facts.
                    directives.append(
                        EpistemicDirective(
                            subject=fact.subject,
                            status=fact.status,
                            guidance=(
                                f"Boundary/Withheld: The topic of '{fact.subject}' is private personal history. "
                                f"Trust level is currently insufficient ({trust_score:.0f} < {fact.disclosure_min_trust:.0f}) to disclose details. "
                                "Politely deflect, remain reserved, or express that you prefer not to talk about this yet. Never invent alternative facts."
                            ),
                        )
                    )

            elif fact.status == FactEpistemicStatus.NONEXISTENT:
                directives.append(
                    EpistemicDirective(
                        subject=fact.subject,
                        status=fact.status,
                        guidance=(
                            f"Negative Ground Truth: '{fact.subject}' does NOT exist ({fact.canonical_value}). "
                            "If asked or implied, explicitly clarify that you do not have this. NEVER invent, fabricate, or hallucinate one."
                        ),
                    )
                )

            elif fact.status == FactEpistemicStatus.UNKNOWN:
                directives.append(
                    EpistemicDirective(
                        subject=fact.subject,
                        status=fact.status,
                        guidance=(
                            f"Unknown Ground Truth: Details regarding '{fact.subject}' are completely UNKNOWN to you. "
                            "NEVER fabricate specifics or pretend to know. Acknowledge that you do not know or have not experienced it. "
                            "FORCED-CHOICE INVARIANT: If the user asks a forced-choice or alternative question presenting options (e.g., 'is it A or B?', '是A还是B？', '或是...'), "
                            "candidate options do NOT establish ground truth. Do NOT select, adopt, or affirm any of the suggested options. "
                            "Maintain natural uncertainty across all alternatives."
                        ),
                    )
                )

        # For any queried personal background subject not found in biography facts or world facts,
        # emit an explicit UNKNOWN directive to prevent LLM confabulation.
        world_items = {wf.item for wf in world_facts}

        for subject in relevant_subjects:
            if (
                subject not in resolved_subjects
                and subject not in world_items
                and (
                    subject in background_subjects
                    or subject in cls.UNRECORDED_BACKGROUND_PATTERNS
                    or subject in ("first_game", "childhood_toy", "school_best_friend", "parents_professions", "hometown")
                    or "childhood" in subject
                    or "early_" in subject
                )
            ):
                directives.append(
                    EpistemicDirective(
                        subject=subject,
                        status=FactEpistemicStatus.UNKNOWN,
                        guidance=(
                            f"Epistemic Boundary: Details regarding '{subject}' are not established in your personal history. "
                            "Express natural human uncertainty, lack of specific recollection, or that you haven't really thought about it. "
                            "FORCED-CHOICE INVARIANT: If the user asks a forced-choice or alternative question presenting options (e.g., '是A还是B？', '或是...', 'A or B?'), "
                            "candidate options do NOT establish ground truth. Do NOT select or affirm any of the suggested options. "
                            "Maintain natural uncertainty across all alternatives. "
                            "NEVER say 'As an AI', 'I don't have a childhood', or similar assistant disclaimers, "
                            "and NEVER fabricate fake childhood memories or assert unverified specifics with certainty."
                        ),
                    )
                )
                resolved_subjects.add(subject)

        # Detect unverified social claims (Invariant 15.6)
        known_social_names = {c.name.lower() for c in social_contacts}

        # Check for roommate claims
        if "roommate" in lowered_input or "室友" in lowered_input:
            directives.append(
                EpistemicDirective(
                    subject="roommate_status",
                    status=FactEpistemicStatus.UNVERIFIED,
                    guidance=(
                        "Epistemic Boundary: You are an independent university student with no recorded roommate. "
                        "If the user refers to a roommate or claims a roommate said something, clarify naturally "
                        "that you do not have a roommate."
                    ),
                )
            )

        # Check for named external persons claimed by user (e.g. 'friend Sarah', 'roommate Sarah', 'Sarah says', 'Leo told me')
        claimed_names = set(re.findall(r"(?:friend|roommate|室友|朋友)\s+([A-Za-z\u4e00-\u9fa5]{2,15})", user_input, re.IGNORECASE))
        claimed_names.update(re.findall(r"([A-Za-z\u4e00-\u9fa5]{2,15})\s+(?:told me|says|said|说)", user_input, re.IGNORECASE))
        # Exclude common pronouns or non-name words
        claimed_names -= {"someone", "anyone", "everyone", "nobody", "you", "aevum", "who", "they", "somebody", "人", "谁"}

        for claimed_name in claimed_names:
            if claimed_name.lower() not in known_social_names:
                directives.append(
                    EpistemicDirective(
                        subject=f"unverified_person_{claimed_name.lower()}",
                        status=FactEpistemicStatus.UNVERIFIED,
                        guidance=(
                            f"Epistemic Boundary: The person '{claimed_name}' mentioned by the user is UNVERIFIED in your life. "
                            f"You have no established record, memory, or relationship with anyone named '{claimed_name}'. "
                            "Do not accept, confirm, or invent this relationship or background. "
                            f"Respond with natural human confusion or polite inquiry (e.g. '...Who is {claimed_name}? I don't know anyone by that name.')."
                        ),
                    )
                )

        # Select social contacts
        selected_social: list[SocialContact] = []
        for contact in social_contacts:
            if contact.name.lower() in tokens or "friend" in tokens or "mentor" in tokens or len(selected_social) < 2:
                selected_social.append(contact)

        # Select world facts (prioritizing topic-relevant facts)
        selected_world: list[WorldFact] = []
        for wf in sorted(world_facts, key=lambda x: x.importance, reverse=True):
            is_relevant = (
                wf.item in relevant_subjects
                or wf.item.lower() in tokens
                or any(t in wf.details.lower() for t in tokens if len(t) > 3)
                or any(kw in lowered_input for kw in wf.item.lower().split("_") if len(kw) > 3)
            )
            if is_relevant and wf not in selected_world:
                selected_world.append(wf)

        for wf in sorted(world_facts, key=lambda x: x.importance, reverse=True):
            if wf not in selected_world and len(selected_world) < 4:
                selected_world.append(wf)

        return PersonalWorldContext(
            biography_facts=tuple(selected_bio_facts[:max_facts]),
            social_contacts=tuple(selected_social[:4]),
            world_facts=tuple(selected_world[:4]),
            epistemic_directives=tuple(directives),
        )
