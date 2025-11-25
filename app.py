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
    # 準備請求內容列表
    content_parts = []
    
    # 指令：定義角色與任務
    system_instruction = f"""
    You are an expert architectural visualizer. 
    Task: Create a highly detailed Stable Diffusion prompt for ControlNet.
    
    1. Base Geometry: Analyze the FIRST image (Line Drawing). Keep the geometry description accurate.
    2. Target Style: {style_text}.
    """
    content_parts.append({"text": system_instruction})
    
    # 處理第一張圖：Revit 線稿
    buf_model = io.BytesIO()
    model_image.save(buf_model, format="JPEG")
    img_model_str = base64.b64encode(buf_model.getvalue()).decode()
    content_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_model_str}})
    content_parts.append({"text": "Above is the GEOMETRY (Revit Model)."})

    # 處理第二張圖：參考圖 (如果有上傳的話)
    if ref_image:
        buf_ref = io.BytesIO()
        ref_image.save(buf_ref, format="JPEG")
        img_ref_str = base64.b64encode(buf_ref.getvalue()).decode()
        content_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_ref_str}})
        content_parts.append({"text": "Above is the STYLE REFERENCE. Adopt its materials, lighting, color palette, and atmosphere, but DO NOT change the geometry of the first image."})
    
    # 處理使用者指令 (中文轉英文)
    if user_text:
        content_parts.append({"text": f"User's specific requirements (Translate to English keywords): {user_text}"})

    # 結尾格式要求
    content_parts.append({"text": "Output format: English keywords separated by commas. No sentences. End with: photorealistic, 8k, architectural photography, cinematic lighting."})

    # 設定目標模型 (使用清單中已知的 2.0 Flash)
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
    
    # A. 主模型
    uploaded_file = st.file_uploader("📤 上傳 Revit 線稿/白模 (必要)", type=["jpg", "png", "jpeg"])
    if uploaded_file:
        image_model = Image.open(uploaded_file)
        st.image(image_model, caption="幾何模型", use_column_width=True)

    st.write("---")
    
    # B. 風格參考
    uploaded_ref = st.file_uploader("🎨 上傳風格參考圖 (選填 - AI 會學習它的材質與光影)", type=["jpg", "png", "jpeg"])
    image_ref = None
    if uploaded_ref:
        image_ref = Image.open(uploaded_ref)
        st.image(image_ref, caption="風格參考範例", width=300)

    st.write("---")

    st.subheader("2. 設計指令")
    
    # C. 風格選單 (中英對照)
    style_option = st.selectbox(
        "選擇基礎風格", 
        [
            "現代玻璃帷幕 (Modern Glass Facade)", 
            "清水模建築 (Concrete Brutalist)", 
            "紅磚工業風 (Industrial Brick)", 
            "溫暖木質度假風 (Warm Wooden Resort)",
            "純白未來主義 (Futuristic White)",
            "日式禪風 (Japanese Zen)"
        ]
    )
    
    # D. 使用者自訂指令 (中文)
    user_input = st.text_area("✍️ 額外指令 (可用中文，例如：'要黃昏氛圍，前面要有草地，玻璃要透一點')", height=80)
    
    if st.button("✨ 呼叫 Gemini 融合分析"):
        if not gemini_key:
            st.error("缺少 Gemini Key！")
        elif not uploaded_file:
            st.error("至少需要上傳 Revit 模型圖片！")
        else:
            with st.spinner("Gemini 正在閱讀模型、參考圖與您的指令..."):
                result = call_gemini_advanced(gemini_key, image_model, image_ref, style_option, user_input)
                
                if "Error" in result:
                    st.error("分析失敗")
                    st.code(result)
                else:
                    st.session_state.ai_prompt = result
                    st.success("Prompt 生成完成！已自動融合所有需求。")
                    st.rerun()

with col2:
    st.subheader("3. 渲染與微調")
    
    # 顯示生成的 Prompt
    final_prompt = st.text_area("最終提示詞 (AI 已自動翻譯並優化)", value=st.session_state.ai_prompt, height=200)
    
    n_prompt = st.text_input("負面提示詞 (不希望出現的東西)", "low quality, blurry, text, watermark, bad perspective, deformed, people, ugly, cars")
    
    # 進階參數
    with st.expander("🛠️ 進階參數"):
        creativity = st.slider("創意度 (Scale - 越高越強烈)", 5.0, 20.0, 9.0)
        strength = st.slider("線條鎖定強度 (1.0 = 嚴格)", 0.0, 2.0, 1.0)

    if st.button("🎨 開始渲染 (Start Render)"):
        if not replicate_api or not uploaded_file:
            st.error("資料不全")
        else:
            with st.spinner("AI 正在繪圖中..."):
                try:
                    # 處理圖檔
                    with open("temp_model.jpg", "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    with open("temp_model.jpg", "rb") as image_file:
                        output = replicate.run(
                            "jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613",
                            input={
                                "image": image_file,
                                "prompt": final_prompt,
                                "negative_prompt": n_prompt,
                                "image_resolution": 768, # 可以改成 1024 獲得更高畫質
                                "scale": creativity,
                                "return_image": True 
                            }
                        )
                    image_url = output[1] if isinstance(output, list) else output
                    st.success("渲染完成！")
                    st.image(image_url, use_column_width=True)
                except Exception as e:
                    # 這裡會捕捉 402 付款錯誤
                    st.error(f"渲染失敗: {e}")
                    if "402" in str(e):
                        st.warning("💡 提示：Replicate 額度不足。請至 Replicate 官網儲值 (約 5 美金)。")
