import os
import re
import json
import datetime

def save_to_markdown(qa_data, filename):
    """
    Save Q&A data to a markdown file following the specified format:
    {number}frame a question
    
    answer
    
    (source)
    
    Args:
        qa_data (list): List of Q&A pairs
        filename (str): Name of the file to save to
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("# Indian Agriculture Data Q&A\n\n")
            f.write(f"*Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
            f.write("*This document contains question-answer pairs extracted from authentic Indian agriculture sources. Each entry is formatted as:*\n\n")
            f.write("```\n{number}frame a question\n\nanswer\n\n(source)\n```\n\n")
            f.write("---\n\n")
            
            for qa_pair in qa_data:
                index = qa_pair.get('index', 0)
                question = qa_pair.get('question', '').strip()
                answer = qa_pair.get('answer', '').strip()
                source = qa_pair.get('source', '').strip()
                
                # Write in the specified format
                f.write(f"{index}. {question}\n\n")
                f.write(f"{answer}\n\n")
                f.write(f"(Source: {source})\n\n")
                f.write("---\n\n")
                
        return True
    except Exception as e:
        print(f"Error saving markdown file: {e}")
        return False

def load_markdown(filename):
    """
    Load Q&A data from a markdown file in the format:
    {number}. question
    
    answer
    
    (Source: url)
    
    Args:
        filename (str): Name of the file to load from
        
    Returns:
        list: List of Q&A pairs
    """
    qa_data = []
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # Skip the header section
            content_sections = content.split("---\n\n", 1)
            if len(content_sections) > 1:
                content = content_sections[1]
            
            # Use regex to extract QA pairs separated by "---"
            qa_sections = re.split(r'---\s*\n', content)
            
            for section in qa_sections:
                if not section.strip():
                    continue
                
                # Extract question with number
                question_match = re.search(r'(\d+)\.\s*(.*?)(?:\n|$)', section)
                if not question_match:
                    # Try alternate format (for backward compatibility)
                    question_match = re.search(r'##\s*(\d+)\.\s*(.*?)(?:\n|$)', section)
                    if not question_match:
                        continue
                    
                index = int(question_match.group(1))
                question = question_match.group(2).strip()
                
                # Extract answer and source
                answer_section = section[question_match.end():].strip()
                source_match = re.search(r'\(Source:\s*(.*?)\)', answer_section)
                
                if source_match:
                    answer = answer_section[:source_match.start()].strip()
                    source = source_match.group(1).strip()
                else:
                    answer = answer_section
                    source = "Unknown"
                
                qa_data.append({
                    'index': index,
                    'question': question,
                    'answer': answer,
                    'source': source
                })
                
        return qa_data
    except Exception as e:
        print(f"Error loading markdown file: {e}")
        return []

def get_qa_data(filename):
    """
    Get Q&A data from file if it exists, or return empty list
    
    Args:
        filename (str): Name of the file to check
        
    Returns:
        list: List of Q&A pairs
    """
    if os.path.exists(filename):
        return load_markdown(filename)
    return []

def extract_questions_from_text(text):
    """
    Extract potential questions from text
    
    Args:
        text (str): Text to extract questions from
        
    Returns:
        list: List of extracted questions
    """
    if not text:
        return []
    
    # Look for question patterns
    question_patterns = [
        r'([A-Z][^.!?]*\?)',  # Standard questions ending with ?
        r'([A-Z][^.!?]*?(what|how|why|when|where|which|who|is|are|can|could|should|would)[^.!?]*\??)'  # Questions with question words
    ]
    
    questions = []
    for pattern in question_patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if isinstance(match, tuple):
                question = match[0].strip()
            else:
                question = match.strip()
                
            if question and question not in questions and len(question) > 15:
                questions.append(question)
    
    return questions
