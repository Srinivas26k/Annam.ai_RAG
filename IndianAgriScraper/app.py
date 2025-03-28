import streamlit as st
import os
import pandas as pd
from datetime import datetime
import time
import re
import base64
import zipfile
import tempfile
import json
import shutil
from io import BytesIO

from scraper import search_agriculture_info, scrape_url
from processor import process_text_to_qa
from search import search_qa_data
from utils import save_to_markdown, load_markdown, get_qa_data
from advanced_scraper import AdvancedScraper, main as run_advanced_scraper

# Set page config
st.set_page_config(
    page_title="Indian Agriculture Data Scraper",
    page_icon="🌾",
    layout="wide"
)

# Initialize session state variables
if 'scraped_data' not in st.session_state:
    st.session_state.scraped_data = []
if 'qa_data' not in st.session_state:
    st.session_state.qa_data = []
if 'current_file' not in st.session_state:
    st.session_state.current_file = None
if 'search_results' not in st.session_state:
    st.session_state.search_results = []
if 'openrouter_api_key' not in st.session_state:
    st.session_state.openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")

# Title and description
st.title("🌾 Indian Agriculture Data Scraper")
st.markdown("""
This tool helps you collect and structure agriculture data from Indian sources.
The output is organized in a Q&A format suitable for RAG (Retrieval Augmented Generation) pipelines.
""")

