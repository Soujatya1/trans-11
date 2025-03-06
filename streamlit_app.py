import streamlit as st
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from deep_translator import GoogleTranslator
import concurrent.futures
import requests

def translate_text(text, source_language, target_language):
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
    
    try:
        response = requests.post(api_url, json=payload, headers=headers)
        if response.status_code == 200:
            response_data = response.json()
            service_id = response_data["pipelineResponseConfig"][0]["config"][0]["serviceId"]
        else:
            return text
    
    except Exception as e:
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
    
    try:
        compute_response = requests.post(callback_url, json=compute_payload, headers=headers2)
        if compute_response.status_code == 200:
            compute_response_data = compute_response.json()
            translated_content = compute_response_data["pipelineResponse"][0]["output"][0]["target"]
            return translated_content
        else:
            return text
    
    except Exception as e:
        return text

def translate_doc(doc, source='en', destination='hi'):
    for p in doc.paragraphs:
        if p.text.strip():
            try:
                for run in p.runs:
                    if run.text.strip():
                        original_text = run.text.strip()
                        translated_text = translate_text(original_text, source, destination) or original_text
                        run.text = translated_text
            except Exception as e:
                print(f"Error translating paragraph: {e}")
   
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    try:
                        for para in cell.paragraphs:
                            for run in para.runs:
                                if run.text.strip():
                                    original_text = run.text.strip()
                                    translated_text = translate_text(original_text, source, destination) or original_text
                                    run.text = translated_text
                    except Exception as e:
                        print(f"Error translating cell text: {e}")
    return doc
    
def main():
    st.title("Word Document Translator")
    
    uploaded_file = st.file_uploader("Upload a Word Document", type=["docx"])
    if uploaded_file:
        doc = Document(uploaded_file)
        
        language_options = {
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
        
        source_language = st.selectbox("Select Source Language", options=["English", "Auto-detect"], index=0)
        source_code = "en" if source_language == "English" else "auto"
        
        target_language = st.selectbox("Select Target Language", options=list(language_options.keys()))
        language_code = language_options[target_language]
        
        if st.button("Translate Document"):
            with st.spinner('Translating...'):
                translated_doc = translate_doc(doc, source_code, language_code)
                
                with open("translated_document.docx", "wb") as f:
                    translated_doc.save(f)
                
                with open("translated_document.docx", "rb") as f:
                    st.download_button(
                        label="Download Translated Document",
                        data=f,
                        file_name="translated_document.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    )
                st.success("Translation complete!")

if __name__ == '__main__':
    main()
