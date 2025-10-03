# # chatbot_engine.py
# import os
# from dotenv import load_dotenv
# from langchain_groq import ChatGroq
# from langchain_community.embeddings import HuggingFaceBgeEmbeddings
# from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
# from langchain_community.vectorstores import Chroma
# from langchain.chains import RetrievalQA
# from langchain.prompts import PromptTemplate
# from langchain.text_splitter import RecursiveCharacterTextSplitter

# load_dotenv()
# qa_chain = None  # global

# def initialize_llm():
#     return ChatGroq(
#         temperature=0,
#         groq_api_key=os.getenv("GROQ_API_KEY"),
#         model_name="llama3-70b-8192"
#     )

# def create_vector_db():
#     loader = DirectoryLoader("./pdfs", glob="*.pdf", loader_cls=PyPDFLoader)
#     documents = loader.load()

#     text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
#     texts = text_splitter.split_documents(documents)

#     embeddings = HuggingFaceBgeEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
#     vector_db = Chroma.from_documents(texts, embeddings, persist_directory="./chroma_db")
#     vector_db.persist()
#     print("✅ ChromaDB created and saved.")
#     return vector_db

# def load_or_create_vector_db():
#     embeddings = HuggingFaceBgeEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
#     if os.path.exists("./chroma_db/index"):
#         print("🔁 Loading existing ChromaDB...")
#         return Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
#     else:
#         print("🆕 No DB found. Creating a new ChromaDB...")
#         return create_vector_db()

# def setup_qa_chain(vector_db, llm):
#     retriever = vector_db.as_retriever()
#     prompt_template = """You are a compassionate mental health chatbot. Respond thoughtfully to the user query.
# Context:
# {context}

# User: {question}
# Chatbot:"""
#     prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
#     return RetrievalQA.from_chain_type(
#         llm=llm,
#         chain_type="stuff",
#         retriever=retriever,
#         chain_type_kwargs={"prompt": prompt}
#     )

# def get_chatbot_response(user_query):
#     global qa_chain
#     if qa_chain is None:
#         llm = initialize_llm()
#         vector_db = load_or_create_vector_db()
#         qa_chain = setup_qa_chain(vector_db, llm)
#     return qa_chain.run(user_query)


    

# chatbot_engine.py
import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter

# Try importing PyPDFLoader safely
try:
    from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
    PDF_LOADER_AVAILABLE = True
except ImportError:
    print("⚠️ pypdf not installed. PDF QA will be skipped.")
    PDF_LOADER_AVAILABLE = False

load_dotenv()
qa_chain = None  # global cache
_last_model_used = None


def initialize_llm():
    # Use a simple local embedding-based retrieval only; the caller (routes) will combine with LLM
    return None


def create_vector_db():
    if not PDF_LOADER_AVAILABLE:
        print("⚠️ Skipping vector DB creation (pypdf missing).")
        return None

    loader = DirectoryLoader("./pdfs", glob="*.pdf", loader_cls=PyPDFLoader)
    documents = loader.load()

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(documents)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_db = Chroma.from_documents(texts, embeddings, persist_directory="./chroma_db")
    vector_db.persist()
    print("✅ ChromaDB created and saved.")
    return vector_db


def load_or_create_vector_db():
    if not PDF_LOADER_AVAILABLE:
        return None

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    if os.path.exists("./chroma_db"):
        print("🔁 Loading existing ChromaDB...")
        return Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    else:
        print("🆕 No DB found. Creating a new ChromaDB...")
        return create_vector_db()


def setup_qa_chain(vector_db, llm):
    if not vector_db:
        print("⚠️ No vector DB available. PDF QA will be skipped.")
        return None

    retriever = vector_db.as_retriever()
    prompt_template = """You are a compassionate mental health chatbot. Respond thoughtfully to the user query.
Context:
{context}

User: {question}
Chatbot:"""
    prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
    return RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff",
        retriever=retriever,
        chain_type_kwargs={"prompt": prompt}
    )


def _build_chain_with_fallback():
    """Build QA chain trying preferred and fallback Groq models."""
    # Build retriever-only chain without Groq LLM
    vector_db = load_or_create_vector_db()
    if not vector_db:
        return None, None

    try:
        chain = setup_qa_chain(vector_db, initialize_llm())
        return chain, "retriever-only"
    except Exception as e:
        print(f"⚠️ Failed initializing PDF retriever: {e}")
        return None, None


def get_chatbot_response(user_query):
    global qa_chain, _last_model_used
    if qa_chain is None:
        qa_chain, _last_model_used = _build_chain_with_fallback()

    if not qa_chain:
        return ""

    try:
        return qa_chain.run(user_query)
    except Exception as e:
        # If the retriever failed, rebuild once
        print(f"⚠️ QA chain run failed: {e}")
        qa_chain, _last_model_used = _build_chain_with_fallback()
        if qa_chain:
            try:
                return qa_chain.run(user_query)
            except Exception as e2:
                print(f"⚠️ Retry with retriever failed: {e2}")
        return ""
