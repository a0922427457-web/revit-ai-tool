import streamlit as st
import replicate
import requests
import os
import base64
import io
from PIL import Image

# --- 頁面設定 ---
st.set_page_config(page_title="Revit 渲染站 (診斷版)", layout="wide", page_icon="🔧")
st.title("🔧 系統診斷模式")
st.warning("目前處於偵錯模式，若發生錯誤將會顯示詳細代碼。")

# --- 初始化 ---
if "ai_prompt" not in st.session_state:
    st.session_state.ai_prompt = ""

# --- 讀取金鑰 ---
# 優先從 Secrets 讀取
replicate_api = st.secrets.get("REPLICATE_API_TOKEN")
gemini_key = st.secrets.get("GOOGLE_API_KEY")

# 側邊欄強制顯示金鑰輸入框 (方便測試)
st.sidebar.header("🔑 金鑰測試區")
user_gemini_key = st.sidebar.text_input("在此手動輸入 Gemini Key (排除 Secrets 設定錯誤)", value=gemini_key if gemini_key else "", type="password")
user_replicate_key = st.sidebar.text_input("Replicate Token", value=replicate_api if replicate_api else "", type="password")

# --- 診斷用連線函數 ---
def debug_gemini(api_key, image):
    # 轉檔
    buffered = io.BytesIO()
    image.save(buffered, format="JPEG")
    img_str = base64.b64encode(buffered.getvalue()).decode()

    # 測試最標準的模型
    target_model = "gemini-1.5-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{target_model}:generateContent?key={api_key}"
    
    headers = {'Content-Type': 'application/json'}
    data = {
        "contents": [{
            "parts": [
                {"text": "Describe this building in 10 words."}, # 簡單指令測試
                {"inline_data": {"mime_type": "image/jpeg", "data": img_str}}
            ]
        }]
    }

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        # 顯示詳細診斷資訊
        st.write("---")
        st.write(f"📡 嘗試連線模型: `{target_model}`")
        st.write(f"📡 HTTP 狀態碼: `{response.status_code}`")
        
        if response.status_code == 200:
            return "SUCCESS", response.json()
        else:
            # 回傳完整的錯誤訊息
            return "ERROR", response.text
            
    except Exception as e:
        return "CRITICAL_ERROR", str(e)

# --- 介面 ---
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1. 診斷測試")
    uploaded_file = st.file_uploader("上傳一張小圖片進行測試", type=["jpg", "png", "jpeg"])
    
    if uploaded_file and st.button("🚨 開始診斷"):
        if not user_gemini_key:
            st.error("❌ 沒有偵測到 API Key！請在左側輸入。")
        else:
            image = Image.open(uploaded_file)
            st.info("正在發送請求給 Google...")
            
            # 執行診斷
            status, result = debug_gemini(user_gemini_key, image)
            
            if status == "SUCCESS":
                st.success("✅ 連線成功！API Key 運作正常。")
                st.json(result) # 顯示成功的回傳資料
                # 這裡簡單抓取文字
                try:
                    text = result['candidates'][0]['content']['parts'][0]['text']
                    st.session_state.ai_prompt = text
                except:
                    pass
            else:
                st.error("❌ 連線失敗")
                st.write("👇 **請把下面這段錯誤訊息截圖或複製給我：**")
                st.code(result, language="json")

with col2:
    st.subheader("2. 渲染測試")
    final_prompt = st.text_area("提示詞", value=st.session_state.ai_prompt)
    if st.button("🎨 測試渲染"):
        if not user_replicate_key or not uploaded_file:
            st.error("資料不全")
        else:
            # (這裡省略複雜代碼，僅做連線測試)
            st.info("渲染功能暫時略過，先解決 Gemini 連線問題。")
