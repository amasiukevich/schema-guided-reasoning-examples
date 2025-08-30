import os
from abc import ABC, abstractmethod

from dotenv import load_dotenv
from openai import OpenAI


class ModelProvider(ABC):
    @abstractmethod
    def chat_completion(self, messages, response_format, model=None, max_completion_tokens=None):
        pass


class OpenAIProvider(ModelProvider):
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def chat_completion(self, messages, response_format, model="gpt-4o", max_completion_tokens=1000):
        completion = self.client.beta.chat.completions.parse(
            model=model,
            response_format=response_format,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
        )
        return completion


class OpenRouterProvider(ModelProvider):
    def __init__(self, api_key: str):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )

    def chat_completion(self, messages, response_format, model="openai/gpt-4o", max_completion_tokens=1000):
        # Convert Pydantic model to JSON schema format for OpenRouter
        json_schema = response_format.model_json_schema()

        # Ensure additionalProperties: false for all object schemas (required by OpenAI)
        def ensure_no_additional_properties(schema_dict):
            if isinstance(schema_dict, dict):
                if schema_dict.get("type") == "object" and "additionalProperties" not in schema_dict:
                    schema_dict["additionalProperties"] = False
                for key, value in schema_dict.items():
                    if isinstance(value, dict):
                        ensure_no_additional_properties(value)
                    elif isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                ensure_no_additional_properties(item)

        ensure_no_additional_properties(json_schema)

        schema = {
            "type": "json_schema",
            "json_schema": {"name": response_format.__name__.lower(), "strict": True, "schema": json_schema},
        }

        completion = self.client.chat.completions.create(
            model=model,
            response_format=schema,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
        )
        return completion


def create_model_provider(provider_type: str = None) -> ModelProvider:
    load_dotenv(".env")

    # Auto-detect provider if not specified
    if provider_type is None:
        provider_type = os.getenv("MODEL_PROVIDER", "openai").lower()

    if provider_type.lower() == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        return OpenAIProvider(api_key)
    elif provider_type.lower() == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment variables")
        return OpenRouterProvider(api_key)
    else:
        raise ValueError(f"Unsupported provider: {provider_type}")


def get_model_name(provider_type: str = None) -> str:
    if provider_type is None:
        provider_type = os.getenv("MODEL_PROVIDER", "openai").lower()

    if provider_type.lower() == "openai":
        return os.getenv("OPENAI_MODEL", "gpt-4o")
    elif provider_type.lower() == "openrouter":
        return os.getenv("OPENROUTER_MODEL", "openai/gpt-4o")
    else:
        return "gpt-4o"
