import asyncio
from app.character.engine import CharacterEngine
from app.character.prompt_assembler import ResponseContextAssembler
from app.db.session import async_session_factory
from app.llm.base import ChatMessage
from app.llm.gemini import GeminiProvider
from google.genai import types

async def debug():
    async with async_session_factory() as session:
        engine = CharacterEngine(session=session)
        history = [
            ChatMessage(role="user", content="我平时一般都一点多两点才睡，算是深度夜猫子了。"),
            ChatMessage(role="assistant", content="这么晚啊，平时第二天不会困吗？"),
            ChatMessage(role="user", content="习惯了，晚上比较安静有灵感。"),
            ChatMessage(role="assistant", content="也是，晚上确实没人打扰。"),
        ]
        ctx = await engine.build_response_context(
            user_input="今晚又要写代码写到凌晨两点了……",
            character_id="aevum",
            user_id="user"
        )
        llm_context = ResponseContextAssembler.assemble(ctx, history)
        provider = GeminiProvider()
        contents, resolved_system = provider._convert_context_to_gemini(llm_context)
        config = types.GenerateContentConfig(
            system_instruction=resolved_system,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )
        resp = await provider._client.aio.models.generate_content(
            model=provider.model_name,
            contents=contents,
            config=config,
        )
        cand = resp.candidates[0]
        print("Cand dict:", cand.model_dump() if hasattr(cand, "model_dump") else cand)
        if hasattr(resp, "prompt_feedback"):
            print("Prompt feedback:", resp.prompt_feedback)

if __name__ == "__main__":
    asyncio.run(debug())
