import streamlit as st
import streamlit_authenticator as stauth
from openai import OpenAI
import PyPDF2
from docx import Document
import openpyxl
from pptx import Presentation
import io
import sqlite3

# --- DB初期化 ---
conn = sqlite3.connect("history.db")
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    question TEXT,
    answer TEXT,
    doc_name TEXT,
    bookmark INTEGER DEFAULT 0
)
""")
conn.commit()

# --- ユーザー認証設定 ---
users = {
    "user1": {"name": "ユーザー1", "password": stauth.Hasher(["password1"]).generate()},
    "user2": {"name": "ユーザー2", "password": stauth.Hasher(["password2"]).generate()},
}
names = [v["name"] for v in users.values()]
usernames = list(users.keys())
passwords = [v["password"] for v in users.values()]

authenticator = stauth.Authenticate(names, usernames, passwords, "app_cookie", "random_key", cookie_expiry_days=30)
name, authentication_status, username = authenticator.login("ログイン", "main")

if authentication_status is False:
    st.error("ユーザー名またはパスワードが違います")
elif authentication_status is None:
    st.info("ログインしてください")
else:
    st.success(f"ようこそ {name} さん！")
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
                # DB保存
                c.execute("INSERT INTO history (username, question, answer, doc_name, bookmark) VALUES (?, ?, ?, ?, 0)",
                          (username, question, answer, uploaded_file.name))
                conn.commit()

        # 履歴表示
        st.header("履歴")
        c.execute("SELECT id, question, answer, doc_name, bookmark FROM history WHERE username=? ORDER BY id DESC", (username,))
        rows = c.fetchall()
        for row in rows:
            id_, q, a, doc, bm = row
            col1, col2 = st.columns([10,1])
            with col1:
                st.write(f"**Q:** {q}")
                st.write(f"**A:** {a}")
                st.write(f"**ドキュメント:** {doc}")
            with col2:
                if st.button("⭐" if bm else "☆", key=f"bookmark_{id_}"):
                    new_bm = 0 if bm else 1
                    c.execute("UPDATE history SET bookmark=? WHERE id=?", (new_bm, id_))
                    conn.commit()
                    st.experimental_rerun()

        # しおり一覧
        st.header("しおり一覧")
        c.execute("SELECT question, answer, doc_name FROM history WHERE username=? AND bookmark=1 ORDER BY id DESC", (username,))
        bookmarks = c.fetchall()
        for q, a, doc in bookmarks:
            st.write(f"**Q:** {q}")
            st.write(f"**A:** {a}")
            st.write(f"**ドキュメント:** {doc}")

        # 履歴ダウンロード
        c.execute("SELECT question, answer, doc_name, bookmark FROM history WHERE username=?", (username,))
        hist = c.fetchall()
        import json
        hist_json = json.dumps([
            {"question": q, "answer": a, "doc_name": d, "bookmark": bool(bm)}
            for q, a, d, bm in hist
        ], ensure_ascii=False, indent=2)
        st.download_button("履歴をダウンロード", data=hist_json, file_name="history.json", mime="application/json")
