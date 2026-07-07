from langchain_huggingface import HuggingFaceEmbeddings

from app.common.custom_exception import CustomException
from app.common.logger import get_logger

logger=get_logger(__name__)

def get_embedding_model():
    try:
        logger.info("Initializing the HuggingFace embedding model")

        model=HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

        logger.info("Embedding model has been loaded...")

        return model

    except Exception as e:
        error_message=CustomException("Error has been occured while loading the embedding model", e)
        logger.error(str(error_message))
        raise error_message
    
