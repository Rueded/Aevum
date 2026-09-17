"""Context formatter for Personal World and Epistemic Grounding blocks."""

from typing import Optional
from app.world.models import FactEpistemicStatus, PersonalWorldContext


class PersonalWorldContextBuilder:
    """Builds prompt-friendly XML blocks for personal world facts and epistemic rules."""

    @classmethod
    def format_context(cls, context: Optional[PersonalWorldContext]) -> str:
        """Format the PersonalWorldContext into structured XML."""
        if not context:
            return ""

        sections: list[str] = []

        # 1. Personal World Facts Block
        world_lines = ["<personal_world>"]
        has_content = False

        if context.biography_facts:
            has_content = True
            world_lines.append("Biographical Ground Truth:")
            for fact in context.biography_facts:
                world_lines.append(f"- {fact.subject.capitalize()}: {fact.canonical_value}")

        if context.social_contacts:
            has_content = True
            world_lines.append("\nSocial Circle:")
            for contact in context.social_contacts:
                world_lines.append(f"- {contact.name} ({contact.relationship}): {contact.traits}")

        if context.world_facts:
            has_content = True
            world_lines.append("\nPersonal Knowledge & Tastes:")
            for wf in context.world_facts:
                world_lines.append(f"- [{wf.category}] {wf.item}: {wf.details}")

        world_lines.append("</personal_world>")

        if has_content:
            sections.append("\n".join(world_lines))

        # 2. Epistemic Directives Block
        if context.epistemic_directives:
            epistemic_lines = [
                "<epistemic_grounding>",
                "CRITICAL EPISTEMIC DIRECTIVES (You MUST adhere strictly to these rules):",
            ]
            has_unknown = any(
                getattr(d, "status", None) == FactEpistemicStatus.UNKNOWN
                or getattr(getattr(d, "status", None), "value", None) == "UNKNOWN"
                for d in context.epistemic_directives
            )
            if has_unknown:
                epistemic_lines.append(
                    "- [FORCED-CHOICE INVARIANT] If a question presents alternative choices (e.g., 'is it A or B?', '是A还是B？', '或是...'), "
                    "candidate options do NOT establish ground truth. For any UNKNOWN topic, do NOT pick, adopt, or validate any presented option as fact."
                )
            for directive in context.epistemic_directives:
                epistemic_lines.append(f"- [{directive.status.value}] {directive.guidance}")
            epistemic_lines.append("</epistemic_grounding>")
            sections.append("\n".join(epistemic_lines))

        return "\n\n".join(sections)
