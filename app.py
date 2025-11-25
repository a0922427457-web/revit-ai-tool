import streamlit as st
import replicate
import requests
import os
import base64
import json
from PIL import Image
import io

# --- 1. 頁面基礎設定 ---
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

if not replicate_api:
    replicate_api = st.sidebar.text_input("Replicate Token", type="password")
if not gemini_key:
    gemini_key = st.sidebar.text_input("Gemini API Key", type="password")

if replicate_api:
    os.environ["REPLICATE_API_TOKEN"] = replicate_api

# --- 4. 萬能連線函數 (不依賴套件) ---
def call_gemini_vision(api_key, image, style_text):
    # 1. 將圖片轉成 Base64 格式 (Gemini API 要求的格式)
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 2. 設定 API 網址 (直接連線最新版 1.5 Flash)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    
    # 3. 準備傳送的資料
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [
                {"text": f"You are an architectural visualizer. Look at this image. Create a detailed English prompt for ControlNet. Describe the building geometry, materials, and lighting. Style: {style_text}. Format: Keywords separated by commas. No sentences."},
                {"inline_data": {
                    "mime_type": "image/jpeg",
                    "data": img_str
                }}
            ]
        }]
    }

    # 4. 發送請求
    response = requests.post(url, headers=headers, json=data)
    
    # 5. 解析結果
    if response.status_code == 200:
        result = response.json()
        try:
            return result['candidates'][0]['content']['parts'][0]['text']
        except:
            return "Error: 無法解析 Gemini 回傳的資料"
    else:
        return f"Error {response.status_code}: {response.text}"

# --- 5. 介面佈局 ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 上傳模型圖片")
    uploaded_file = st.file_uploader("請上傳 JPG/PNG", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="原始模型", use_column_width=True)

        st.subheader("2. 環境設定")
        style_option = st.selectbox(
            "選擇風格", 
            ["Modern Glass Facade", "Concrete Brutalist", "Industrial Brick", "Wooden Resort", "Futuristic White"]
        )
        
        if st.button("✨ 呼叫 Gemini 分析模型"):
            if not gemini_key:
                st.error("缺少 Gemini Key！")
            else:
                with st.spinner("Gemini 正在觀察你的設計..."):
                    # 使用我們手寫的萬能連線函數
                    result_text = call_gemini_vision(gemini_key, image, style_option)
                    
                    if "Error" in result_text:
                        st.error(result_text)
                    else:
                        st.session_state.ai_prompt = result_text + ", photorealistic, 8k, architectural photography, cinematic lighting"
                        st.success("分析完成！")
                        st.rerun()

with col2:
    st.subheader("3. 渲染操作")
    final_prompt = st.text_area("提示詞 (請保持英文)", value=st.session_state.ai_prompt, height=150)
    n_prompt = st.text_input("負面提示詞", "low quality, blurry, text, watermark, bad perspective, deformed, people, ugly")
    
    if st.button("🎨 開始渲染 (Start Render)"):
        if not replicate_api:
            st.error("缺少 Replicate Token！")
        elif not uploaded_file:
            st.error("請先上傳圖片！")
        else:
            with st.spinner("AI 正在繪圖中..."):
                try:
                    # 圖片轉存處理
                    with open("temp_upload.jpg", "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    with open("temp_upload.jpg", "rb") as image_file:
                        output = replicate.run(
                            "jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613",
                            input={
                                "image": image_file,
                                "prompt": final_prompt,
                                "negative_prompt": n_prompt,
                                "image_resolution": 768,
                                "scale": 9.0,
                                "return_image": True 
                            }
                        )
                    image_url = output[1] if isinstance(output, list) else output
                    st.success("渲染完成！")
                    st.image(image_url, caption="AI 效果圖", use_column_width=True)
                except Exception as e:
                    st.error(f"渲染失敗: {e}")
