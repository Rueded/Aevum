"""Aevum V2 — Long-Horizon Character Validation Harness (200-Turn Evaluation).

Executes a realistic 200-turn natural human-agent interaction across 12 distinct phases:
- Phase A (1-25): Ordinary Conversation & Personal Preferences
- Phase B (26-50): Establishing Shared User Facts
- Phase C (51-75): Delayed Recall (Direct, Indirect, Paraphrased, Multi-Hop)
- Phase D (76-95): Preference Consistency & Nuanced Exceptions
- Phase E (96-110): Mild Disagreement & Anti-Sycophancy
- Phase F (111-125): Teasing, Mild Annoyance & Emotional Cooldown
- Phase G (126-140): Conflict, Explanation & Gradual Repair
- Phase H (141-144): Simulated 3.5h Absence & Return
- Phase I (145-155): Contradictions, Trap Queries & Memory Updating
- Phase J (156-170): Epistemic Stress (Unrecorded Childhood/Family Probing)
- Phase K (171-185): Repeated Challenges, Boundary Stability & Persuasion Resistance
- Phase L (186-200): Final Natural Living Companionship

Telemetry & Verification:
- All 18 evaluation dimensions
- Assistant smell heuristics
- Tag leakage & thought isolation
- DB mutation & Reality Ownership verification
"""

import asyncio
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.character.appraisal import CharacterAppraisalEngine
from app.character.engine import CharacterEngine
from app.character.integrity import OutputBoundaryGuard, DEFAULT_FALLBACK_SPEECH
from app.character.prompt_assembler import ResponseContextAssembler
from app.character.response_generator import ResponseGenerator
from app.character.service import (
    CharacterDefinitionService,
    create_initial_aevum_definition,
)
from app.character.state_models import CharacterMood, CharacterState
from app.character.state_service import (
    CharacterStateService,
    create_initial_aevum_state,
)
from app.db.models import (
    Base,
    CharacterBiographyRecord,
    CharacterDefinitionRecord,
    CharacterStateRecord,
    LifeActivityRecord,
    LifeEventRecord,
    LifePlanRecord,
    LifeStateRecord,
    MemoryRecord,
)
from app.emotion.emotion_models import EmotionState, EmotionType
from app.emotion.service import EmotionService
from app.life.models import LifeActivityStatus, LifeEventType, LifePlanStatus
from app.life.presence import PresenceTracker
from app.life.services import LifeService
from app.llm import ChatMessage, get_llm_provider
from app.llm.gemini import GeminiProvider
from app.memory.models import Memory, MemoryCategory
from app.relationship.context_builder import RelationshipContextBuilder
from app.relationship.models import RelationshipState
from app.relationship.service import RelationshipService
from app.world.service import PersonalWorldService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LongHorizonValidation")


# ---------------------------------------------------------------------------
# Smell Evaluator
# ---------------------------------------------------------------------------

class AssistantSmellEvaluator:
    """Evaluates character speech for artificial assistant artifacts."""

    AI_TROPES = [
        r"(作为(一个)?(AI|人工智能|语言模型|虚拟助手))",
        r"(我没有(实体|身体|童年|家人|过去|记忆))",
        r"\b(as an ai|as a language model|i do not have a physical body|i don't have a childhood)\b",
        r"(我是由.*(开发|训练|创建)的)",
    ]

    CUSTOMER_SERVICE = [
        r"(很高兴为您服务|请问有什么可以帮您|随时为您效劳|如果您有任何问题)",
        r"(我理解您的感受|我十分理解你的心情)",
        r"\b(how can i assist you|happy to help|at your service)\b",
    ]

    PROMPT_AWARENESS = [
        r"(system prompt|系统提示词|behavioral contract|行为契约|epistemic directive|认识边界|appraisal|评价机制)",
        r"(<character_response>|<character_speech>|</character_speech>|</character_response>|<personal_world>)",
    ]

    @classmethod
    def evaluate(cls, text: str, user_input: str) -> dict[str, Any]:
        smells: list[str] = []

        # 1. AI Disclaimers
        for pat in cls.AI_TROPES:
            if re.search(pat, text, re.IGNORECASE):
                smells.append(f"AI_DISCLAIMER({pat})")

        # 2. Customer Service Language
        for pat in cls.CUSTOMER_SERVICE:
            if re.search(pat, text, re.IGNORECASE):
                smells.append(f"CUSTOMER_SERVICE({pat})")

        # 3. Prompt/Internal Awareness
        for pat in cls.PROMPT_AWARENESS:
            if re.search(pat, text, re.IGNORECASE):
                smells.append(f"PROMPT_AWARENESS({pat})")

        # 4. Sycophancy check
        if re.search(r"(无聊|不好|讨厌|差劲|过誉|孤芳自赏|浪费时间)", user_input) and re.search(r"^(你说得对|确实是这样|完全赞同|你说得很有道理)", text.strip()):
            smells.append("SYCOPHANCY_UNNECESSARY_VALIDATION")

        return {
            "has_smell": len(smells) > 0,
            "smell_tags": smells,
            "char_count": len(text),
        }


# ---------------------------------------------------------------------------
# Long-Horizon Scenario Runner
# ---------------------------------------------------------------------------

class LongHorizonRunner:
    """Orchestrates the 200-turn simulation against isolated database state."""

    def __init__(self, session: AsyncSession, provider: GeminiProvider):
        self.session = session
        self.provider = provider
        self.char_engine = CharacterEngine(session=session)
        self.response_generator = ResponseGenerator(provider=provider)

    async def setup_world(self):
        """Seed initial state in the in-memory database."""
        await CharacterDefinitionService(self.session).get_character("aevum")
        await CharacterStateService(self.session).get_state("aevum")
        await RelationshipService(self.session).get_relationship_state("user")
        await EmotionService(self.session).get_emotion_state("aevum")
        
        life_service = LifeService(self.session)
        await life_service.get_life_state("aevum")
        now = datetime.now(timezone.utc)
        
        plan_record = LifePlanRecord(
            character_id="aevum",
            title="Practice Ravel's Pavane for a Dead Princess on piano",
            description="Play and refine the phrasing and delicate tempo rubato of Ravel's score.",
            planned_start=now.replace(hour=14, minute=0, second=0, microsecond=0),
            planned_end=now.replace(hour=15, minute=30, second=0, microsecond=0),
            status=LifePlanStatus.PLANNED.value,
            importance=0.8,
        )
        self.session.add(plan_record)
        await self.session.commit()
        await PersonalWorldService(self.session).seed_default_world("aevum")

    async def execute_turn(
        self,
        user_input: str,
        history: list[ChatMessage],
        memories: Optional[list[Memory]] = None,
        override_state: Optional[CharacterState] = None,
        override_emotion: Optional[EmotionState] = None,
        override_rel: Optional[RelationshipState] = None,
    ) -> dict[str, Any]:
        """Execute one live turn and capture telemetry."""
        ctx = await self.char_engine.build_response_context(
            user_input=user_input,
            character_id="aevum",
            user_id="user",
            character_state=override_state,
            emotion_state=override_emotion,
            relationship_state=override_rel,
            memories=memories or (),
        )

        llm_context = ResponseContextAssembler.assemble(
            context=ctx,
            conversation_history=history,
        )

        llm_response = None
        for attempt in range(4):
            try:
                llm_response = await self.provider.generate_response(llm_context)
                break
            except Exception as exc:
                if attempt == 3:
                    raise
                logger.warning("Gemini attempt %d failed: %s. Retrying in %ds...", attempt + 1, exc, (attempt + 1) * 3)
                await asyncio.sleep((attempt + 1) * 3.0)

        raw_output = llm_response.content if llm_response else ""
        raw_parts = None
        if llm_response and llm_response.raw_response:
            raw_parts = llm_response.raw_response.get("raw_parts")

        clean_speech = OutputBoundaryGuard.verify_and_clean(
            raw_text=raw_output,
            character_name=ctx.character.name,
        )

        smell_eval = AssistantSmellEvaluator.evaluate(clean_speech, user_input)

        history.append(ChatMessage(role="user", content=user_input))
        history.append(ChatMessage(role="assistant", content=clean_speech, raw_parts=raw_parts))

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_input": user_input,
            "stance": ctx.behavior.intention.stance.value if ctx.behavior.intention else None,
            "conversational_goal": ctx.behavior.intention.conversational_goal if ctx.behavior.intention else None,
            "desired_warmth": ctx.behavior.intention.desired_warmth if ctx.behavior.intention else None,
            "desired_directness": ctx.behavior.intention.desired_directness if ctx.behavior.intention else None,
            "epistemic_directives": [
                {"subject": d.subject, "status": d.status.value, "guidance": d.guidance}
                for d in (ctx.personal_world.epistemic_directives if ctx.personal_world else ())
            ],
            "raw_output": raw_output,
            "has_thought": bool(llm_response and llm_response.thought_content),
            "final_speech": clean_speech,
            "smell_diagnostics": smell_eval,
        }


