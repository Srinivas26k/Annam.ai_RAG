import argparse
from langchain_community.vectorstores import Chroma
from creating_database import ChromaDataStore, OllamaEmbeddings
from openai import OpenAI
from langchain.prompts import ChatPromptTemplate

CHROMA_PATH = "chroma"
PROMPT_TEMPLATE = """
Answer the question based only on the following context:

{context}

---

Answer the question based on the above context: {question}
"""

class ChromaQueryHandler:
    def __init__(self, chroma_path=CHROMA_PATH, model_name="deepseek-r1:1.5b", base_url='http://localhost:11434/v1'):
        self.chroma_path = chroma_path
        self.client = OpenAI(base_url=base_url, api_key='ollama')  # Initialize OpenAI client
        self.embedding_function = OllamaEmbeddings(self.client)  # Pass the client to OllamaEmbeddings
        self.db = Chroma(persist_directory=self.chroma_path, embedding_function=self.embedding_function)
        self.model_name = model_name
    
    def search_query(self, query_text):
        results = self.db.similarity_search_with_relevance_scores(query_text, k=3)
        if len(results) == 0 or results[0][1] < 0.7:
            print("Unable to find matching results.")
            return
        
        context_text = "\n\n---\n\n".join([doc.page_content for doc, _score in results])
        prompt_template = ChatPromptTemplate.from_template(PROMPT_TEMPLATE)
        prompt = prompt_template.format(context=context_text, question=query_text)
        
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "system", "content": "You are a helpful assistant."},
                      {"role": "user", "content": prompt}]
        )
        response_text = response.choices[0].message.content
        
        sources = [doc.metadata.get("source", None) for doc, _score in results]
        formatted_response = f"Response: {response_text}\nSources: {sources}"
        print(formatted_response)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("query_text", type=str, help="The query text.")
    args = parser.parse_args()
    
    handler = ChromaQueryHandler()
    handler.search_query(args.query_text)
