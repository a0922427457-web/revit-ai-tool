import streamlit as st
import replicate
import requests
import os
import base64
import io
from PIL import Image

# --- 1. 頁面設定 ---
st.set_page_config(page_title="Revit 智慧渲染站 (旗艦版)", layout="wide", page_icon="🏢")
st.markdown("""
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
.stTextArea textarea {font-size: 16px !important;}
</style>
""", unsafe_allow_html=True)

st.title("🏢 公司專用：Revit AI 渲染旗艦站")
st.markdown("Revit 模型 + 參考圖風格 + 個人指令 -> AI 完美渲染")

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

# --- 4. 核心邏輯：雙圖分析與指令融合 ---
def call_gemini_advanced(api_key, model_image, ref_image, style_text, user_text):
    content_parts = []
    
    # 指令
    system_instruction = f"""
    You are an expert architectural visualizer. 
    Task: Create a highly detailed Stable Diffusion prompt for ControlNet.
    1. Base Geometry: Analyze the FIRST image (Line Drawing). Keep the geometry description accurate.
    2. Target Style: {style_text}.
    """
    content_parts.append({"text": system_instruction})
    
    # 第一張圖：Revit 線稿
    buf_model = io.BytesIO()
    model_image.save(buf_model, format="JPEG")
    img_model_str = base64.b64encode(buf_model.getvalue()).decode()
    content_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_model_str}})
    content_parts.append({"text": "Above is the GEOMETRY (Revit Model)."})

    # 第二張圖：參考圖
    if ref_image:
        buf_ref = io.BytesIO()
        ref_image.save(buf_ref, format="JPEG")
        img_ref_str = base64.b64encode(buf_ref.getvalue()).decode()
        content_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_ref_str}})
        content_parts.append({"text": "Above is the STYLE REFERENCE. Adopt its materials and lighting, but DO NOT change the geometry."})
    
    # 使用者指令
    if user_text:
        content_parts.append({"text": f"User's specific requirements (Translate to English keywords): {user_text}"})

    content_parts.append({"text": "Output format: English keywords separated by commas. No sentences. End with: photorealistic, 8k, architectural photography, cinematic lighting."})

    # 使用你清單上確認有的 2.0-flash
    target_model = "gemini-2.0-flash"
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {"contents": [{"parts": content_parts}]}
    
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
    st.subheader("1. 匯入資料")
    uploaded_file = st.file_uploader("📤 上傳 Revit 線稿/白模 (必要)", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        image_model = Image.open(uploaded_file)
        st.image(image_model, caption="幾何模型", use_column_width=True)

    st.write("---")
    
    uploaded_ref = st.file_uploader("🎨 上傳風格參考圖 (選填)", type=["jpg", "png", "jpeg"])
    image_ref = None
    if uploaded_ref:
        image_ref = Image.open(uploaded_ref)
        st.image(image_ref, caption="風格參考", width=300)

    st.write("---")
    st.subheader("2. 設計指令")
    
    style_option = st.selectbox(
        "選擇基礎風格", 
        ["現代玻璃帷幕 (Modern Glass Facade)", "清水模建築 (Concrete Brutalist)", "紅磚工業風 (Industrial Brick)", "溫暖木質度假風 (Warm Wooden Resort)", "純白未來主義 (Futuristic White)", "日式禪風 (Japanese Zen)"]
    )
    
    user_input = st.text_area("✍️ 額外指令 (中文)", height=80)
    
    if st.button("✨ 呼叫 Gemini 融合分析"):
        if not gemini_key:
            st.error("缺少 Gemini Key！")
        elif not uploaded_file:
            st.error("請上傳模型圖片！")
        else:
            with st.spinner("Gemini 正在思考..."):
                result = call_gemini_advanced(gemini_key, image_model, image_ref, style_option, user_input
