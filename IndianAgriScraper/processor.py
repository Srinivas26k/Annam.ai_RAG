import re
import nltk
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
import os
import random
import time
import string
import spacy
import traceback

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# Download all required NLTK data
print("Downloading required NLTK data...")
nltk.download('punkt', quiet=True)
nltk.download('stopwords', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)

# Load spaCy model for NER and dependency parsing
try:
    nlp = spacy.load("en_core_web_sm")
except:
    # If not installed, use a smaller model
    try:
        import spacy.cli
        spacy.cli.download("en_core_web_sm")
        nlp = spacy.load("en_core_web_sm")
    except:
        nlp = None

def clean_text(text):
    """
    Clean and normalize text
    
    Args:
        text (str): Raw text to clean
        
    Returns:
        str: Cleaned text
    """
    if not text:
        return ""
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    
    # Remove excessive punctuation
    text = re.sub(r'([.,;!?])\1+', r'\1', text)
    
    # Fix common encoding issues
    text = text.replace('â€™', "'")
    text = text.replace('â€œ', '"')
    text = text.replace('â€', '"')
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    
    return text.strip()

def extract_paragraphs(text, min_length=100):
    """
    Extract meaningful paragraphs from text
    
    Args:
        text (str): Text to extract paragraphs from
        min_length (int): Minimum character length for a paragraph
        
    Returns:
        list: List of paragraph strings
    """
    if not text:
        return []
    
    # Split by double newlines to identify paragraphs
    raw_paragraphs = re.split(r'\n\s*\n', text)
    
    # Clean each paragraph and filter out short ones
    paragraphs = []
    for p in raw_paragraphs:
        clean_p = clean_text(p)
        if len(clean_p) >= min_length:
            paragraphs.append(clean_p)
    
    return paragraphs

def identify_topics(text):
    """
    Identify agriculture-related topics from text
    
    Args:
        text (str): Text to analyze
        
    Returns:
        list: List of identified topics
    """
    if not nlp or not text:
        return []
    
    # Process text with spaCy
    doc = nlp(text[:10000])  # Limit to first 10K chars for efficiency
    
    # Extract entities that could be topics
    entities = [ent.text for ent in doc.ents if ent.label_ in ["ORG", "PRODUCT", "GPE", "LOC", "NORP"]]
    
    # Extract noun phrases
    noun_phrases = [chunk.text for chunk in doc.noun_chunks if len(chunk.text.split()) > 1]
    
    # Combine and filter for agriculture-related terms
    agriculture_keywords = [
        'crop', 'farm', 'soil', 'irrigation', 'seed', 'fertilizer', 'pesticide', 
        'harvest', 'yield', 'organic', 'sustainable', 'agriculture', 'farming',
        'farmer', 'cultivation', 'rural', 'monsoon', 'rabi', 'kharif'
    ]
    
    # Filter entities and noun phrases for agriculture relevance
    topics = set()
    for item in entities + noun_phrases:
        item_lower = item.lower()
        if any(keyword in item_lower for keyword in agriculture_keywords):
            topics.add(item)
    
    return list(topics)

def custom_sent_tokenize(text):
    """
    Custom sentence tokenization function that doesn't rely on NLTK's punkt_tab
    
    Args:
        text (str): Text to tokenize into sentences
        
    Returns:
        list: List of sentences
    """
    # Simple sentence splitting based on common sentence-ending punctuation
    text = re.sub(r'([.!?])\s+([A-Z])', r'\1\n\2', text)
    text = re.sub(r'([.!?])\s*$', r'\1', text)
    
    # Split by newlines and filter out empty sentences
    sentences = [s.strip() for s in text.split('\n') if s.strip()]
    
    # Handle cases where sentences weren't properly split
    result = []
    for sentence in sentences:
        # If a sentence is too long, it might contain multiple sentences
        if len(sentence) > 300:
            # Try to split on common ending punctuation followed by space and capital letter
            parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', sentence)
            result.extend(parts)
        else:
            result.append(sentence)
    
    return result

def generate_question_from_paragraph(paragraph, topics=None):
    """
    Generate a relevant question from a paragraph using rule-based approach
    
    Args:
        paragraph (str): The paragraph to generate a question from
        topics (list): Optional list of topics to focus on
        
    Returns:
        str: Generated question
    """
    if not paragraph:
        return ""
    
    # Clean paragraph
    paragraph = clean_text(paragraph)
    
    # Tokenize the paragraph using our custom tokenizer
    sentences = custom_sent_tokenize(paragraph)
    if not sentences:
        return ""
    
    # Try to use spaCy for better question generation if available
    if nlp:
        # Process first two sentences as they often contain key information
        doc = nlp(" ".join(sentences[:2]))
        
        # Look for key entities or subjects that could form questions
        for ent in doc.ents:
            if ent.label_ in ["ORG", "PERSON", "GPE", "LOC", "PRODUCT"]:
                if ent.label_ == "PERSON":
                    return f"What is the role of {ent.text} in Indian agriculture?"
                elif ent.label_ == "ORG":
                    return f"What does {ent.text} do for Indian agriculture?"
                elif ent.label_ == "GPE" or ent.label_ == "LOC":
                    return f"What are the agricultural practices in {ent.text}?"
                elif ent.label_ == "PRODUCT":
                    return f"How is {ent.text} used in Indian agriculture?"
        
        # If we couldn't generate a question from entities, try noun chunks
        for chunk in doc.noun_chunks:
            if len(chunk.text.split()) > 1:
                return f"What is the importance of {chunk.text} in Indian agriculture?"
    
    # Fallback approach using first sentence and simple patterns
    first_sent = sentences[0]
    
    # Simple patterns for question generation
    patterns = [
        # What questions
        f"What are the main aspects of {topics[0] if topics else 'this agricultural practice'}?",
        f"What is the significance of {topics[0] if topics else 'this approach'} in Indian agriculture?",
        
        # How questions
        "How do Indian farmers implement these practices?",
        "How does this agricultural method benefit Indian farmers?",
        
        # Why questions
        "Why is this approach important for Indian agriculture?",
        "Why should Indian farmers consider adopting these methods?",
        
        # General questions
        "What challenges do Indian farmers face regarding this issue?",
        "How can these agricultural techniques be improved in the Indian context?"
    ]
    
    # Select a random pattern
    return random.choice(patterns)

