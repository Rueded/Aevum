import logging
import warnings
from typing import Any
from google import genai
from google.genai import types

# Suppress benign Google GenAI SDK recommendation warning regarding automatic function calling
warnings.filterwarnings("ignore", message=".*Direct use of automatic function calling.*")
logging.getLogger("google.genai").addFilter(
    lambda record: "Direct use of automatic function calling" not in record.getMessage()
)

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.llm.base import (
    LLMError,
    LLMGenerationError,
    LLMProvider,
    LLMProviderNotConfiguredError,
    LLMResponse,
)
from app.llm.context import LLMContext


class GeminiProvider(LLMProvider):
    """Google Gemini LLM provider implementation using the official google-genai SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        client: Any | None = None,
    ) -> None:
        """Initialize the Gemini provider.

        Args:
            api_key: Optional API key. Defaults to settings.gemini_api_key.
            model_name: Optional model identifier. Defaults to settings.gemini_model.
            client: Optional pre-configured genai.Client (useful for mocking in tests).
        """
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.gemini_model or "gemini-2.5-flash"
        self._client = client

        # Initialize client if API key is provided and no client was injected
        if self._client is None and self.api_key:
            self._client = genai.Client(api_key=self.api_key)

    @property
    def provider_name(self) -> str:
        return "gemini"

    def _convert_context_to_gemini(
        self,
        context: LLMContext,
    ) -> tuple[list[types.Content], str | None]:
        """Convert provider-neutral LLMContext into Gemini Content objects and system instruction.

        Database / Neutral roles:
          - 'user'      -> Gemini 'user'
          - 'assistant' -> Gemini 'model'
          - 'system'    -> Accumulated into system_instruction
        """
        contents: list[types.Content] = []
        system_parts: list[str] = list(context.system_instructions)

        for msg in context.messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            elif msg.role == "user":
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=msg.content)],
                    )
                )
            elif msg.role == "assistant":
                if msg.raw_parts:
                    contents.append(
                        types.Content(
                            role="model",
                            parts=list(msg.raw_parts),
                        )
                    )
                else:
                    contents.append(
                        types.Content(
                            role="model",
                            parts=[types.Part.from_text(text=msg.content)],
                        )
                    )
            else:
                # Default unknown roles to user for safety
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=msg.content)],
                    )
                )

        combined_system = "\n\n".join(system_parts) if system_parts else None
        return contents, combined_system

    async def generate_response(
        self,
        context: LLMContext,
    ) -> LLMResponse:
        """Generate response from Gemini model using provider-neutral LLMContext.

        Raises:
            LLMProviderNotConfiguredError: If API key is missing.
            LLMGenerationError: If the upstream call fails or produces empty output.
        """
        if self._client is None:
            raise LLMProviderNotConfiguredError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in the environment."
            )

        if isinstance(context, list):
            context = LLMContext(messages=context)

        if not context.messages:
            raise LLMGenerationError("Cannot generate response from empty message history.")

        contents, resolved_system = self._convert_context_to_gemini(context=context)

        config_kwargs: dict[str, Any] = {
            "thinking_config": types.ThinkingConfig(thinking_budget=0),
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if resolved_system:
            config_kwargs["system_instruction"] = resolved_system

        enable_grounding = getattr(context, "enable_grounding", True)
        if enable_grounding:
            config_kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )
            except Exception as search_exc:
                if enable_grounding and "tools" in config_kwargs:
                    logger.warning("Grounding with Google Search failed (%s), retrying without tools...", search_exc)
                    config_kwargs.pop("tools", None)
                    fallback_config = types.GenerateContentConfig(**config_kwargs)
                    response = await self._client.aio.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=fallback_config,
                    )
                else:
                    raise
        except LLMError:
            raise
        except Exception as exc:
            err_msg = str(exc)
            if self.api_key and self.api_key in err_msg:
                err_msg = err_msg.replace(self.api_key, "[REDACTED]")
            raise LLMGenerationError(f"Gemini API request failed: {err_msg}") from exc

        # Extract output text, carefully filtering out internal thought/reasoning parts
        text_parts: list[str] = []
        thought_parts: list[str] = []

        if hasattr(response, "candidates") and response.candidates:
            cand = response.candidates[0]
            if hasattr(cand, "content") and cand.content and hasattr(cand.content, "parts") and cand.content.parts:
                for p in cand.content.parts:
                    is_thought = getattr(p, "thought", False)
                    p_text = getattr(p, "text", None)
                    if p_text:
                        if is_thought:
                            thought_parts.append(p_text)
                        else:
                            text_parts.append(p_text)

        if text_parts:
            content_text = "".join(text_parts)
        else:
            content_text = getattr(response, "text", None)

        if not content_text or not content_text.strip():
            logger.warning(
                "Gemini empty content: cand=%s, thought_len=%d",
                response.candidates[0].model_dump() if (hasattr(response, "candidates") and response.candidates and hasattr(response.candidates[0], "model_dump")) else "no_cand",
                len(thought_parts),
            )
            raise LLMGenerationError("Gemini returned an empty or blank response.")

        thought_str = "".join(thought_parts).strip() if thought_parts else None

        # Capture raw candidate parts if available to preserve thought signatures internally
        raw_parts = None
        if hasattr(response, "candidates") and response.candidates:
            cand = response.candidates[0]
            if hasattr(cand, "content") and cand.content and hasattr(cand.content, "parts"):
                raw_parts = cand.content.parts

        return LLMResponse(
            content=content_text.strip(),
            thought_content=thought_str,
            raw_response={"raw_parts": raw_parts} if raw_parts else None,
        )

    async def generate_structured(
        self,
        context: LLMContext,
        response_schema: type[Any] | None = None,
    ) -> str:
        """Generate structured JSON output using Gemini's native JSON mode."""
        if self._client is None:
            raise LLMProviderNotConfiguredError(
                "Gemini API key is not configured. Please set GEMINI_API_KEY in the environment."
            )

        if not context.messages:
            raise LLMGenerationError("Cannot generate response from empty message history.")

        contents, resolved_system = self._convert_context_to_gemini(context=context)

        config_kwargs: dict[str, Any] = {
            "response_mime_type": "application/json",
            "automatic_function_calling": types.AutomaticFunctionCallingConfig(disable=True),
        }
        if resolved_system:
            config_kwargs["system_instruction"] = resolved_system
        if response_schema is not None:
            # Handle Pydantic models by stripping additionalProperties which causes Gemini API errors
            if hasattr(response_schema, "model_json_schema"):
                schema_dict = response_schema.model_json_schema()
                
                def strip_additional_properties(schema: dict[str, Any]) -> dict[str, Any]:
                    if not isinstance(schema, dict):
                        return schema
                    schema = {k: v for k, v in schema.items() if k != "additionalProperties"}
                    for k, v in schema.items():
                        if isinstance(v, dict):
                            schema[k] = strip_additional_properties(v)
                        elif isinstance(v, list):
                            schema[k] = [
                                strip_additional_properties(item) if isinstance(item, dict) else item 
                                for item in v
                            ]
                    return schema
                
                config_kwargs["response_schema"] = strip_additional_properties(schema_dict)
            else:
                config_kwargs["response_schema"] = response_schema

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            response = await self._client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config,
            )
        except LLMError:
            raise
        except Exception as exc:
            err_msg = str(exc)
            if self.api_key and self.api_key in err_msg:
                err_msg = err_msg.replace(self.api_key, "[REDACTED]")
            raise LLMGenerationError(f"Gemini structured request failed: {err_msg}") from exc

        content_text = getattr(response, "text", None)
        if not content_text or not content_text.strip():
            raise LLMGenerationError("Gemini returned an empty structured response.")

        return content_text.strip()

