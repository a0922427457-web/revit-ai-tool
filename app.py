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

st.title("🏢 公司專用：Revit 模型 AI 渲染器 (自動切換版)")

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

# --- 4. 萬能連線函數 (自動嘗試多種模型) ---
def call_gemini_vision(api_key, image, style_text):
    # 圖片轉碼
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 準備我們要嘗試的模型清單 (如果第一個失敗，就試下一個)
    # 包含了最新版、穩定版、跟特定版號
    models_to_try = [
        "gemini-1.5-flash-latest", # 最新版 Flash
        "gemini-1.5-flash-001",    # 指定版號 Flash
        "gemini-1.5-pro-latest",   # 最新版 Pro (比較慢但強大)
        "gemini-1.5-pro-001"       # 指定版號 Pro
    ]

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

    # 開始迴圈嘗試
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        try:
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                # 成功！解析結果
                result = response.json()
                text = result['candidates'][0]['content']['parts'][0]['text']
                return f"SUCCESS|{model_name}|{text}" # 回傳成功標記
            else:
                # 失敗，印出這個模型為何失敗，然後繼續下一個
                print(f"嘗試 {model_name} 失敗: {response.status_code}")
                continue 
        except Exception as e:
            print(f"連線錯誤: {e}")
            continue

    # 如果全部都失敗
    return "ERROR|所有模型都嘗試失敗，請檢查 API Key 是否正確或有權限限制。"

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
                with st.spinner("Gemini 正在嘗試連線 (會自動切換模型)..."):
                    # 呼叫自動切換函數
                    result_raw = call_gemini_vision(gemini_key, image, style_option)
                    
                    if result_raw.startswith("ERROR"):
                        st.error(result_raw.split("|")[1])
                    elif result_raw.startswith("SUCCESS"):
                        _, model_used, prompt_text = result_raw.split("|", 2)
                        st.success(f"分析成功！(使用模型: {model_used})")
                        st.session_state.ai_prompt = prompt_text + ", photorealistic, 8k, architectural photography, cinematic lighting"
                        st.rerun()
                    else:
                        st.error("未知錯誤")

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
