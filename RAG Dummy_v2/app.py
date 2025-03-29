from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langchain_community.vectorstores import Chroma
from creating_database import ChromaDataStore, OllamaEmbeddings
from openai import OpenAI
from langchain.prompts import ChatPromptTemplate
import os

# Constants
CHROMA_PATH = "chroma"
PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---

Answer the question based on the above context: {question}
"""

# Initialize FastAPI app
app = FastAPI()

# Allow frontend to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html
@app.get("/")
async def serve_home():
    return FileResponse("static/index.html")

# Input model
class QueryRequest(BaseModel):
    query: str

# Query Handler
class ChromaQueryHandler:
    def __init__(self, chroma_path=CHROMA_PATH, model_name="deepseek-r1:1.5b", base_url='http://localhost:11434/v1'):
        self.chroma_path = chroma_path
        self.client = OpenAI(base_url=base_url, api_key='ollama')  # Initialize OpenAI client
        self.embedding_function = OllamaEmbeddings(self.client)  # Pass the client to OllamaEmbeddings
        self.db = Chroma(persist_directory=self.chroma_path, embedding_function=self.embedding_function)
        self.model_name = model_name

    def search_query(self, query_text):
        results = self.db.similarity_search_with_relevance_scores(query_text, k=3)
        if not results or results[0][1] < 0.7:
            return {
                "query": query_text,
                "context": "No relevant context found.",
                "answer": "Unable to find matching results.",
                "sources": []
            }
        
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=query_text)
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content
        sources = [doc.metadata.get("source", "Unknown Source") for doc, _score in results]

        return {
            "query": query_text,
            "context": context_text,
            "answer": response_text,
            "sources": sources
        }

# Initialize handler
handler = ChromaQueryHandler()

@app.post("/query")
async def query_endpoint(request: QueryRequest):
    try:
        result = handler.search_query(request.query)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
