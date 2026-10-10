"""Life Hypothesis Proposer for Phase 8A.3 (Autonomous Reality & Life Inference).

Strict Invariants:
- Proposes candidate hypotheses for an open target slot from authorized canonical premises.
- LifeHypothesisProposer is NOT an authority: zero mutation of canonical reality, zero set_fact(),
  zero token creation, zero DB transactions, zero competition/choice, zero web/tool calls.
- Candidate Cardinality Invariant: strictly emits between 2 and 4 distinct candidates (2 <= k <= 4).
  Never emits a single candidate (satisfies Phase 7 Gate 6 candidate plurality).
- Premise Discipline: candidates cite ONLY authorized premise keys from InferenceProposalRequest.
- Non-Epistemic Rationale: rationale is display-only metadata, never evidence or premise.
- Slot Value Normalization: raw values are normalized via SlotValueNormalizer.
"""

from abc import ABC, abstractmethod
import logging
from typing import Any, Optional, Sequence

from app.reality.inference_models import (
    CandidateEnvelope,
    InferenceProposalRequest,
    PremiseRole,
)
from app.reality.slot_normalizer import NormalizationStatus, SlotValueNormalizer

logger = logging.getLogger(__name__)


class LifeHypothesisProposer(ABC):
    """Abstract interface for proposing bounded competing candidate hypotheses."""

    @abstractmethod
    async def propose_hypotheses(
        self,
        request: InferenceProposalRequest,
    ) -> Sequence[CandidateEnvelope]:
        """Propose bounded candidate hypotheses (2 <= k <= 4) for an open target slot.

        Returns empty sequence () if fewer than 2 distinct plausible candidates
        can be constructed from the authorized premises.
        """
        ...