# Create sidebar for controls
with st.sidebar:
    st.header("Controls")
    tab1, tab2 = st.tabs(["Scrape New Data", "Load Existing Data"])
    
    with tab1:
        st.subheader("Search and Scrape")
        search_option = st.radio("Choose input method:", ["Search Keywords", "Direct URL"])
        
        if search_option == "Search Keywords":
            keywords = st.text_input("Enter keywords to search (e.g., 'Indian agriculture practices'):")
            num_results = st.slider("Number of search results to scrape:", 1, 20, 5)
            
            if st.button("Search and Scrape"):
                with st.spinner("Searching and scraping data..."):
                    if keywords:
                        try:
                            search_results = search_agriculture_info(keywords, num_results)
                            
                            # Progress bar for scraping
                            progress_bar = st.progress(0)
                            st.session_state.scraped_data = []
                            
                            for i, result in enumerate(search_results):
                                st.write(f"Scraping: {result['title']} - {result['url']}")
                                try:
                                    content = scrape_url(result['url'])
                                    if content:
                                        st.session_state.scraped_data.append({
                                            'url': result['url'],
                                            'title': result['title'],
                                            'content': content
                                        })
                                except Exception as e:
                                    st.error(f"Error scraping {result['url']}: {str(e)}")
                                
                                # Update progress
                                progress = (i + 1) / len(search_results)
                                progress_bar.progress(progress)
                                
                            st.success(f"Scraped {len(st.session_state.scraped_data)} pages successfully!")
                            
                            # Process scraped data into QA format
                            with st.spinner("Processing data into Q&A format..."):
                                # Use OpenRouter if API key is available
                                use_openrouter = bool(st.session_state.openrouter_api_key)
                                if use_openrouter:
                                    st.info("✓ Using OpenRouter API for enhanced Q&A generation...")
                                else:
                                    st.warning("⚠️ OpenRouter API key not provided. For better results, add your OpenRouter API key in the sidebar.")
                                    
                                # Show progress
                                progress_bar = st.progress(0)
                                processing_status = st.empty()
                                processing_status.text("Starting processing...")
                                
                                # Process each item with progress updates
                                total_items = len(st.session_state.scraped_data)
                                st.session_state.qa_data = []
                                
                                if total_items > 0:
                                    for i, item in enumerate(st.session_state.scraped_data):
                                        processing_status.text(f"Processing content from {item.get('url', 'unknown')}...")
                                        
                                        # Process this item only
                                        single_item_qa = process_text_to_qa([item], 
                                                                          use_openrouter=use_openrouter, 
                                                                          api_key=st.session_state.openrouter_api_key)
                                        
                                        # Add the results to our overall list
                                        st.session_state.qa_data.extend(single_item_qa)
                                        
                                        # Update progress
                                        progress = (i + 1) / total_items
                                        progress_bar.progress(progress)
                                        processing_status.text(f"Processed {i+1}/{total_items} sources. Generated {len(st.session_state.qa_data)} Q&A pairs so far.")
                                
                                st.success(f"✓ Successfully generated {len(st.session_state.qa_data)} Q&A pairs!")
                                
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")
        
        else:  # Direct URL
            url = st.text_input("Enter URL to scrape:")
            
            if st.button("Scrape URL"):
                with st.spinner("Scraping URL..."):
                    if url:
                        try:
                            content = scrape_url(url)
                            if content:
                                st.session_state.scraped_data = [{
                                    'url': url,
                                    'title': url.split("/")[-1],
                                    'content': content
                                }]
                                st.success("URL scraped successfully!")
                                
                                # Process scraped data into QA format
                                with st.spinner("Processing data into Q&A format..."):
                                    # Use OpenRouter if API key is available
                                    use_openrouter = bool(st.session_state.openrouter_api_key)
                                    if use_openrouter:
                                        st.info("✓ Using OpenRouter API for enhanced Q&A generation...")
                                    else:
                                        st.warning("⚠️ OpenRouter API key not provided. For better results, add your OpenRouter API key in the sidebar.")
                                    
                                    # Show progress
                                    progress_bar = st.progress(0)
                                    processing_status = st.empty()
                                    processing_status.text("Starting processing...")
                                    
                                    # Process the single URL with progress
                                    processing_status.text(f"Processing content from {url}...")
                                    
                                    st.session_state.qa_data = process_text_to_qa(st.session_state.scraped_data, 
                                                                                 use_openrouter=use_openrouter, 
                                                                                 api_key=st.session_state.openrouter_api_key)
                                    
                                    progress_bar.progress(1.0)
                                    st.success(f"✓ Successfully generated {len(st.session_state.qa_data)} Q&A pairs!")
                            else:
                                st.error("Failed to extract content from the URL.")
                        except Exception as e:
                            st.error(f"An error occurred: {str(e)}")
    
    with tab2:
        st.subheader("Load Existing Data")
        # Get list of markdown files in current directory
        md_files = [f for f in os.listdir('.') if f.endswith('.md') and f.startswith('agriculture_qa_')]
        
        if md_files:
            selected_file = st.selectbox("Select a file to load:", md_files)
            
            if st.button("Load File"):
                with st.spinner("Loading data..."):
                    try:
                        st.session_state.qa_data = load_markdown(selected_file)
                        st.session_state.current_file = selected_file
                        st.success(f"Loaded {len(st.session_state.qa_data)} Q&A pairs from {selected_file}")
                    except Exception as e:
                        st.error(f"Error loading file: {str(e)}")
        else:
            st.info("No saved files found.")
    
    # Note about downloading data
    st.subheader("Download Data")
    st.info("⚠️ Note: To download your data, please use the 'Download' tab in the main content area. No data is stored on the server.")
    st.write("This ensures your data privacy and prevents excessive storage usage.")
    
    # OpenRouter API Key input
    st.subheader("OpenRouter Integration")
    api_key = st.text_input("OpenRouter API Key (optional):", 
                            value=st.session_state.openrouter_api_key, 
                            type="password")
    if api_key != st.session_state.openrouter_api_key:
        st.session_state.openrouter_api_key = api_key
        st.success("API key updated")

# Helper functions for downloading data
def get_binary_file_downloader_html(bin_file, file_label='File'):
    """
    Generate an HTML link to download a binary file
    """
    with open(bin_file, 'rb') as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    href = f'<a href="data:application/octet-stream;base64,{b64}" download="{os.path.basename(bin_file)}">{file_label}</a>'
    return href

def download_qa_data_as_json(qa_data):
    """
    Convert QA data to JSON for download
    """
    json_str = json.dumps(qa_data, indent=4)
    b64 = base64.b64encode(json_str.encode()).decode()
    href = f'<a href="data:file/json;base64,{b64}" download="agriculture_qa_data.json">Download JSON</a>'
    return href

