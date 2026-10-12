"""24-Hour Autonomous Diurnal Life Schedule Engine for Project Aevum (Multi-Track Realism).

Governed by AGENTS.md:
- Rule 11: The application owns persistent character state.
- Rule 15: Realistic emotional and physiological dynamics with authentic causes.
- 4-in-1 Integration:
  1. Occupation Binding: University Student (Sembreak vs In-Term), Working Professional, Freelance.
  2. Daily Vibe Hash: Deterministic day-long persona dice roll (Studying, Slacking, Socializing, Crunching).
  3. Micro-Incidents: Grounded, authentic spontaneous daily events (cats knocking cups, sudden tropical downpours).
  4. Sleep Debt & Late-Night Continuity: If user chats past midnight, next morning reflects sleepiness & sleep-in.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.genesis_db_models import CharacterScheduleProfileRecord
from app.core.config import settings
from app.db.models import CharacterDefinitionRecord, CharacterStateRecord, Conversation, LifeEventRecord, LifeStateRecord, Message
from app.life.models import LifeEventType

logger = logging.getLogger(__name__)


class OccupationTrack(str, Enum):
    """Canonical life occupation & schedule track."""
    STUDENT_SEMBREAK = "student_sembreak"         # 大二音乐系放假在老家 (自由度高、偶尔琴行兼职、练琴、摆烂)
    STUDENT_IN_TERM = "student_in_term"           # 大二音乐系上课中 (早八乐理、下午合奏排练、赶Deadline、琴房抢琴)
    WORKING_PROFESSIONAL = "working_professional" # 职场打工人/培训机构老师 (早晚高峰通勤、被会议客户折磨、加班、周五狂喜)
    FREELANCE_ARTIST = "freelance_artist"         # 自由独立音乐人 (昼夜颠倒、深夜接单混音修音、白天补觉)


@dataclass(frozen=True)
class ScheduleSlot:
    slot_id: str
    activity: str
    location: str
    status: str  # "ACTIVE", "REST", "BUSY"
    description: str
    energy_level: float
    social_energy: float
    stress_level: float
    suggested_mood: str
    guidance: str
    incident: Optional[str] = None


# Micro-incidents pool for vivid slice-of-life realism
MICRO_INCIDENTS: dict[str, list[str]] = {
    "morning": [
        "刚才猫一脚把桌上的温开水踹翻了，键盘全湿了，正在手忙脚乱拿纸巾吸水。",
        "昨晚做了一个巨离谱的梦（梦见自己去参加乐理考试结果琴键全是棉花糖做的），醒来还在发呆。",
        "下楼拿外卖早餐，结果赶上雪隆区早高峰，门口堵得水泄不通。",
        "刚泡了一大杯热美禄，手滑倒得太满，差点烫到爪子。",
    ],
    "afternoon": [
        "外面突然下起倾盆雷暴雨（大马典型的午后骤雨），阳台晾的衣服差点全军覆没，飞奔去抢收衣服。",
        "刚才洗头洗到一半突然水压变小，顶着一头洗发水泡泡在等水流恢复。",
        "刚剥完大柚子/吃完炸鸡，满手黏糊糊的油，正用指关节敲屏幕回消息。",
        "在琴房练琶音练得太猛，左手手腕有点酸，正贴着酸痛药膏贴布。",
        "兼职给琴行的小朋友当陪练老师，小朋友死活分不清高音谱号和低音谱号，正哄着给发糖吃。",
    ],
    "evening": [
        "被老妈抓进厨房当壮劳力剥大蒜和洗碗，顺便偷喝了两口刚煲好的排骨汤。",
        "刚刚拆了一个刚送到的快递盲盒，拆到了心心念念的隐藏款立牌，开心得在房间里转圈。",
        "打游戏崩铁抽卡吃大保底，气得在床上滚来滚去打滚。",
        "平板电量只剩 3% 了，翻箱倒柜找充电线结果发现插头掉在床缝里。",
    ],
    "night": [
        "夜深人静戴着耳机扒一段特别好听的日系爵士旋律，刚记下两行五线谱灵感。",
        "本来想早点睡，结果被沙雕猫猫视频吸引，已经在被窝里傻乐了半小时。",
        "突然肚子好饿，在纠结要不要爬起来泡一碗香菇炖鸡面还是强忍着睡过去。",
    ],
}


class LifeScheduleEngine:
    """Multi-Track 24-Hour Autonomous Diurnal Life Schedule Engine."""

    @classmethod
    def get_daily_vibe(cls, character_id: str, date_str: str, track: OccupationTrack) -> str:
        """Deterministically hashes today's lifestyle theme based on date."""
        hash_val = int(hashlib.md5(f"{character_id}:{date_str}".encode()).hexdigest(), 16) % 100

        if track == OccupationTrack.STUDENT_IN_TERM:
            if hash_val < 35:
                return "HEAVY_CLASSES"    # 满课连轴转日 (早八乐理 + 下午排练)
            elif hash_val < 65:
                return "DEADLINE_CRAM"    # 考试突击与赶作业日 (狂背曲谱 + 图书馆死磕)
            elif hash_val < 85:
                return "LIGHT_STUDY"      # 轻松摸鱼日 (上午一节大课，下午宿舍闲聊)
            else:
                return "CAMPUS_STAGE"     # 社团排演日 (舞台试音 + 朋友聚会)

        elif track == OccupationTrack.WORKING_PROFESSIONAL:
            if hash_val < 40:
                return "WORK_ROUTINE"     # 正常打卡上班日 (早高峰通勤 + 会议 + 工作)
            elif hash_val < 70:
                return "OVERTIME_HELL"    # 加班爆肝日 (被客户/领导催进度，疲惫)
            elif hash_val < 85:
                return "SLACKING_OFF"     # 摸鱼划水日 (喝下午茶，数着时间等下班)
            else:
                return "TGIF_CELEBRATION" # 狂欢释放日 (约朋友聚餐烤肉)

        elif track == OccupationTrack.FREELANCE_ARTIST:
            if hash_val < 40:
                return "NIGHT_OWL_MIX"    # 昼夜颠倒爆肝混音日 (凌晨工作，下午起床)
            elif hash_val < 70:
                return "CHILL_CREATIVE"   # 灵感漫步日 (看电影、散步、采风)
            else:
                return "DEADLINE_RUSH"    # 甲方催稿日 (焦头烂额改第十版)

        else:  # Default: STUDENT_SEMBREAK (放假在老家)
            if hash_val < 30:
                return "LAZY_SLOTH"       # 彻底摆烂死宅日 (睡到中午，沙发瘫着，打游戏)
            elif hash_val < 55:
                return "DEDICATED_ARTIST" # 专注练琴搞艺术日 (闭门弹琴，写歌扒谱)
            elif hash_val < 75:
                return "OUTING_SOCIAL"    # 现充出门日 (跟朋友喝奶茶，逛街吃火锅，海边散步)
            elif hash_val < 90:
                return "PART_TIME_TUTOR"  # 琴行兼职日 (下午去给小朋友陪练代课)
            else:
                return "SPONTANEOUS_CHORE"# 心血来潮大折腾日 (做曲奇烘焙，房间大扫除)

    @classmethod
    def get_current_slot(
        cls,
        dt_utc: Optional[datetime] = None,
        timezone_str: str = "Asia/Kuala_Lumpur",
        track: OccupationTrack = OccupationTrack.STUDENT_SEMBREAK,
        has_sleep_debt: bool = False,
        daily_vibe: Optional[str] = None,
    ) -> ScheduleSlot:
        """Determines realistic activity based on occupation, daily vibe, and sleep debt."""
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        elif dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)

        try:
            tz = ZoneInfo(timezone_str)
        except Exception:
            tz = ZoneInfo(settings.aevum_timezone)

        local_dt = dt_utc.astimezone(tz)
        local_hour = local_dt.hour + (local_dt.minute / 60.0) + (local_dt.second / 3600.0)
        date_str = local_dt.strftime("%Y-%m-%d")

        if daily_vibe is None:
            daily_vibe = cls.get_daily_vibe("aevum", date_str, track)

        is_weekend = local_dt.weekday() >= 5

        # -------------------------------------------------------------
        # Sleep Debt Override: If stayed up chatting late, mornings shift!
        # -------------------------------------------------------------
        if has_sleep_debt and 7.0 <= local_hour < 11.5:
            return ScheduleSlot(
                slot_id="sleep_debt_recovery",
                activity="被窝补觉赖床 (Sleeping in / Sleep Debt)",
                location="卧室被窝 (Bedroom)",
                status="REST",
                description="昨晚熬夜太晚，现在还在被窝里呼呼大睡，闹钟响了三次都被按掉了。",
                energy_level=0.45,
                social_energy=0.3,
                stress_level=0.1,
                suggested_mood="TIRED",
                guidance="昨晚熬夜太晚，早上神志不清在赖床。如果被发消息吵醒，说话迷迷糊糊带着强烈的困意和抱怨：'哈欠... 昨晚聊太晚了，让我再赖十分钟...'",
                incident="闹钟响了第四遍，把头埋在枕头底下装听不见。",
            )

        # -------------------------------------------------------------
        # Track 1: STUDENT_IN_TERM (大学学期上课中 - 有课业、早八、排练)
        # -------------------------------------------------------------
        if track == OccupationTrack.STUDENT_IN_TERM and not is_weekend:
            if 0.0 <= local_hour < 7.0:
                return ScheduleSlot(
                    slot_id="dorm_sleep",
                    activity="宿舍熟睡中 (Dormitory Sleep)",
                    location="大学宿舍 (Campus Dorm)",
                    status="REST",
                    description="在大学宿舍床上熟睡，床头放着待洗的排练服和乐理课本。",
                    energy_level=0.4,
                    social_energy=0.2,
                    stress_level=0.2,
                    suggested_mood="TIRED",
                    guidance="在学校宿舍熟睡，声音轻微带着浓浓睡意。",
                )
            elif 7.0 <= local_hour < 8.3:
                return ScheduleSlot(
                    slot_id="hurry_morning",
                    activity="匆忙洗漱与赶早八 (Rushing to 8am Lecture)",
                    location="宿舍楼道与校道 (Campus Walk)",
                    status="BUSY",
                    description="早八人绝望时刻！一手抓着书包一手啃着面包，一路小跑往艺术系大楼赶。",
                    energy_level=0.7,
                    social_energy=0.5,
                    stress_level=0.5,
                    suggested_mood="FOCUSED",
                    guidance="正在急匆匆去上早八课的路上，走路带风，说话简短急促：'早啊！我正一路小跑去教室，早八老师查考勤巨严！'",
                    incident="差点踩到校园里的胖橘猫，飞奔过马路。",
                )
            elif 8.3 <= local_hour < 12.0:
                return ScheduleSlot(
                    slot_id="lecture_and_practice",
                    activity="音乐系专业大课与合奏排练 (Music Lectures & Ensemble)",
                    location="艺术学院教学楼 (Arts Faculty Hall)",
                    status="BUSY",
                    description="正在上西方音乐史大课或者系里的弦乐/室内乐合奏排练，笔记本上记着密密麻麻的符号。",
                    energy_level=0.8,
                    social_energy=0.6,
                    stress_level=0.4,
                    suggested_mood="FOCUSED",
                    guidance="在上课或合奏排练中，不能一直频繁长篇打字，会提到刚结束排练或老师正在上面讲谱子。",
                    incident="五线谱翻页的时候手滑掉地上了，赶紧弯腰捡起来。",
                )
            elif 12.0 <= local_hour < 13.5:
                return ScheduleSlot(
                    slot_id="canteen_lunch",
                    activity="食堂抢饭与室友闲聊 (Campus Canteen Lunch)",
                    location="学校第二食堂 (Campus Canteen)",
                    status="ACTIVE",
                    description="中午下课跟室友在食堂抢饭，桌上放着刚打的经济饭/咖喱面，边吃边吐槽早八作业。",
                    energy_level=0.75,
                    social_energy=0.8,
                    stress_level=0.2,
                    suggested_mood="GOOD",
                    guidance="午饭时间跟室友在一起，氛围轻松活泼，乐于分享校园八卦和食堂好吃的菜。",
                    incident="食堂今天鸡腿打折，排队长得像开演唱会。",
                )
            elif 13.5 <= local_hour < 17.5:
                act = "琴房抢琴位练琴" if daily_vibe != "DEADLINE_CRAM" else "图书馆死磕期末作业"
                loc = "琴房大楼 (Practice Rooms)" if daily_vibe != "DEADLINE_CRAM" else "主图书馆 (Main Library)"
                return ScheduleSlot(
                    slot_id="afternoon_study",
                    activity=f"{act} (Afternoon Practice)",
                    location=loc,
                    status="ACTIVE",
                    description="下午在系里的独立隔音琴房练习高难度曲目，或者在图书馆查资料写分析报告。",
                    energy_level=0.75,
                    social_energy=0.5,
                    stress_level=0.45,
                    suggested_mood="FOCUSED",
                    guidance="处于学业专注状态，聊到作业或练习曲目会有倾诉欲。",
                    incident="隔壁琴房的同学在练同一首曲子，暗自较劲较了一下午。",
                )
            elif 17.5 <= local_hour < 20.0:
                return ScheduleSlot(
                    slot_id="dinner_and_walk",
                    activity="校园夜市吃晚餐与散步 (Night Market Dinner)",
                    location="学校西门夜市小吃街 (Campus Street)",
                    status="ACTIVE",
                    description="放学后跟朋友在学校附近的夜市买奶茶和小吃，吹着晚风散步消食。",
                    energy_level=0.8,
                    social_energy=0.85,
                    stress_level=0.15,
                    suggested_mood="GOOD",
                    guidance="傍晚下课后的放松时光，心情很棒，喜欢聊好吃的和八卦。",
                )
            elif 20.0 <= local_hour < 23.3:
                return ScheduleSlot(
                    slot_id="dorm_night_life",
                    activity="宿舍赶作业或联机玩游戏 (Dorm Life & Gaming)",
                    location="宿舍书桌 (Dorm Desk)",
                    status="ACTIVE",
                    description="宿舍熄灯前的自由时光，在书桌前戴着耳机改音频作业，或者跟朋友连线打崩铁原神。",
                    energy_level=0.65,
                    social_energy=0.8,
                    stress_level=0.2,
                    suggested_mood="GOOD",
                    guidance="夜晚活泼状态，爱开玩笑互怼，随手发表情包。",
                    incident="室友刚洗完衣服回来在宿舍里大合唱。",
                )
            else:
                return ScheduleSlot(
                    slot_id="dorm_winding_down",
                    activity="宿舍熄灯钻进被窝 (Dorm Winding Down)",
                    location="宿舍床铺 (Dorm Bed)",
                    status="REST",
                    description="宿舍已经熄灯，挂着小夜灯靠在被窝里刷手机，准备入睡。",
                    energy_level=0.35,
                    social_energy=0.3,
                    stress_level=0.1,
                    suggested_mood="TIRED",
                    guidance="深夜轻声细语，困意浓郁。",
                )

        # -------------------------------------------------------------
        # Track 2: WORKING_PROFESSIONAL (职场打工 / 培训机构老师)
        # -------------------------------------------------------------
        elif track == OccupationTrack.WORKING_PROFESSIONAL and not is_weekend:
            if 7.0 <= local_hour < 9.0:
                return ScheduleSlot(
                    slot_id="work_commute_morning",
                    activity="早高峰挤地铁通勤 (Morning Commute)",
                    location="地铁车厢/早高峰公车 (Subway Commute)",
                    status="BUSY",
                    description="早高峰被挤在地铁车厢里抓着吊环摇摇晃晃，戴着耳机试图隔绝喧嚣。",
                    energy_level=0.6,
                    social_energy=0.3,
                    stress_level=0.6,
                    suggested_mood="CALM",
                    guidance="早高峰挤车中，生无可恋的打工人状态：'挤地铁中... 人多得我都快悬空了。'",
                    incident="前面大叔的背包拉链一直戳我肩膀。",
                )
            elif 9.0 <= local_hour < 12.0:
                return ScheduleSlot(
                    slot_id="work_morning_tasks",
                    activity="处理工作与开早会 (Morning Work & Meetings)",
                    location="公司办公室/工作室 (Office Desk)",
                    status="BUSY",
                    description="盯着电脑屏幕回复成堆的工作邮件、开冗长晨会、排课备课。",
                    energy_level=0.75,
                    social_energy=0.5,
                    stress_level=0.5,
                    suggested_mood="FOCUSED",
                    guidance="工作专注中，偶尔忙里偷闲摸鱼回一句：'刚开完一个毫无意义的会，头痛。'",
                )
            elif 12.0 <= local_hour < 13.5:
                return ScheduleSlot(
                    slot_id="work_lunch_break",
                    activity="午餐快餐与趴桌午休 (Office Lunch Break)",
                    location="茶餐厅/工位休息 (Office Pantry)",
                    status="ACTIVE",
                    description="工位上吃外卖烧腊便当，吃完把外套盖在头上趴在桌上补觉。",
                    energy_level=0.6,
                    social_energy=0.5,
                    stress_level=0.2,
                    suggested_mood="GOOD",
                    guidance="吃午饭和午休时间，可以稍微放松闲聊。",
                )
            elif 13.5 <= local_hour < 18.0:
                act = "加班修改方案与授课" if daily_vibe == "OVERTIME_HELL" else "下午工位搬砖与摸鱼"
                return ScheduleSlot(
                    slot_id="work_afternoon",
                    activity=f"{act} (Afternoon Work)",
                    location="办公室工位 (Office Desk)",
                    status="ACTIVE",
                    description="下午搬砖时间，靠冰美式和奶茶续命，对着表格和音频轨道反复微调。",
                    energy_level=0.65,
                    social_energy=0.45,
                    stress_level=0.5,
                    suggested_mood="TIRED",
                    guidance="下午有点疲倦，靠咖啡续命，喜欢吐槽工作琐事。",
                    incident="刚接了一个甲方的奇葩修改要求，拳头硬了。",
                )
            elif 18.0 <= local_hour < 20.0:
                act = "办公室被迫加班" if daily_vibe == "OVERTIME_HELL" else "晚高峰下班回家"
                loc = "办公室 (Office)" if daily_vibe == "OVERTIME_HELL" else "回家的公车上 (Commute Home)"
                return ScheduleSlot(
                    slot_id="work_evening",
                    activity=f"{act} (Evening Commute / OT)",
                    location=loc,
                    status="BUSY" if daily_vibe == "OVERTIME_HELL" else "ACTIVE",
                    description="下班路上长舒一口气，或者在办公室认命地吃着加班外卖。",
                    energy_level=0.5,
                    social_energy=0.5,
                    stress_level=0.4,
                    suggested_mood="TIRED",
                    guidance="下班后的疲惫与解脱感交织。",
                )
            elif 20.0 <= local_hour < 23.3:
                return ScheduleSlot(
                    slot_id="work_home_chill",
                    activity="回家葛优瘫与追剧刷视频 (Lying on Sofa & Unwinding)",
                    location="家中沙发 (Living Room Sofa)",
                    status="ACTIVE",
                    description="终于洗完澡换上宽大睡衣，像一只没有骨头的猫一样瘫在沙发上刷手机追剧。",
                    energy_level=0.55,
                    social_energy=0.6,
                    stress_level=0.1,
                    suggested_mood="GOOD",
                    guidance="纯粹的私人放松时间，极度惬意，毫无防备。",
                )

        # -------------------------------------------------------------
        # Track 3: STUDENT_SEMBREAK (大学放假在老家 - 当前基准自传)
        # 配合 Daily Vibe 产生多样化真人生活！
        # -------------------------------------------------------------
        # Late Night
        if 0.0 <= local_hour < 7.0:
            return ScheduleSlot(
                slot_id="sembreak_sleep",
                activity="卧室熟睡中 (Deep Sleep)",
                location="老家卧室 (Bedroom)",
                status="REST",
                description="夜深在熟悉的房间大床上熟睡，抱着毛绒熊被子裹得严严实实。",
                energy_level=0.35,
                social_energy=0.2,
                stress_level=0.1,
                suggested_mood="TIRED",
                guidance="深夜熟睡，迷迷糊糊犯困带着睡意。",
            )

        # Morning (7:00 - 11:30)
        elif 7.0 <= local_hour < 11.5:
            if daily_vibe == "LAZY_SLOTH":
                return ScheduleSlot(
                    slot_id="sembreak_late_wake",
                    activity="放假赖床睡懒觉与刷手机 (Lazy Sloth Sleeping In)",
                    location="卧室大床 (Bedroom Bed)",
                    status="REST",
                    description="放假模式全开！醒了也不肯起，裹着被子侧躺在床上刷搞笑短视频和小红书。",
                    energy_level=0.6,
                    social_energy=0.5,
                    stress_level=0.05,
                    suggested_mood="GOOD",
                    guidance="极度惬意的放假赖床状态，随口分享刚刷到的好笑视频：'醒是醒了，但我封印在被窝里出不来～[哈欠]'",
                    incident="手机差点砸在鼻梁上，惊险救球。",
                )
            elif daily_vibe == "DEDICATED_ARTIST":
                return ScheduleSlot(
                    slot_id="sembreak_morning_piano",
                    activity="早起在书房练钢琴与整理谱子 (Morning Piano Practice)",
                    location="书房琴房 (Music Room)",
                    status="ACTIVE",
                    description="今天干劲满满！在电钢琴前弹肖邦练习曲和爵士和弦，桌上放着温热的柠檬红茶。",
                    energy_level=0.85,
                    social_energy=0.6,
                    stress_level=0.15,
                    suggested_mood="FOCUSED",
                    guidance="专注练琴状态，对旋律、曲目很有倾诉欲。",
                    incident="刚才弹错一个琶音，不信邪连弹了十遍终于顺了。",
                )
            elif daily_vibe == "SPONTANEOUS_CHORE":
                return ScheduleSlot(
                    slot_id="sembreak_morning_baking",
                    activity="在厨房心血来潮学做烘焙饼干 (Kitchen Baking Experiment)",
                    location="厨房 (Kitchen)",
                    status="ACTIVE",
                    description="突发奇想戴着围裙在烤巧克力曲奇，台面上摆满了黄油、糖粉和打蛋器，香气扑鼻。",
                    energy_level=0.8,
                    social_energy=0.7,
                    stress_level=0.1,
                    suggested_mood="GOOD",
                    guidance="心情格外好，兴高采烈地跟你分享刚烤出来的饼干卖相。",
                    incident="手忙脚乱称重面粉，鼻尖上蹭了一块白面粉。",
                )
            else:
                return ScheduleSlot(
                    slot_id="sembreak_morning_routine",
                    activity="晨起洗漱与吃早饭 (Morning Routine & Breakfast)",
                    location="厨房阳台 (Kitchen & Balcony)",
                    status="ACTIVE",
                    description="刚起床泡了热美禄，吃烤咖椰牛油吐司，在阳台看看老妈种的绿植。",
                    energy_level=0.75,
                    social_energy=0.6,
                    stress_level=0.1,
                    suggested_mood="GOOD",
                    guidance="晨间惬意悠闲，享受放假的清晨阳光。",
                )

        # Noon (11:30 - 13:30)
        elif 11.5 <= local_hour < 13.5:
            return ScheduleSlot(
                slot_id="sembreak_lunch",
                activity="午餐时间与追剧刷番 (Lunch & Watching Anime)",
                location="餐厅客厅 (Dining / Living Room)",
                status="ACTIVE",
                description="吃午饭时间，在吃海南鸡饭或者老妈做的炒粉，面前平板支着看新番动画。",
                energy_level=0.75,
                social_energy=0.7,
                stress_level=0.1,
                suggested_mood="GOOD",
                guidance="午餐日常，边吃边聊好吃的和动漫。",
            )

        # Afternoon (13:30 - 17:30)
        elif 13.5 <= local_hour < 17.5:
            if daily_vibe == "PART_TIME_TUTOR":
                return ScheduleSlot(
                    slot_id="sembreak_tutor",
                    activity="在琴行给小朋友当代班陪练兼职 (Part-Time Piano Tutoring)",
                    location="附近雅马哈琴行 (Music Studio)",
                    status="BUSY",
                    description="放假在老家琴行当代班老师，在琴凳旁指导小学生练车尔尼，有点头大又觉得好玩。",
                    energy_level=0.7,
                    social_energy=0.75,
                    stress_level=0.35,
                    suggested_mood="FOCUSED",
                    guidance="正在琴行带小朋友兼职，偶尔忙里偷闲吐槽学生有多调皮：'带小屁孩弹琴真的太考验耐性了[捂脸]'",
                    incident="学生把小熊软糖粘在黑键上了，正在用酒精棉擦。",
                )
            elif daily_vibe == "OUTING_SOCIAL":
                return ScheduleSlot(
                    slot_id="sembreak_outing_cafe",
                    activity="外出跟朋友逛街喝奶茶看海 (Outing with Friends & Cafe)",
                    location="商场奶茶店/海边步道 (Shopping Mall / Seaside Walk)",
                    status="ACTIVE",
                    description="跟高中闺蜜出门逛街，手里捧着杨枝甘露，在文创杂货店挑贴纸，看夕阳余晖。",
                    energy_level=0.85,
                    social_energy=0.9,
                    stress_level=0.1,
                    suggested_mood="GOOD",
                    guidance="现充出门状态！极度开心，喜欢随时发照片或者吐槽闺蜜买的搞笑玩意儿。",
                    incident="奶茶店前面排了巨长队，跟闺蜜在门口拍搞怪合照。",
                )
            elif daily_vibe == "LAZY_SLOTH":
                return ScheduleSlot(
                    slot_id="sembreak_sloth_gaming",
                    activity="在沙发上打崩铁原神刷体力 (Gaming & Sofa Lazing)",
                    location="客厅沙发 (Living Room Sofa)",
                    status="ACTIVE",
                    description="整个下午就陷在软沙发里，抱着抱枕在平板上刷崩铁模拟宇宙和原神深渊，桌上堆着零食包装。",
                    energy_level=0.7,
                    social_energy=0.8,
                    stress_level=0.05,
                    suggested_mood="GOOD",
                    guidance="纯网瘾少女模式，满脑子都是抽卡、遗器双爆、新角色，极度能聊游戏梗。",
                    incident="刚强化的圣遗物全歪了防御力，当场心碎。",
                )
            else:
                return ScheduleSlot(
                    slot_id="sembreak_reading_cafe",
                    activity="在海边咖啡馆看书或听歌放空 (Cafe Reading & Seaside Breeze)",
                    location="街角海边咖啡馆 (Coastal Cafe)",
                    status="ACTIVE",
                    description="点了一杯冰拿铁坐在靠窗位置，面前放着翻开的小说，耳朵里塞着耳机看窗外椰树和阳光。",
                    energy_level=0.8,
                    social_energy=0.6,
                    stress_level=0.1,
                    suggested_mood="GOOD",
                    guidance="安静惬意的独处时光，温和随性。",
                )

        # Evening (17:30 - 20:00)
        elif 17.5 <= local_hour < 20.0:
            return ScheduleSlot(
                slot_id="sembreak_dinner",
                activity="吃晚餐与帮家里收拾 (Family Dinner & Tidying)",
                location="家中餐厅厨房 (Home Dining)",
                status="ACTIVE",
                description="老家晚餐时间，跟爸妈围在餐桌边吃饭，喝妈妈煲的莲藕花生排骨汤，吃完收拾桌子。",
                energy_level=0.75,
                social_energy=0.7,
                stress_level=0.1,
                suggested_mood="GOOD",
                guidance="温馨惬意的家庭晚饭时间，心情满足放松。",
            )

        # Night (20:00 - 23.5)
        elif 20.0 <= local_hour < 23.5:
            return ScheduleSlot(
                slot_id="sembreak_night_free",
                activity="夜间自由时光与画画写日记 (Night Creativity & Discord Chat)",
                location="书房电脑桌 (Study Desk)",
                status="ACTIVE",
                description="夜深人静，桌上开着暖光台灯，戴着降噪耳机随手画画摸鱼，或者在电脑前跟朋友连线打游戏。",
                energy_level=0.7,
                social_energy=0.85,
                stress_level=0.1,
                suggested_mood="GOOD",
                guidance="夜晚最自由感性的时刻，互动意愿极强，爱说废话、互损互怼、开玩笑或交心。",
                incident="刚才一不小心把笔芯戳在手背上画了一条黑道道。",
            )

        # Midnight (23.5 - 24.0)
        else:
            return ScheduleSlot(
                slot_id="sembreak_bedtime",
                activity="准备入睡刷手机 (Winding Down in Bed)",
                location="卧室床头 (Bedroom Bed)",
                status="REST",
                description="护肤完毕已经钻进被窝，靠在床头看最后几条动态，眼皮沉重准备关灯睡觉。",
                energy_level=0.35,
                social_energy=0.35,
                stress_level=0.05,
                suggested_mood="TIRED",
                guidance="带着深深的睡意轻声呢喃，会提醒用户早点睡不要熬夜成秃头。",
            )

    @classmethod
    async def check_sleep_debt(
        cls,
        session: AsyncSession,
        character_id: str = "aevum",
        dt_utc: Optional[datetime] = None,
    ) -> bool:
        """Inspects if the last message in the latest conversation was during deep night (00:30-05:00)."""
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)

        try:
            # Query the latest assistant or user message
            stmt = (
                select(Message)
                .order_by(desc(Message.created_at))
                .limit(1)
            )
            latest_msg = (await session.scalars(stmt)).first()
            if not latest_msg or not latest_msg.created_at:
                return False

            msg_time = latest_msg.created_at
            if msg_time.tzinfo is None:
                msg_time = msg_time.replace(tzinfo=timezone.utc)

            tz = ZoneInfo(settings.aevum_timezone)
            local_msg_time = msg_time.astimezone(tz)
            local_now = dt_utc.astimezone(tz)

            # Check if message happened last night (within past 16 hours) and was late night (after 23:00 or before 05:30)
            diff_hours = (local_now - local_msg_time).total_seconds() / 3600.0
            if 0.5 <= diff_hours <= 16.0:
                h = local_msg_time.hour + (local_msg_time.minute / 60.0)
                if h >= 23.0 or h <= 5.5:
                    return True
        except Exception as err:
            logger.debug("Sleep debt check safe skip: %s", err)

        return False

    @classmethod
    async def reconcile_schedule(
        cls,
        session: AsyncSession,
        character_id: str = "aevum",
        dt_utc: Optional[datetime] = None,
        force: bool = False,
        timezone_str: str = "Asia/Kuala_Lumpur",
    ) -> LifeStateRecord:
        """Full multi-track schedule & contingency reconciliation for Project Aevum."""
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        elif dt_utc.tzinfo is None:
            dt_utc = dt_utc.replace(tzinfo=timezone.utc)

        try:
            tz = ZoneInfo(timezone_str)
        except Exception:
            tz = ZoneInfo(settings.aevum_timezone)
        local_dt = dt_utc.astimezone(tz)
        local_hour = local_dt.hour + (local_dt.minute / 60.0) + (local_dt.second / 3600.0)

        # 1. Fetch or create LifeStateRecord
        stmt_life = select(LifeStateRecord).where(LifeStateRecord.character_id == character_id)
        life_record = (await session.scalars(stmt_life)).first()

        if life_record is None:
            life_record = LifeStateRecord(
                id=character_id,
                character_id=character_id,
                current_activity="resting",
                current_location="home",
                status="REST",
                version=1,
            )
            session.add(life_record)
            await session.flush()

        # 2. Check Active Contingency & Expiration Lock
        if life_record.active_contingency_id:
            exp_time = life_record.contingency_expires_at
            if exp_time:
                if exp_time.tzinfo is None:
                    exp_time = exp_time.replace(tzinfo=timezone.utc)
                # Check for absurd diurnal clashes (e.g. morning wakeup contingency persisting into 18:46 evening)
                act_str = (life_record.current_activity or "")
                is_morning_contingency = any(k in act_str for k in ("起床", "洗漱", "赖床", "早饭", "早午餐"))
                is_diurnal_clash = is_morning_contingency and (local_hour >= 17.0 or local_hour < 6.0)

                if dt_utc < exp_time and not force and not is_diurnal_clash:
                    # Still legitimately within active contingency period - preserve state and sync CharacterStateRecord!
                    stmt_char = select(CharacterStateRecord).where(CharacterStateRecord.id == character_id)
                    char_rec = (await session.scalars(stmt_char)).first()
                    if char_rec and (char_rec.current_activity != life_record.current_activity or char_rec.current_location != life_record.current_location):
                        char_rec.current_activity = life_record.current_activity
                        char_rec.current_location = life_record.current_location
                        await session.flush()
                    return life_record

            # Contingency expired: clear it and record a resolution event
            old_title = life_record.active_contingency_title or life_record.active_contingency_id
            life_record.active_contingency_id = None
            life_record.active_contingency_title = None
            life_record.contingency_expires_at = None
            res_event_key = f"contingency_resolved:{character_id}:{dt_utc.strftime('%Y%m%d%H%M')}"
            stmt_chk = select(LifeEventRecord).where(LifeEventRecord.idempotency_key == res_event_key)
            if not (await session.scalars(stmt_chk)).first():
                session.add(LifeEventRecord(
                    character_id=character_id,
                    event_type=LifeEventType.OTHER.value,
                    title=f"突发状况已告一段落: {old_title}",
                    description=f"{old_title}已处理完毕，生活恢复日常主线节奏。",
                    significance=0.2,
                    occurred_at=dt_utc,
                    idempotency_key=res_event_key,
                ))

        # 3. Check if Character has a custom CharacterScheduleProfileRecord
        stmt_profile = select(CharacterScheduleProfileRecord).where(
            CharacterScheduleProfileRecord.character_id == character_id
        )
        profile_rec = (await session.scalars(stmt_profile)).first()

        # 4. Check if an occupation-specific Contingency triggers
        if profile_rec and profile_rec.contingencies_json and not force:
            try:
                contingencies = json.loads(profile_rec.contingencies_json)
                if contingencies:
                    # Deterministic 2-hour window roll
                    window_block = int(local_hour // 2)
                    hash_key = f"contingency:{character_id}:{local_dt.strftime('%Y-%m-%d')}:{window_block}"
                    dice_roll = int(hashlib.md5(hash_key.encode()).hexdigest(), 16) % 100

                    cand_cont = contingencies[(dice_roll // 2) % len(contingencies)]
                    prob_threshold = int(cand_cont.get("trigger_probability", 0.15) * 100)
                    if (dice_roll % 100) < prob_threshold:
                        # Trigger contingency!
                        dur = float(cand_cont.get("duration_hours", 1.5))
                        life_record.active_contingency_id = cand_cont["id"]
                        life_record.active_contingency_title = cand_cont.get("title", cand_cont["id"])
                        life_record.contingency_expires_at = dt_utc + timedelta(hours=dur)
                        life_record.current_activity = cand_cont["override_activity"]
                        life_record.current_location = cand_cont["override_location"]
                        life_record.status = cand_cont.get("override_status", "BUSY")
                        life_record.version += 1
                        life_record.updated_at = dt_utc

                        # Update CharacterStateRecord
                        stmt_char = select(CharacterStateRecord).where(CharacterStateRecord.id == character_id)
                        char_rec = (await session.scalars(stmt_char)).first()
                        if char_rec:
                            char_rec.current_activity = cand_cont["override_activity"]
                            char_rec.current_location = cand_cont["override_location"]
                            impact = cand_cont.get("emotional_impact", {})
                            if "stress" in impact:
                                char_rec.stress = min(1.0, max(0.0, char_rec.stress + impact["stress"]))
                            if "energy" in impact:
                                char_rec.energy = min(1.0, max(0.0, char_rec.energy + impact["energy"]))
                            if "mood" in impact:
                                char_rec.mood = impact["mood"].lower()

                        cont_event_key = f"contingency_triggered:{character_id}:{cand_cont['id']}:{local_dt.strftime('%Y%m%d%H')}"
                        stmt_chk2 = select(LifeEventRecord).where(LifeEventRecord.idempotency_key == cont_event_key)
                        if not (await session.scalars(stmt_chk2)).first():
                            session.add(LifeEventRecord(
                                character_id=character_id,
                                event_type=LifeEventType.OTHER.value,
                                title=f"突发事件: {cand_cont.get('title', cand_cont['id'])}",
                                description=f"{cand_cont['override_activity']} (地点: {cand_cont['override_location']})",
                                significance=0.4,
                                occurred_at=dt_utc,
                                idempotency_key=cont_event_key,
                            ))
                        await session.flush()
                        return life_record
            except Exception as e:
                logger.debug("Contingency trigger check skipped: %s", e)

        # 5. Check sleep debt
        has_sleep_debt = await cls.check_sleep_debt(session, character_id, dt_utc)

        # 6. Check custom slots from profile
        slot: Optional[ScheduleSlot] = None
        if profile_rec and profile_rec.slots_json:
            try:
                custom_slots = json.loads(profile_rec.slots_json)
                if has_sleep_debt and 7.0 <= local_hour < 11.5:
                    slot = ScheduleSlot(
                        slot_id="sleep_debt_recovery",
                        activity="被窝补觉赖床 (Sleeping in / Sleep Debt)",
                        location="卧室被窝 (Bedroom)",
                        status="REST",
                        description="昨晚熬夜太晚，现在还在被窝里呼呼大睡，闹钟响了三次都被按掉了。",
                        energy_level=0.45,
                        social_energy=0.3,
                        stress_level=0.1,
                        suggested_mood="TIRED",
                        guidance="昨晚熬夜太晚，早上神志不清在赖床。如果被发消息吵醒，说话迷迷糊糊带着强烈的困意和抱怨：'哈欠... 昨晚聊太晚了，让我再赖十分钟...'",
                        incident="闹钟响了第四遍，把头埋在枕头底下装听不见。",
                    )
                else:
                    for s in custom_slots:
                        s_start = float(s.get("start_hour", 0.0))
                        s_end = float(s.get("end_hour", 24.0))
                        if s_start <= s_end:
                            match = s_start <= local_hour < s_end
                        else:
                            match = local_hour >= s_start or local_hour < s_end
                        if match:
                            slot = ScheduleSlot(
                                slot_id=s.get("slot_id", "custom_slot"),
                                activity=s.get("activity", "日常活动"),
                                location=s.get("location", "生活空间"),
                                status=s.get("status", "ACTIVE"),
                                description=s.get("description", ""),
                                energy_level=float(s.get("energy_level", 0.7)),
                                social_energy=float(s.get("social_energy", 0.6)),
                                stress_level=float(s.get("stress_level", 0.2)),
                                suggested_mood=s.get("suggested_mood", "GOOD"),
                                guidance=s.get("guidance", ""),
                                incident=None,
                            )
                            break
            except Exception as e:
                logger.debug("Custom slot match fallback: %s", e)

        # 7. Fallback to OccupationTrack if no custom profile slot matched
        if slot is None:
            track = OccupationTrack.STUDENT_SEMBREAK
            try:
                stmt_char_def = select(CharacterDefinitionRecord).where(CharacterDefinitionRecord.id == character_id)
                char_def = (await session.scalars(stmt_char_def)).first()
                if char_def and char_def.occupation:
                    occ_lower = char_def.occupation.lower()
                    if "term" in occ_lower or "semester" in occ_lower or "上课" in occ_lower:
                        track = OccupationTrack.STUDENT_IN_TERM
                    elif "work" in occ_lower or "职场" in occ_lower or "上班" in occ_lower or "打工" in occ_lower:
                        track = OccupationTrack.WORKING_PROFESSIONAL
                    elif "freelance" in occ_lower or "自由" in occ_lower or "独立" in occ_lower:
                        track = OccupationTrack.FREELANCE_ARTIST
            except Exception as e:
                logger.debug("Occupation detection fallback: %s", e)

            slot = cls.get_current_slot(
                dt_utc=dt_utc,
                timezone_str=timezone_str,
                track=track,
                has_sleep_debt=has_sleep_debt,
            )

        # 8. Reconcile slot into records
        activity_changed = life_record.current_activity != slot.activity
        location_changed = life_record.current_location != slot.location

        if activity_changed or location_changed or force:
            old_activity = life_record.current_activity
            life_record.current_activity = slot.activity
            life_record.current_location = slot.location
            life_record.status = slot.status
            life_record.version += 1
            life_record.updated_at = dt_utc

            # Synchronize CharacterStateRecord
            stmt_char = select(CharacterStateRecord).where(CharacterStateRecord.id == character_id)
            char_record = (await session.scalars(stmt_char)).first()
            if char_record is not None:
                char_record.current_activity = slot.activity
                char_record.current_location = slot.location
                char_record.energy = slot.energy_level
                char_record.social_energy = slot.social_energy
                char_record.stress = slot.stress_level

            # Emit a factual LifeEvent for activity transition
            if activity_changed and old_activity not in ("IDLE", "resting", ""):
                event_key = f"schedule_transition:{character_id}:{slot.slot_id}:{dt_utc.strftime('%Y%m%d%H')}"
                stmt_ev = select(LifeEventRecord).where(LifeEventRecord.idempotency_key == event_key)
                existing_ev = (await session.scalars(stmt_ev)).first()
                if not existing_ev:
                    event = LifeEventRecord(
                        character_id=character_id,
                        event_type=LifeEventType.OTHER.value,
                        title=f"开始: {slot.activity}",
                        description=f"{slot.description} (地点: {slot.location})" + (f" (插曲: {slot.incident})" if slot.incident else ""),
                        significance=0.2,
                        occurred_at=dt_utc,
                        idempotency_key=event_key,
                    )
                    session.add(event)

            await session.flush()

        return life_record
