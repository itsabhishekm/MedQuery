from langchain_mistralai import ChatMistralAI
import os

from app.common.logger import get_logger
from app.common.custom_exception import CustomException

logger=get_logger(__name__)

def load_llm():
    try:
        logger.info("Loading LLM from Mistral")

        llm = ChatMistralAI(
            model="open-mistral-7b",
            temperature=0.3,
            max_tokens=256,
            api_key=os.environ.get("MISTRAL_API_KEY")
        )
        logger.info("LLM has been loaded")
        return llm

    except Exception as e:
        error_message=CustomException("Failed to load the LLM", e)
        logger.error(str(error_message))
        return None