def download_qa_data_as_csv(qa_data):
    """
    Convert QA data to CSV for download
    """
    # Convert to DataFrame
    rows = []
    for item in qa_data:
        rows.append({
            'index': item.get('index', ''),
            'question': item.get('question', ''),
            'answer': item.get('answer', ''),
            'source': item.get('source', '')
        })
    
    df = pd.DataFrame(rows)
    
    # Convert to CSV
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="agriculture_qa_data.csv">Download CSV</a>'
    return href

def create_zip_from_qa(qa_data):
    """
    Create a zip file from QA data with multiple formats
    """
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Create the main content
        md_file = os.path.join(tmpdirname, "agriculture_qa_data.md")
        json_file = os.path.join(tmpdirname, "agriculture_qa_data.json")
        csv_file = os.path.join(tmpdirname, "agriculture_qa_data.csv")
        
        # Save as markdown
        save_to_markdown(qa_data, md_file)
        
        # Save as JSON
        with open(json_file, 'w') as f:
            json.dump(qa_data, f, indent=4)
        
        # Save as CSV
        rows = []
        for item in qa_data:
            rows.append({
                'index': item.get('index', ''),
                'question': item.get('question', ''),
                'answer': item.get('answer', ''),
                'source': item.get('source', '')
            })
        
        df = pd.DataFrame(rows)
        df.to_csv(csv_file, index=False)
        
        # Create zip file
        memory_file = BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add files to the zip
            for root, dirs, files in os.walk(tmpdirname):
                for file in files:
                    zf.write(
                        os.path.join(root, file),
                        os.path.basename(os.path.join(root, file))
                    )
        
        memory_file.seek(0)
        return memory_file.getvalue()

# Main content area
tab1, tab2, tab3, tab4 = st.tabs(["Data Viewer", "Search", "Download", "Advanced Scraper"])

with tab1:
    if st.session_state.qa_data:
        st.subheader(f"Q&A Data ({len(st.session_state.qa_data)} entries)")
        
        # Filter options
        st.write("Filter Q&A entries:")
        col1, col2 = st.columns(2)
        with col1:
            filter_text = st.text_input("Filter by text content:", "")
        with col2:
            filter_source = st.text_input("Filter by source URL:", "")
        
        # Apply filters
        filtered_data = st.session_state.qa_data
        if filter_text:
            filtered_data = [item for item in filtered_data if filter_text.lower() in item['question'].lower() or 
                             filter_text.lower() in item['answer'].lower()]
        if filter_source:
            filtered_data = [item for item in filtered_data if filter_source.lower() in item['source'].lower()]
        
        st.write(f"Showing {len(filtered_data)} entries")
        
        # Display QA data
        for i, qa_pair in enumerate(filtered_data):
            with st.expander(f"{i+1}. {qa_pair['question']}"):
                st.markdown(f"**Answer:** {qa_pair['answer']}")
                st.markdown(f"**Source:** [{qa_pair['source']}]({qa_pair['source']})")
                
                # Delete button for each entry
                if st.button(f"Delete entry #{i+1}", key=f"delete_{i}"):
                    st.session_state.qa_data.remove(qa_pair)
                    st.success(f"Entry #{i+1} deleted")
                    st.rerun()
    else:
        st.info("No Q&A data available. Use the sidebar to scrape new data or load existing data.")

with tab2:
    st.subheader("Search Q&A Data")
    search_query = st.text_input("Enter search query:")
    
    if st.button("Search") and search_query:
        if st.session_state.qa_data:
            with st.spinner("Searching..."):
                st.session_state.search_results = search_qa_data(search_query, st.session_state.qa_data)
                st.success(f"Found {len(st.session_state.search_results)} results")
        else:
            st.warning("No data to search. Please scrape or load data first.")
    
    # Display search results
    if hasattr(st.session_state, 'search_results') and st.session_state.search_results:
        for i, result in enumerate(st.session_state.search_results):
            with st.expander(f"{i+1}. {result['question']} (Score: {result['score']:.2f})"):
                st.markdown(f"**Answer:** {result['answer']}")
                st.markdown(f"**Source:** [{result['source']}]({result['source']})")
    elif search_query:
        st.info("No matching results found.")

