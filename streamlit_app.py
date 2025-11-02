import streamlit as st
from openai import OpenAI
import PyPDF2
from docx import Document
import openpyxl
import io
from pptx import Presentation
import json

st.title("📄 ドキュメント質問応答")
st.write(
    "下のフォームからドキュメントをアップロードし、質問を入力してください。GPTが回答します！"
    "このアプリを利用するには OpenAI API キーが必要です。取得方法は[こちら](https://platform.openai.com/account/api-keys)。"
)

openai_api_key = st.text_input("OpenAI APIキー", type="password")
if not openai_api_key:
    st.info("OpenAI APIキーを入力してください。", icon="🗝️")
else:
    client = OpenAI(api_key=openai_api_key)
    uploaded_file = st.file_uploader(
        "ドキュメントをアップロードしてください（.txt, .md, .pdf, .docx, .xlsx, .pptx）", 
        type=("txt", "md", "pdf", "docx", "xlsx", "pptx")
    )
    question = st.text_area(
        "ドキュメントについて質問してください！",
        placeholder="この文書の要約を教えてください。",
        disabled=not uploaded_file,
    )

    # 履歴データの初期化
    if "history" not in st.session_state:
        st.session_state["history"] = []  # [{"question":..., "answer":..., "bookmark":False, "doc_name":...}]
        
    def extract_text(file):
        filename = file.name
        ext = filename.split('.')[-1].lower()
        if ext in ['txt', 'md']:
            return file.read().decode()
        elif ext == 'pdf':
            pdf_reader = PyPDF2.PdfReader(file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() or ""
            return text
        elif ext == 'docx':
            doc = Document(io.BytesIO(file.read()))
            return "\n".join([para.text for para in doc.paragraphs])
        elif ext == 'xlsx':
            wb = openpyxl.load_workbook(io.BytesIO(file.read()), data_only=True)
            text = ""
            for ws in wb.worksheets:
                for row in ws.iter_rows(values_only=True):
                    text += " ".join([str(cell) if cell is not None else "" for cell in row]) + "\n"
            return text
        elif ext == 'pptx':
            prs = Presentation(io.BytesIO(file.read()))
            text = ""
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text += shape.text + "\n"
            return text
        else:
            return None

    # 質問＆回答
    if uploaded_file and question:
        document = extract_text(uploaded_file)
        if not document or document.strip() == "":
            st.error("ファイルからテキストを抽出できませんでした。")
        else:
            messages = [
                {
                    "role": "user",
                    "content": f"以下はドキュメントです: {document} \n\n---\n\n {question}",
                }
            ]
            stream = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                stream=True,
            )
            answer = st.write_stream(stream)
            
            # 履歴追加
            st.session_state["history"].append({
                "question": question,
                "answer": answer,
                "bookmark": False,
                "doc_name": uploaded_file.name
            })

    st.header("履歴")
    for i, h in enumerate(st.session_state["history"]):
        col1, col2 = st.columns([10, 1])
        with col1:
            st.write(f"**Q:** {h['question']}")
            st.write(f"**A:** {h['answer']}")
            st.write(f"**ドキュメント:** {h['doc_name']}")
        with col2:
            if st.button("⭐" if h["bookmark"] else "☆", key=f"bookmark_{i}"):
                st.session_state["history"][i]["bookmark"] = not h["bookmark"]

    st.header("しおり一覧")
    for h in [x for x in st.session_state["history"] if x["bookmark"]]:
        st.write(f"**Q:** {h['question']}")
        st.write(f"**A:** {h['answer']}")
        st.write(f"**ドキュメント:** {h['doc_name']}")

    history_json = json.dumps(st.session_state["history"], ensure_ascii=False, indent=2)
    st.download_button("履歴をダウンロード", data=history_json, file_name="history.json", mime="application/json")
