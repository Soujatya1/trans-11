import streamlit as st
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
import concurrent.futures
import requests
from langdetect import detect
import time
from docx.shared import RGBColor
from docx.enum.text import WD_COLOR_INDEX
import os
import logging
from logging.handlers import RotatingFileHandler
import traceback
from datetime import datetime

def list_log_files(log_directory="logs"):
    """List all log files in the specified directory"""
    if not os.path.exists(log_directory):
        return []
    
    log_files = [f for f in os.listdir(log_directory) if f.endswith('.log')]
    # Sort by modification time, newest first
    log_files.sort(key=lambda x: os.path.getmtime(os.path.join(log_directory, x)), reverse=True)
    return log_files

def setup_logging(log_directory="logs", log_level=logging.INFO):
    os.makedirs(log_directory, exist_ok=True)
    logger = logging.getLogger('document_translator')
    logger.setLevel(log_level)
    
    log_file = os.path.join(log_directory, f'document_translator_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    file_handler.setLevel(log_level)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"Logging configured. Log file: {log_file}")
    return logger

logger = setup_logging()

def translate_text(text, source_language, target_language):
    if not text or not text.strip():
        logger.debug(f"Empty text received for translation, returning as is")
        return text
        
    if source_language == target_language:
        logger.debug(f"Source and target languages are the same ({source_language}), skipping translation")
        return text
        
    api_url = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline/"
    user_id = "00fe73dcb98f43f39c1c308616856405"
    ulca_api_key = "426d392042-9028-4f13-aea7-ad172f8048f8"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {ulca_api_key}",
        "userID": user_id,
        "ulcaApiKey": ulca_api_key
    }
    
    payload = {
        "pipelineTasks": [
            {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source_language,
                        "targetLanguage": target_language
                    }
                }
            }
        ],
        "pipelineRequestConfig": {
            "pipelineId": "64392f96daac500b55c543cd"
        }
    }
    
    max_retries = 3
    logger.info(f"Translating text from {source_language} to {target_language} (length: {len(text)})")
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Translation attempt {attempt+1}/{max_retries}")
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                response_data = response.json()
                service_id = response_data["pipelineResponseConfig"][0]["config"][0]["serviceId"]
                logger.debug(f"Successfully obtained service ID: {service_id}")
                break
            else:
                logger.warning(f"Failed to get service ID, status code: {response.status_code}, attempt {attempt+1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    logger.error(f"Failed to get service ID after {max_retries} attempts")
                    return text
        except Exception as e:
            logger.error(f"Exception in getting service ID: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                logger.error(f"Failed to get service ID after {max_retries} attempts due to exception")
                return text
    
    compute_payload = {
        "pipelineTasks": [
            {
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source_language,
                        "targetLanguage": target_language
                    },
                    "serviceId": service_id
                }
            }
        ],
        "inputData": {
            "input": [
                {
                    "source": text
                }
            ]
        }
    }
    
    callback_url = response_data["pipelineInferenceAPIEndPoint"]["callbackUrl"]
    headers2 = {
        "Content-Type": "application/json",
        response_data["pipelineInferenceAPIEndPoint"]["inferenceApiKey"]["name"]: 
        response_data["pipelineInferenceAPIEndPoint"]["inferenceApiKey"]["value"]
    }
    
    for attempt in range(max_retries):
        try:
            logger.debug(f"Translation compute attempt {attempt+1}/{max_retries}")
            compute_response = requests.post(callback_url, json=compute_payload, headers=headers2, timeout=15)
            if compute_response.status_code == 200:
                compute_response_data = compute_response.json()
                translated_content = compute_response_data["pipelineResponse"][0]["output"][0]["target"]
                logger.debug(f"Translation successful")
                return translated_content
            else:
                logger.warning(f"Translation compute failed, status code: {compute_response.status_code}, attempt {attempt+1}/{max_retries}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    logger.error(f"Translation compute failed after {max_retries} attempts")
                    return text
        except Exception as e:
            logger.error(f"Exception in translation compute: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                logger.error(f"Translation compute failed after {max_retries} attempts due to exception")
                return text

def detect_language(text, valid_languages):
    if not text or not text.strip():
        logger.debug(f"Empty text for language detection, returning default 'en'")
        return "en"
    
    try:
        detected = detect(text.strip())
        if detected in valid_languages:
            logger.debug(f"Detected language: {detected}")
            return detected
        logger.debug(f"Detected language {detected} not in valid languages, returning default 'en'")
        return "en"
    except Exception as e:
        logger.error(f"Error detecting language: {str(e)}")
        return "en"

def translate_paragraph_text(paragraph, target_language, valid_languages):
    if not paragraph.text.strip():
        logger.debug("Empty paragraph, skipping translation")
        return
        
    source_lang = detect_language(paragraph.text, valid_languages)
    if source_lang == target_language:
        logger.debug(f"Paragraph already in target language ({target_language}), skipping translation")
        return
        
    try:
        logger.info(f"Translating paragraph from {source_lang} to {target_language} (length: {len(paragraph.text)})")
        full_translation = translate_text(paragraph.text, source_lang, target_language)
        if full_translation and full_translation != paragraph.text:
            logger.debug("Translation successful, updating paragraph")
            for run in paragraph.runs:
                run.text = ""
            new_run = paragraph.add_run(full_translation)
            return True
        else:
            logger.warning("Translation failed or returned same text, highlighting paragraph")
            # Highlight all runs in the paragraph if translation fails
            for run in paragraph.runs:
                run.font.highlight_color = WD_COLOR_INDEX.RED
            return False
    except Exception as e:
        logger.error(f"Error in paragraph translation: {str(e)}")
        logger.debug(traceback.format_exc())
        # Highlight all runs in the paragraph on error
        for run in paragraph.runs:
            run.font.highlight_color = WD_COLOR_INDEX.RED
        return False
        
def translate_doc(doc, target_language='hi', valid_languages=None):
    # Default valid languages now include all languages from language_options
    if valid_languages is None:
        valid_languages = [
            "en", "ks", "ne", "bn", "mr", "sd", "te", "gu", "gom", "ur",
            "sat", "kn", "ml", "mni", "ta", "hi", "pa", "or", "doi", 
            "as", "sa", "brx", "mai"
        ]
        
    stats = {
        "runs_processed": 0,
        "paragraphs_processed": 0,
        "successful_translations": 0,
        "fallback_translations": 0,
        "failed_translations": 0
    }
    
    logger.info(f"Starting document translation to {target_language}")
    
    # Process paragraphs
    logger.info("Processing document paragraphs")
    for p_idx, p in enumerate(doc.paragraphs):
        if p.text.strip():
            stats["paragraphs_processed"] += 1
            logger.debug(f"Processing paragraph {p_idx+1} (length: {len(p.text)})")
            
            if len(p.runs) > 1:
                if translate_paragraph_text(p, target_language, valid_languages):
                    stats["successful_translations"] += 1
                    continue
            
            for run_idx, run in enumerate(p.runs):
                if run.text.strip():
                    stats["runs_processed"] += 1
                    try:
                        original_text = run.text
                        source_lang = detect_language(original_text, valid_languages)
                        
                        if source_lang == target_language:
                            logger.debug(f"Run {run_idx+1} already in target language, skipping")
                            continue
                            
                        logger.debug(f"Translating run {run_idx+1} from {source_lang} to {target_language}")
                        translated_text = translate_text(original_text, source_lang, target_language)
                        if translated_text and translated_text != original_text:
                            run.text = translated_text
                            stats["successful_translations"] += 1
                            logger.debug(f"Run {run_idx+1} translation successful")
                        else:
                            run.font.highlight_color = WD_COLOR_INDEX.RED
                            stats["failed_translations"] += 1
                            logger.warning(f"Run {run_idx+1} translation failed or unchanged")
                    except Exception as e:
                        logger.error(f"Error translating run {run_idx+1}: {str(e)}")
                        logger.debug(traceback.format_exc())
                        run.font.highlight_color = WD_COLOR_INDEX.RED
                        stats["failed_translations"] += 1
   
    # Process tables
    logger.info("Processing document tables")
    for table_idx, table in enumerate(doc.tables):
        logger.debug(f"Processing table {table_idx+1}")
        for row_idx, row in enumerate(table.rows):
            for cell_idx, cell in enumerate(row.cells):
                for para_idx, para in enumerate(cell.paragraphs):
                    if para.text.strip():
                        stats["paragraphs_processed"] += 1
                        logger.debug(f"Processing table {table_idx+1}, row {row_idx+1}, cell {cell_idx+1}, paragraph {para_idx+1}")
                        
                        if len(para.runs) > 1:
                            if translate_paragraph_text(para, target_language, valid_languages):
                                stats["successful_translations"] += 1
                                continue
                        
                        for run_idx, run in enumerate(para.runs):
                            if run.text.strip():
                                stats["runs_processed"] += 1
                                try:
                                    original_text = run.text
                                    source_lang = detect_language(original_text, valid_languages)
                                    
                                    if source_lang == target_language:
                                        logger.debug(f"Cell run already in target language, skipping")
                                        continue
                                        
                                    logger.debug(f"Translating cell run from {source_lang} to {target_language}")
                                    translated_text = translate_text(original_text, source_lang, target_language)
                                    if translated_text and translated_text != original_text:
                                        run.text = translated_text
                                        stats["successful_translations"] += 1
                                        logger.debug(f"Cell run translation successful")
                                    else:
                                        run.font.highlight_color = WD_COLOR_INDEX.RED
                                        stats["failed_translations"] += 1
                                        logger.warning(f"Cell run translation failed or unchanged")
                                except Exception as e:
                                    logger.error(f"Error translating cell run: {str(e)}")
                                    logger.debug(traceback.format_exc())
                                    run.font.highlight_color = WD_COLOR_INDEX.RED
                                    stats["failed_translations"] += 1
    
    logger.info(f"Document translation complete. Stats: {stats}")                    
    return doc, stats
    
def main():
    logger.info("Starting Multilingual Document Translator application")
    
    st.title("Multilingual Document Translator")
    st.write("This app detects and translates text in multiple languages within the same document.")
    
    uploaded_file = st.file_uploader("Upload a Word Document", type=["docx"])
    if uploaded_file:
        logger.info(f"File uploaded: {uploaded_file.name}")
        
        try:
            doc = Document(uploaded_file)
            logger.info(f"Document loaded successfully")
        except Exception as e:
            logger.error(f"Error loading document: {str(e)}")
            logger.debug(traceback.format_exc())
            st.error(f"Error loading document: {str(e)}")
            return
        
        language_options = {
            "English": "en",
            "Kashmiri": "ks",
            "Nepali": "ne",
            "Bengali": "bn",
            "Marathi": "mr",
            "Sindhi": "sd",
            "Telugu": "te",
            "Gujarati": "gu",
            "Gom": "gom",
            "Urdu": "ur",
            "Santali": "sat",
            "Kannada": "kn",
            "Malayalam": "ml",
            "Manipuri": "mni",
            "Tamil": "ta",
            "Hindi": "hi",
            "Punjabi": "pa",
            "Odia": "or",
            "Dogri": "doi",
            "Assamese": "as",
            "Sanskrit": "sa",
            "Bodo": "brx",
            "Maithili": "mai"
        }
        
        valid_language_codes = list(language_options.values())
        valid_language_codes.append("en")
        
        target_language = st.selectbox("Select Target Language", options=list(language_options.keys()))
        language_code = language_options[target_language]
        logger.info(f"Target language selected: {target_language} ({language_code})")
        
        with st.expander("Advanced Options"):
            show_detected = st.checkbox("Show detected languages in document", value=True)
            show_stats = st.checkbox("Show translation statistics", value=True)
            logger.debug(f"Advanced options: show_detected={show_detected}, show_stats={show_stats}")
        
        if st.button("Translate Document"):
            logger.info("Translation process started")
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            if show_detected:
                status_text.text("Analyzing document languages...")
                progress_bar.progress(10)
                logger.info("Analyzing document languages")
                
                languages_detected = {}
                
                try:
                    # Detect languages in paragraphs
                    for p_idx, p in enumerate(doc.paragraphs):
                        if p.text.strip():
                            try:
                                detected_lang = detect_language(p.text.strip(), valid_language_codes)
                                if detected_lang in languages_detected:
                                    languages_detected[detected_lang] += 1
                                else:
                                    languages_detected[detected_lang] = 1
                            except Exception as e:
                                logger.error(f"Error detecting language in paragraph {p_idx+1}: {str(e)}")
                                logger.debug(traceback.format_exc())
                
                    # Detect languages in tables
                    for table_idx, table in enumerate(doc.tables):
                        for row in table.rows:
                            for cell in row.cells:
                                if cell.text.strip():
                                    try:
                                        detected_lang = detect_language(cell.text.strip(), valid_language_codes)
                                        if detected_lang in languages_detected:
                                            languages_detected[detected_lang] += 1
                                        else:
                                            languages_detected[detected_lang] = 1
                                    except Exception as e:
                                        logger.error(f"Error detecting language in table {table_idx+1} cell: {str(e)}")
                                        logger.debug(traceback.format_exc())
                    
                    logger.info(f"Languages detected: {languages_detected}")
                except Exception as e:
                    logger.error(f"Error during language detection: {str(e)}")
                    logger.debug(traceback.format_exc())
                
                progress_bar.progress(30)
                
                if languages_detected:
                    st.info("Languages detected in document:")
                    for lang, count in sorted(languages_detected.items(), key=lambda x: x[1], reverse=True):
                        st.write(f"- {lang}: {count} text segments")
                else:
                    logger.warning("No languages detected in document")
                    st.warning("Could not detect any language. Will use English as default source.")
            
            status_text.text("Translating document... This may take several minutes for large documents.")
            progress_bar.progress(40)
            
            try:
                logger.info(f"Starting document translation to {language_code}")
                translated_doc, stats = translate_doc(doc, language_code, valid_language_codes)
                logger.info(f"Translation complete. Stats: {stats}")
            except Exception as e:
                logger.error(f"Error during document translation: {str(e)}")
                logger.debug(traceback.format_exc())
                st.error(f"Error during translation: {str(e)}")
                return
            
            progress_bar.progress(90)
            status_text.text("Saving translated document...")
            
            try:
                logger.info("Saving translated document")
                with open("translated_document.docx", "wb") as f:
                    translated_doc.save(f)
                logger.info("Document saved successfully")
            except Exception as e:
                logger.error(f"Error saving translated document: {str(e)}")
                logger.debug(traceback.format_exc())
                st.error(f"Error saving document: {str(e)}")
                return
            
            progress_bar.progress(100)
            
            if show_stats:
                logger.info("Displaying translation statistics")
                st.subheader("Translation Statistics")
                st.write(f"- Paragraphs processed: {stats['paragraphs_processed']}")
                st.write(f"- Runs processed: {stats['runs_processed']}")
                st.write(f"- Successful translations: {stats['successful_translations']}")
                st.write(f"- Failed translations: {stats['failed_translations']}")
                
                success_rate = 0
                if stats['runs_processed'] > 0:
                    success_rate = (stats['successful_translations'] / stats['runs_processed']) * 100
                st.write(f"- Success rate: {success_rate:.1f}%")
            
            try:
                logger.info("Preparing download button for translated document")
                with open("translated_document.docx", "rb") as f:
                    st.download_button(
                        label="Download Translated Document",
                        data=f,
                        file_name="translated_document.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                status_text.text("")
                st.success("Translation complete!")
                logger.info("Translation process completed successfully")
            except Exception as e:
                logger.error(f"Error preparing download button: {str(e)}")
                logger.debug(traceback.format_exc())
                st.error(f"Error preparing download: {str(e)}")

    with st.expander("Log Files"):
    st.subheader("Download Log Files")
    log_files = list_log_files()
    
    if not log_files:
        st.info("No log files available.")
    else:
        selected_log = st.selectbox("Select Log File", options=log_files)
        
        if selected_log:
            log_path = os.path.join("logs", selected_log)
            try:
                with open(log_path, "rb") as f:
                    log_content = f.read()
                
                st.download_button(
                    label="Download Log File",
                    data=log_content,
                    file_name=selected_log,
                    mime="text/plain"
                )
                
                # Optional: Show log preview
                with st.expander("Log Preview"):
                    try:
                        # Read the last 50 lines for preview
                        with open(log_path, "r") as f:
                            lines = f.readlines()
                            preview = "".join(lines[-50:])  # Last 50 lines
                            st.text_area("Log Content (last 50 lines)", preview, height=300)
                    except Exception as e:
                        st.error(f"Error reading log file: {str(e)}")
                        
            except Exception as e:
                st.error(f"Error preparing log file for download: {str(e)}")

if __name__ == '__main__':
    try:
        logger.info("Application starting")
        main()
        logger.info("Application ended normally")
    except Exception as e:
        logger.critical(f"Unhandled exception in main: {str(e)}")
        logger.critical(traceback.format_exc())
        st.error(f"An unexpected error occurred: {str(e)}")