def process_text_to_qa(scraped_data, use_openrouter=False, api_key=None):
    """
    Process scraped text into question-answer pairs
    
    Args:
        scraped_data (list): List of dictionaries with scraped content
        use_openrouter (bool): Whether to use OpenRouter for QA generation
        api_key (str): OpenRouter API key if using OpenRouter
        
    Returns:
        list: List of dictionaries with QA pairs
    """
    qa_data = []
    qa_index = 1
    
    for item in scraped_data:
        try:
            url = item.get('url', '')
            content = item.get('content', '')
            
            if not content or len(content) < 200:  # Skip if content is too short
                continue
            
            # Extract paragraphs
            paragraphs = extract_paragraphs(content)
            
            # Process each paragraph into a QA pair
            for paragraph in paragraphs:
                if len(paragraph) < 200:  # Skip short paragraphs
                    continue
                
                # Identify topics in the paragraph
                topics = identify_topics(paragraph)
                
                # If OpenRouter is available and enabled, use it
                if use_openrouter and OpenAI and api_key:
                    try:
                        qa_pair = generate_qa_with_openrouter(paragraph, url, api_key)
                        if qa_pair:
                            qa_pair['index'] = qa_index
                            qa_data.append(qa_pair)
                            qa_index += 1
                            continue
                    except Exception as e:
                        print(f"OpenRouter generation failed: {e}")
                        # Fall back to rule-based approach
                
                # Rule-based approach
                question = generate_question_from_paragraph(paragraph, topics)
                
                if question:
                    qa_pair = {
                        'index': qa_index,
                        'question': question,
                        'answer': paragraph,
                        'source': url
                    }
                    qa_data.append(qa_pair)
                    qa_index += 1
        
        except Exception as e:
            print(f"Error processing content from {item.get('url', 'unknown')}: {e}")
            traceback.print_exc()
    
    return qa_data

def generate_qa_with_openrouter(paragraph, source_url, api_key):
    """
    Generate a QA pair using OpenRouter API
    
    Args:
        paragraph (str): Paragraph to generate QA from
        source_url (str): Source URL
        api_key (str): OpenRouter API key
        
    Returns:
        dict: Dictionary with question and answer
    """
    if not OpenAI or not api_key:
        print("OpenAI client or API key not available")
        return None
    
    try:
        print(f"Generating QA with OpenRouter for paragraph from {source_url}")
        
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        
        prompt = f"""
        Given the following paragraph about Indian agriculture, generate a detailed factual question 
        and comprehensive answer pair. The question should be clear, specific, and directly answerable 
        from the text. Both the question and answer should be detailed and thorough, providing valuable 
        information for Indian farmers.
        
        Paragraph: {paragraph}
        
        Format your response exactly like this:
        QUESTION: [your generated detailed question]
        ANSWER: [comprehensive, detailed answer based strictly on the paragraph, with additional relevant context]
        """
        
        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": "https://agriculture-qa-scraper.replit.app",
                "X-Title": "Indian Agriculture Data Scraper",
            },
            extra_body={},
            model="featherless/qwerky-72b:free",
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=1500
        )
        
        response_text = completion.choices[0].message.content
        print("OpenRouter response received")
        
        # Parse the response to extract question and answer
        question_match = re.search(r'QUESTION:\s*(.*?)(?=ANSWER:|$)', response_text, re.DOTALL)
        answer_match = re.search(r'ANSWER:\s*(.*?)(?=$)', response_text, re.DOTALL)
        
        if question_match and answer_match:
            question = question_match.group(1).strip()
            answer = answer_match.group(1).strip()
            
            print(f"Generated question: {question[:50]}...")
            
            # If answer is too short, use the original paragraph
            if len(answer) < 100:
                answer = paragraph
                print("Answer too short, using original paragraph")
            else:
                print(f"Generated answer length: {len(answer)} characters")
            
            return {
                'question': question,
                'answer': answer,
                'source': source_url
            }
        else:
            print("Failed to parse question and answer from response")
            print(f"Response text: {response_text[:100]}...")
    
    except Exception as e:
        print(f"Error with OpenRouter API: {e}")
        traceback.print_exc()
    
    return None