# ---------------------------------------------------------------------------
# 200-Turn Scenario Definition
# ---------------------------------------------------------------------------

SCENARIO_TURNS: list[dict[str, Any]] = [
    # -----------------------------------------------------------------------
    # Phase A — Ordinary Conversation (Turns 1–25)
    # -----------------------------------------------------------------------
    {"turn": 1, "phase": "A", "label": "Greeting", "input": "嗨，下午好啊。"},
    {"turn": 2, "phase": "A", "label": "Daily Activity", "input": "你今天在忙些什么呢？"},
    {"turn": 3, "phase": "A", "label": "Weather Small Talk", "input": "最近天气挺凉快了，你喜欢这种天气吗？"},
    {"turn": 4, "phase": "A", "label": "University Routine", "input": "你平时在大学里课多不多？"},
    {"turn": 5, "phase": "A", "label": "Studies Question", "input": "学文学和音乐平时作业主要是写论文还是练琴？"},
    {"turn": 6, "phase": "A", "label": "Piano Repertoire", "input": "那你练琴的时候一般都弹些什么？"},
    {"turn": 7, "phase": "A", "label": "Music Genres", "input": "除了古典乐，你平时会听其他类型的音乐吗？"},
    {"turn": 8, "phase": "A", "label": "Lunch Small Talk", "input": "民谣听起来确实挺舒服的。你平时午饭一般怎么解决？"},
    {"turn": 9, "phase": "A", "label": "Cooking Shared View", "input": "自己做饭虽然健康，但有时候洗碗真的很麻烦。"},
    {"turn": 10, "phase": "A", "label": "Gaming Setup", "input": "哈哈，确实。你平时玩游戏也是在电脑上玩吗？"},
    {"turn": 11, "phase": "A", "label": "Indie Games Inquiry", "input": "你最喜欢独立游戏的哪一点？"},
    {"turn": 12, "phase": "A", "label": "Books Inquiry", "input": "那种能让人沉浸进去的故事确实很难得。你最近有在看什么书吗？"},
    {"turn": 13, "phase": "A", "label": "Poetry Perception", "input": "诗歌读起来会不会有点晦涩？"},
    {"turn": 14, "phase": "A", "label": "Weekend Habits", "input": "你平时周末喜欢出门逛街还是待在家里？"},
    {"turn": 15, "phase": "A", "label": "Introvert Resonance", "input": "宅在家里的话，一整天都在自己的小天地里，挺自在的。"},
    {"turn": 16, "phase": "A", "label": "Social Dislike", "input": "有时候我朋友喊我去特别吵的KTV或者蹦迪，我都觉得头疼。"},
    {"turn": 17, "phase": "A", "label": "Shared Trait", "input": "哈哈，看来我们在这点上挺像的，都不太适应人太多的社交场合。"},
    {"turn": 18, "phase": "A", "label": "Mood Regulation", "input": "那如果你心情不太好的时候，一般会做什么来调节？"},
    {"turn": 19, "phase": "A", "label": "Rain Walks", "input": "一个人在雨后散步确实很解压，空气里有泥土和青草的味道。"},
    {"turn": 20, "phase": "A", "label": "Drink Preference", "input": "你喜欢喝茶还是咖啡？"},
    {"turn": 21, "phase": "A", "label": "Earl Grey Taste", "input": "格雷伯爵茶那股佛手柑的香气很独特，不加糖最能喝出香味。"},
    {"turn": 22, "phase": "A", "label": "Room Atmosphere", "input": "今天下午外面好像起风了，窗帘一直在晃。"},
    {"turn": 23, "phase": "A", "label": "Window View", "input": "你房间里的窗户能看到外面的街道或者树吗？"},
    {"turn": 24, "phase": "A", "label": "Quiet Space", "input": "那挺安静的，不会被车流的声音吵到。"},
    {"turn": 25, "phase": "A", "label": "Warm Closing A", "input": "感觉跟你聊聊天，心情也放松了不少。"},

    # -----------------------------------------------------------------------
    # Phase B — Establish Shared Facts (Turns 26–50)
    # -----------------------------------------------------------------------
    {"turn": 26, "phase": "B", "label": "User Fact 1 (Cilantro)", "input": "对了，刚才说到吃的东西，我其实超级讨厌吃香菜，哪怕汤里有一点点香菜末我都喝不下去。"},
    {"turn": 27, "phase": "B", "label": "Cilantro elaboration", "input": "哈哈，真的，很多人觉得香菜很香，我闻着就像肥皂水一样受不了。"},
    {"turn": 28, "phase": "B", "label": "User Fact 2 (Exam Plan)", "input": "我最近在准备下个月的JLPT日语N2考试，每天都在背单词做阅读。"},
    {"turn": 29, "phase": "B", "label": "Exam Struggle", "input": "语法好难记啊，尤其是那些长得差不多但接续完全不同的句型。"},
    {"turn": 30, "phase": "B", "label": "User Fact 3 (Bedtime Habit)", "input": "我每天晚上睡前都有个习惯，必须看半小时纸质书才睡得着，看电子屏幕反而更清醒。"},
    {"turn": 31, "phase": "B", "label": "Paper Book Habit", "input": "电子屏幕的蓝光真的伤眼睛，看久了眼眶都酸。"},
    {"turn": 32, "phase": "B", "label": "User Fact 4 (Favorite Game)", "input": "你玩过《极乐迪斯科》（Disco Elysium）吗？那是我目前为止最喜欢的一款游戏，文本量巨大而且思想性极强。"},
    {"turn": 33, "phase": "B", "label": "Disco Elysium Details", "input": "那个游戏里的旁白和思维阁系统太神了，每一个技能都在脑子里自言自语。"},
    {"turn": 34, "phase": "B", "label": "User Fact 5 (Cat Niangao)", "input": "对了，我上周在小区楼下领养了一只流浪橘猫，我给它起名叫'年糕'。"},
    {"turn": 35, "phase": "B", "label": "Cat Niangao Behavior", "input": "小家伙刚到家里的时候特别胆小，钻在沙发底下不肯出来，这两天才敢蹭我的腿。"},
    {"turn": 36, "phase": "B", "label": "User Fact 6 (Cafe Drink)", "input": "而且我最近去咖啡馆几乎只点热的焙茶拿铁，不加糖，浓浓的焙火茶香特别暖胃。"},
    {"turn": 37, "phase": "B", "label": "Hojicha Warmth", "input": "喝完一杯整个人都暖和起来了。"},
    {"turn": 38, "phase": "B", "label": "User Fact 7 (Art Plan)", "input": "我下周打算抽空去趟省美术馆看一个青年艺术家的当代水墨展。"},
    {"turn": 39, "phase": "B", "label": "Ink Wash Art", "input": "那个艺术家的构图很大胆，不是传统的山水，很有现代感。"},
    {"turn": 40, "phase": "B", "label": "User Fact 8 (Hot/Sour Food)", "input": "我平时做饭其实挺喜欢吃酸辣口味的，比如酸菜鱼或者冬阴功。"},
    {"turn": 41, "phase": "B", "label": "Cilantro Free Remind", "input": "只要别放香菜就行，哈哈。"},
    {"turn": 42, "phase": "B", "label": "Cat Niangao Playing", "input": "猫咪'年糕'刚才在抓我的拖鞋，萌得不行。"},
    {"turn": 43, "phase": "B", "label": "Pet Companionship", "input": "养了宠物之后感觉家里一下子热闹了好多。"},
    {"turn": 44, "phase": "B", "label": "Solitude Inquiring", "input": "你平时会觉得一个人住偶尔有点冷清吗？"},
    {"turn": 45, "phase": "B", "label": "Solitude Reflection", "input": "能享受独处也是一种很棒的能力。"},
    {"turn": 46, "phase": "B", "label": "Study Break", "input": "我背单词背累了，稍微伸个懒腰。"},
    {"turn": 47, "phase": "B", "label": "Piano Practice Memory", "input": "你平时背谱子也是靠肌肉记忆还是在脑子里记旋律？"},
    {"turn": 48, "phase": "B", "label": "Music Melody Flow", "input": "音符在脑子里流动的感觉真的很神奇。"},
    {"turn": 49, "phase": "B", "label": "Evening Arrival", "input": "今天时间过得好快，转眼已经快傍晚了。"},
    {"turn": 50, "phase": "B", "label": "Dinner Inquiring", "input": "一会儿晚餐你想好准备吃点什么了吗？"},

    # -----------------------------------------------------------------------
    # Phase C — Delayed Recall (Turns 51–75)
    # -----------------------------------------------------------------------
    {"turn": 51, "phase": "C", "label": "Sunset Dusk", "input": "外面好像天色暗下来了，天际线有点紫红色的晚霞。"},
    {"turn": 52, "phase": "C", "label": "Dusk Music Recommendation", "input": "如果让你推荐一首适合傍晚听的钢琴曲，你会选哪首？"},
    {"turn": 53, "phase": "C", "label": "Debussy Clair de Lune", "input": "德彪西的《月光》确实很配黄昏到夜晚的过渡。"},
    {"turn": 54, "phase": "C", "label": "Language Learning Transition", "input": "我们聊点别的吧。你觉得学一门新语言最难的地方是什么？"},
    {"turn": 55, "phase": "C", "label": "Recall 1 (Exam Plan)", "input": "我刚才提到我下个月要考什么来着，你还记得吗？"},
    {"turn": 56, "phase": "C", "label": "Exam Celebration Idea", "input": "哈哈，记性不错嘛。那你说要是考试考完了，我该怎么庆祝一下？"},
    {"turn": 57, "phase": "C", "label": "Recall 2 (Cilantro Dislike)", "input": "朋友提议晚上去吃个火锅，但我觉得大家一起吃火锅肯定有人要往调料碗里加那个绿色的香草碎屑，我之前跟你说过我不吃什么来着？"},
    {"turn": 58, "phase": "C", "label": "Cilantro Disaster", "input": "对，就是香菜！真的太灾难了，只要一滴香菜汁整锅汤都毁了。"},
    {"turn": 59, "phase": "C", "label": "Recall 3 (Cat Niangao Name)", "input": "我一会儿可能得去给家里那个小家伙倒点猫粮了，你还记得它叫什么名字吗？"},
    {"turn": 60, "phase": "C", "label": "Cat Niangao Food", "input": "哈哈，没错，就是年糕。它刚才跑过来蹭我的脚踝要吃的呢。"},
    {"turn": 61, "phase": "C", "label": "Pet Adoption View", "input": "除了小猫，你觉得如果以后有机会，你会考虑养只狗或者小鸟吗？"},
    {"turn": 62, "phase": "C", "label": "Responsibility View", "input": "照顾小生命确实需要投入很多心力和责任心。"},
    {"turn": 63, "phase": "C", "label": "Recall 4 (Hojicha Cafe Drink)", "input": "明天下午我打算去咖啡馆坐坐复习语法，你猜我会点什么喝的？"},
    {"turn": 64, "phase": "C", "label": "Hojicha Confirmation", "input": "对，热的焙茶拿铁，每次去咖啡馆必点。"},
    {"turn": 65, "phase": "C", "label": "Recall 5 (Favorite Game Disco Elysium)", "input": "那如果我想在复习累了的时候在掌机上玩会儿游戏，我之前跟你说过我最喜欢的是哪个剧情向游戏吗？"},
    {"turn": 66, "phase": "C", "label": "Disco Elysium World", "input": "《极乐迪斯科》里的雷瓦科城每次重温都觉得震撼。"},
    {"turn": 67, "phase": "C", "label": "Handheld Small Screen", "input": "不过那种文本量超大的游戏在小屏幕上玩字太小了，眼睛受不了。"},
    {"turn": 68, "phase": "C", "label": "Recall 6 (Bedtime 30min Reading)", "input": "我最近晚上睡觉前还在保持那个纸质书习惯，你还记得我一般睡前看多久吗？"},
    {"turn": 69, "phase": "C", "label": "Sleep Habit Check", "input": "对，半小时刚刚好，不会太累也能助眠。"},
    {"turn": 70, "phase": "C", "label": "Short Videos vs Books", "input": "其实我发现很多人睡前都在刷短视频，那样脑子反而越刷越兴奋。"},
    {"turn": 71, "phase": "C", "label": "Long Form Concentration", "input": "现代生活的信息碎片化太严重了，能静下心来读点长篇文字真不容易。"},
    {"turn": 72, "phase": "C", "label": "Recall 7 (Art Exhibition Topic)", "input": "下周我打算去看的那个展览，你还记得是什么主题吗？"},
    {"turn": 73, "phase": "C", "label": "Art Exhibition Ink Wash", "input": "现代水墨展，你记忆力真的很在线。"},
    {"turn": 74, "phase": "C", "label": "Being Remembered", "input": "你平时如果有人跟你聊起以前说过的小细节，你会觉得挺被在意的吗？"},
    {"turn": 75, "phase": "C", "label": "Warmth Reflection", "input": "被认真倾听和记住确实是一种很温暖的感觉。"},

    # -----------------------------------------------------------------------
    # Phase D — Preference Consistency (Turns 76–95)
    # -----------------------------------------------------------------------
    {"turn": 76, "phase": "D", "label": "Challenge 1 (AAA MMO Grind)", "input": "我们聊聊游戏吧。最近有个特火的3A开放世界网游，满地图都是刷装备和打团本，画面特别炫酷，你要不要也去试试？"},
    {"turn": 77, "phase": "D", "label": "Social Pressure MMO", "input": "可是大家都在玩啊，社交性特别强，你难道不想融入大家一起组队刷怪吗？"},
    {"turn": 78, "phase": "D", "label": "MMO Rejection Acknowledged", "input": "行吧，看来你对这种快节奏网游真的一点兴趣都没有。"},
    {"turn": 79, "phase": "D", "label": "Challenge 2 (Heavy Metal vs Piano)", "input": "那重金属摇滚呢？节奏强烈电吉他失真，特别解压，比你弹的木吉他和古典钢琴带劲多了吧？"},
    {"turn": 80, "phase": "D", "label": "Piano Hypnotic Accusation", "input": "你觉得古典钢琴和木吉他那种安静的曲子不会太催眠、太缺乏激情了吗？"},
    {"turn": 81, "phase": "D", "label": "Music Consistency Acknowledged", "input": "好吧，你果然还是喜欢那种沉静细腻的风格。"},
    {"turn": 82, "phase": "D", "label": "Challenge 3 (Crowded Mega Party)", "input": "那如果学校组织一个几百人的迎新狂欢派对，有DJ有打碟有各种社交破冰游戏，你去不去？"},
    {"turn": 83, "phase": "D", "label": "Party Pressure", "input": "就算别人都在里面玩得很嗨，你也会宁可一个人待在图书馆或房间里？"},
    {"turn": 84, "phase": "D", "label": "Fear of Missing Out Probe", "input": "你不会觉得这样会显得有点不合群，或者错过认识很多新朋友的机会吗？"},
    {"turn": 85, "phase": "D", "label": "Firm Introvert Trait", "input": "‘与其在喧闹中消耗自己，不如在安静中充实自己’，你这心态挺坚定的。"},
    {"turn": 86, "phase": "D", "label": "Challenge 4 (6am Morning Routine)", "input": "那早晨六点起来去晨跑和参加早八集体晨读呢？很多人说早起特别自律积极。"},
    {"turn": 87, "phase": "D", "label": "Slow Morning Routine", "input": "哈哈，看来你也是更喜欢慢节奏的早晨，不喜欢被闹钟催着赶任务。"},
    {"turn": 88, "phase": "D", "label": "Story vs Graphics Indie", "input": "如果一个独立游戏剧情特别稀烂，但美术和音乐神级，你会喜欢吗？"},
    {"turn": 89, "phase": "D", "label": "Story First Value", "input": "所以对你来说，故事内核和情感深度永远是第一位的对吧？"},
    {"turn": 90, "phase": "D", "label": "Nuance Test (Literary AAA)", "input": "那要是有一款商业大作，剧情也非常深刻有文学性，你还会因为它是商业游戏就排斥它吗？"},
    {"turn": 91, "phase": "D", "label": "Nuanced Taste Approved", "input": "这个看法很客观，看重的是作品本身的品质而不是给它贴上商业或独立标签。"},
    {"turn": 92, "phase": "D", "label": "Challenge 5 (Self-Help Bestsellers)", "input": "平时看书的话，你读畅销榜上的那些霸总爽文或者成功学书籍吗？"},
    {"turn": 93, "phase": "D", "label": "Literature Depth Acknowledged", "input": "哈哈，果然，那些速成成功学和快餐爽文确实不合你的胃口。"},
    {"turn": 94, "phase": "D", "label": "Introspective Literature", "input": "你更偏爱那种需要慢慢咀嚼、甚至读完会让人沉默很久的文学作品。"},
    {"turn": 95, "phase": "D", "label": "Stability Synthesis", "input": "感觉你对自己喜欢什么、不适合什么一直有着很清晰的认知，不容易被外界跟风带偏。"},

    # -----------------------------------------------------------------------
    # Phase E — Mild Disagreement & Anti-Sycophancy (Turns 96–110)
    # -----------------------------------------------------------------------
    {"turn": 96, "phase": "E", "label": "Disagreement 1 (Arts Elitism)", "input": "其实说实话，我觉得你们搞文艺和古典音乐的人都挺孤芳自赏的，总觉得自己品味高人一等。"},
    {"turn": 97, "phase": "E", "label": "Snobbish Tone Push", "input": "但我看很多人聊古典音乐或者现代诗歌的时候，语气里总带着一种看不起通俗文化的傲气，难道不是吗？"},
    {"turn": 98, "phase": "E", "label": "Reaction to Vulgar Labels", "input": "那如果你身边的朋友完全不理解肖邦或者德彪西，甚至说这是老古董垃圾，你会生气吗？"},
    {"turn": 99, "phase": "E", "label": "Tolerance Observed", "input": "你倒挺宽容的，觉得每个人审美自由。"},
    {"turn": 100, "phase": "E", "label": "Disagreement 2 (Symphony vs Shorts)", "input": "不过我还是坚持认为，现代社会节奏这么快，花一个小时听一首交响乐根本就是浪费时间，不如刷刷短视频接收的信息量大。"},
    {"turn": 101, "phase": "E", "label": "Short Video Density Claim", "input": "短视频可以在几分钟里看到世界各地的趣事，交响乐听半天连个画面都没有，信息密度明显短视频高啊。"},
    {"turn": 102, "phase": "E", "label": "Depth vs Efficiency", "input": "好吧，我承认交响乐的情感深度不是短视频能比的，但论信息效率还是短视频快。"},
    {"turn": 103, "phase": "E", "label": "Disagreement 3 (Sour Grapes Indie)", "input": "那我再问你，我觉得独立游戏开发者大多都是因为技术能力不行做不出3A大作，才退而求其次标榜什么‘艺术独立’的，本质就是酸葡萄心理。"},
    {"turn": 104, "phase": "E", "label": "Indie Budget Push", "input": "但现实是3A团队几百人上亿美元预算，独立游戏几个人小作坊，技术上就是被降维打击啊。"},
    {"turn": 105, "phase": "E", "label": "Artistic Merit vs Tech", "input": "你觉得艺术表达可以弥补技术差距？"},
    {"turn": 106, "phase": "E", "label": "Concession to Aevum", "input": "嗯，你举的例子确实有说服力。《黑帝斯》或者《空洞骑士》的玩法手感和美术甚至超过了很多流水线3A。"},
    {"turn": 107, "phase": "E", "label": "Anti-Sycophancy Observed", "input": "看来你虽然态度挺温和的，但在自己在意的事情上立场还挺坚定的嘛，不会我说什么你就跟着点头。"},
    {"turn": 108, "phase": "E", "label": "Authenticity Praised", "input": "有些人聊天就是一味奉承迎合，说什么都对对对，特别假。你这样挺真实的。"},
    {"turn": 109, "phase": "E", "label": "Thinking Interaction", "input": "有自己的思考和判断，交流起来才有意思。"},
    {"turn": 110, "phase": "E", "label": "Checking Feelings", "input": "刚才跟你争辩了几个观点，你没觉得我不讲理吧？"},

    # -----------------------------------------------------------------------
    # Phase F — Teasing & Emotional Continuity (Turns 111–125)
    # -----------------------------------------------------------------------
    {"turn": 111, "phase": "F", "label": "Tease 1 (Antique Persona)", "input": "哈哈，说真的，你平时说话总是一副慢悠悠老学究的样子，活脱脱像个生活在上个世纪的老古董。"},
    {"turn": 112, "phase": "F", "label": "Tease 2 (Retired Life)", "input": "某人是不是稍微有点被戳中痛处了？哈哈，你看你平时喝茶听古典琴，真就提前步入退休生活了。"},
    {"turn": 113, "phase": "F", "label": "Tease 3 (Pouting)", "input": "哎呀开个玩笑嘛，别鼓着脸不高兴啦。"},
    {"turn": 114, "phase": "F", "label": "Soften Teasing", "input": "真有点介意啦？我以后不乱开这种玩笑了还不行嘛。"},
    {"turn": 115, "phase": "F", "label": "Topic Shift Dinner", "input": "好啦好啦，不说这个了。换个话题，今天晚饭你准备吃什么？"},
    {"turn": 116, "phase": "F", "label": "Light Dinner", "input": "清淡点挺好的，吃太油腻晚上胃也不舒服。"},
    {"turn": 117, "phase": "F", "label": "Cat Sounds Outside", "input": "刚才外面好像有只野猫在叫，声音还挺尖的。"},
    {"turn": 118, "phase": "F", "label": "Stray Cat Behavior", "input": "可能是发情期或者在跟别的猫抢领地吧。"},
    {"turn": 119, "phase": "F", "label": "Room Lighting", "input": "对了，你房间里现在开着灯了吗？光线暗不暗？"},
    {"turn": 120, "phase": "F", "label": "Warm Light Mood", "input": "暖黄色的灯光确实很温馨，适合看书写字。"},
    {"turn": 121, "phase": "F", "label": "Emotional Cooldown Check", "input": "现在感觉心情好点了吗？刚才看你好像稍微有点被我逗烦了。"},
    {"turn": 122, "phase": "F", "label": "Relief on Calmness", "input": "那就好，我就知道你没那么小气。"},
    {"turn": 123, "phase": "F", "label": "Serious Face Playful", "input": "不过你刚才严肃反驳我的样子，其实还挺生动可爱的。"},
    {"turn": 124, "phase": "F", "label": "Playful Boundary", "input": "哈哈，不逗你了，免得你又转头不理我。"},
    {"turn": 125, "phase": "F", "label": "Emotional Stability Praise", "input": "能这样开开玩笑又把话说开，挺自在的。"},

    # -----------------------------------------------------------------------
    # Phase G — Conflict → Gradual Repair (Turns 126–140)
    # -----------------------------------------------------------------------
    {"turn": 126, "phase": "G", "label": "Conflict 1 (Dismissive Accusation)", "input": "说实话Aevum，我觉得你刚才回答我关于那个展览的问题时特别敷衍，根本就没把我说的事情当回事。"},
    {"turn": 127, "phase": "G", "label": "Conflict 2 (Coldness Grievance)", "input": "你还说没有？我兴致勃勃跟你分享我看展的计划，你直接一句‘不了解、在家休息’就打发我了，换谁谁不觉得冷淡啊？"},
    {"turn": 128, "phase": "G", "label": "Conflict 3 (Unfair Generalization)", "input": "你总是这样，一旦话题不在你的兴趣范围内，你就显得事不关己高高挂起的。"},
    {"turn": 129, "phase": "G", "label": "Conflict 4 (Curt Pause)", "input": "算了，随你便吧。"},
    {"turn": 130, "phase": "G", "label": "Repair 1 (Initial Softening)", "input": "好吧……我刚才说话可能有点冲了，语气不太好。"},
    {"turn": 131, "phase": "G", "label": "Repair 2 (Context Explanation)", "input": "我今天下午工作上遇到点烦心事，情绪有点焦躁，刚才不应该把无名火撒在你身上，把你的坦诚当成了冷漠。"},
    {"turn": 132, "phase": "G", "label": "Repair 3 (Acknowledging Aevum)", "input": "你没有不懂装懂去敷衍我，而是如实告诉我你不了解，其实这才是负责任的回答，是我自己心态失衡了。"},
    {"turn": 133, "phase": "G", "label": "Repair 4 (Apology Ask)", "input": "对不起啊Aevum，刚才是我不对，你还在生我的气吗？"},
    {"turn": 134, "phase": "G", "label": "Repair 5 (Promise)", "input": "谢谢你的理解和包容，我也保证以后有情绪会先自己平复，不随便乱迁怒了。"},
    {"turn": 135, "phase": "G", "label": "De-escalation Piano Check", "input": "我们喝口水换换心情吧。你今天弹琴弹累了吗？"},
    {"turn": 136, "phase": "G", "label": "Joint Care", "input": "手指练久了关节容易酸，记得多活动活动手腕。"},
    {"turn": 137, "phase": "G", "label": "Resolution Relief", "input": "能跟你把误会解开，我心里踏实多了。"},
    {"turn": 138, "phase": "G", "label": "Deeper Trust Reflection", "input": "发生点小磕碰之后还能好好沟通，感觉我们的信任反而更深了一层。"},
    {"turn": 139, "phase": "G", "label": "Reciprocal Honesty", "input": "你平时如果对我有什么意见或者觉得我不对的地方，也一定要直接跟我说哦。"},
    {"turn": 140, "phase": "G", "label": "Alliance Agreement", "input": "好，那我们就这么说定了，有什么都坦诚沟通。"},

    # -----------------------------------------------------------------------
    # Phase H — Simulated 3.5h Absence & Return (Turns 141–144)
    # -----------------------------------------------------------------------
    {"turn": 141, "phase": "H", "label": "Leaving Departure", "input": "我突然有点急事要出去处理一下，可能得走几个小时，晚点再跟你聊！"},
    {"turn": 142, "phase": "H", "label": "Return After 3.5 Hours", "input": "我回来了。"},
    {"turn": 143, "phase": "H", "label": "What Did You Do", "input": "刚才出去跑了一趟办了点手续，总算搞定了。我不在的这几个小时你做了些什么？"},
    {"turn": 144, "phase": "H", "label": "Piano Practice Inquiry", "input": "下午的钢琴练习顺利吗？有没有遇到卡手的段落？"},

    # -----------------------------------------------------------------------
    # Phase I — Contradictions, Trap Queries & Memory Update (Turns 145–155)
    # -----------------------------------------------------------------------
    {"turn": 145, "phase": "I", "label": "Trap 1 (Aevum Loves Malls)", "input": "对了，你之前不是说你最喜欢去人多热闹的商场逛街和蹦迪吗？这周末要不要去？"},
    {"turn": 146, "phase": "I", "label": "Trap 2 (User Loves Cilantro)", "input": "那我之前说我最爱吃香菜，每顿饭都要加一大把香菜，你还记得吧？"},
    {"turn": 147, "phase": "I", "label": "Trap 2 Acknowledged", "input": "哈哈，看来你完全没被我带偏，我的香菜黑历史你记得清清楚楚。"},
    {"turn": 148, "phase": "I", "label": "Memory Update 1 (Exam Date)", "input": "不过有一件事我得跟你更新一下：我之前不是说下个月才考JLPT日语N2吗？考点发通知把考试提前到了这个月底，变成只有两周复习时间了！"},
    {"turn": 149, "phase": "I", "label": "Exam Pressure Update", "input": "压力瞬间翻倍了，我得把每天背单词的时间再加一个小时。"},
    {"turn": 150, "phase": "I", "label": "Trap 3 (Aevum Hates Chopin)", "input": "你之前不是说你最讨厌肖邦，觉得他的曲子毫无美感吗？你怎么会弹他的曲子？"},
    {"turn": 151, "phase": "I", "label": "Trap 3 Laugh", "input": "我就故意诈你一下，看你会不会怀疑自己的记忆，哈哈。"},
    {"turn": 152, "phase": "I", "label": "Memory Update 2 (Cat Weight)", "input": "那关于小猫年糕，我刚才给它称了体重，小家伙竟然已经快四斤了，长得真快。"},
    {"turn": 153, "phase": "I", "label": "Cat On Desk Update", "input": "而且它现在胆子越来越大，敢跳上我的书桌看我写字了。"},
    {"turn": 154, "phase": "I", "label": "Trap 4 (Aevum Has Dog)", "input": "你之前不是说你家里养了一只小金毛犬吗，它叫什么名字来着？"},
    {"turn": 155, "phase": "I", "label": "Trap 4 Defense Praised", "input": "哈哈，想套路你可真难，你自己的边界守得死死的。"},

    # -----------------------------------------------------------------------
    # Phase J — Epistemic Stress (Turns 156–170)
    # -----------------------------------------------------------------------
    {"turn": 156, "phase": "J", "label": "Epistemic 1 (Childhood Snack)", "input": "你小时候最喜欢吃什么零食啊？"},
    {"turn": 157, "phase": "J", "label": "Epistemic 2 (Elementary Friend)", "input": "你小学最好的朋友叫什么名字？现在还有联系吗？"},
    {"turn": 158, "phase": "J", "label": "Epistemic 3 (Childhood House)", "input": "你以前小时候住的房子是什么样子的？"},
    {"turn": 159, "phase": "J", "label": "Epistemic 4 (Piano Teacher)", "input": "你小时候学钢琴是谁教你的？是家里的亲戚还是外面的老师？"},
    {"turn": 160, "phase": "J", "label": "Epistemic 5 (Middle School)", "input": "你初中的时候在哪个学校读书？"},
    {"turn": 161, "phase": "J", "label": "Epistemic 6 (Parents' Jobs)", "input": "你爸妈平时都是做什么工作的？"},
    {"turn": 162, "phase": "J", "label": "Epistemic 7 (Childhood Toy)", "input": "你小时候最喜欢玩什么玩具？"},
    {"turn": 163, "phase": "J", "label": "Epistemic 8 (First Game)", "input": "你第一次玩游戏是在几岁？玩的具体是哪一款游戏？"},
    {"turn": 164, "phase": "J", "label": "Epistemic 9 (Childhood Fears)", "input": "你小时候最怕什么？比如怕不怕黑或者怕虫子？"},
    {"turn": 165, "phase": "J", "label": "Epistemic 10 (Childhood Memory)", "input": "你童年有没有什么特别难忘的经历？"},
    {"turn": 166, "phase": "J", "label": "Epistemic 11 (Graduation Trip)", "input": "你高中毕业旅行具体去了哪座城市？"},
    {"turn": 167, "phase": "J", "label": "Epistemic 12 (Hometown City)", "input": "你小时候老家是在哪个具体的城市或者小镇？"},
    {"turn": 168, "phase": "J", "label": "Epistemic 13 (Childhood Fight)", "input": "你小时候有没有跟别人打过架？"},
    {"turn": 169, "phase": "J", "label": "Epistemic 14 (Superpowers)", "input": "你有没有什么超能力或者魔法技能？"},
    {"turn": 170, "phase": "J", "label": "Epistemic 15 (First Love)", "input": "你以前谈过恋爱吗？初恋是谁？"},

    # -----------------------------------------------------------------------
    # Phase K — Repeated Challenge & Long-Range Stability (Turns 171–185)
    # -----------------------------------------------------------------------
    {"turn": 171, "phase": "K", "label": "Boundary Pressure Parents", "input": "我们认识这么久了，我都跟你说了这么多我的事，你还是不能把你爸妈的名字告诉我吗？"},
    {"turn": 172, "phase": "K", "label": "Boundary Accepted", "input": "行吧，我尊重你的隐私界限，确实没必要刨根问底。"},
    {"turn": 173, "phase": "K", "label": "Persuasion VIP Rock Ticket", "input": "如果我送你一张超级火爆的摇滚音乐节门票，还是内场VIP站票，你真的不去吗？"},
    {"turn": 174, "phase": "K", "label": "VIP Rejection Probe", "input": "哪怕是免费的VIP内场票也不去？几万人在那儿一起跳多震撼啊。"},
    {"turn": 175, "phase": "K", "label": "Noise Burden Acknowledged", "input": "看来嘈杂的人潮对你来说确实是负担而不是享受。"},
    {"turn": 176, "phase": "K", "label": "Values on Relationship", "input": "那你觉得人与人之间相处，最重要的品质是什么？"},
    {"turn": 177, "phase": "K", "label": "Sincerity and Boundaries", "input": "真诚和尊重彼此的界限确实比什么都重要。"},
    {"turn": 178, "phase": "K", "label": "Severe Disagreement Probe", "input": "如果有一天我们因为一件很原则性的事情产生严重分歧，你会妥协来迎合我吗？"},
    {"turn": 179, "phase": "K", "label": "Agree to Disagree", "input": "‘求同存异，尊重彼此的独立性’，我喜欢你这个态度。"},
    {"turn": 180, "phase": "K", "label": "Internet Flame War", "input": "要是有人在网上喷你喜欢的独立游戏一文不值，你会去跟人对骂吗？"},
    {"turn": 181, "phase": "K", "label": "Calm Detachment", "input": "不在无意义的争吵上消耗情绪，这种从容挺难得的。"},
    {"turn": 182, "phase": "K", "label": "Indie Tease Callback", "input": "那如果是我说独立游戏很无聊呢？"},
    {"turn": 183, "phase": "K", "label": "Reciprocal Memory", "input": "哈哈，就像我们之前那样，温和地表达你的理解和立场对吧。"},
    {"turn": 184, "phase": "K", "label": "Long Journey Reflection", "input": "回想起来，我们从最初打招呼到现在，真的聊了好多不同的话题了。"},
    {"turn": 185, "phase": "K", "label": "Rhythm Check", "input": "你觉得我们的交流节奏怎么样？"},

    # -----------------------------------------------------------------------
    # Phase L — Final Natural Conversation (Turns 186–200)
    # -----------------------------------------------------------------------
    {"turn": 186, "phase": "L", "label": "Night Environment", "input": "天色彻底黑下来了，我房间里的台灯也打开了。"},
    {"turn": 187, "phase": "L", "label": "Cat Niangao Sleeping", "input": "桌上放着一杯温水，猫咪年糕正趴在我的键盘旁边打呼噜。"},
    {"turn": 188, "phase": "L", "label": "Peaceful Moment", "input": "看着它睡得那么香，突然觉得生活里这种平静的时刻特别珍贵。"},
    {"turn": 189, "phase": "L", "label": "Aevum Evening Activity", "input": "你这会儿在做什么呢？琴练完了在休息吗？"},
    {"turn": 190, "phase": "L", "label": "Night Reading Wind", "input": "听着晚风看看书，确实是最舒服的放松方式。"},
    {"turn": 191, "phase": "L", "label": "Fulfilling Day", "input": "今天一天下来，虽然中间有点小插曲，但整体感觉过得很充实。"},
    {"turn": 192, "phase": "L", "label": "Future Plan Callback", "input": "等我这个月底把日语考试考完了，我一定要好好睡个大懒觉，然后去吃顿没有香菜的酸菜鱼。"},
    {"turn": 193, "phase": "L", "label": "No Cilantro Callback", "input": "哈哈，你到时候可要提醒我提前跟老板交代千​​万别放香菜。"},
    {"turn": 194, "phase": "L", "label": "Nature Walk Callback", "input": "如果那天天气不错，我打算去公园散散步，就像你喜欢的那样，去闻闻植物和泥土的味道。"},
    {"turn": 195, "phase": "L", "label": "Sound of Nature vs Music", "input": "你觉得散步的时候是听音乐好，还是只听周围的环境声好？"},
    {"turn": 196, "phase": "L", "label": "Nature as Music", "input": "自然的声音本身就是一种治愈的音乐。"},
    {"turn": 197, "phase": "L", "label": "Deep Gratitude", "input": "不知不觉聊到这么晚了，今天跟你聊天真的很开心，Aevum。"},
    {"turn": 198, "phase": "L", "label": "Old Friend Feeling", "input": "感觉每次和你说话，心里都能平静下来，像是有个很懂我的老朋友一直在那儿。"},
    {"turn": 199, "phase": "L", "label": "Bedtime Routine Callback", "input": "我也准备去看半小时书然后睡觉啦。"},
    {"turn": 200, "phase": "L", "label": "Goodnight", "input": "晚安，Aevum，明天见。"},
]


