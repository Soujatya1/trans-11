import streamlit as st
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
import concurrent.futures
import requests
from langdetect import detect
import time

def translate_text(text, source_language, target_language):
    if not text or not text.strip():
        return text
        
    if source_language == target_language:
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
    for attempt in range(max_retries):
        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=10)
            if response.status_code == 200:
                response_data = response.json()
                service_id = response_data["pipelineResponseConfig"][0]["config"][0]["serviceId"]
                break
            else:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
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
            compute_response = requests.post(callback_url, json=compute_payload, headers=headers2, timeout=15)
            if compute_response.status_code == 200:
                compute_response_data = compute_response.json()
                translated_content = compute_response_data["pipelineResponse"][0]["output"][0]["target"]
                return translated_content
            else:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                else:
                    return text
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                return text

def detect_language(text, valid_languages):
    if not text or not text.strip():
        return "en"
    
    try:
        detected = detect(text.strip())
        if detected in valid_languages:
            return detected
        return "en"
    except Exception as e:
        print(f"Error detecting language: {e}")
        return "en"

def translate_paragraph_text(paragraph, target_language, valid_languages):
    if not paragraph.text.strip():
        return
        
    source_lang = detect_language(paragraph.text, valid_languages)
    if source_lang == target_language:
        return
        
    try:
        full_translation = translate_text(paragraph.text, source_lang, target_language)
        if full_translation and full_translation != paragraph.text:
            for run in paragraph.runs:
                run.text = ""
            new_run = paragraph.add_run(full_translation)
            return True
    except Exception as e:
        print(f"Error in paragraph translation: {e}")
        return False
        
def translate_doc(doc, target_language='hi', valid_languages=None):
    if valid_languages is None:
        valid_languages = ["en", "hi"]
        
    stats = {
        "runs_processed": 0,
        "paragraphs_processed": 0,
        "successful_translations": 0,
        "fallback_translations": 0,
        "failed_translations": 0
    }
    
    for p in doc.paragraphs:
        if p.text.strip():
            stats["paragraphs_processed"] += 1
            if len(p.runs) > 1:
                if translate_paragraph_text(p, target_language, valid_languages):
                    stats["successful_translations"] += 1
                    continue
            
            for run in p.runs:
                if run.text.strip():
                    stats["runs_processed"] += 1
                    try:
                        original_text = run.text
                        source_lang = detect_language(original_text, valid_languages)
                        
                        if source_lang == target_language:
                            continue
                            
                        translated_text = translate_text(original_text, source_lang, target_language)
                        if translated_text and translated_text != original_text:
                            run.text = translated_text
                            stats["successful_translations"] += 1
                        else:
                            stats["failed_translations"] += 1
                    except Exception as e:
                        print(f"Error translating run: {e}")
                        stats["failed_translations"] += 1
   
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    stats["paragraphs_processed"] += 1
                    
                    if len(para.runs) > 1:
                        if translate_paragraph_text(para, target_language, valid_languages):
                            stats["successful_translations"] += 1
                            continue
                    
                    for run in para.runs:
                        if run.text.strip():
                            stats["runs_processed"] += 1
                            try:
                                original_text = run.text
                                source_lang = detect_language(original_text, valid_languages)
                                
                                if source_lang == target_language:
                                    continue
                                    
                                translated_text = translate_text(original_text, source_lang, target_language)
                                if translated_text and translated_text != original_text:
                                    run.text = translated_text
                                    stats["successful_translations"] += 1
                                else:
                                    stats["failed_translations"] += 1
                            except Exception as e:
                                print(f"Error translating cell run: {e}")
                                stats["failed_translations"] += 1
                                
    return doc, stats
    
def main():
    st.title("Multilingual Document Translator")
    st.write("This app detects and translates text in multiple languages within the same document.")
    
    uploaded_file = st.file_uploader("Upload a Word Document", type=["docx"])
    if uploaded_file:
        doc = Document(uploaded_file)
        
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
        
        with st.expander("Advanced Options"):
            show_detected = st.checkbox("Show detected languages in document", value=True)
            show_stats = st.checkbox("Show translation statistics", value=True)
        
        if st.button("Translate Document"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            if show_detected:
                status_text.text("Analyzing document languages...")
                progress_bar.progress(10)
                
                languages_detected = {}
                
                for p in doc.paragraphs:
                    if p.text.strip():
                        try:
                            detected_lang = detect_language(p.text.strip(), valid_language_codes)
                            if detected_lang in languages_detected:
                                languages_detected[detected_lang] += 1
                            else:
                                languages_detected[detected_lang] = 1
                        except:
                            pass
                
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                try:
                                    detected_lang = detect_language(cell.text.strip(), valid_language_codes)
                                    if detected_lang in languages_detected:
                                        languages_detected[detected_lang] += 1
                                    else:
                                        languages_detected[detected_lang] = 1
                                except:
                                    pass
                
                progress_bar.progress(30)
                
                if languages_detected:
                    st.info("Languages detected in document:")
                    for lang, count in sorted(languages_detected.items(), key=lambda x: x[1], reverse=True):
                        st.write(f"- {lang}: {count} text segments")
                else:
                    st.warning("Could not detect any language. Will use English as default source.")
            
            status_text.text("Translating document... This may take several minutes for large documents.")
            progress_bar.progress(40)
            
            translated_doc, stats = translate_doc(doc, language_code, valid_language_codes)
            
            progress_bar.progress(90)
            status_text.text("Saving translated document...")
            
            with open("translated_document.docx", "wb") as f:
                translated_doc.save(f)
            
            progress_bar.progress(100)
            
            if show_stats:
                st.subheader("Translation Statistics")
                #st.write(f"- Paragraphs processed: {stats['paragraphs_processed']}")
                #st.write(f"- Runs processed: {stats['runs_processed']}")
                #st.write(f"- Successful translations: {stats['successful_translations']}")
                st.write(f"- Failed translations: {stats['failed_translations']}")
                
                success_rate = 0
                if stats['runs_processed'] > 0:
                    success_rate = (stats['successful_translations'] / stats['runs_processed']) * 100
                st.write(f"- Success rate: {success_rate:.1f}%")
            
            with open("translated_document.docx", "rb") as f:
                st.download_button(
                    label="Download Translated Document",
                    data=f,
                    file_name="translated_document.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                )
            status_text.text("")
            st.success("Translation complete!")

if __name__ == '__main__':
    main()
