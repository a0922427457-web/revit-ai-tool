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

st.title("🏢 公司專用：Revit 模型 AI 渲染器 (自動偵測版)")

# --- 2. 初始化 Session State ---
if "ai_prompt" not in st.session_state:
    st.session_state.ai_prompt = ""
if "valid_model_name" not in st.session_state:
    st.session_state.valid_model_name = None

# --- 3. 讀取金鑰 ---
replicate_api = st.secrets.get("REPLICATE_API_TOKEN")
gemini_key = st.secrets.get("GOOGLE_API_KEY")

# 側邊欄輸入
st.sidebar.header("🔑 設定")
if not replicate_api:
    replicate_api = st.sidebar.text_input("Replicate Token", type="password")
if not gemini_key:
    gemini_key = st.sidebar.text_input("Gemini API Key", type="password")

if replicate_api:
    os.environ["REPLICATE_API_TOKEN"] = replicate_api

# --- 4. 關鍵功能：自動尋找可用模型 ---
def find_working_model(api_key):
    # 問 Google: "請給我你的菜單 (ListModels)"
    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            models_data = response.json()
            st.toast("✅ 成功取得模型清單！正在挑選...", icon="🤖")
            
            # 優先順序：最新的 Flash -> 最新的 Pro -> 舊版 Vision
            preferred_keywords = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-pro-vision"]
            
            # 1. 先列出所有支援 'generateContent' 的模型
            available_models = []
            if 'models' in models_data:
                for m in models_data['models']:
                    if "generateContent" in m.get("supportedGenerationMethods", []):
                        # 去掉 'models/' 前綴，只留名稱
                        clean_name = m['name'].replace("models/", "")
                        available_models.append(clean_name)
            
            # 2. 顯示給使用者看 (除錯用)
            with st.expander("👀 Google 提供的可用模型清單 (點我查看)"):
                st.write(available_models)

            # 3. 挑選最佳模型
            for keyword in preferred_keywords:
                for model in available_models:
                    if keyword in model:
                        return model # 找到就回傳
            
            # 4. 如果都沒找到喜歡的，就隨便回傳第一個有 'vision' 功能的
            for model in available_models:
                if "vision" in model:
                    return model
                    
            return None # 真的沒菜了
        else:
            st.error(f"無法取得模型清單: {response.text}")
            return None
    except Exception as e:
        st.error(f"連線錯誤: {e}")
        return None

# --- 5. 執行連線 ---
def call_gemini_dynamic(api_key, model_name, image, style_text):
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [
                {"text": f"You are an architectural visualizer. Look at this image. Create a detailed English prompt for ControlNet. Describe the building geometry, materials, and lighting. Style: {style_text}. Format: Keywords separated by commas. No sentences."},
                {"inline_data": {"mime_type": "image/jpeg", "data": img_str}}
            ]
        }]
    }
    
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        return response.json()['candidates'][0]['content']['parts'][0]['text']
    else:
        return f"Error: {response.text}"

# --- 6. 介面佈局 ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 上傳模型圖片")
    uploaded_file = st.file_uploader("請上傳 JPG/PNG", type=["jpg", "png", "jpeg"])
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.image(image, caption="原始模型", use_column_width=True)

        st.subheader("2. 環境設定")
        style_option = st.selectbox("選擇風格", ["Modern Glass", "Concrete Brutalist", "Industrial Brick", "Wooden Resort"])
        
        if st.button("✨ 呼叫 Gemini 分析模型"):
            if not gemini_key:
                st.error("缺少 Gemini Key！")
            else:
                with st.spinner("1/2 正在掃描可用模型..."):
                    # 如果還沒找過模型，先找一次
                    if not st.session_state.valid_model_name:
                        found_model = find_working_model(gemini_key)
                        if found_model:
                            st.session_state.valid_model_name = found_model
                            st.success(f"已鎖定可用模型: {found_model}")
                        else:
                            st.error("❌ 找不到任何可用的 Gemini 模型，請檢查 API Key 權限。")
                            st.stop()
                
                if st.session_state.valid_model_name:
                    with st.spinner(f"2/2 正在使用 {st.session_state.valid_model_name} 分析圖片..."):
                        result = call_gemini_dynamic(gemini_key, st.session_state.valid_model_name, image, style_option)
                        if "Error" in result:
                            st.error(result)
                        else:
                            st.session_state.ai_prompt = result + ", photorealistic, 8k, architectural photography"
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