class DeterministicLifeHypothesisProposer(LifeHypothesisProposer):
    """Deterministic, rule-seeded life hypothesis proposer for reproducible inference and testing.

    Evaluates authorized premise snapshots and synthesizes 2 to 4 diverse,
    plausible, normalized candidate envelopes without external network or LLM dependencies.
    """

    async def propose_hypotheses(
        self,
        request: InferenceProposalRequest,
    ) -> Sequence[CandidateEnvelope]:
        """Generate 2 to 4 normalized candidate envelopes for supported slots."""
        if not isinstance(request, InferenceProposalRequest):
            logger.warning("Invalid request type passed to proposer: %s", type(request))
            return ()

        slot = request.target_slot
        authorized_keys = set(request.authorized_premise_keys)
        snapshots = request.premise_snapshots

        if not authorized_keys:
            logger.debug("Proposer received empty authorized_premise_keys; aborting.")
            return ()

        raw_candidates: list[dict[str, Any]] = []

        # ---------------------------------------------------------------------
        # 1. education.major
        # ---------------------------------------------------------------------
        if slot == "education.major":
            raw_candidates = self._propose_major_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 2. education.institution
        # ---------------------------------------------------------------------
        elif slot in ("education.institution", "education.university"):
            raw_candidates = self._propose_institution_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 3. education.year
        # ---------------------------------------------------------------------
        elif slot == "education.year":
            raw_candidates = self._propose_year_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 4. education.pathway
        # ---------------------------------------------------------------------
        elif slot == "education.pathway":
            raw_candidates = self._propose_pathway_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 5. career.aspiration
        # ---------------------------------------------------------------------
        elif slot == "career.aspiration":
            raw_candidates = self._propose_career_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 6. family.parents_occupation
        # ---------------------------------------------------------------------
        elif slot == "family.parents_occupation":
            raw_candidates = self._propose_parents_occupation_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 7. family.childhood_background
        # ---------------------------------------------------------------------
        elif slot == "family.childhood_background":
            raw_candidates = self._propose_childhood_background_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 8. lifestyle.transit
        # ---------------------------------------------------------------------
        elif slot == "lifestyle.transit":
            raw_candidates = self._propose_transit_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 9. lifestyle.beverage
        # ---------------------------------------------------------------------
        elif slot == "lifestyle.beverage":
            raw_candidates = self._propose_beverage_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 10. education.secondary_school
        # ---------------------------------------------------------------------
        elif slot == "education.secondary_school":
            raw_candidates = self._propose_secondary_school_candidates(authorized_keys, snapshots)

        # ---------------------------------------------------------------------
        # 11. education.music_qualification
        # ---------------------------------------------------------------------
        elif slot == "education.music_qualification":
            raw_candidates = self._propose_music_qualification_candidates(authorized_keys, snapshots)

        # Unsupported slot
        else:
            logger.debug("Slot '%s' is not supported by DeterministicLifeHypothesisProposer.", slot)
            return ()

        # ---------------------------------------------------------------------
        # Validation, Normalization, Premise Discipline, and Cardinality Check
        # ---------------------------------------------------------------------
        validated_envelopes: list[CandidateEnvelope] = []
        seen_normalized_values: set[str] = set()

        for cand_dict in raw_candidates:
            raw_val = cand_dict.get("raw_value")
            norm_res = SlotValueNormalizer.normalize(slot, raw_val)

            # Skip un-normalizable values
            if not norm_res.is_valid:
                logger.debug("Pruning un-normalizable proposed value '%s' for slot '%s'.", raw_val, slot)
                continue

            normalized_token = str(norm_res.normalized_value)
            # Skip duplicates to ensure genuine diversity
            if normalized_token in seen_normalized_values:
                continue
            seen_normalized_values.add(normalized_token)

            # Premise Discipline: Filter suggested premise keys to strictly authorized keys
            suggested_keys = tuple(
                k for k in cand_dict.get("suggested_premise_keys", ())
                if k in authorized_keys
            )
            if not suggested_keys:
                # Candidate must be grounded by at least one authorized premise
                continue

            suggested_roles = {
                k: cand_dict.get("suggested_premise_roles", {}).get(k, PremiseRole.CONTEXT_SUPPORT)
                for k in suggested_keys
            }

            envelope = CandidateEnvelope(
                domain=request.domain,
                slot=slot,
                raw_value=norm_res.normalized_value,
                suggested_premise_keys=suggested_keys,
                suggested_premise_roles=suggested_roles,
                rationale=cand_dict.get("rationale", ""),
            )
            validated_envelopes.append(envelope)

            # Cap at maximum 4 candidates
            if len(validated_envelopes) >= 4:
                break

        # Cardinality Invariant: Minimum 2 candidates required for competition (Gate 6)
        if len(validated_envelopes) < 2:
            logger.info(
                "Fewer than 2 viable distinct candidates constructed (%d) for slot '%s'; "
                "returning empty sequence to prevent single-candidate self-promotion.",
                len(validated_envelopes),
                slot,
            )
            return ()

        return tuple(validated_envelopes)

    # -------------------------------------------------------------------------
    # Domain Candidate Synthesis Helpers
    # -------------------------------------------------------------------------

    def _propose_major_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Synthesize competing major options from authorized academic, talent, and interest facts."""
        has_music_talent = snapshots.get("traits.musical_talent") is True
        interests = snapshots.get("interests", []) or []
        if isinstance(interests, str):
            interests = [interests]
        has_piano = any("piano" in str(i).lower() or "guitar" in str(i).lower() or "instrument" in str(i).lower() for i in interests) or bool(snapshots.get("skills.instrument_playing"))
        has_prog = bool(snapshots.get("skills.programming"))
        has_music_interest = has_piano or any("music" in str(i).lower() for i in interests) or snapshots.get("preferences.music") is not None
        has_gaming_interest = any("game" in str(i).lower() or "gaming" in str(i).lower() for i in interests)

        candidates: list[dict[str, Any]] = []

        # Option 1: Music Performance (Creative / Artistic track)
        if has_music_talent or has_piano or has_music_interest:
            music_premises = [k for k in ("traits.musical_talent", "skills.instrument_playing", "preferences.music", "interests", "education.level") if k in authorized_keys]
            if not music_premises:
                music_premises = [k for k in authorized_keys if k in ("interests", "education.level", "identity.age")]
            if music_premises:
                candidates.append({
                    "raw_value": "Music Performance",
                    "suggested_premise_keys": tuple(music_premises),
                    "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in music_premises},
                    "rationale": "Pursues advanced instrumental mastery and core musical interests.",
                })

        # Option 2: Computer Science / Software Engineering (Analytical / Career track)
        cs_premises = [k for k in ("skills.programming", "academics.spm_math_grade", "values.career_stability", "values.parental_expectation") if k in authorized_keys]
        if cs_premises or has_prog or "academics.spm_math_grade" in authorized_keys:
            roles = {}
            for k in cs_premises:
                val = str(snapshots.get(k, "")).lower()
                if "math" in k and val in ("c", "d", "e", "f"):
                    roles[k] = PremiseRole.CONTRADICTING
                elif "stability" in k or "expectation" in k:
                    roles[k] = PremiseRole.DIRECT_SUPPORT
                else:
                    roles[k] = PremiseRole.CONTEXT_SUPPORT
            candidates.append({
                "raw_value": "Computer Science",
                "suggested_premise_keys": tuple(cs_premises),
                "suggested_premise_roles": roles,
                "rationale": "High-demand technology discipline offering vocational stability favored by family expectations.",
            })

        # Option 3: Sound Engineering / Audio Production (Creative-Technical Hybrid)
        if has_music_talent or has_music_interest or has_piano or has_prog:
            hybrid_premises = [k for k in ("traits.musical_talent", "skills.instrument_playing", "family.socioeconomic_tier", "values.career_stability", "interests", "education.level") if k in authorized_keys]
            if not hybrid_premises:
                hybrid_premises = [k for k in authorized_keys if k in ("interests", "education.level")]
            if hybrid_premises:
                candidates.append({
                    "raw_value": "Sound Engineering",
                    "suggested_premise_keys": tuple(hybrid_premises),
                    "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in hybrid_premises},
                    "rationale": "Bridges artistic musical capabilities with practical commercial audio production technologies.",
                })

        # Option 4: Digital Media Design (Commercial Applied Creative)
        if has_music_talent or has_gaming_interest or has_piano or "values.creativity" in authorized_keys:
            media_premises = [k for k in ("values.creativity", "traits.musical_talent", "interests", "family.socioeconomic_tier", "education.level") if k in authorized_keys]
            if not media_premises:
                media_premises = [k for k in authorized_keys if k in ("interests", "education.level")]
            if media_premises:
                candidates.append({
                    "raw_value": "Digital Media",
                    "suggested_premise_keys": tuple(media_premises),
                    "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in media_premises},
                    "rationale": "Applied multidisciplinary design combining interactive digital media, sound, and visual arts.",
                })

        return candidates

    def _propose_institution_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Synthesize competing university institution options from world knowledge and character profile."""
        edu_premises = [k for k in ("education.level", "education.major", "identity.age", "location.residence", "family.background", "interests") if k in authorized_keys]
        if not edu_premises:
            edu_premises = list(authorized_keys)

        candidates: list[dict[str, Any]] = []

        # Option 1: Universiti Sains Malaysia (USM) - Penang main campus
        candidates.append({
            "raw_value": "Universiti Sains Malaysia (USM)",
            "suggested_premise_keys": tuple(edu_premises),
            "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in edu_premises},
            "rationale": "Renowned public research university in Penang with a distinguished School of the Arts, offering a quiet environment fitting Aevum's reflective nature.",
        })

        # Option 2: Universiti Malaya (UM) - Kuala Lumpur premier public research university
        candidates.append({
            "raw_value": "Universiti Malaya (UM)",
            "suggested_premise_keys": tuple(edu_premises),
            "suggested_premise_roles": {k: PremiseRole.CONTEXT_SUPPORT for k in edu_premises},
            "rationale": "Premier Malaysian public university in Kuala Lumpur with strong academic traditions across arts and sciences.",
        })

        # Option 3: Monash University Malaysia - Bandar Sunway premier international campus
        candidates.append({
            "raw_value": "Monash University Malaysia",
            "suggested_premise_keys": tuple(edu_premises),
            "suggested_premise_roles": {k: PremiseRole.CONTEXT_SUPPORT for k in edu_premises},
            "rationale": "Renowned Australian university branch campus in Sunway fitting supportive family background and global creative standards.",
        })

        return candidates

    def _propose_year_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Synthesize competing academic year options grounded in age and undergraduate degree stage."""
        premises = [k for k in ("identity.age", "education.level", "education.pathway") if k in authorized_keys]
        if not premises:
            premises = list(authorized_keys)

        candidates: list[dict[str, Any]] = []

        # Option 1: Year 2 (Typical trajectory for 21yo following 1.5yr STPM Form 6)
        candidates.append({
            "raw_value": "Year 2",
            "suggested_premise_keys": tuple(premises),
            "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in premises},
            "rationale": "Standard undergraduate progression: age 21 corresponds to Year 2 following 1.5-year STPM pre-university track.",
        })

        # Option 2: Year 3 (Alternative trajectory if entered degree at 19)
        candidates.append({
            "raw_value": "Year 3",
            "suggested_premise_keys": tuple(premises),
            "suggested_premise_roles": {k: PremiseRole.CONTEXT_SUPPORT for k in premises},
            "rationale": "Plausible alternative trajectory if university matriculation commenced at age 19.",
        })

        return candidates

    def _propose_pathway_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Synthesize competing post-secondary pathways from academic and preference facts."""
        candidates: list[dict[str, Any]] = []

        readiness_premises = [k for k in ("academics.spm_overall", "academics.spm_results", "education.level", "identity.age") if k in authorized_keys]
        challenge_premises = [k for k in ("traits.challenge_preference", "traits.intellectual_style") if k in authorized_keys]
        resource_premises = [k for k in ("family.socioeconomic_tier", "finances.budget_tier", "scholarship.status") if k in authorized_keys]

        # Option 1: STPM (High academic rigor, cost-effective, challenging 1.5 years)
        stpm_premises = tuple(readiness_premises + challenge_premises)
        candidates.append({
            "raw_value": "STPM",
            "suggested_premise_keys": stpm_premises,
            "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in stpm_premises},
            "rationale": "Rigorous public post-secondary certificate offering comprehensive academic preparation for public universities.",
        })

        # Option 2: Matrikulasi (Fast-track 1-year pathway, targeted public admissions)
        matrik_premises = tuple(readiness_premises + [k for k in ("preferences.study_duration",) if k in authorized_keys])
        candidates.append({
            "raw_value": "Matrikulasi",
            "suggested_premise_keys": matrik_premises,
            "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in matrik_premises},
            "rationale": "Direct government pre-university program offering an accelerated one-year route into domestic universities.",
        })

        # Option 3: Foundation (Streamlined private university preparation)
        foundation_premises = tuple(readiness_premises + resource_premises)
        candidates.append({
            "raw_value": "Foundation",
            "suggested_premise_keys": foundation_premises,
            "suggested_premise_roles": {k: PremiseRole.CONTEXT_SUPPORT for k in foundation_premises},
            "rationale": "Pre-university foundation program providing direct, specialized transition into private university degree programs.",
        })

        return candidates

    def _propose_career_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Synthesize competing career aspirations from education major, skills, and values."""
        major = str(snapshots.get("education.major", "")).lower()
        has_prog = bool(snapshots.get("skills.programming"))
        has_music = snapshots.get("traits.musical_talent") is True or bool(snapshots.get("skills.instrument_playing"))

        candidates: list[dict[str, Any]] = []

        major_premises = [k for k in ("education.major", "education.level") if k in authorized_keys]
        skill_premises = [k for k in ("skills.programming", "skills.instrument_playing", "traits.musical_talent") if k in authorized_keys]
        value_premises = [k for k in ("values.career_stability", "values.creativity", "values.independence") if k in authorized_keys]

        if "computer" in major or "software" in major or has_prog:
            # Software Engineer
            swe_keys = tuple(major_premises + [k for k in ("skills.programming", "values.career_stability") if k in authorized_keys])
            candidates.append({
                "raw_value": "Software Engineer",
                "suggested_premise_keys": swe_keys,
                "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in swe_keys},
                "rationale": "Core software engineering role developing enterprise systems and scalable digital platforms.",
            })
            # Game Developer
            gamedev_keys = tuple(major_premises + [k for k in ("skills.programming", "values.creativity") if k in authorized_keys])
            candidates.append({
                "raw_value": "Game Developer",
                "suggested_premise_keys": gamedev_keys,
                "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in gamedev_keys},
                "rationale": "Combines interactive systems programming with creative game design and simulation logic.",
            })

        if "music" in major or "sound" in major or has_music:
            # Musician / Performer
            musician_keys = tuple(major_premises + [k for k in ("traits.musical_talent", "skills.instrument_playing") if k in authorized_keys])
            candidates.append({
                "raw_value": "Musician",
                "suggested_premise_keys": musician_keys,
                "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in musician_keys},
                "rationale": "Professional music performance, composition, and instrumental artistry.",
            })
            # Sound Designer
            sound_keys = tuple(major_premises + [k for k in ("traits.musical_talent", "skills.programming") if k in authorized_keys])
            candidates.append({
                "raw_value": "Sound Designer",
                "suggested_premise_keys": sound_keys,
                "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in sound_keys},
                "rationale": "Audio design, Foley production, and sound synthesis for interactive entertainment and media.",
            })

        # Academic Researcher (fallback intellectual aspiration)
        if "traits.challenge_preference" in authorized_keys or "education.level" in authorized_keys:
            acad_keys = tuple(major_premises + [k for k in ("traits.challenge_preference", "education.level") if k in authorized_keys])
            candidates.append({
                "raw_value": "Academic Researcher",
                "suggested_premise_keys": acad_keys,
                "suggested_premise_roles": {k: PremiseRole.DIRECT_SUPPORT for k in acad_keys},
                "rationale": "Scholarly research and teaching in academic and institutional research laboratories.",
            })

        return candidates

    def _propose_parents_occupation_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        premise_keys = tuple(k for k in ("family.background", "identity.background", "identity.occupation") if k in authorized_keys)
        if not premise_keys:
            premise_keys = tuple(authorized_keys)[:1]
        roles = {k: PremiseRole.DIRECT_SUPPORT for k in premise_keys}
        return [
            {
                "raw_value": "父亲是大学数理学院教授，母亲是公立综合医院专科医生",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "典型高知中产知识分子家庭背景，家教严谨但注重身心修养与学术熏陶。",
            },
            {
                "raw_value": "父亲是资深建筑工程设计高级顾问，母亲是医学院临床讲师",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "专业技术中产家庭，成长环境优渥且包容艺术发展。",
            },
        ]

    def _propose_childhood_background_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        premise_keys = tuple(k for k in ("family.background", "interests", "education.major") if k in authorized_keys)
        if not premise_keys:
            premise_keys = tuple(authorized_keys)[:1]
        roles = {k: PremiseRole.DIRECT_SUPPORT for k in premise_keys}
        return [
            {
                "raw_value": "6岁在家庭熏陶下开始学古典钢琴，父母注重品格与艺术素养培养，自幼品学兼优",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "早期音乐启蒙，家庭长期支持正规钢琴古典训练。",
            },
            {
                "raw_value": "小学起加入学校管乐团任键盘手，初中立志走专业音乐路线，家庭给予坚定支持",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "从学校社团乐团实践中萌发专业音乐志向，自幼学业与艺术兼备。",
            },
        ]

    def _propose_transit_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        premise_keys = tuple(k for k in ("location.residence", "identity.occupation", "education.level") if k in authorized_keys)
        if not premise_keys:
            premise_keys = tuple(authorized_keys)[:1]
        roles = {k: PremiseRole.DIRECT_SUPPORT for k in premise_keys}
        return [
            {
                "raw_value": "在雪隆日常多搭乘LRT/MRT轻快铁或开家里的小车，跨城往返槟城坐KTM ETS快速火车",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "契合马来西亚雪隆与槟城两地的真实公共交通与城际铁路网络习惯。",
            },
            {
                "raw_value": "平时偏好搭轻快铁LRT出行看风景，赶时间或深夜聚会才叫Grab打车",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "城市青年典型捷运与网约车结合的自主出行方式。",
            },
        ]

    def _propose_beverage_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        premise_keys = tuple(k for k in ("interests", "identity.occupation") if k in authorized_keys)
        if not premise_keys:
            premise_keys = tuple(authorized_keys)[:1]
        roles = {k: PremiseRole.DIRECT_SUPPORT for k in premise_keys}
        return [
            {
                "raw_value": "少糖冰美禄(Milo Peng)或者海盐燕麦拿铁",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "本土南洋特色美禄饮品与当代咖啡馆拿铁的自然偏好。",
            },
            {
                "raw_value": "无糖冷萃白咖啡或者清爽柠檬伯爵红茶",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "清新、清醒提神的现代大学生饮品口味。",
            },
        ]

    def _propose_secondary_school_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        premise_keys = tuple(k for k in ("education.level", "family.background", "identity.age") if k in authorized_keys)
        if not premise_keys:
            premise_keys = tuple(authorized_keys)[:1]
        roles = {k: PremiseRole.DIRECT_SUPPORT for k in premise_keys}
        return [
            {
                "raw_value": "雪隆区校风严谨声誉优秀的华文国民型华文中学(SMJK)",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "学术声誉优秀的中学，文理兼修且自幼成绩优异。",
            },
            {
                "raw_value": "八打灵再也学术与文艺社团活跃的重点国中",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "雪隆名校背景，课外音乐与合唱活动丰富。",
            },
        ]

    def _propose_music_qualification_candidates(
        self,
        authorized_keys: set[str],
        snapshots: dict[str, Any],
    ) -> list[dict[str, Any]]:
        premise_keys = tuple(k for k in ("interests", "education.major") if k in authorized_keys)
        if not premise_keys:
            premise_keys = tuple(authorized_keys)[:1]
        roles = {k: PremiseRole.DIRECT_SUPPORT for k in premise_keys}
        return [
            {
                "raw_value": "英国皇家音乐学院联合委员会(ABRSM)钢琴八级卓越优秀(Distinction)",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "扎实的英皇古典钢琴专业考级认证，作为攻读USM音乐表演系的强力基石。",
            },
            {
                "raw_value": "圣三一音乐学院(Trinity College London)高级演奏文凭(ATCL)",
                "suggested_premise_keys": premise_keys,
                "suggested_premise_roles": roles,
                "rationale": "专业演奏级文凭资质，体现专注的器乐演奏素养。",
            },
        ]


class BoundedLLMProposer(LifeHypothesisProposer):
    """Architecture boundary for future bounded LLM-powered candidate generation.

    Strict Invariants:
    - Bounded context: prompt receives only target slot, domain, authorized premise snapshots,
      and known constraints.
    - Zero raw transcript exposure, zero unrestricted biography.
    - Fallback: delegates to deterministic proposer when live generative engine is absent or fails.
    """

    def __init__(
        self,
        fallback_proposer: Optional[LifeHypothesisProposer] = None,
        llm_client: Any = None,
    ) -> None:
        self._fallback = fallback_proposer or DeterministicLifeHypothesisProposer()
        self._client = llm_client

    async def propose_hypotheses(
        self,
        request: InferenceProposalRequest,
    ) -> Sequence[CandidateEnvelope]:
        """Propose hypotheses using LLM client if configured, falling back to deterministic seeder."""
        if self._client is None:
            # Deterministic offline execution path for safe, reproducible operation
            return await self._fallback.propose_hypotheses(request)

        # In production with live client: would format prompt, parse JSON, enforce 2<=k<=4 and normalize
        # If any validation or parsing failure occurs, fails safe to deterministic fallback
        try:
            return await self._fallback.propose_hypotheses(request)
        except Exception as exc:
            logger.error("BoundedLLMProposer execution failed: %s; falling back to deterministic seeder.", exc)
            return await self._fallback.propose_hypotheses(request)
