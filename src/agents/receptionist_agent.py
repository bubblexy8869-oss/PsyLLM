from __future__ import annotations
import asyncio
from typing import Any, Dict, Callable, List
from copy import deepcopy

from utils.prompt_utils import render_prompt, call_json_with_stream_legacy
from services.event_types import StreamEvent, StreamEventType
from graph.common import add_ai_message

REQUIRED_FIELDS = [
    # 基本信息
    "name_or_nickname",  # 姓名可选，若不愿提供，用昵称；内部折叠到 name/nickname
    "gender",
    "age",
    # 婚姻
    "marital_status",         # 在婚/离婚/丧偶/分居
    "marriage_type",          # 初婚/再婚（仅在婚时）
    "marriage_duration_years",
    # 配偶
    "spouse_age",
    "spouse_occupation",
    "spouse_prior_marriage",
    # 子女：可能多条，这里用 children_count 先收数量，随后逐条细化
    "children_count"
]

def _normalize_profile_fields(updated: Dict[str, Any]) -> Dict[str, Any]:
    """
    将 LLM 返回的 updated_fields 标准化到 GraphState.profile 结构：
    {
      name/nickname, gender, age,
      marital_status, marriage_type, marriage_duration_years,
      spouse: {age, occupation, prior_marriage},
      children: [{age, gender, relation}, ...]
    }
    """
    norm = {}

    # name / nickname
    name = updated.get("name") or None
    nickname = updated.get("nickname") or None
    name_or_nick = updated.get("name_or_nickname")
    if name_or_nick and not (name or nickname):
        # 如果模型只给了一个组合字段，优先按“昵称”落位（保护隐私）
        nickname = name_or_nick

    if name: norm["name"] = name
    if nickname: norm["nickname"] = nickname

    # 单值
    for k_src, k_dst in [
        ("gender", "gender"),
        ("age", "age"),
        ("marital_status", "marital_status"),
        ("marriage_type", "marriage_type"),
        ("marriage_duration_years", "marriage_duration_years"),
    ]:
        v = updated.get(k_src)
        if v not in (None, ""):
            norm[k_dst] = v

    # 配偶
    spouse = {}
    if updated.get("spouse_age") not in (None, ""):
        spouse["age"] = updated.get("spouse_age")
    if updated.get("spouse_occupation") not in (None, ""):
        spouse["occupation"] = updated.get("spouse_occupation")
    if updated.get("spouse_prior_marriage") not in (None, ""):
        spouse["prior_marriage"] = updated.get("spouse_prior_marriage")
    if spouse:
        norm["spouse"] = spouse

    # 子女
    children = []
    # 结构化 children 优先
    if isinstance(updated.get("children"), list):
        for ch in updated["children"]:
            if not isinstance(ch, dict): continue
            rec = {}
            if ch.get("age") not in (None, ""): rec["age"] = ch.get("age")
            if ch.get("gender") not in (None, ""): rec["gender"] = ch.get("gender")
            if ch.get("relation") not in (None, ""): rec["relation"] = ch.get("relation")  # 亲生/继子/领养
            if rec: children.append(rec)
    # 如果只提供了 children_count，可先占位
    cc = updated.get("children_count")
    if isinstance(cc, int) and cc > 0 and not children:
        for _ in range(cc):
            children.append({})
    if children:
        norm["children"] = children

    return norm

