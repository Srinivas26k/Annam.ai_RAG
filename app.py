import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain_ollama import OllamaLLM, OllamaEmbeddings
import os



@st.cache_resource
def init_models():
    os.environ["OLLAMA_HOST"] = "http://localhost:11434"  # Set host via env var
    return OllamaLLM(
        model="llama3.2:latest",
        temperature=0.1,
        num_ctx=2048,
        num_thread=4
    ), OllamaEmbeddings(
        model="nomic-embed-text:latest"
    )

ollama, embeddings = init_models()

@st.cache_resource
def load_vector_store(_embeddings):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        length_function=len
    )
    if not os.path.exists('vector_store'):
        documents = []
        data_dir = 'data'
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            st.error("Data directory created. Please add PDFs to the 'data' folder and restart the app.")
            st.stop()
        for pdf_file in os.listdir(data_dir):
            if pdf_file.endswith('.pdf'):
                pdf_path = os.path.join(data_dir, pdf_file)
                loader = PyPDFLoader(pdf_path)
                pages = loader.load()
                documents.extend(pages)
        if not documents:
            st.error("No PDFs found in 'data' directory. Please add PDFs and restart the app.")
            st.stop()
        splits = text_splitter.split_documents(documents)
        vector_store = FAISS.from_documents(splits, _embeddings)
        vector_store.save_local('vector_store')
    else:
        vector_store = FAISS.load_local('vector_store', _embeddings, allow_dangerous_deserialization=True)
    return vector_store

vector_store = load_vector_store(embeddings)

@st.cache_resource
def create_qa_chain(_vector_store, _llm):  # Add underscores to both parameters
    return ConversationalRetrievalChain.from_llm(
        llm=_llm,  # Use the underscore-prefixed parameter
        retriever=_vector_store.as_retriever(search_kwargs={"k": 3}),
        return_source_documents=True,
        verbose=False
    )

# The rest of your code remains the same
qa_chain = create_qa_chain(vector_store, ollama)

st.title("PDF Chat with RAG")

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

user_question = st.text_input("Ask a question about your PDFs:")

if user_question:
    try:
        response = qa_chain.invoke({
            "question": user_question,
            "chat_history": st.session_state.chat_history
        })
    except Exception as e:
        st.error(f"Error: {str(e)}")
    
    st.session_state.chat_history.append((user_question, response["answer"]))
    
    if len(st.session_state.chat_history) > 10:
        st.session_state.chat_history = st.session_state.chat_history[-10:]
    
    for question, answer in st.session_state.chat_history:
        st.write(f"Q: {question}")
        st.write(f"A: {answer}")
        st.write("---")

if st.button("Clear Chat"):
    st.session_state.chat_history = []