with tab3:
    st.subheader("Download Data")
    
    if st.session_state.qa_data:
        st.write(f"Download the current Q&A dataset ({len(st.session_state.qa_data)} entries)")
        
        download_format = st.radio("Select format:", ["Markdown", "JSON", "CSV", "All formats (ZIP)"])
        
        if download_format == "Markdown":
            # Generate a temporary markdown file
            temp_md = tempfile.NamedTemporaryFile(delete=False, suffix='.md')
            temp_md.close()
            save_to_markdown(st.session_state.qa_data, temp_md.name)
            
            st.markdown(get_binary_file_downloader_html(temp_md.name, 'Download Markdown'), unsafe_allow_html=True)
            os.unlink(temp_md.name)  # Clean up the temp file
            
        elif download_format == "JSON":
            st.markdown(download_qa_data_as_json(st.session_state.qa_data), unsafe_allow_html=True)
            
        elif download_format == "CSV":
            st.markdown(download_qa_data_as_csv(st.session_state.qa_data), unsafe_allow_html=True)
            
        elif download_format == "All formats (ZIP)":
            zip_data = create_zip_from_qa(st.session_state.qa_data)
            b64 = base64.b64encode(zip_data).decode()
            href = f'<a href="data:application/zip;base64,{b64}" download="agriculture_qa_data.zip">Download ZIP with all formats</a>'
            st.markdown(href, unsafe_allow_html=True)
    else:
        st.info("No data available for download. Please scrape or load data first.")

with tab4:
    st.subheader("Advanced Web Scraper")
    st.markdown("""
    This advanced scraper can extract text, tables, images, and PDF content from websites.
    All content is organized and provided as a downloadable ZIP archive.
    """)
    
    # Initialize session state for advanced scraper
    if 'advanced_scraping_result' not in st.session_state:
        st.session_state.advanced_scraping_result = None
    if 'advanced_scraping_zip' not in st.session_state:
        st.session_state.advanced_scraping_zip = None
    
    url = st.text_input("Enter URL to scrape:", key="advanced_url")
    max_pages = st.slider("Maximum pages to scrape (depth limit):", 1, 100, 20)
    
    if st.button("Start Advanced Scraping"):
        if url:
            with st.spinner("Scraping website... This may take several minutes depending on the website size."):
                try:
                    # Create a temporary directory for output
                    with tempfile.TemporaryDirectory() as tmpdirname:
                        output_dir = os.path.join(tmpdirname, 'scraped_data')
                        
                        # Initialize the scraper
                        scraper = AdvancedScraper(
                            base_url=url,
                            output_dir=output_dir,
                            max_pages=max_pages
                        )
                        
                        # Start scraping
                        result = scraper.scrape()
                        
                        # Get the zip file
                        zip_path = result['zip_path']
                        
                        # Read the zip file into memory
                        with open(zip_path, 'rb') as f:
                            zip_data = f.read()
                        
                        # Store in session state
                        st.session_state.advanced_scraping_result = result
                        st.session_state.advanced_scraping_zip = zip_data
                        
                        st.success("Scraping completed successfully!")
                except Exception as e:
                    st.error(f"An error occurred during scraping: {str(e)}")
        else:
            st.warning("Please enter a URL to scrape.")
    
    # Display result and download option
    if st.session_state.advanced_scraping_result:
        result = st.session_state.advanced_scraping_result
        
        st.subheader("Scraping Summary")
        st.write(f"Pages scraped: {result['pages_scraped']}")
        st.write(f"Text files: {result['text_files']}")
        st.write(f"Tables extracted: {result['tables']}")
        st.write(f"Images downloaded: {result['images']}")
        st.write(f"PDFs downloaded: {result['pdfs']}")
        
        # Provide download link
        if st.session_state.advanced_scraping_zip:
            b64 = base64.b64encode(st.session_state.advanced_scraping_zip).decode()
            filename = f"scraped_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            href = f'<a href="data:application/zip;base64,{b64}" download="{filename}">Download all scraped content (ZIP)</a>'
            st.markdown(href, unsafe_allow_html=True)
            
            # Option to clear results
            if st.button("Clear scraping results"):
                st.session_state.advanced_scraping_result = None
                st.session_state.advanced_scraping_zip = None
                st.rerun()

# Footer
st.markdown("---")
st.markdown("Made for Master Srinivas by agent_siri from Srinivas VC")
st.markdown("Built for Indian Agriculture Data Collection for RAG Pipeline Development")