def _merge_profile(old: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    prof = deepcopy(old or {})
    for k, v in patch.items():
        if k == "spouse":
            prof.setdefault("spouse", {})
            prof["spouse"].update(v or {})
        elif k == "children":
            # 简单策略：若已有 children，逐条对齐更新，否则直接覆盖
            if prof.get("children"):
                # 对齐长度
                while len(prof["children"]) < len(v):
                    prof["children"].append({})
                for i, rec in enumerate(v):
                    prof["children"][i].update(rec or {})
            else:
                prof["children"] = v
        else:
            prof[k] = v
    return prof

def _missing_fields(profile: Dict[str, Any]) -> List[str]:
    missing = []
    # 展开 profile 判断缺失
    if not (profile.get("name") or profile.get("nickname")):
        missing.append("name_or_nickname")
    if not profile.get("gender"): missing.append("gender")
    if not profile.get("age"): missing.append("age")

    if not profile.get("marital_status"): missing.append("marital_status")
    # marriage_type 仅在婚时收集
    if profile.get("marital_status") in ("在婚", "在婚-初婚", "在婚-再婚", "在婚(初婚)", "在婚(再婚)"):
        if not profile.get("marriage_type"): missing.append("marriage_type")
        if not profile.get("marriage_duration_years"): missing.append("marriage_duration_years")

    sp = profile.get("spouse") or {}
    if not sp.get("age"): missing.append("spouse_age")
    if not sp.get("occupation"): missing.append("spouse_occupation")
    if not sp.get("prior_marriage"): missing.append("spouse_prior_marriage")

    ch = profile.get("children") or []
    if not ch:
        # 尚未收集子女条目时，用 children_count 先问数量
        missing.append("children_count")
    else:
        # 若有占位但信息空，可在后续轮次继续追问
        for i, rec in enumerate(ch):
            if not rec.get("age") or not rec.get("gender") or not rec.get("relation"):
                # 在提示里会逐条引导完善，这里不用标具体键名
                pass
    return missing

async def run_receptionist(
    state: Dict[str, Any],
    emit: Callable[[StreamEvent], Any],
    llm_client,
) -> Dict[str, Any]:
    """
    Prompt 期望输出（JSON）：
    {
      "empathic_opening": "...",      # 温和开场
      "updated_fields": {...},        # 可包含 name/nickname/gender/.../spouse_*/children/children_count
      "ask_next": "...",              # 若仍缺字段，给下一问
      "notes": ["..."]                # 可选：任何有助于后续评估的备注
    }
    """
    # 检查是否是"用户刚刚回复后"的解析轮
    # 优先从messages中获取最新用户消息，如果没有则从last_user_reply获取
    last_reply = ""
    if state.get("messages"):
        # 从messages中获取最新的人类消息
        from graph.common import get_latest_human_message
        last_reply = get_latest_human_message(state)
    else:
        # 兼容旧的方式
        last_reply = (state.get("last_user_reply") or "").strip()
    
    profile = deepcopy(state.get("profile") or {})
    missing_before = _missing_fields(profile)
    
    # 如果有用户回复且不在messages中，将其添加到消息历史中
    if last_reply and not state.get("messages"):
        add_ai_message(state, "user", last_reply)
        # 清除last_user_reply，避免重复处理
        state["last_user_reply"] = ""

    prompt = render_prompt("receptionist", {
        "profile": profile,
        "missing_fields": missing_before,
        "last_user_reply": last_reply,
        "policy": {
            "name_optional": True,
            "allow_nickname": True,
            "allow_skip_unknown": True,
            "tone": "咨询师风格，温和、不评判、非查表",
        }
    })

    async def _emit_token(tok: str):
        await emit(StreamEvent(type=StreamEventType.token, payload={"text": tok}, node="Receptionist"))

    data = call_json_with_stream_legacy(llm_client, prompt, on_token=lambda t: asyncio.create_task(_emit_token(t)))

    # 1) 合并结构化字段
    updated_fields = data.get("updated_fields") or {}
    patch = _normalize_profile_fields(updated_fields)
    state["profile"] = _merge_profile(profile, patch)

    # 2) 记录备注
    if isinstance(data.get("notes"), list):
        state.setdefault("exploration_notes", []).extend([n for n in data["notes"] if isinstance(n, str)])

    # 3) 计算缺失 & 决定下一步
    missing_after = _missing_fields(state["profile"])
    state["profile_completeness"] = float((len(REQUIRED_FIELDS) - len(missing_after)) / len(REQUIRED_FIELDS))

    # 4) 输出对话（开场 + 下一问）
    opening = data.get("empathic_opening")
    if opening:
        # 只添加消息到状态，不发送emit事件
        add_ai_message(state, "assistant", opening)
    
    if missing_after:
        # 仍有缺失 → 给下一问，并保持等待用户输入
        ask_next = data.get("ask_next") or "您愿意先告诉我一个称呼（可以用昵称），以及您的性别和年龄吗？"
        # 只添加消息到状态
        add_ai_message(state, "assistant", ask_next)
        state["awaiting_user_reply"] = True
    else:
        # 资料齐全 → 简短收尾
        closing = data.get("closing") or "谢谢你的配合，这些信息会帮助我更好地理解你的处境。接下来我们会一起梳理你目前最关心的困扰。"
        # 只添加消息到状态
        add_ai_message(state, "assistant", closing)
        state["awaiting_user_reply"] = False

    # 5) 完成事件
    await emit(StreamEvent(type=StreamEventType.node_end, payload={
        "stage": "Receptionist",
        "profile_completeness": state.get("profile_completeness")
    }))
    return state