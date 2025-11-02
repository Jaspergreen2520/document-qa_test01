import streamlit as st
from openai import OpenAI

# タイトルと説明を表示
st.title("📄 ドキュメント質問応答")
st.write(
    "下のフォームからドキュメントをアップロードし、質問を入力してください。GPTが回答します！"
    "このアプリを利用するには OpenAI API キーが必要です。取得方法は[こちら](https://platform.openai.com/account/api-keys)。"
)

# OpenAI APIキーを入力してもらう
# または `./.streamlit/secrets.toml` に保存し、`st.secrets` から取得できます
openai_api_key = st.text_input("OpenAI APIキー", type="password")
if not openai_api_key:
    st.info("OpenAI APIキーを入力してください。", icon="🗝️")
else:

    # OpenAIクライアントを作成
    client = OpenAI(api_key=openai_api_key)

    # ファイルアップロード
    uploaded_file = st.file_uploader(
        "ドキュメントをアップロードしてください（.txt または .md）", type=("txt", "md")
    )

    # 質問を入力してもらう
    question = st.text_area(
        "ドキュメントについて質問してください！",
        placeholder="この文書の要約を教えてください。",
        disabled=not uploaded_file,
    )

    if uploaded_file and question:

        # アップロードされたファイルと質問を処理
        document = uploaded_file.read().decode()
        messages = [
            {
                "role": "user",
                "content": f"以下はドキュメントです: {document} \n\n---\n\n {question}",
            }
        ]

        # OpenAI APIで回答を生成
        stream = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=messages,
            stream=True,
        )

        # 回答をストリーム表示
        st.write_stream(stream)
