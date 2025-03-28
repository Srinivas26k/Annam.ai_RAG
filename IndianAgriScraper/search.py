import re
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
import string
from collections import Counter
import math

# Download NLTK resources if needed
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

# Initialize NLTK components
stemmer = PorterStemmer()
stop_words = set(stopwords.words('english'))

def preprocess_text(text):
    """
    Preprocess text for search indexing
    
    Args:
        text (str): Raw text to preprocess
        
    Returns:
        list: List of preprocessed tokens
    """
    if not text:
        return []
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove punctuation
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    # Tokenize
    tokens = word_tokenize(text)
    
    # Remove stop words and stem
    tokens = [stemmer.stem(token) for token in tokens if token not in stop_words and len(token) > 2]
    
    return tokens

def calculate_tf(text_tokens):
    """
    Calculate term frequency
    
    Args:
        text_tokens (list): List of tokens
        
    Returns:
        dict: Dictionary with term frequencies
    """
    tf_dict = Counter(text_tokens)
    
    # Normalize by dividing by the total number of tokens
    for token in tf_dict:
        tf_dict[token] = tf_dict[token] / len(text_tokens) if len(text_tokens) > 0 else 0
        
    return tf_dict

def calculate_idf(documents_tokens):
    """
    Calculate inverse document frequency
    
    Args:
        documents_tokens (list): List of token lists for each document
        
    Returns:
        dict: Dictionary with IDF values
    """
    idf_dict = {}
    total_docs = len(documents_tokens)
    
    # Count document frequency for each term
    all_tokens = set()
    for doc_tokens in documents_tokens:
        all_tokens.update(set(doc_tokens))
        
    for token in all_tokens:
        doc_count = sum(1 for doc_tokens in documents_tokens if token in doc_tokens)
        idf_dict[token] = math.log(total_docs / (1 + doc_count))
        
    return idf_dict

def search_qa_data(query, qa_data, top_n=20):
    """
    Search QA data for relevant entries
    
    Args:
        query (str): Search query
        qa_data (list): List of QA pairs
        top_n (int): Number of top results to return
        
    Returns:
        list: List of matched QA pairs with scores
    """
    if not query or not qa_data:
        return []
    
    # Preprocess query
    query_tokens = preprocess_text(query)
    
    # Prepare document tokens for TF-IDF
    documents = []
    for qa_item in qa_data:
        question = qa_item.get('question', '')
        answer = qa_item.get('answer', '')
        combined_text = f"{question} {answer}"
        doc_tokens = preprocess_text(combined_text)
        documents.append({
            'tokens': doc_tokens,
            'qa_item': qa_item
        })
    
    # Calculate IDF
    documents_tokens = [doc['tokens'] for doc in documents]
    idf_dict = calculate_idf(documents_tokens)
    
    # Calculate TF for query
    query_tf = calculate_tf(query_tokens)
    
    # Calculate scores for each document
    results = []
    for doc in documents:
        score = 0
        doc_tf = calculate_tf(doc['tokens'])
        
        # Calculate TF-IDF similarity
        for token in query_tokens:
            if token in doc_tf and token in idf_dict:
                score += query_tf[token] * doc_tf[token] * idf_dict[token]
        
        # Boost score for exact phrase matches
        if query.lower() in doc['qa_item']['question'].lower() or query.lower() in doc['qa_item']['answer'].lower():
            score *= 2
            
        # Add extra weight for matches in question vs answer
        question_matches = sum(1 for token in query_tokens if token in preprocess_text(doc['qa_item']['question']))
        if question_matches > 0:
            score *= 1.5
        
        if score > 0:
            results.append({
                'question': doc['qa_item']['question'],
                'answer': doc['qa_item']['answer'],
                'source': doc['qa_item']['source'],
                'score': score
            })
    
    # Sort results by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    return results[:top_n]
