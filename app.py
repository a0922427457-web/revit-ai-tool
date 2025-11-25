import streamlit as st
import replicate
import requests
import os
import base64
import json
from PIL import Image
import io

# --- 1. 頁面設定 ---
st.set_page_config(page_title="Revit 智慧渲染站", layout="wide", page_icon="🏢")
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

st.title("🏢 公司專用：Revit 模型 AI 渲染器")

# --- 2. 初始化 Session State ---
if "ai_prompt" not in st.session_state:
    st.session_state.ai_prompt = ""

# --- 3. 讀取金鑰 ---
replicate_api = st.secrets.get("REPLICATE_API_TOKEN")
gemini_key = st.secrets.get("GOOGLE_API_KEY")

# 側邊欄輸入
if not replicate_api:
    replicate_api = st.sidebar.text_input("Replicate Token", type="password")
if not gemini_key:
    gemini_key = st.sidebar.text_input("Gemini API Key", type="password")

if replicate_api:
    os.environ["REPLICATE_API_TOKEN"] = replicate_api

# --- 4. 連線函數 (指定使用 gemini-2.0-flash) ---
def call_gemini_2_0(api_key, image, style_text):
    # 圖片轉碼
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # --- 關鍵修正：這裡直接使用你清單上有的模型 ---
    target_model = "gemini-2.0-pro-exp" 
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    
    data = {
        "contents": [{
            "parts": [
                {"text": f"You are an architectural visualizer. Look at this image. Create a detailed English prompt for ControlNet. Describe the building geometry, materials, and lighting. Style: {style_text}. Format: Keywords separated by commas. No sentences. End with: photorealistic, 8k, architectural photography"},
                {"inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_str
                }}
            ]
        }]
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            return response.json()['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"連線錯誤: {str(e)}"

# --- 5. 介面佈局 ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 上傳模型圖片")
    uploaded_file = st.file_uploader("請上傳 JPG/PNG", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="原始模型", use_column_width=True)

        st.subheader("2. 環境設定")
        style_option = st.selectbox("選擇風格", ["Modern Glass", "Concrete Brutalist", "Industrial Brick", "Wooden Resort"])
        
        if st.button("✨ 呼叫 Gemini 2.0 分析"):
            if not gemini_key:
                st.error("缺少 Gemini Key！")
            else:
                with st.spinner("Gemini 2.0 正在分析圖片..."):
                    result = call_gemini_2_0(gemini_key, image, style_option)
                    
                    if "Error" in result:
                        st.error("分析失敗，請檢查錯誤訊息：")
                        st.code(result)
                    else:
                        st.session_state.ai_prompt = result
                        st.success("分析成功！")
                        st.rerun()

with col2:
    st.subheader("3. 渲染操作")
    final_prompt = st.text_area("提示詞", value=st.session_state.ai_prompt, height=150)
    n_prompt = st.text_input("負面提示詞", "low quality, blurry, text, watermark, bad perspective, deformed, people, ugly")
    
    if st.button("🎨 開始渲染"):
        if not replicate_api or not uploaded_file:
            st.error("資料不全")
        else:
            with st.spinner("AI 繪圖中..."):
                try:
                    with open("temp_upload.jpg", "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    with open("temp_upload.jpg", "rb") as image_file:
                        output = replicate.run(
                            "jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613",
                            input={"image": image_file, "prompt": final_prompt, "negative_prompt": n_prompt, "return_image": True}
                        )
                    image_url = output[1] if isinstance(output, list) else output
                    st.success("渲染完成！")
                    st.image(image_url, use_column_width=True)
                except Exception as e:
                    st.error(f"渲染失敗: {e}")