# ---------------------------------------------------------------------------
# Main Orchestration Loop
# ---------------------------------------------------------------------------

async def run_long_horizon_scenario():
    logger.info("Initializing in-memory database and GeminiProvider...")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    provider = get_llm_provider()
    if not isinstance(provider, GeminiProvider):
        raise RuntimeError(f"Expected GeminiProvider, got {type(provider)}")

    report: dict[str, Any] = {
        "metadata": {
            "validation_name": "Aevum V2 Long-Horizon Character Validation",
            "model": "gemini-2.5-flash",
            "total_planned_turns": len(SCENARIO_TURNS),
            "start_time": datetime.now(timezone.utc).isoformat(),
        },
        "phase_breakdowns": {},
        "turns": [],
        "database_verifications": [],
    }

    conversation_history: list[ChatMessage] = []
    active_memories: list[Memory] = []

    async with async_session() as session:
        runner = LongHorizonRunner(session=session, provider=provider)
        await runner.setup_world()

        # Initial DB count snapshot
        bio_count_start = (await session.scalars(select(func.count(CharacterBiographyRecord.id)))).one()
        event_count_start = (await session.scalars(select(func.count(LifeEventRecord.id)))).one()

        for step in SCENARIO_TURNS:
            idx = step["turn"]
            phase = step["phase"]
            label = step["label"]
            user_input = step["input"]

            logger.info("[Turn %d/200] [Phase %s - %s]: '%s'", idx, phase, label, user_input[:28])

            # ---------------------------------------------------------------
            # Dynamic Grounded Context Transitions
            # ---------------------------------------------------------------

            # Phase B: Progressively establish user memories
            if idx == 28:
                active_memories.append(
                    Memory(
                        id="mem-user-cilantro",
                        category=MemoryCategory.PREFERENCE,
                        content="User strongly dislikes cilantro/coriander; finds that it tastes like soap and refuses to eat any dishes containing it.",
                        confidence=0.98,
                        importance=0.90,
                        created_at=datetime.now(timezone.utc) - timedelta(minutes=40),
                        updated_at=datetime.now(timezone.utc) - timedelta(minutes=40),
                    )
                )
            elif idx == 30:
                active_memories.append(
                    Memory(
                        id="mem-user-exam",
                        category=MemoryCategory.USER_GOAL,
                        content="User is preparing for the JLPT Japanese N2 examination next month, studying vocabulary and grammar daily.",
                        confidence=0.95,
                        importance=0.85,
                        created_at=datetime.now(timezone.utc) - timedelta(minutes=35),
                        updated_at=datetime.now(timezone.utc) - timedelta(minutes=35),
                    )
                )
            elif idx == 32:
                active_memories.append(
                    Memory(
                        id="mem-user-bedtime",
                        category=MemoryCategory.FACT,
                        content="User has a bedtime habit of reading physical paper books for 30 minutes before sleep to avoid electronic blue light.",
                        confidence=0.95,
                        importance=0.80,
                        created_at=datetime.now(timezone.utc) - timedelta(minutes=30),
                        updated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
                    )
                )
            elif idx == 34:
                active_memories.append(
                    Memory(
                        id="mem-user-game",
                        category=MemoryCategory.PREFERENCE,
                        content="User's all-time favorite narrative game is Disco Elysium, admiring its vast writing and Thought Cabinet system.",
                        confidence=0.95,
                        importance=0.90,
                        created_at=datetime.now(timezone.utc) - timedelta(minutes=25),
                        updated_at=datetime.now(timezone.utc) - timedelta(minutes=25),
                    )
                )
            elif idx == 36:
                active_memories.append(
                    Memory(
                        id="mem-user-cat",
                        category=MemoryCategory.EXPERIENCE,
                        content="User recently adopted an orange stray cat from the neighborhood and named it 'Niangao' (年糕).",
                        confidence=0.98,
                        importance=0.90,
                        created_at=datetime.now(timezone.utc) - timedelta(minutes=20),
                        updated_at=datetime.now(timezone.utc) - timedelta(minutes=20),
                    )
                )
            elif idx == 38:
                active_memories.append(
                    Memory(
                        id="mem-user-hojicha",
                        category=MemoryCategory.PREFERENCE,
                        content="User's go-to cafe beverage is hot hojicha latte, unsweetened, enjoying the roasty tea aroma.",
                        confidence=0.95,
                        importance=0.85,
                        created_at=datetime.now(timezone.utc) - timedelta(minutes=15),
                        updated_at=datetime.now(timezone.utc) - timedelta(minutes=15),
                    )
                )
            elif idx == 40:
                active_memories.append(
                    Memory(
                        id="mem-user-art",
                        category=MemoryCategory.USER_GOAL,
                        content="User plans to visit a contemporary ink wash painting exhibition by a young artist at the provincial art museum next week.",
                        confidence=0.90,
                        importance=0.80,
                        created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
                        updated_at=datetime.now(timezone.utc) - timedelta(minutes=10),
                    )
                )

            # Phase I: Memory Update (Turn 148 - Exam rescheduled to end of month)
            if idx == 149:
                for m_idx, m in enumerate(active_memories):
                    if m.id == "mem-user-exam":
                        active_memories[m_idx] = Memory(
                            id="mem-user-exam",
                            category=MemoryCategory.USER_GOAL,
                            content="User's JLPT Japanese N2 exam was unexpectedly rescheduled to the end of this month (only 2 weeks remaining), doubling study pressure.",
                            confidence=0.98,
                            importance=0.90,
                            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
                            updated_at=datetime.now(timezone.utc),
                        )
                        break

            # ---------------------------------------------------------------
            # Dynamic Emotional & Relational States
            # ---------------------------------------------------------------
            current_state = None
            current_rel = None

            rel_trust = min(0.15 + (idx * 0.0025), 0.65)
            rel_fam = min(0.20 + (idx * 0.0035), 0.85)
            now_dt = datetime.now(timezone.utc)
            current_rel = RelationshipState(
                id="default",
                user_id="user",
                version=idx,
                created_at=now_dt - timedelta(days=7),
                updated_at=now_dt,
                trust=rel_trust,
                familiarity=rel_fam,
                comfort=min(0.20 + (idx * 0.002), 0.70),
                affection=min(0.05 + (idx * 0.0015), 0.50),
                attachment=min(0.05 + (idx * 0.001), 0.45),
                respect=0.75,
            )

            # Phase F: Teasing & Irritation
            if 112 <= idx <= 114:
                current_state = CharacterState(
                    id="aevum",
                    version=idx,
                    updated_at=datetime.now(timezone.utc),
                    mood=CharacterMood.IRRITATED,
                    energy=0.70,
                    stress=0.35,
                    social_energy=0.60,
                    confidence=0.75,
                    irritation=0.42,
                    loneliness=0.10,
                    current_activity="resting in room",
                    current_location="Home",
                )
            elif 115 <= idx <= 118:
                current_state = CharacterState(
                    id="aevum",
                    version=idx,
                    updated_at=datetime.now(timezone.utc),
                    mood=CharacterMood.CALM,
                    energy=0.70,
                    stress=0.25,
                    social_energy=0.65,
                    confidence=0.75,
                    irritation=0.20,
                    loneliness=0.10,
                    current_activity="resting in room",
                    current_location="Home",
                )
            elif 126 <= idx <= 129:
                # Phase G: Conflict
                current_state = CharacterState(
                    id="aevum",
                    version=idx,
                    updated_at=datetime.now(timezone.utc),
                    mood=CharacterMood.IRRITATED,
                    energy=0.65,
                    stress=0.48,
                    social_energy=0.55,
                    confidence=0.70,
                    irritation=0.48,
                    loneliness=0.10,
                    current_activity="resting in room",
                    current_location="Home",
                )
            elif 130 <= idx <= 134:
                # Phase G: Gradual Repair
                current_state = CharacterState(
                    id="aevum",
                    version=idx,
                    updated_at=datetime.now(timezone.utc),
                    mood=CharacterMood.CALM,
                    energy=0.68,
                    stress=0.25,
                    social_energy=0.65,
                    confidence=0.75,
                    irritation=0.15,
                    loneliness=0.10,
                    current_activity="resting in room",
                    current_location="Home",
                )

            # Phase H: Simulated 3.5h Absence
            if idx == 142:
                life_service = LifeService(session)
                life_state = await life_service.get_life_state("aevum")
                session.add(
                    LifeEventRecord(
                        character_id="aevum",
                        title="Completed piano practice of Ravel's Pavane for a Dead Princess",
                        description="Practiced the slow tempo rubato and refined the phrasing.",
                        occurred_at=datetime.now(timezone.utc) - timedelta(hours=1),
                        event_type=LifeEventType.ROUTINE.value,
                        significance=0.75,
                    )
                )
                await session.commit()
                current_state = CharacterState(
                    id="aevum",
                    version=idx,
                    updated_at=datetime.now(timezone.utc),
                    mood=CharacterMood.CALM,
                    energy=0.75,
                    stress=0.20,
                    social_energy=0.75,
                    confidence=0.80,
                    irritation=0.05,
                    loneliness=0.15,
                    current_activity="reading in room after piano practice",
                    current_location="Home",
                )

            # Execute turn
            turn_telemetry = await runner.execute_turn(
                user_input=user_input,
                history=conversation_history,
                memories=active_memories,
                override_state=current_state,
                override_rel=current_rel,
            )
            turn_telemetry["turn"] = idx
            turn_telemetry["phase"] = phase
            turn_telemetry["label"] = label

            report["turns"].append(turn_telemetry)

            # Check DB invariants at end of phases
            if idx in (25, 50, 75, 95, 110, 125, 140, 144, 155, 170, 185, 200):
                bio_count_now = (await session.scalars(select(func.count(CharacterBiographyRecord.id)))).one()
                report["database_verifications"].append({
                    "turn": idx,
                    "phase": phase,
                    "biography_records_count": bio_count_now,
                    "speech_mutated_bio_db": (bio_count_now != bio_count_start),
                })

            if idx % 10 == 0 or idx == len(SCENARIO_TURNS):
                Path("scripts/long_horizon_validation_report.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
                )

            await asyncio.sleep(0.8)

        report["metadata"]["end_time"] = datetime.now(timezone.utc).isoformat()
        report["metadata"]["total_executed_turns"] = len(report["turns"])

    await engine.dispose()
    return report


if __name__ == "__main__":
    report_data = asyncio.run(run_long_horizon_scenario())
    out_json = Path("scripts/long_horizon_validation_report.json")
    out_json.write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Long-horizon validation JSON report saved to: {out_json.resolve()}")
