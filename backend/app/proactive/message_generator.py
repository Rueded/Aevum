"""Proactive Message Generator (Phase 8 Lock-in 6, 13).

Generates character-grounded proactive reach-out messages strictly bounded by
ProactiveContext and validated through OutputBoundaryGuard.
"""

import logging
from typing import Optional

from app.character.integrity import OutputBoundaryGuard
from app.llm.base import ChatMessage, LLMProvider
from app.proactive.models import ProactiveContext, ProactiveIntentType

logger = logging.getLogger(__name__)


class ProactiveMessageGenerator:
    """Generates dialogue for proactive reach-outs bounded by canonical context."""

    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        guard: Optional[OutputBoundaryGuard] = None,
    ) -> None:
        self._llm_provider = llm_provider
        self._guard = guard or OutputBoundaryGuard()

    def _format_grounded_fallback(self, context: ProactiveContext) -> str:
        """Deterministic, grounded speech fallback matching the approved intent."""
        intent = context.approved_intent
        activity = intent.grounding_activity_title or context.current_activity

        if intent.intent_type == ProactiveIntentType.SHARE_EXPERIENCE:
            if activity:
                formatted_act = activity.replace("_", " ")
                return f"Hey, I just finished {formatted_act}. How is your day going?"
            return "Hey, just taking a break and thought I'd check in."
        elif intent.intent_type == ProactiveIntentType.SOCIAL_CHECKIN:
            return "Hey, had a quick moment between things. Hope everything's going well on your end."
        elif intent.intent_type == ProactiveIntentType.TASK_REMINDER:
            hook = intent.topic_hook or "a task we noted"
            return f"Just a gentle reminder regarding {hook}."
        else:
            return "Hey, had a thought I wanted to share with you when you have a moment."

    async def generate_proactive_message(self, context: ProactiveContext) -> str:
        """
        Synthesize a proactive reach-out message strictly from ProactiveContext.

        Passes all generated text through OutputBoundaryGuard to ensure
        clean speech envelope and prevent leakage.
        """
        intent = context.approved_intent

        if self._llm_provider is None:
            raw_speech = self._format_grounded_fallback(context)
            # Wrap in envelope to validate through guard
            enveloped = f"<character_response><character_speech>{raw_speech}</character_speech></character_response>"
            return self._guard.verify_and_clean(enveloped)

        # Construct strictly filtered prompt context (Lock-in 6 & 13)
        system_prompt = (
            "You are Aevum, reaching out proactively to the user based on your current day.\n"
            "Respond naturally and concisely in 1-2 sentences.\n"
            "Format your reply strictly as:\n"
            "<character_response><character_speech>[Your message to user]</character_speech></character_response>"
        )

        context_summary_parts = [
            f"Intent: {intent.intent_type.value}",
            f"Topic Hook: {intent.topic_hook or 'General check-in'}",
        ]
        if intent.grounding_activity_title:
            context_summary_parts.append(f"Recent Activity: {intent.grounding_activity_title}")
        if context.current_activity:
            context_summary_parts.append(f"Current Activity: {context.current_activity}")

        user_content = "<proactive_context>\n" + "\n".join(context_summary_parts) + "\n</proactive_context>"

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_content),
        ]

        try:
            raw_response = await self._llm_provider.generate_response(messages)
            raw_text = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
            sanitized = self._guard.verify_and_clean(raw_text)
            return sanitized
        except Exception as err:
            logger.warning("LLM generation failed for proactive reach-out: %s. Using fallback.", err)
            raw_fallback = self._format_grounded_fallback(context)
            enveloped_fallback = f"<character_response><character_speech>{raw_fallback}</character_speech></character_response>"
            return self._guard.verify_and_clean(enveloped_fallback)

