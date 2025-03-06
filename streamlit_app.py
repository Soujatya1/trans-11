import streamlit as st
from docx import Document
from docx.oxml.ns import qn
from docx.shared import Pt
from deep_translator import GoogleTranslator
import concurrent.futures

def translate_doc(doc, destination='hi'):
    translator = GoogleTranslator(source='auto', target=destination)

    for p in doc.paragraphs:
        if p.text.strip():
            try:
                for run in p.runs:
                    if run.text.strip():
                        original_text = run.text.strip()
                        translated_text = translator.translate(original_text) or original_text

            
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
                                    translated_text = translator.translate(original_text) or original_text
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
            "Bengali": "bn", "Hindi": "hi", "Odia": "or", "Punjabi": "pa", 
            "Tamil": "ta", "Telegu": "te", "Gujarati": "gu", "Malayalam": "ml"
        }
        target_language = st.selectbox("Select Target Language", options=list(language_options.keys()))
        language_code = language_options[target_language]
        
        if st.button("Translate Document"):
            with st.spinner('Translating...'):
                translated_doc = translate_doc(doc, language_code)
                
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
