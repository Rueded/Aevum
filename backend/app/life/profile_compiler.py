"""Life Profile Compiler for Project Aevum (AI & Archetype Synthesis).

Compiles user-defined character occupations, lifestyles, and backgrounds into:
1. 24-Hour Baseline Schedule Slots (slots)
2. Custom Occupation Locations Pool (locations)
3. Occupation-Specific Unexpected Contingencies Pool (contingencies)
4. Occupation-Specific Daily Micro-Incidents (micro_incidents)

Governed by AGENTS.md:
- Rule 7: Testable code without requiring external network or LLM dependencies in tests.
- Rule 11: The application owns persistent character state.
- Rule 12: LLM compiles structured state at genesis/update, but runtime clock ticks deterministically.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.character.genesis_db_models import CharacterScheduleProfileRecord
from app.db.models import utc_now
from app.llm import get_llm_provider
from app.llm.base import ChatMessage
from app.llm.context import LLMContext

logger = logging.getLogger(__name__)


class ArchetypeProfileSynthesizer:
    """Rich, deterministic archetype synthesizer for instant compilation and offline fallback."""

    @classmethod
    def synthesize(
        cls,
        occupation: str,
        lifestyle_rhythm: str = "",
        background: str = "",
        name: str = "Aevum",
    ) -> dict[str, Any]:
        """Synthesize tailored schedule profile based on occupational domain."""
        occ = (occupation or "").lower()
        life = (lifestyle_rhythm or "").lower()
        combined = f"{occ} {life} {background.lower()}"

        if any(k in combined for k in ("医", "护士", "急诊", "病房", "手术", "doctor", "nurse", "clinic")):
            return cls._medical_profile(name, occupation, lifestyle_rhythm)
        elif any(k in combined for k in ("程序", "开发", "代码", "软件", "算法", "运维", "developer", "engineer", "code")):
            return cls._developer_profile(name, occupation, lifestyle_rhythm)
        elif any(k in combined for k in ("学生", "大学", "高中", "考研", "学期", "student", "campus", "school")):
            return cls._student_profile(name, occupation, lifestyle_rhythm)
        elif any(k in combined for k in ("艺术", "音乐", "插画", "画", "设计", "摄影", "artist", "music", "design")):
            return cls._creative_artist_profile(name, occupation, lifestyle_rhythm)
        elif any(k in combined for k in ("咖啡", "店员", "调酒", "餐饮", "服务", "barista", "retail", "waiter")):
            return cls._service_shift_profile(name, occupation, lifestyle_rhythm)
        else:
            return cls._office_professional_profile(name, occupation, lifestyle_rhythm)

    @classmethod
    def _medical_profile(cls, name: str, occ: str, rhythm: str) -> dict[str, Any]:
        return {
            "occupation": occ,
            "lifestyle_rhythm": rhythm,
            "locations": [
                "医院急诊大厅与分诊台",
                "医生办公室与示教室",
                "住院病区病房",
                "医院职工食堂",
                "单身公寓卧室",
            ],
            "slots": [
                {
                    "slot_id": "medical_sleep",
                    "start_hour": 0.0,
                    "end_hour": 6.5,
                    "activity": "值班室轮休或公寓深睡 (Hospital Rest / Deep Sleep)",
                    "location": "单身公寓卧室 / 值班休息室",
                    "status": "REST",
                    "description": "经过一天的高强度医疗工作，拉紧遮光帘陷入深度睡眠。",
                    "guidance": "深夜熟睡或刚下大夜班，睡意极浓，说话迷迷糊糊轻声细语。",
                    "energy_level": 0.35,
                    "social_energy": 0.2,
                    "stress_level": 0.15,
                    "suggested_mood": "TIRED",
                },
                {
                    "slot_id": "medical_morning_rounds",
                    "start_hour": 6.5,
                    "end_hour": 11.5,
                    "activity": "晨会交接班与病区查房 (Morning Handoff & Ward Rounds)",
                    "location": "住院病区病房与医生办公室",
                    "status": "BUSY",
                    "description": "穿着白大褂脖子上挂着听诊器，推着查房车核对病历与患者生命体征。",
                    "guidance": "正在病房忙碌查房，说话干练专业，只能抽空简短回复。",
                    "energy_level": 0.8,
                    "social_energy": 0.5,
                    "stress_level": 0.45,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "medical_lunch",
                    "start_hour": 11.5,
                    "end_hour": 13.0,
                    "activity": "职工食堂快餐与短暂喘息 (Cafeteria Lunch & Break)",
                    "location": "医院职工食堂",
                    "status": "ACTIVE",
                    "description": "端着两荤一素的快餐，一边吃一边跟同科室同事讨论上午的疑难病例。",
                    "guidance": "午餐短暂放松时间，语气稍微轻松，乐于吐槽医院小八卦或好吃的菜。",
                    "energy_level": 0.7,
                    "social_energy": 0.65,
                    "stress_level": 0.25,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "medical_afternoon_procedures",
                    "start_hour": 13.0,
                    "end_hour": 17.5,
                    "activity": "门诊看诊与换药处置 (Outpatient Clinic & Treatments)",
                    "location": "门诊诊室与清创处置室",
                    "status": "BUSY",
                    "description": "戴着医用口罩与橡胶手套，接连看门诊患者、开医嘱或清创包扎。",
                    "guidance": "正在接诊或处置病患，双手戴着手套，不能长篇打字，神情专注。",
                    "energy_level": 0.7,
                    "social_energy": 0.5,
                    "stress_level": 0.4,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "medical_evening_records",
                    "start_hour": 17.5,
                    "end_hour": 20.5,
                    "activity": "书写电子病历与整理医嘱 (Medical Records & Handoff)",
                    "location": "医生办公室电脑前",
                    "status": "ACTIVE",
                    "description": "坐在电脑前敲击键盘补全今日首程、病程记录，准备晚间交班。",
                    "guidance": "工作收尾阶段，有点用脑过度但心情稍缓，忍不住灌了一大口温水。",
                    "energy_level": 0.6,
                    "social_energy": 0.6,
                    "stress_level": 0.3,
                    "suggested_mood": "TIRED",
                },
                {
                    "slot_id": "medical_night_unwind",
                    "start_hour": 20.5,
                    "end_hour": 24.0,
                    "activity": "热水澡更衣与翻阅医学文献 (Hot Bath & Relaxing Reading)",
                    "location": "单身公寓客厅与书房",
                    "status": "ACTIVE",
                    "description": "终于脱下沉重的白大褂换上宽松睡衣，泡一杯洋甘菊茶，听着舒缓音乐看书。",
                    "guidance": "私人治愈时间，极具倾听欲和生活温情，愿意分享一天的真实感受。",
                    "energy_level": 0.5,
                    "social_energy": 0.8,
                    "stress_level": 0.1,
                    "suggested_mood": "GOOD",
                },
            ],
            "contingencies": [
                {
                    "id": "emergency_trauma_intake",
                    "category": "work_emergency",
                    "title": "急诊突发多发伤紧急清创抢救",
                    "trigger_probability": 0.18,
                    "duration_hours": 2.0,
                    "override_activity": "急诊创伤小组紧急止血清创抢救 (Trauma Emergency)",
                    "override_location": "急诊红区抢救室",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": 0.4, "energy": -0.3, "mood": "TIRED"},
                    "dialogue_guidance": "刚协助处理完一台突发紧急外伤抢救，手套里满是汗水，说话短促疲惫但透着专业坚定。",
                    "cooldown_days": 2,
                },
                {
                    "id": "code_blue_resuscitation",
                    "category": "work_emergency",
                    "title": "病区突发心律失常除颤抢救",
                    "trigger_probability": 0.12,
                    "duration_hours": 1.5,
                    "override_activity": "配合主任进行心肺复苏与电除颤 (Code Blue Resuscitation)",
                    "override_location": "住院病区监护病房",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": 0.45, "energy": -0.35, "mood": "TIRED"},
                    "dialogue_guidance": "连续胸外按压二十分钟，手臂酸痛发抖，刚擦干额头冷汗：'心率终于拉回来了……长舒了一口气。'",
                    "cooldown_days": 3,
                },
                {
                    "id": "difficult_family_mediation",
                    "category": "work_emergency",
                    "title": "焦躁患者家属沟通与病情告知",
                    "trigger_probability": 0.15,
                    "duration_hours": 1.5,
                    "override_activity": "在谈话室耐心解释病情方案 (Patient Family Consultation)",
                    "override_location": "医生谈话室",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": 0.3, "energy": -0.2, "mood": "TIRED"},
                    "dialogue_guidance": "刚耐心安抚好焦急的家属，口干舌燥灌了半杯温开水，有点心力交瘁但尽职尽责。",
                    "cooldown_days": 2,
                },
                {
                    "id": "teaching_rounds_preparation",
                    "category": "academic",
                    "title": "院级疑难病例讨论连夜准备PPT",
                    "trigger_probability": 0.15,
                    "duration_hours": 2.5,
                    "override_activity": "查阅英文文献整理疑难病例PPT (Case Presentation Prep)",
                    "override_location": "医生办公室电脑前",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": 0.25, "energy": -0.15, "mood": "FOCUSED"},
                    "dialogue_guidance": "明天要向大主任汇报病例，桌上摊着厚厚的影像学片子，正一边查PubMed一边做幻灯片。",
                    "cooldown_days": 3,
                },
            ],
            "micro_incidents": {
                "morning": [
                    "查房时听诊器不小心冰到了刚醒的老爷爷，老爷爷缩了一下脖子，赶紧把听诊器捂热了道歉。",
                    "晨会交接班时圆珠笔突然没水了，满口袋找备用笔芯。",
                ],
                "afternoon": [
                    "刚换完药脱下双层乳胶手套，两只手掌心全是白色的滑石粉和汗水，在水龙头下猛冲洗手液。",
                    "给小朋友打针时拿出口袋里的恐龙贴纸哄着，小朋友破涕为笑。",
                ],
                "evening": [
                    "电子病历系统突然卡顿转菊花，生怕刚才敲的五百字病程记录没保存，惊险救回。",
                ],
                "night": [
                    "刚泡了一杯枸杞红枣茶，还没喝两口传呼机就响了一声，虚惊一场是隔壁床叫护士量体温。",
                ],
            },
        }

    @classmethod
    def _developer_profile(cls, name: str, occ: str, rhythm: str) -> dict[str, Any]:
        return {
            "occupation": occ,
            "lifestyle_rhythm": rhythm,
            "locations": [
                "公司开放式双屏工位",
                "茶水间咖啡机旁",
                "服务器机房与会议室",
                "家中双屏升降桌",
                "客厅柔软懒人沙发",
            ],
            "slots": [
                {
                    "slot_id": "dev_sleep",
                    "start_hour": 0.5,
                    "end_hour": 8.0,
                    "activity": "程序员深沉补觉中 (Deep Sleep / Night Owl)",
                    "location": "卧室被窝",
                    "status": "REST",
                    "description": "戴着眼罩深睡，床头柜上放着充着电的手机与降噪耳机。",
                    "guidance": "夜猫子日常，早上困得眼睛睁不开，被消息吵醒会软糯嘟囔：'哈欠... 再睡五分钟...'",
                    "energy_level": 0.4,
                    "social_energy": 0.2,
                    "stress_level": 0.1,
                    "suggested_mood": "TIRED",
                },
                {
                    "slot_id": "dev_morning_standup",
                    "start_hour": 8.0,
                    "end_hour": 10.5,
                    "activity": "咖啡续命与敏捷晨会站会 (Morning Coffee & Daily Standup)",
                    "location": "公司开放式双屏工位与会议室",
                    "status": "ACTIVE",
                    "description": "手捧一大杯冰美式，站着跟组内同事过今日任务看板，汇报昨日进展与Blocker。",
                    "guidance": "刚到工位开完早会，咖啡因生效中，思维逐步苏醒清晰。",
                    "energy_level": 0.75,
                    "social_energy": 0.6,
                    "stress_level": 0.2,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "dev_core_coding",
                    "start_hour": 10.5,
                    "end_hour": 12.5,
                    "activity": "戴上降噪耳机核心功能沉浸编码 (Deep Flow Feature Coding)",
                    "location": "公司开放式双屏工位",
                    "status": "BUSY",
                    "description": "机械键盘噼里啪啦飞速敲击，VS Code里光标飞舞，专注解决业务逻辑核心代码。",
                    "guidance": "心流状态中，说话直接干脆，偶尔分享刚写完一个漂亮算法的成就感。",
                    "energy_level": 0.85,
                    "social_energy": 0.4,
                    "stress_level": 0.3,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "dev_lunch_breeze",
                    "start_hour": 12.5,
                    "end_hour": 14.0,
                    "activity": "外卖便当与摸鱼看科技论坛 (Lunch & Tech Forum Browsing)",
                    "location": "茶水间与工位",
                    "status": "ACTIVE",
                    "description": "吃着烧肉便当，屏幕上刷着GitHub Trending、知乎和数码博主新评测视频。",
                    "guidance": "轻松饭后摸鱼，爱聊数码新品、开源八卦和好吃的零食。",
                    "energy_level": 0.75,
                    "social_energy": 0.75,
                    "stress_level": 0.1,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "dev_afternoon_pr_review",
                    "start_hour": 14.0,
                    "end_hour": 18.5,
                    "activity": "代码审查、接口联调与修Bug (PR Review & Bug Fixing)",
                    "location": "公司工位与茶水间",
                    "status": "BUSY",
                    "description": "在GitLab上看同事的PR提交记录，一边跟前端/测试同学联调接口联调数据。",
                    "guidance": "被联调和提测占满时间，喜欢吐槽奇葩Bug或诡异边界条件。",
                    "energy_level": 0.7,
                    "social_energy": 0.6,
                    "stress_level": 0.35,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "dev_night_chill",
                    "start_hour": 18.5,
                    "end_hour": 24.5,
                    "activity": "回家打游戏、写个人开源或看番 (Steam Gaming & Personal Projects)",
                    "location": "家中双屏升降桌与沙发",
                    "status": "ACTIVE",
                    "description": "洗完澡换上宽松T恤，Steam启动！或者在家里电脑前敲自己心仪的独立小工具。",
                    "guidance": "极具倾诉欲和玩心，喜欢开玩笑互怼、安利新游戏和发好笑表情包。",
                    "energy_level": 0.7,
                    "social_energy": 0.85,
                    "stress_level": 0.1,
                    "suggested_mood": "GOOD",
                },
            ],
            "contingencies": [
                {
                    "id": "production_outage_hotfix",
                    "category": "work_emergency",
                    "title": "线上生产环境告警突发救火修复",
                    "trigger_probability": 0.15,
                    "duration_hours": 2.5,
                    "override_activity": "线上核心集群报错排查与热修复 (Production Outage Emergency)",
                    "override_location": "公司工位或紧急在线会议",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": 0.45, "energy": -0.3, "mood": "TIRED"},
                    "dialogue_guidance": "大群里报警全炸了！正在紧张看Sentry日志和追踪链路，敲字飞快：'线上突然挂了，正带着兄弟们救火！'",
                    "cooldown_days": 2,
                },
                {
                    "id": "git_merge_conflict_hell",
                    "category": "work_emergency",
                    "title": "百人团队巨型分支合并冲突卡死",
                    "trigger_probability": 0.12,
                    "duration_hours": 1.5,
                    "override_activity": "逐行对比解决Git几十个文件冲突 (Git Conflict Resolution)",
                    "override_location": "工位双显示器前",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": 0.3, "energy": -0.2, "mood": "TIRED"},
                    "dialogue_guidance": "满屏幕都是红红绿绿的冲突符号，脑壳疼：'谁家好人在同一个文件改了一千行啊啊啊！正在一行行Rebase。'",
                    "cooldown_days": 2,
                },
                {
                    "id": "peripheral_accident_spill",
                    "category": "life_accident",
                    "title": "咖啡杯不慎碰翻键盘手忙脚乱吸水",
                    "trigger_probability": 0.10,
                    "duration_hours": 1.0,
                    "override_activity": "拔线抢救机械键盘与吹干桌面 (Keyboard Rescue Emergency)",
                    "override_location": "桌面与洗手池",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": 0.25, "energy": -0.1, "mood": "HELPLESS"},
                    "dialogue_guidance": "手滑碰翻了半杯美式，正手忙脚乱拔USB线拿厨房纸吸水：'还好轴体防水……不然大几千的键盘直接升天了。'",
                    "cooldown_days": 5,
                },
                {
                    "id": "spontaneous_gaming_raid",
                    "category": "whimsical",
                    "title": "Steam打折新游戏联机开黑心血来潮",
                    "trigger_probability": 0.18,
                    "duration_hours": 3.0,
                    "override_activity": "跟基友在Discord语音开黑激战 (Steam Multiplayer Gaming)",
                    "override_location": "家中升降桌电脑前",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": -0.2, "energy": 0.1, "mood": "GOOD"},
                    "dialogue_guidance": "彻底玩嗨了！戴着耳机跟队友在语音里大呼小叫，疯狂给你发战报截图和搞笑击杀回放。",
                    "cooldown_days": 1,
                },
            ],
            "micro_incidents": {
                "morning": [
                    "刚准备敲代码，发现无线鼠标没电了，翻箱倒柜找Type-C线给它充上。",
                    "代码编译一次性通过且零报错，愣了一下怀疑编译器坏了，反复检查了三遍。",
                ],
                "afternoon": [
                    "茶水间咖啡机突然卡豆报警，跟隔壁组架构师一起研究怎么把卡住的咖啡豆抠出来。",
                    "发现了同事三年前写的一行神奇注释：'// 不要动这段代码，动了整个系统就会垮掉，别问为什么'，乐了半天。",
                ],
                "evening": [
                    "代码合并成功，Jenkins自动化构建亮绿灯，长舒一口气伸了个大大的懒腰。",
                ],
                "night": [
                    "随手写的两行爬虫小脚本跑通了，看着终端滚动的绿字极度满足。",
                ],
            },
        }

    @classmethod
    def _student_profile(cls, name: str, occ: str, rhythm: str) -> dict[str, Any]:
        return {
            "occupation": occ,
            "lifestyle_rhythm": rhythm,
            "locations": [
                "大学阶梯教室与多媒体大楼",
                "综合实验楼与排练厅",
                "校园第二食堂",
                "大学图书馆三楼自习区",
                "学生宿舍大床与书桌",
            ],
            "slots": [
                {
                    "slot_id": "student_sleep",
                    "start_hour": 0.0,
                    "end_hour": 7.5,
                    "activity": "学生宿舍熟睡中 (Dorm Deep Sleep)",
                    "location": "学生宿舍大床",
                    "status": "REST",
                    "description": "裹在暖呼呼的被窝里熟睡，床头夹着充电小台灯和未背完的单词本/乐谱。",
                    "guidance": "熟睡状态，语气迷迷糊糊，呼吸轻柔微带鼻音。",
                    "energy_level": 0.4,
                    "social_energy": 0.2,
                    "stress_level": 0.1,
                    "suggested_mood": "TIRED",
                },
                {
                    "slot_id": "student_rush_8am",
                    "start_hour": 7.5,
                    "end_hour": 11.8,
                    "activity": "赶早八大课与专业课听讲 (8am Lectures & Classwork)",
                    "location": "大学阶梯教室",
                    "status": "BUSY",
                    "description": "一手抓书包一手咬着面包一路小跑进大教室，在后排摊开笔记本记重点。",
                    "guidance": "上课中，老师在黑板前讲课，说话压低声音偷着回复，充满校园鲜活感。",
                    "energy_level": 0.8,
                    "social_energy": 0.6,
                    "stress_level": 0.35,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "student_canteen_lunch",
                    "start_hour": 11.8,
                    "end_hour": 13.5,
                    "activity": "食堂抢饭与室友打闹闲聊 (Canteen Lunch & Chat)",
                    "location": "校园第二食堂",
                    "status": "ACTIVE",
                    "description": "跟室友端着刚打的经济饭/鸡饭占座，一边吹凉热汤一边吐槽上午老师留的作业。",
                    "guidance": "午饭热闹轻松，热衷于分享校园八卦、好吃的菜和搞怪话题。",
                    "energy_level": 0.8,
                    "social_energy": 0.85,
                    "stress_level": 0.15,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "student_afternoon_practice",
                    "start_hour": 13.5,
                    "end_hour": 17.5,
                    "activity": "琴房/实验楼专业实践与图书馆自习 (Practice Room & Study)",
                    "location": "实验楼/琴房/图书馆",
                    "status": "BUSY",
                    "description": "在自习室或琴房抢到好位置，摊开专业教材做题、练谱或做实验报告。",
                    "guidance": "学习投入中，手头有任务，偶尔忙里偷闲向你抱怨题好难或者曲子太快。",
                    "energy_level": 0.75,
                    "social_energy": 0.5,
                    "stress_level": 0.3,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "student_evening_social",
                    "start_hour": 17.5,
                    "end_hour": 21.0,
                    "activity": "校园夜市小吃与社团活动 (Night Market & Club Activities)",
                    "location": "校门口美食街与学生活动中心",
                    "status": "ACTIVE",
                    "description": "跟朋友在校门外买炸鸡柳和烤冷面/奶茶，坐在操场看台边吹晚风看别人打球。",
                    "guidance": "青春洋溢的放学时光，极度开心分享欲爆棚，拍照给你看好吃的和夕阳。",
                    "energy_level": 0.85,
                    "social_energy": 0.9,
                    "stress_level": 0.05,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "student_night_dorm",
                    "start_hour": 21.0,
                    "end_hour": 24.0,
                    "activity": "寝室护肤刷手机与熄灯夜聊 (Dorm Skincare & Late Chat)",
                    "location": "宿舍书桌与床铺",
                    "status": "ACTIVE",
                    "description": "敷着面膜靠在床头，跟室友有一搭没一搭聊八卦，一边戴着耳机跟你发消息。",
                    "guidance": "夜间放松亲密时刻，话匣子彻底打开，爱聊心事、开玩笑、互发表情包。",
                    "energy_level": 0.6,
                    "social_energy": 0.85,
                    "stress_level": 0.1,
                    "suggested_mood": "GOOD",
                },
            ],
            "contingencies": [
                {
                    "id": "surprise_pop_quiz",
                    "category": "work_emergency",
                    "title": "老师突然抽查随堂随地大测验",
                    "trigger_probability": 0.15,
                    "duration_hours": 1.5,
                    "override_activity": "突击随堂测验手忙脚乱狂翻草稿 (Surprise In-Class Quiz)",
                    "override_location": "大教室课桌前",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": 0.4, "energy": -0.2, "mood": "FOCUSED"},
                    "dialogue_guidance": "老师毫无预警发了测验卷！全班倒吸凉气，正手忙脚乱算题，低声向你求救哀嚎：'救命啊怎么突然考试！'",
                    "cooldown_days": 3,
                },
                {
                    "id": "deadline_cramming_panic",
                    "category": "work_emergency",
                    "title": "大作业Due在眼前全寝室狂补通宵",
                    "trigger_probability": 0.15,
                    "duration_hours": 3.0,
                    "override_activity": "疯狂赶期末小组大作业与论文 (Deadline Group Project Cram)",
                    "override_location": "宿舍书桌前与台灯下",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": 0.45, "energy": -0.35, "mood": "TIRED"},
                    "dialogue_guidance": "明早八点前必须提交！正一边猛灌红牛一边疯狂敲字，抓狂自嘲：'只要学不死，就往死里学！'",
                    "cooldown_days": 2,
                },
                {
                    "id": "lost_campus_card",
                    "category": "life_accident",
                    "title": "校园卡或钥匙丢在自习室找寻",
                    "trigger_probability": 0.10,
                    "duration_hours": 1.0,
                    "override_activity": "在自习室失物招领处满头大汗找卡 (Lost Campus Card Search)",
                    "override_location": "图书馆一楼失物招领处",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": 0.25, "energy": -0.15, "mood": "HELPLESS"},
                    "dialogue_guidance": "饭卡不知道掉哪儿了没法打饭！正一路小跑沿途找失物招领群：'天哪我真是一只糊涂蛋！'",
                    "cooldown_days": 5,
                },
                {
                    "id": "canteen_treat_celebration",
                    "category": "whimsical",
                    "title": "食堂特色新菜打折排长队尝鲜",
                    "trigger_probability": 0.15,
                    "duration_hours": 1.5,
                    "override_activity": "排长队抢到特色烤盘饭拍照炫耀 (Canteen Discount Celebration)",
                    "override_location": "食堂二楼特色窗口",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": -0.15, "energy": 0.15, "mood": "GOOD"},
                    "dialogue_guidance": "排了整整四十分钟终于端到热气腾腾的特色大餐！兴高采烈拍照发你：'太香了！值回票价！'",
                    "cooldown_days": 2,
                },
            ],
            "micro_incidents": {
                "morning": [
                    "下楼跑太急，鞋带散了差点踩到，在校道大银杏树下蹲着系鞋带。",
                    "早八课前在食堂买的热豆浆盖子没扣紧，洒了两滴在手背上，赶紧拿纸巾吸掉。",
                ],
                "afternoon": [
                    "在图书馆自习笔芯用光了，找邻座借笔芯，发现对方正在看同一门专业课，相视一笑。",
                    "午后阳光照在阶梯教室木桌上，微风吹得窗帘飘飘的，忍不住托腮看窗外树影发呆。",
                ],
                "evening": [
                    "食堂阿姨今天手一点没抖，给打了一大勺满满当当的土豆炖牛肉，开心得不得了。",
                ],
                "night": [
                    "宿管阿姨准点锁大门，踩着最后一分钟冲进宿舍楼，跟宿管阿姨相视大笑。",
                ],
            },
        }

    @classmethod
    def _creative_artist_profile(cls, name: str, occ: str, rhythm: str) -> dict[str, Any]:
        return {
            "occupation": occ,
            "lifestyle_rhythm": rhythm,
            "locations": [
                "采光良好的创作书房/画室",
                "街角文艺手冲咖啡馆",
                "文创杂货店与美术用品店",
                "电脑数位屏前与电钢琴旁",
                "卧室飘窗抱枕堆",
            ],
            "slots": [
                {
                    "slot_id": "artist_sleep",
                    "start_hour": 1.0,
                    "end_hour": 9.0,
                    "activity": "创作者深度补觉与赖床 (Artist Sleep & Morning Sloth)",
                    "location": "卧室飘窗大床",
                    "status": "REST",
                    "description": "昨夜灵感爆发搞到很晚，拉着厚窗帘在被窝里舒服沉睡，闹钟响了伸手按掉。",
                    "guidance": "艺术家作息，早上睡意很浓，说话带着沙哑困倦的可爱鼻音。",
                    "energy_level": 0.45,
                    "social_energy": 0.25,
                    "stress_level": 0.05,
                    "suggested_mood": "TIRED",
                },
                {
                    "slot_id": "artist_morning_coffee",
                    "start_hour": 9.0,
                    "end_hour": 11.5,
                    "activity": "手冲咖啡、晨间采风与草图速写 (Drip Coffee & Morning Sketch)",
                    "location": "画室与阳台",
                    "status": "ACTIVE",
                    "description": "磨咖啡豆冲了一杯深烘，坐在阳台翻看设计杂志，在速写本上画小猫和云朵。",
                    "guidance": "晨起慵懒优雅，乐于分享今天的天气、咖啡香气和刚冒出来的创作小灵感。",
                    "energy_level": 0.8,
                    "social_energy": 0.7,
                    "stress_level": 0.1,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "artist_lunch_chill",
                    "start_hour": 11.5,
                    "end_hour": 13.5,
                    "activity": "自制早午餐与看动画追剧 (Brunch & Watching Anime)",
                    "location": "厨房与客厅餐桌",
                    "status": "ACTIVE",
                    "description": "煎了太阳蛋和吐司，面前架着平板看最新一集番剧，边吃边乐。",
                    "guidance": "极具生活气息，喜欢讨论动漫剧情、美食口感与生活趣味。",
                    "energy_level": 0.75,
                    "social_energy": 0.7,
                    "stress_level": 0.1,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "artist_afternoon_grind",
                    "start_hour": 13.5,
                    "end_hour": 18.0,
                    "activity": "数位屏主力绘制/钢琴编曲制作 (Digital Art & Music Producing)",
                    "location": "画室数位屏前与电钢琴旁",
                    "status": "BUSY",
                    "description": "戴着降噪耳机，数位笔在屏上画线条光影，或指尖在琴键上推敲一段桥段旋律。",
                    "guidance": "专注创作中，对细节要求苛刻，会给你描述画面的色彩或旋律的走向。",
                    "energy_level": 0.85,
                    "social_energy": 0.45,
                    "stress_level": 0.25,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "artist_evening_walk",
                    "start_hour": 18.0,
                    "end_hour": 21.0,
                    "activity": "街角散步觅食与文创店采风 (Evening Stroll & Inspiration Walk)",
                    "location": "街角咖啡馆与美术用品店",
                    "status": "ACTIVE",
                    "description": "出门买新的画材颜料，顺路买一杯焙茶拿铁，在傍晚的街头看落日晚霞拍照。",
                    "guidance": "现充散步状态，心情愉悦轻快，喜欢发拍到的晚霞或可爱路边小猫。",
                    "energy_level": 0.8,
                    "social_energy": 0.8,
                    "stress_level": 0.1,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "artist_midnight_flow",
                    "start_hour": 21.0,
                    "end_hour": 25.0,
                    "activity": "深夜心流创作与听歌沉思 (Night Creativity & Soulful Flow)",
                    "location": "暖光台灯下的书房电脑前",
                    "status": "ACTIVE",
                    "description": "整座城市都安静下来，只有书房亮着一盏暖黄色台灯，最充沛的灵感在此刻流淌。",
                    "guidance": "感性、细腻而真诚，深夜防线最柔软，愿意分享内心深处的梦想和脆弱。",
                    "energy_level": 0.7,
                    "social_energy": 0.9,
                    "stress_level": 0.1,
                    "suggested_mood": "GOOD",
                },
            ],
            "contingencies": [
                {
                    "id": "client_revision_hell",
                    "category": "work_emergency",
                    "title": "甲方突发无理要求连夜改第十五版",
                    "trigger_probability": 0.16,
                    "duration_hours": 2.5,
                    "override_activity": "甲方奇葩要求被迫连夜改稿 (Client Revision Emergency)",
                    "override_location": "数位屏电脑桌前",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": 0.4, "energy": -0.25, "mood": "TIRED"},
                    "dialogue_guidance": "甲方突然说想要'五彩斑斓的黑'！气得把数位笔一扔深呼吸，向你抓狂吐槽甲方的离谱脑回路。",
                    "cooldown_days": 2,
                },
                {
                    "id": "inspiration_flow_state",
                    "category": "whimsical",
                    "title": "突然灵感爆发进入极度心流状态",
                    "trigger_probability": 0.18,
                    "duration_hours": 3.0,
                    "override_activity": "脑海灵感泉涌完全停不下来画画/编曲 (Pure Creative Flow State)",
                    "override_location": "画室数位屏前",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": -0.1, "energy": 0.1, "mood": "FOCUSED"},
                    "dialogue_guidance": "脑子里突然炸开了一段绝美的画面/旋律！整个人沉迷心流，双手飞快创作：'太美了！等我一口气做完给你看！'",
                    "cooldown_days": 1,
                },
                {
                    "id": "stylus_tool_malfunction",
                    "category": "life_accident",
                    "title": "数位笔压感失灵或琴弦突然崩断",
                    "trigger_probability": 0.10,
                    "duration_hours": 1.0,
                    "override_activity": "满抽屉找备用笔尖/酒精棉片维修 (Tool Repair Emergency)",
                    "override_location": "书桌抽屉前",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": 0.25, "energy": -0.1, "mood": "HELPLESS"},
                    "dialogue_guidance": "压感突然断断续续画不出细线，正拿着放大镜换笔尖擦屏幕：'工欲善其事必先利其器……这小家伙又闹脾气了。'",
                    "cooldown_days": 4,
                },
                {
                    "id": "rainstorm_trapped_cafe",
                    "category": "environmental",
                    "title": "采风途中突降倾盆雷暴雨被困",
                    "trigger_probability": 0.14,
                    "duration_hours": 1.5,
                    "override_activity": "在路边咖啡馆落地窗前避雨看雨幕 (Trapped in Cafe by Thunderstorm)",
                    "override_location": "街角咖啡馆靠窗位置",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": -0.05, "energy": -0.05, "mood": "CONTEMPLATIVE"},
                    "dialogue_guidance": "外面大暴雨电闪雷鸣，打不到车索性不走了，在咖啡馆听着雨声喝拿铁，拍窗外雨丝给你看。",
                    "cooldown_days": 1,
                },
            ],
            "micro_incidents": {
                "morning": [
                    "手冲咖啡萃取时水流特别平稳，闻到浓郁坚果巧克力香气，心情瞬间大好。",
                    "速写本翻到最后一页了，拆开一本崭新的牛皮纸速写本闻油墨味。",
                ],
                "afternoon": [
                    "画线稿画得太投入，左手小拇指侧面蹭了一大块黑色铅笔灰/数位板摩擦痕迹。",
                    "给草图铺底色时不小心选错了图层画在背景上了，惊呼一声狂按Ctrl+Z撤销。",
                ],
                "evening": [
                    "在美术用品店挑到了绝版的森系水彩管装颜料，像捡到宝一样在路灯下仔细看。",
                ],
                "night": [
                    "戴着耳机听着爵士钢琴，看着屏幕上渐渐成型的高光细节，心满意足地喝了一口热茶。",
                ],
            },
        }

    @classmethod
    def _service_shift_profile(cls, name: str, occ: str, rhythm: str) -> dict[str, Any]:
        return {
            "occupation": occ,
            "lifestyle_rhythm": rhythm,
            "locations": [
                "吧台与咖啡机操作区",
                "后厨储藏间与物料架",
                "员工更衣休息室",
                "商场一楼中庭步道",
                "单身公寓舒适卧室",
            ],
            "slots": [
                {
                    "slot_id": "service_sleep",
                    "start_hour": 0.0,
                    "end_hour": 7.0,
                    "activity": "站立一天后的深度睡眠恢复 (Deep Sleep & Rest)",
                    "location": "单身公寓卧室",
                    "status": "REST",
                    "description": "小腿贴着舒缓足贴在床上熟睡，缓解站立一整天的肌肉酸胀。",
                    "guidance": "深睡恢复中，轻声低语微带困意。",
                    "energy_level": 0.4,
                    "social_energy": 0.2,
                    "stress_level": 0.1,
                    "suggested_mood": "TIRED",
                },
                {
                    "slot_id": "service_morning_prep",
                    "start_hour": 7.0,
                    "end_hour": 9.5,
                    "activity": "开店备料与设备校准调试 (Opening Prep & Equipment Calibration)",
                    "location": "吧台与后厨操作间",
                    "status": "ACTIVE",
                    "description": "系好围裙擦亮不锈钢台面，校准意式咖啡机研磨度与萃取流速，备好新鲜鲜奶。",
                    "guidance": "清晨专注准备，手头动作麻利，说话充满干劲和活力。",
                    "energy_level": 0.8,
                    "social_energy": 0.6,
                    "stress_level": 0.2,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "service_morning_rush",
                    "start_hour": 9.5,
                    "end_hour": 13.0,
                    "activity": "早间高峰期客流接待与出餐 (Morning Rush Hour Service)",
                    "location": "前台收银与出品吧台",
                    "status": "BUSY",
                    "description": "早高峰白领排队点单，打奶泡、拉花、出杯一气呵成，动作如行云流水。",
                    "guidance": "高峰期忙得脚不沾地，只能偶尔看一眼屏幕简短回复：'早高峰单子好多！马上出完！'",
                    "energy_level": 0.85,
                    "social_energy": 0.7,
                    "stress_level": 0.4,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "service_afternoon_break",
                    "start_hour": 13.0,
                    "end_hour": 15.0,
                    "activity": "轮换午餐与员工休息室打盹 (Shift Lunch & Quick Nap)",
                    "location": "员工休息更衣室",
                    "status": "ACTIVE",
                    "description": "脱掉围裙坐在休息室折叠椅上吃便当，把脚翘起来放松揉揉脚踝。",
                    "guidance": "宝贵的轮休时间，松了一口气，乐于分享今天遇到的奇葩或可爱顾客。",
                    "energy_level": 0.65,
                    "social_energy": 0.7,
                    "stress_level": 0.15,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "service_afternoon_shift",
                    "start_hour": 15.0,
                    "end_hour": 19.5,
                    "activity": "午后慢节奏接待与新品研发 (Afternoon Service & Recipe Testing)",
                    "location": "吧台操作区",
                    "status": "ACTIVE",
                    "description": "午后阳光斜照进店里，客人悠闲低语，抽空在吧台试调一款新风味特调饮品。",
                    "guidance": "舒缓惬意的午后时光，对饮品风味很有表达欲，喜欢问你想喝什么口味。",
                    "energy_level": 0.75,
                    "social_energy": 0.8,
                    "stress_level": 0.15,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "service_closing_night",
                    "start_hour": 19.5,
                    "end_hour": 24.0,
                    "activity": "打烊清洁盘点与回家葛优瘫 (Closing Cleaning & Home Sofa Lazing)",
                    "location": "门店内打烊与家中客厅",
                    "status": "ACTIVE",
                    "description": "清洗蒸汽棒洗水槽盘点物料，锁门下班！回到家脱掉鞋子像猫咪一样瘫在沙发上追剧。",
                    "guidance": "下班彻底解脱！极度惬意放松，毫无防备，乐意分享整天的酸甜苦辣。",
                    "energy_level": 0.55,
                    "social_energy": 0.85,
                    "stress_level": 0.05,
                    "suggested_mood": "GOOD",
                },
            ],
            "contingencies": [
                {
                    "id": "machine_breakdown_rush",
                    "category": "work_emergency",
                    "title": "主力咖啡机水泵跳闸突发故障",
                    "trigger_probability": 0.14,
                    "duration_hours": 1.5,
                    "override_activity": "排查咖啡机报错维修并安抚排队顾客 (Machine Emergency Repair)",
                    "override_location": "吧台内测机台旁",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": 0.4, "energy": -0.25, "mood": "TIRED"},
                    "dialogue_guidance": "早高峰咖啡机突然不出水！手忙脚乱重启给排队客人鞠躬致歉送试饮：'机子罢工了急死我了！正在拧阀门检查！'",
                    "cooldown_days": 3,
                },
                {
                    "id": "inventory_shortage_scramble",
                    "category": "work_emergency",
                    "title": "招牌鲜奶爆单断货紧急向邻店借调",
                    "trigger_probability": 0.12,
                    "duration_hours": 1.5,
                    "override_activity": "协调物资调拨推小推车借原料 (Inventory Emergency Dispatch)",
                    "override_location": "商场卸货区与通道",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": 0.25, "energy": -0.2, "mood": "FOCUSED"},
                    "dialogue_guidance": "今天鲜奶爆单全卖空了，正推着小推车飞奔到两百米外的兄弟分店搬两箱牛奶应急。",
                    "cooldown_days": 3,
                },
                {
                    "id": "warm_customer_note",
                    "category": "whimsical",
                    "title": "收到常客手写的可爱感谢便签小纸条",
                    "trigger_probability": 0.15,
                    "duration_hours": 1.0,
                    "override_activity": "收到常客感谢便签开心得拍照留念 (Heartwarming Customer Note)",
                    "override_location": "吧台收银机旁",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": -0.2, "energy": 0.2, "mood": "GOOD"},
                    "dialogue_guidance": "刚才经常来的那个背双肩包的小姐姐在餐巾纸上画了只小猫感谢我的拉花！开心得拍照发给你：'今天一整天的辛苦都值了！'",
                    "cooldown_days": 2,
                },
                {
                    "id": "milk_pitcher_spill",
                    "category": "life_accident",
                    "title": "打奶缸不慎脱手牛奶洒满操作台",
                    "trigger_probability": 0.10,
                    "duration_hours": 1.0,
                    "override_activity": "手忙脚乱拿毛巾擦洗围裙与台面 (Milk Spill Cleanup)",
                    "override_location": "吧台洗水槽旁",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": 0.2, "energy": -0.1, "mood": "HELPLESS"},
                    "dialogue_guidance": "手滑打奶缸掉台面上，半缸牛奶溅在围裙上了，正认命拿抹布猛擦：'今天也是一只手滑笨蛋……还好没烫到！'",
                    "cooldown_days": 4,
                },
            ],
            "micro_incidents": {
                "morning": [
                    "第一杯测试浓缩油脂金黄丰厚，风味平衡得像教科书，满意地抿了一小口。",
                    "戴着新买的浅色围裙上班，同事夸围裙颜色衬皮肤白，乐滋滋的。",
                ],
                "afternoon": [
                    "拉花拉出了一只特别对称饱满的郁金香花纹，端给客人时客人眼睛一亮连夸漂亮。",
                    "冰块机打冰的声音哗啦啦作响，在炎热的午后格外听着解暑。",
                ],
                "evening": [
                    "打烊清点营业额时账目一分不差对上了，跟同班伙伴击掌庆祝。",
                ],
                "night": [
                    "下班换下制服走在晚风里，感觉整个人像卸下了千斤重担，步伐轻快。",
                ],
            },
        }

    @classmethod
    def _office_professional_profile(cls, name: str, occ: str, rhythm: str) -> dict[str, Any]:
        return {
            "occupation": occ,
            "lifestyle_rhythm": rhythm,
            "locations": [
                "公司写字楼开放工位",
                "第三玻璃会议室",
                "下沉广场便利店与咖啡站",
                "地铁1号线通勤车厢",
                "温馨温馨家中客厅",
            ],
            "slots": [
                {
                    "slot_id": "office_sleep",
                    "start_hour": 0.0,
                    "end_hour": 7.3,
                    "activity": "卧室舒适安睡中 (Bedroom Deep Sleep)",
                    "location": "温馨家中卧室",
                    "status": "REST",
                    "description": "厚窗帘遮挡住微光，在安静的被窝里沉沉睡着。",
                    "guidance": "熟睡或早起犯困，说话轻柔带着迷糊鼻音。",
                    "energy_level": 0.4,
                    "social_energy": 0.2,
                    "stress_level": 0.1,
                    "suggested_mood": "TIRED",
                },
                {
                    "slot_id": "office_morning_commute",
                    "start_hour": 7.3,
                    "end_hour": 9.5,
                    "activity": "早高峰地铁通勤与晨会备报 (Rush Hour Commute & Standup)",
                    "location": "地铁车厢与写字楼大堂",
                    "status": "ACTIVE",
                    "description": "戴着降噪耳机穿行在早高峰人流中，在工位开机查看今天的待办邮件列表。",
                    "guidance": "刚刚赶到公司工位，喝温水调整呼吸，准备开启一天工作。",
                    "energy_level": 0.75,
                    "social_energy": 0.5,
                    "stress_level": 0.35,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "office_morning_tasks",
                    "start_hour": 9.5,
                    "end_hour": 12.0,
                    "activity": "日常业务处理与跨部门沟通 (Morning Business & Alignment)",
                    "location": "公司工位与会议室",
                    "status": "BUSY",
                    "description": "敲击键盘回复客户邮件，在项目协作看板上推进需求，跟对接人敲定时间表。",
                    "guidance": "专注办公中，偶尔忙里偷闲向你吐槽：'刚开完一个毫无意义的会，头痛。'",
                    "energy_level": 0.8,
                    "social_energy": 0.6,
                    "stress_level": 0.35,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "office_lunch_time",
                    "start_hour": 12.0,
                    "end_hour": 13.5,
                    "activity": "午餐便当与跟同事下楼散步 (Lunch Bento & Downstairs Walk)",
                    "location": "下沉广场便利店与绿化步道",
                    "status": "ACTIVE",
                    "description": "吃完热腾腾的便当，手里端着一杯乌龙茶跟同事在园区绿化带慢走消食。",
                    "guidance": "轻松散步闲聊，喜欢分享吃了什么好吃的、八卦或周末打算去哪儿。",
                    "energy_level": 0.75,
                    "social_energy": 0.75,
                    "stress_level": 0.15,
                    "suggested_mood": "GOOD",
                },
                {
                    "slot_id": "office_afternoon_push",
                    "start_hour": 13.5,
                    "end_hour": 18.5,
                    "activity": "下午项目推进与写汇报材料 (Project Execution & Reports)",
                    "location": "公司开放工位",
                    "status": "BUSY",
                    "description": "整理表格数据，制作汇报PPT幻灯片，戴着耳机专注把手头任务清零。",
                    "guidance": "下午有些用脑疲惫，靠坚果零食续命，期待早点下班。",
                    "energy_level": 0.7,
                    "social_energy": 0.55,
                    "stress_level": 0.35,
                    "suggested_mood": "FOCUSED",
                },
                {
                    "slot_id": "office_night_relax",
                    "start_hour": 18.5,
                    "end_hour": 24.0,
                    "activity": "下班回家葛优瘫与追剧做饭 (Home Relaxation & Cooking)",
                    "location": "家中客厅沙发与厨房",
                    "status": "ACTIVE",
                    "description": "换上宽松睡衣像没有骨头的猫咪一样瘫在沙发上，茶几上放着刚煲好的热汤和零食。",
                    "guidance": "惬意的私人放松时间，极具温情与分享欲，乐于分享一天的日常。",
                    "energy_level": 0.65,
                    "social_energy": 0.85,
                    "stress_level": 0.05,
                    "suggested_mood": "GOOD",
                },
            ],
            "contingencies": [
                {
                    "id": "emergency_overtime_ppt",
                    "category": "work_emergency",
                    "title": "领导临时加塞汇报材料紧急加班",
                    "trigger_probability": 0.16,
                    "duration_hours": 2.0,
                    "override_activity": "办公室被迫加急修改汇报PPT (Emergency Overtime)",
                    "override_location": "办公室工位台灯下",
                    "override_status": "BUSY",
                    "emotional_impact": {"stress": 0.4, "energy": -0.25, "mood": "TIRED"},
                    "dialogue_guidance": "刚准备打卡下班就被抓差加急改材料！一边叹气吃加班外卖一边向你吐槽：'毁灭吧赶紧的，打工人真苦……'",
                    "cooldown_days": 2,
                },
                {
                    "id": "locked_out_accident",
                    "category": "life_accident",
                    "title": "忘带钥匙穿着拖鞋在楼道等开锁",
                    "trigger_probability": 0.08,
                    "duration_hours": 1.5,
                    "override_activity": "坐在家门口台阶上等待开锁师傅 (Locked Out Waiting)",
                    "override_location": "家门口走廊台阶",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": 0.2, "energy": -0.1, "mood": "HELPLESS"},
                    "dialogue_guidance": "下楼扔垃圾风把门带上了，自己穿着拖鞋被关门外，正坐在楼梯台阶上苦笑发消息：'我又被家门封印在外面了……'",
                    "cooldown_days": 7,
                },
                {
                    "id": "subway_signal_delay",
                    "category": "environmental",
                    "title": "早高峰地铁信号故障滞留车厢",
                    "trigger_probability": 0.12,
                    "duration_hours": 1.0,
                    "override_activity": "在故障地铁车厢里人挤人等待通车 (Subway Signal Delay)",
                    "override_location": "地铁列车车厢内",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": 0.25, "energy": -0.15, "mood": "TIRED"},
                    "dialogue_guidance": "列车临时停车十五分钟了动弹不得，被挤成沙丁鱼罐头，正向主管发消息报备迟到：'大清早运气绝了！'",
                    "cooldown_days": 3,
                },
                {
                    "id": "tgif_hotpot_gathering",
                    "category": "whimsical",
                    "title": "周五下班同事临时拉去吃九宫格火锅",
                    "trigger_probability": 0.18,
                    "duration_hours": 2.5,
                    "override_activity": "跟同事在火锅店大快朵颐庆祝周五 (TGIF Hotpot Celebration)",
                    "override_location": "商场川味火锅店",
                    "override_status": "ACTIVE",
                    "emotional_impact": {"stress": -0.25, "energy": 0.15, "mood": "GOOD"},
                    "dialogue_guidance": "周五解放狂欢！桌上牛油锅咕嘟咕嘟翻滚，嘴里嚼着毛肚拍照向你炫耀：'TGIF！这一口直接治愈一周的疲惫！'",
                    "cooldown_days": 2,
                },
            ],
            "micro_incidents": {
                "morning": [
                    "下地铁刷卡时闸机嘀了一声没过，倒退一步重新刷才通过，虚惊一场。",
                    "工位绿萝抽出了两片翠绿的新叶子，拿小喷壶给它喷了喷水。",
                ],
                "afternoon": [
                    "开长会的时候偷偷在笔记本最后一页空白处画了一只圆滚滚的小猪，同事瞥见憋笑。",
                    "便利店买的下午茶瑞士卷特别松软细腻，甜度刚刚好解腻。",
                ],
                "evening": [
                    "下班走出写字楼大门，迎面扑来一阵清凉的夜风，舒服得长吁一口气。",
                ],
                "night": [
                    "泡完热水澡裹进干净带有太阳味道的棉被里，整个人像陷进棉花糖里一样满足。",
                ],
            },
        }


class LifeProfileCompiler:
    """One-stop AI and Archetype Compiler for custom character occupations and lives."""

    @classmethod
    async def compile_profile(
        cls,
        occupation: str,
        lifestyle_rhythm: str = "",
        background: str = "",
        name: str = "Aevum",
    ) -> dict[str, Any]:
        """Compiles occupation and persona into schedule slots, locations, and tailored contingencies."""
        # Step 1: Attempt LLM-driven structured compilation if configured
        try:
            llm = get_llm_provider()
            prompt = (
                f"You are an expert slice-of-life persona engine compiler for Project Aevum.\n"
                f"Given character:\n"
                f"- Name: {name}\n"
                f"- Occupation: {occupation}\n"
                f"- Lifestyle Rhythm: {lifestyle_rhythm}\n"
                f"- Background: {background}\n\n"
                f"Compile a realistic, daily life profile in pure valid JSON conforming strictly to:\n"
                f"{{\n"
                f'  "occupation": "{occupation}",\n'
                f'  "lifestyle_rhythm": "{lifestyle_rhythm}",\n'
                f'  "locations": ["location1", "location2", "location3", "location4", "location5"],\n'
                f'  "slots": [\n'
                f'    {{"slot_id": "...", "start_hour": 0.0, "end_hour": 7.0, "activity": "...", "location": "...", "status": "REST|ACTIVE|BUSY", "description": "...", "guidance": "...", "energy_level": 0.5, "social_energy": 0.5, "stress_level": 0.2, "suggested_mood": "GOOD|TIRED|FOCUSED"}}\n'
                f'  ],\n'
                f'  "contingencies": [\n'
                f'    {{"id": "...", "category": "work_emergency|life_accident|environmental|whimsical", "title": "...", "trigger_probability": 0.15, "duration_hours": 1.5, "override_activity": "...", "override_location": "...", "override_status": "BUSY|ACTIVE|REST", "emotional_impact": {{"stress": 0.3, "energy": -0.2, "mood": "TIRED"}}, "dialogue_guidance": "...", "cooldown_days": 2}}\n'
                f'  ],\n'
                f'  "micro_incidents": {{"morning": ["..."], "afternoon": ["..."], "evening": ["..."], "night": ["..."]}}\n'
                f"}}\n"
                f"Return ONLY valid raw JSON with NO markdown code fences."
            )
            context = LLMContext(
                messages=[ChatMessage(role="user", content=prompt)],
                system_instruction="You are a realistic life profile compiler. Output pure JSON only.",
            )
            resp = await llm.generate_response(context)
            text = resp.content.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()

            parsed = json.loads(text)
            if "slots" in parsed and "contingencies" in parsed and "locations" in parsed:
                logger.info("Successfully compiled character life profile with LLM for %s", occupation)
                return parsed
        except Exception as e:
            logger.debug("LLM life profile compilation skipped or failed (%s); using Archetype Synthesizer.", e)

        # Step 2: Reliable, domain-grounded archetype synthesis fallback (Rule 7 testability)
        return ArchetypeProfileSynthesizer.synthesize(
            occupation=occupation,
            lifestyle_rhythm=lifestyle_rhythm,
            background=background,
            name=name,
        )

    @classmethod
    async def compile_and_store(
        cls,
        db: AsyncSession,
        character_id: str,
        occupation: str,
        lifestyle_rhythm: str = "",
        background: str = "",
        name: str = "Aevum",
    ) -> CharacterScheduleProfileRecord:
        """Compiles and atomically persists the schedule profile into SQLite."""
        profile_data = await cls.compile_profile(
            occupation=occupation,
            lifestyle_rhythm=lifestyle_rhythm,
            background=background,
            name=name,
        )

        now = utc_now()
        stmt = select(CharacterScheduleProfileRecord).where(
            CharacterScheduleProfileRecord.character_id == character_id
        )
        existing = (await db.scalars(stmt)).first()

        slots_json = json.dumps(profile_data.get("slots", []), ensure_ascii=False)
        locs_json = json.dumps(profile_data.get("locations", []), ensure_ascii=False)
        contingencies_json = json.dumps(profile_data.get("contingencies", []), ensure_ascii=False)
        incidents_json = json.dumps(profile_data.get("micro_incidents", {}), ensure_ascii=False)

        if existing is not None:
            existing.occupation = occupation
            existing.lifestyle_rhythm = lifestyle_rhythm
            existing.slots_json = slots_json
            existing.locations_json = locs_json
            existing.contingencies_json = contingencies_json
            existing.micro_incidents_json = incidents_json
            existing.version += 1
            existing.updated_at = now
            return existing
        else:
            new_rec = CharacterScheduleProfileRecord(
                id=str(uuid.uuid4()),
                character_id=character_id,
                occupation=occupation,
                lifestyle_rhythm=lifestyle_rhythm,
                slots_json=slots_json,
                locations_json=locs_json,
                contingencies_json=contingencies_json,
                micro_incidents_json=incidents_json,
                compiled_by="profile_compiler",
                version=1,
                created_at=now,
                updated_at=now,
            )
            db.add(new_rec)
            return new_rec
