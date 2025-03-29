from markdown_parser import PDFtoMarkdownConverter
from creating_database import ChromaDataStore
from query_data import ChromaQueryHandler

pdf_folder = r"C:\Users\amank\Downloads\RAG Dummy\pdf_files"
markdown_folder = r"C:\Users\amank\Downloads\RAG Dummy\data\pdfs"
chroma_path = "chroma"

pdf_converter = PDFtoMarkdownConverter(pdf_folder, markdown_folder)
pdf_converter.convert()

chroma_store = ChromaDataStore(markdown_folder, chroma_path)
chroma_store.generate_data_store()

query_text = input("Enter your query: ")
query_handler = ChromaQueryHandler(chroma_path)
query_handler.search_query(query_text)