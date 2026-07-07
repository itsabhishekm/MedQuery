from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

from app.components.llm import load_llm
from app.components.vector_store import load_vector_store

from app.common.logger import get_logger
from app.common.custom_exception import CustomException


logger = get_logger(__name__)

CUSTOM_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful medical assistant. Answer the question in 2-3 lines using only the information provided in the context below.

Context:
{context}"""),
    ("human", "{input}")
])

def create_qa_chain():
    try:
        logger.info("Loading vector store for context")
        db = load_vector_store()

        if db is None:
            raise CustomException("Vector store not present or empty")

        llm = load_llm()

        if llm is None:
            raise CustomException("LLM not loaded")

        combine_docs_chain = create_stuff_documents_chain(llm, CUSTOM_PROMPT_TEMPLATE)
        qa_chain = create_retrieval_chain(
            retriever=db.as_retriever(search_kwargs={'k': 1}),
            combine_docs_chain=combine_docs_chain
        )

        logger.info("Successfully created the QA chain")
        return qa_chain

    except Exception as e:
        error_message = CustomException("Failed to make a QA chain", e)
        logger.error(str(error_message))
        return None
