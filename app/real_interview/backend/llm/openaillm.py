import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.real_interview import logger

load_dotenv()


class OpenAILLM:
    def __init__(self) -> None:
        logger.info("inside __init__")

    def get_llm_model(self) -> ChatOpenAI:
        logger.info("inside get_llm_model")
        try:
            openai_api_key = os.getenv("OPENAI_API_KEY", "")
            if isinstance(openai_api_key, str):
                openai_api_key = openai_api_key.strip().strip("'\"")
            if not openai_api_key:
                raise ValueError("OPENAI_API_KEY is not set in the environment or .env file")
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=openai_api_key)
            return llm
        except Exception as e:
            logger.error("Error getting LLM model: %s", e)
            raise
