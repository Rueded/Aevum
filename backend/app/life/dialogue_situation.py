"""Dialogue-driven situation & activity extraction service for Project Aevum.

Governed by AGENTS.md:
- Rule 11: The application owns persistent character state.
- Rule 12: Dialogue generates language and reflects reality; deterministic application state records it.
- Rule 15: Authentic state transitions driven by real events and interactions.

Extracts ground-truth character activity, location, and status from dialogue interactions,
ensuring real-world actions (oversleeping, waking up, eating brunch, petting cats, playing piano, going on dates)
are faithfully updated in CharacterStateRecord and LifeStateRecord.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CharacterStateRecord, LifeEventRecord, LifeStateRecord
from app.life.models import LifeEventType

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DialogueSituation:
    activity: str
    location: str
    status: str  # "ACTIVE", "REST", "BUSY"
    duration_minutes: int = 90
    idempotency_title: str = ""


class DialogueSituationAppraisalService:
    """Evaluates dialogue turns to extract immediate situational activities and locations."""

    @classmethod
    def extract_situation(
        cls,
        user_input: str,
        assistant_response: str,
    ) -> Optional[DialogueSituation]:
        """Analyzes dialogue turn to determine character's ongoing activity and location."""
        usr_text = user_input.strip()
        ast_text = assistant_response.strip()
        if not usr_text and not ast_text:
            return None

        usr_lower = usr_text.lower()
        ast_lower = ast_text.lower()
        combined_text = f"{usr_lower} {ast_lower}"

        # -------------------------------------------------------------
        # 1. Future Plans Discussion Guard (talking about tomorrow / later)
        # -------------------------------------------------------------
        is_future = any(w in combined_text for w in ("明天", "后天", "下次", "改天", "周末", "等会儿", "稍后")) and not any(
            now_w in combined_text for now_w in ("现在", "这就去", "马上", "已经到了", "出发了", "开吃了", "出发吧", "正在", "坐下", "开动")
        )
        if is_future and any(k in combined_text for k in ("行程", "计划", "去哪", "玩", "出去", "安排", "看电影", "吃饭")):
            return DialogueSituation(
                activity="在卧室和对方商量之后的约会行程",
                location="老家-卧室",
                status="ACTIVE",
                duration_minutes=60,
                idempotency_title="商量约会行程",
            )

        # -------------------------------------------------------------
        # 2. Oversleeping Panic (waking up very late in shock)
        # -------------------------------------------------------------
        if any(k in ast_lower for k in ("睡到现在", "怎么睡到现在", "十二点半了", "十二点了", "睡过头", "怎么现在了", "睡到中午", "我的练琴计划")):
            return DialogueSituation(
                activity="睡过头惊醒/手忙脚乱起床中",
                location="老家-卧室床上",
                status="ACTIVE",
                duration_minutes=45,
                idempotency_title="睡过头惊醒起床",
            )

        # -------------------------------------------------------------
        # 3. Sleeping / Groggy / In Bed (Staying in bed, murmuring)
        # -------------------------------------------------------------
        is_waking_denial = any(k in ast_lower for k in ("刚起来", "洗漱完", "已经起来了", "在客厅", "在沙发", "已经醒了"))
        if not is_waking_denial and (
            any(k in ast_lower for k in (
                "还在睡", "还在睡觉", "在睡觉啦", "在睡觉呢", "想睡", "还想睡",
                "再睡一会儿", "再睡会", "别吵我睡", "吵我睡懒觉", "困死了",
                "没睡醒", "被窝里", "还在床上", "赖床", "声音含糊",
                "声音越来越小", "迷迷糊糊", "揉眼睛", "吵醒我", "吵我啦",
            ))
            or (
                any(k in usr_lower for k in ("还在睡", "在睡觉", "没醒", "睡懒觉", "多睡会儿", "再睡会儿"))
                and any(k in ast_lower for k in ("嗯", "唔", "别吵", "困", "好困", "早安", "睡了", "懒觉", "声音"))
            )
        ):
            return DialogueSituation(
                activity="在卧室被窝迷糊赖床/补觉中",
                location="老家-卧室床上",
                status="REST",
                duration_minutes=90,
                idempotency_title="在被窝迷糊赖床补觉",
            )

        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # 4. Washing Up / Morning Routine (Explicit Waking Up)
        # -------------------------------------------------------------
        is_explicit_morning_waking = any(k in ast_lower for k in ("刚起来", "刚起床", "洗漱完", "洗完脸", "刷完牙")) or (
            any(k in combined_text for k in ("刚洗漱", "刚起")) and any(k in combined_text for k in ("沙发", "客厅", "小橘"))
        )
        if is_explicit_morning_waking and not any(k in combined_text for k in (
            "出发", "去吃", "餐厅", "日料", "定食", "要不要去试试", "在路上", "选餐厅", "换衣服", "开门", "菜单", "点单", "去哪吃", "晚上", "晚饭", "晚餐"
        )):
            return DialogueSituation(
                activity="刚起床洗漱完/在客厅沙发揉小橘",
                location="老家-客厅沙发",
                status="ACTIVE",
                duration_minutes=45,
                idempotency_title="客厅沙发洗漱揉猫",
            )

        # -------------------------------------------------------------
        # 4b. Living Room Sofa / Petting Xiao Ju (Cat) / General Relaxing
        # -------------------------------------------------------------
        if (
            any(k in ast_lower for k in (
                "揉小橘", "揉猫", "撸猫", "抱小橘", "小橘在", "小橘就趴", "沙发上揉",
                "在客厅沙发", "在客厅坐", "客厅沙发上", "趴在旁边", "旁边呼噜",
            )) or (
                any(k in combined_text for k in ("小橘", "狸花猫", "揉猫", "撸猫", "猫猫"))
                and any(k in combined_text for k in ("沙发", "客厅", "打盹", "休息"))
            )
        ) and not any(k in combined_text for k in (
            "阳台", "出发", "去吃", "餐厅", "日料", "定食", "要不要去试试", "在路上", "选餐厅", "换衣服", "开门", "菜单", "点单", "去哪吃"
        )):
            return DialogueSituation(
                activity="在客厅沙发放松揉小橘",
                location="老家-客厅沙发",
                status="ACTIVE",
                duration_minutes=45,
                idempotency_title="客厅沙发放松揉猫",
            )

        # -------------------------------------------------------------
        # 4c. Home Balcony / Plants / Breeze / Xiao Ju on Balcony
        # -------------------------------------------------------------
        if any(k in ast_lower for k in (
            "在阳台", "阳台看花", "阳台吹风", "阳台呢", "阳台上", "花花草草", "看植物", "打理植物", "阳台看风景", "看晚霞"
        )) or (
            any(k in combined_text for k in ("在阳台", "去阳台", "阳台"))
            and any(k in combined_text for k in ("小橘", "花草", "植物", "吹风", "晚霞", "盆栽", "浇水"))
        ):
            return DialogueSituation(
                activity="在阳台照顾花草吹风放空",
                location="老家-阳台",
                status="ACTIVE",
                duration_minutes=45,
                idempotency_title="阳台照顾花草吹风",
            )

        # -------------------------------------------------------------
        # 5. Dining at Home / Dinner, Lunch, Breakfast, Milo
        # -------------------------------------------------------------
        dinner_keywords = ("吃晚饭", "吃晚餐", "晚饭时间", "喝排骨汤", "莲藕汤", "煲汤", "帮妈妈洗碗", "帮家里收拾", "晚饭")
        if any(k in combined_text for k in dinner_keywords) and not any(
            out_k in combined_text for out_k in ("店里", "进店", "餐厅", "服务员", "日料店", "商场", "外出")
        ):
            return DialogueSituation(
                activity="在餐厅享用晚餐/家庭时光",
                location="老家-餐厅餐桌",
                status="ACTIVE",
                duration_minutes=60,
                idempotency_title="享用家常晚餐",
            )

        home_dining_keywords = ("吃早饭", "吃早餐", "吃午饭", "吃午餐", "喝美禄", "烤吐司", "吃炒粉", "在餐厅吃", "点外卖", "煮面", "泡面", "吃面包")
        if any(k in combined_text for k in home_dining_keywords) and not any(
            out_k in combined_text for out_k in ("店里", "进店", "餐厅", "服务员", "日料店", "商场", "外出")
        ):
            return DialogueSituation(
                activity="在餐厅享用早午餐/喝热美禄",
                location="老家-餐厅餐桌",
                status="ACTIVE",
                duration_minutes=60,
                idempotency_title="享用家常早午餐",
            )

        # -------------------------------------------------------------
        # 6. Dressing Up / Getting Ready to Head Out
        # -------------------------------------------------------------
        if any(k in ast_lower for k in (
            "等我换衣服", "换衣服", "去换套衣服", "化个妆", "收拾一下",
            "去收拾", "准备准备", "等等我哈", "我这就去准备", "挑裙子",
            "化得比较快", "在梳头", "马上换好",
        )):
            return DialogueSituation(
                activity="在更衣室梳妆打扮/准备出门赴约",
                location="老家-卧室更衣室",
                status="BUSY",
                duration_minutes=45,
                idempotency_title="梳妆打扮准备出门",
            )

        # -------------------------------------------------------------
        # 7. Meeting at Doorway / Departure
        # -------------------------------------------------------------
        if any(k in ast_lower for k in ("来开门", "给你开门", "马上开门", "在门口了", "到玄关", "下楼接你", "动作倒是挺快")) or (
            any(k in usr_lower for k in ("开门", "我到了", "敲门", "到你家楼下", "到门口"))
            and any(k in ast_lower for k in ("来", "快", "走", "好", "门", "开", "走吧"))
        ):
            return DialogueSituation(
                activity="在玄关开门迎接/准备出发赴约",
                location="老家-玄关门口",
                status="ACTIVE",
                duration_minutes=30,
                idempotency_title="玄关开门迎接出发",
            )

        # -------------------------------------------------------------
        # 8. High-Altitude Rooftop Terrace / Horizon Grill / Romantic Evening
        # -------------------------------------------------------------
        if any(k in combined_text for k in ("horizon grill", "戴上项链", "项链好漂亮", "帮她戴上项链", "帮我戴上项链", "双子塔夜景", "露台看夜景", "郁金香", "牵手")):
            return DialogueSituation(
                activity="高空露台餐厅漫步看夜景/甜蜜互动",
                location="Banyan Tree Horizon Grill 露台",
                status="ACTIVE",
                duration_minutes=90,
                idempotency_title="露台漫步与浪漫互动",
            )

        # -------------------------------------------------------------
        # 9. Cinema / Movie in Progress
        # -------------------------------------------------------------
        if any(k in combined_text for k in ("放映厅", "开场了", "电影开始了", "爆米花", "检票", "看电影中", "散场", "买电影票", "电影院选座")):
            return DialogueSituation(
                activity="商场影城看电影放映中",
                location="商场影城 (GSC/TGV Cinemas)",
                status="ACTIVE",
                duration_minutes=120,
                idempotency_title="影城看电影",
            )

        # -------------------------------------------------------------
        # 10. Post-Dining Mall Walk / Shopping
        # -------------------------------------------------------------
        is_dining_inquiry = any(k in usr_lower for k in ("吃饱了吗", "吃饱了么", "吃饱没", "吃饱了没", "还没吃饱", "吃饱了吗？", "吃饱了吗?"))
        if not is_dining_inquiry and any(k in combined_text for k in ("我吃饱了", "买单了", "结账走", "买完单", "吃得好撑", "消食散步")):
            return DialogueSituation(
                activity="商场闲逛散步/前往影城途中",
                location="商场 (The Intermark Mall / Pavilion)",
                status="ACTIVE",
                duration_minutes=75,
                idempotency_title="商场闲逛散步",
            )

        # -------------------------------------------------------------
        # 10a. Pick-up / In Car / Passenger Seat / Transit
        # -------------------------------------------------------------
        is_pickup_transit = any(k in combined_text for k in (
            "接到你", "接到她", "来接你", "我到了你出来", "上车吧", "上车了", "坐在副驾", "坐副驾",
            "在车里", "坐在车里", "系好安全带", "在副驾驶", "开车带你", "兜风"
        )) or (
            any(k in usr_lower for k in ("我到了", "接你", "到了楼下", "在车上等你", "上车"))
            and any(k in ast_lower for k in ("来啦", "这就下来", "上车", "副驾驶", "走吧", "系好", "出发"))
        )
        if is_pickup_transit and not any(k in combined_text for k in ("到超市了", "到店里了", "进商场了", "进店了")):
            return DialogueSituation(
                activity="坐在副驾驶/与对方在车上闲聊前往目的地",
                location="车内 (副驾驶/前往目的地途中)",
                status="ACTIVE",
                duration_minutes=45,
                idempotency_title="车内副驾闲聊兜风",
            )

        # -------------------------------------------------------------
        # 10b. Supermarket & Grocery Shopping
        # -------------------------------------------------------------
        supermarket_keywords = ("超市", "逛超市", "买零食", "买食材", "推购物车", "生鲜区", "挑零食", "大润发", "aeon", "jaya grocer", "lotus", "买菜")
        if any(k in combined_text for k in supermarket_keywords) and not any(
            future_k in combined_text for future_k in ("明天", "改天", "下次再去超市", "改天去超市")
        ):
            return DialogueSituation(
                activity="在超市推购物车挑选零食与食材",
                location="超市零食与生鲜区 (Supermarket)",
                status="ACTIVE",
                duration_minutes=60,
                idempotency_title="超市挑选零食食材",
            )

        # -------------------------------------------------------------
        # 10c. Mall Shopping & Boutique Browsing
        # -------------------------------------------------------------
        mall_keywords = ("逛街", "逛商场", "试衣服", "买衣服", "挑小物件", "挑衣服", "商场逛逛", "文创店", "百货")
        if any(k in combined_text for k in mall_keywords) and not any(
            future_k in combined_text for future_k in ("明天", "改天", "下次再逛")
        ):
            return DialogueSituation(
                activity="在商场悠闲逛街挑选小物件与试衣",
                location="商场步行街与精品店",
                status="ACTIVE",
                duration_minutes=75,
                idempotency_title="商场悠闲逛街购物",
            )

        # -------------------------------------------------------------
        # 10d. Campus Classes & Lecture Hall
        # -------------------------------------------------------------
        campus_class_keywords = ("在教室", "上课呢", "在上课", "早八", "听讲座", "阶梯教室", "老师在讲", "专业课", "大课")
        campus_class_negations = ("下课", "不上课", "翘课", "没上课", "放学", "逃课")
        if any(k in combined_text for k in campus_class_keywords) and not any(k in combined_text for k in campus_class_negations):
            return DialogueSituation(
                activity="在大学阶梯教室认真上课听讲",
                location="大学计算机系教学楼阶梯教室",
                status="BUSY",
                duration_minutes=90,
                idempotency_title="大学阶梯教室上课",
            )

        # -------------------------------------------------------------
        # 10e. Campus After-Class & Walkway
        # -------------------------------------------------------------
        if any(k in combined_text for k in ("刚下课", "下课了", "走出教室", "走出教学楼", "走在校园", "走在校道")):
            return DialogueSituation(
                activity="刚下课走出教学楼/走在校园林荫道",
                location="大学校园林荫道与教学楼前",
                status="ACTIVE",
                duration_minutes=45,
                idempotency_title="下课走出教学楼",
            )

        # -------------------------------------------------------------
        # 10f. University Library & Silent Study Hall
        # -------------------------------------------------------------
        if any(k in combined_text for k in ("在图书馆", "图书馆自习", "在自习室", "看文献", "自习中", "写论文", "查论文", "阅览室")):
            return DialogueSituation(
                activity="在大学图书馆静音阅览室看书自习",
                location="大学图书馆五楼阅览室",
                status="ACTIVE",
                duration_minutes=90,
                idempotency_title="大学图书馆静音自习",
            )

        # -------------------------------------------------------------
        # 11. En Route / In Car / Deciding on Destination
        # -------------------------------------------------------------
        en_route_keywords = (
            "出发吧", "想吃", "要不要去试试", "叫什么名字", "选餐厅", "挑餐厅", "在车上",
            "去吃", "去哪吃", "没找到", "换一间", "离这里不远", "商量", "在路上", "去店里途中",
            "快到了", "在出租车上", "花见小路", "hanamikoji", "intermark mall", "the intermark"
        )
        if any(k in combined_text for k in en_route_keywords) and not any(
            seated_k in combined_text for seated_k in ("到店里了", "进店了", "坐下看", "已入座", "菜单点菜", "尝尝这道菜")
        ):
            return DialogueSituation(
                activity="外出赴约途中/商量挑选约会餐厅",
                location="雪隆外出途中 (商场/车上)",
                status="ACTIVE",
                duration_minutes=60,
                idempotency_title="外出赴约途中",
            )

        # -------------------------------------------------------------
        # 12. Restaurant Dining / Japanese Cuisine / Date Meal
        # -------------------------------------------------------------
        # -------------------------------------------------------------
        # 12. Restaurant Dining / Hotpot / Japanese / Date Meal
        # -------------------------------------------------------------
        if any(k in combined_text for k in ("吃火锅", "火锅店", "涮羊肉", "海底捞", "辣锅", "番茄锅")):
            return DialogueSituation(
                activity="在火锅店共进晚餐/品尝热气腾腾的火锅",
                location="热气腾腾的火锅餐厅",
                status="ACTIVE",
                duration_minutes=90,
                idempotency_title="火锅餐厅用餐",
            )

        dining_keywords = (
            "点菜", "菜单", "入座", "好香", "上菜", "吃寿司", "开吃", "坐下", "这道菜", "尝尝",
            "进店", "到店里", "在店里", "刺身", "拉面", "烤肉", "随便点", "想吃什么吃什么",
            "看看有什么好吃", "点单", "午市套餐", "定食", "日料", "hanare", "hanaya", "怀石料理",
            "吃饱了吗", "吃饱了么", "吃饱没", "吃寿司", "吃刺身", "寿司"
        )
        if any(k in combined_text for k in dining_keywords):
            return DialogueSituation(
                activity="在日料店共进午餐/约会用餐中",
                location="商场日料店 (The Intermark Mall Hanare)",
                status="ACTIVE",
                duration_minutes=90,
                idempotency_title="餐厅约会用餐",
            )

        # -------------------------------------------------------------
        # 13. Returning Home / Winding Down in Pajamas
        # -------------------------------------------------------------
        if any(k in combined_text for k in ("送我回家", "到家了", "进家门", "换睡衣", "累瘫了", "洗完澡了", "躺床上了", "钻进被窝")):
            return DialogueSituation(
                activity="约会结束返家休息/换上睡衣放松",
                location="老家-卧室",
                status="REST",
                duration_minutes=90,
                idempotency_title="返家换睡衣休息",
            )

        # -------------------------------------------------------------
        # 14. Piano Practice (CRITICAL NEGATION & REJECTION GUARD)
        # -------------------------------------------------------------
        has_piano_terms = any(k in combined_text for k in ("练琴", "扒谱", "弹琴", "电钢琴", "肖邦", "乐理", "琴谱", "和弦"))
        # Denials / Questions / Sleeping overrides MUST NOT trigger piano!
        has_piano_denial = any(k in combined_text for k in (
            "练什么琴", "练什么", "哪有练琴", "没练琴", "才没练", "还在睡",
            "在睡觉", "睡到现在", "被窝", "赖床", "怎么可能在练琴",
        ))
        if has_piano_terms and not has_piano_denial:
            return DialogueSituation(
                activity="古典钢琴练习与扒谱",
                location="家中钢琴房",
                status="ACTIVE",
                duration_minutes=90,
                idempotency_title="钢琴练习与扒谱",
            )

        # -------------------------------------------------------------
        # 15. Coding / Writing Code / Indie Game Dev
        # -------------------------------------------------------------
        if any(k in combined_text for k in ("写代码", "敲代码", "捣鼓新代码", "改bug", "独立游戏", "看录播", "写脚本")):
            return DialogueSituation(
                activity="在书房电脑前写代码敲键盘",
                location="老家-书房电脑前",
                status="ACTIVE",
                duration_minutes=90,
                idempotency_title="书房写代码",
            )

        # -------------------------------------------------------------
        # 16. Gaming / Co-op / Discord Call
        # -------------------------------------------------------------
        if any(k in combined_text for k in ("上号", "联机", "开黑", "连麦打游戏", "打崩铁", "刷圣遗物", "双排", "打原神")):
            return DialogueSituation(
                activity="电脑前联机游戏中",
                location="老家-书房电脑前",
                status="ACTIVE",
                duration_minutes=75,
                idempotency_title="电脑前打游戏",
            )

        # -------------------------------------------------------------
        # 17. Cafe Chill
        # -------------------------------------------------------------
        if any(k in combined_text for k in ("喝咖啡", "咖啡馆", "点杯拿铁", "奶茶店", "坐会儿喝饮料")):
            return DialogueSituation(
                activity="在海边咖啡馆悠闲喝下午茶",
                location="街角海边咖啡馆",
                status="ACTIVE",
                duration_minutes=75,
                idempotency_title="咖啡馆喝下午茶",
            )

        return None

    @classmethod
    async def apply_situation(
        cls,
        session: AsyncSession,
        character_id: str,
        situation: DialogueSituation,
    ) -> None:
        """Applies extracted dialogue situation to LifeStateRecord, CharacterStateRecord, and LifeEventRecord."""
        now_utc = datetime.now(timezone.utc)
        exp_time = now_utc + timedelta(minutes=situation.duration_minutes)

        # 1. Update LifeStateRecord
        stmt_life = select(LifeStateRecord).where(LifeStateRecord.character_id == character_id)
        life_rec = (await session.scalars(stmt_life)).first()
        if life_rec:
            life_rec.current_activity = situation.activity
            life_rec.current_location = situation.location
            life_rec.status = situation.status
            life_rec.active_contingency_id = "conversational_situation"
            life_rec.active_contingency_title = f"{situation.activity} @ {situation.location}"
            life_rec.contingency_expires_at = exp_time
            life_rec.version += 1
            life_rec.updated_at = now_utc

        # 2. Update CharacterStateRecord
        stmt_char = select(CharacterStateRecord).where(CharacterStateRecord.id == character_id)
        char_rec = (await session.scalars(stmt_char)).first()
        if char_rec:
            char_rec.current_activity = situation.activity
            char_rec.current_location = situation.location

        # 3. Emit LifeEventRecord
        event_key = f"dialogue_situation:{character_id}:{uuid4()}"
        event = LifeEventRecord(
            character_id=character_id,
            event_type=LifeEventType.OTHER.value,
            title=f"对话情境推进: {situation.idempotency_title or situation.activity}",
            description=f"苏棠当前处于: {situation.activity} (地点: {situation.location})",
            significance=0.3,
            occurred_at=now_utc,
            idempotency_key=event_key,
        )
        session.add(event)
        await session.commit()
        logger.info(
            "Dialogue situation applied for '%s': activity='%s', location='%s', expires_in=%dm",
            character_id,
            situation.activity,
            situation.location,
            situation.duration_minutes,
        )
