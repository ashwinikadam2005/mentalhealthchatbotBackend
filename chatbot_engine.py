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
# chatbot_engine.py
import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_community.vectorstores import Chroma
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from googletrans import Translator   # ✅ use googletrans

load_dotenv()
qa_chain = None
translator = Translator()

def initialize_llm():
    return ChatGroq(
        temperature=0,
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama3-70b-8192"
    )

def create_vector_db():
    loader = DirectoryLoader("./pdfs", glob="*.pdf", loader_cls=PyPDFLoader)
    documents = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(documents)

    embeddings = HuggingFaceBgeEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vector_db = Chroma.from_documents(texts, embeddings, persist_directory="./chroma_db")
    vector_db.persist()
    print("✅ ChromaDB created and saved.")
    return vector_db

def load_or_create_vector_db():
    embeddings = HuggingFaceBgeEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

    if os.path.exists("./chroma_db") and os.listdir("./chroma_db"):
        print("🔁 Loading existing ChromaDB...")
        return Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    else:
        print("🆕 No DB found. Creating a new ChromaDB...")
        return create_vector_db()

def setup_qa_chain(vector_db, llm):
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

def get_chatbot_response(user_query):
    global qa_chain

    # ✅ Detect language & translate to English
    detected_lang = translator.detect(user_query).lang
    translated_query = translator.translate(user_query, src=detected_lang, dest="en").text

    # ✅ Initialize chain if not ready
    if qa_chain is None:
        llm = initialize_llm()
        vector_db = load_or_create_vector_db()
        qa_chain = setup_qa_chain(vector_db, llm)

    # ✅ Get response in English
    english_response = qa_chain.run(translated_query)

    # ✅ Translate back
    if detected_lang != "en":
        final_response = translator.translate(english_response, src="en", dest=detected_lang).text
    else:
        final_response = english_response

    return final_response
