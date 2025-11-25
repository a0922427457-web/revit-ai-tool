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

# --- 4. 核心邏輯：Gemini 分析 ---
def call_gemini_advanced(api_key, model_image, ref_image, style_text, user_text, is_clean_mode):
    content_parts = []
    
    # 根據是否開啟「專注模式」調整 AI 指令
    background_instruction = ""
    if is_clean_mode:
        background_instruction = "IMPORTANT: Keep the background CLEAN and MINIMAL. Use a studio lighting setting or simple sky. Do NOT invent complex landscapes, forests, or cities around the building."
    else:
        background_instruction = "Generate a realistic environment suitable for the building."

    system_instruction = f"""
    You are an expert architectural visualizer. 
    Task: Create a highly detailed Stable Diffusion prompt for ControlNet.
    1. Base Geometry: Analyze the FIRST image (Line Drawing). Keep the geometry description accurate.
    2. Target Style: {style_text}.
    3. Background: {background_instruction}
    """
    content_parts.append({"text": system_instruction})
    
    # Model Image
    buf_model = io.BytesIO()
    model_image.save(buf_model, format="JPEG")
    img_model_str = base64.b64encode(buf_model.getvalue()).decode()
    content_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_model_str}})
    content_parts.append({"text": "Above is the GEOMETRY (Revit Model)."})

    # Reference Image
    if ref_image:
        buf_ref = io.BytesIO()
        ref_image.save(buf_ref, format="JPEG")
        img_ref_str = base64.b64encode(buf_ref.getvalue()).decode()
        content_parts.append({"inline_data": {"mime_type": "image/jpeg", "data": img_ref_str}})
        content_parts.append({"text": "Above is the STYLE REFERENCE. Adopt its materials and lighting."})
    
    # User Input
    if user_text:
        content_parts.append({"text": f"User's specific requirements (Translate to English keywords): {user_text}"})

    content_parts.append({"text": "Output format: English keywords separated by commas. No sentences. End with: architectural photography."})

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
    if uploaded_ref:
        st.image(uploaded_ref, caption="風格參考", width=300)

    st.write("---")
    st.subheader("2. 設計指令")
    
    style_option = st.selectbox(
        "選擇基礎風格", 
        ["現代玻璃帷幕 (Modern Glass Facade)", "清水模建築 (Concrete Brutalist)", "紅磚工業風 (Industrial Brick)", "溫暖木質度假風 (Warm Wooden Resort)", "純白未來主義 (Futuristic White)", "日式禪風 (Japanese Zen)"]
    )
    
    user_input = st.text_area("✍️ 額外指令 (中文)", height=80)
    
    # --- 新增：專注模式開關 ---
    clean_mode = st.checkbox("🎯 專注模型 (純淨背景/不亂加配景)", value=True, help="勾選後，AI 會使用攝影棚光或乾淨天空，並強制移除樹木、街道、人車。")
    
    if st.button("✨ 呼叫 Gemini 融合分析"):
        if not gemini_key:
            st.error("缺少 Gemini Key！")
        elif not uploaded_file:
            st.error("請上傳模型圖片！")
        else:
            with st.spinner("Gemini 正在分析 (已啟用專注模式)..." if clean_mode else "Gemini 正在分析..."):
                ref_img_obj = Image.open(uploaded_ref) if uploaded_ref else None
                
                # 傳入 clean_mode 參數
                result = call_gemini_advanced(gemini_key, image_model, ref_img_obj, style_option, user_input, clean_mode)
                
                if "Error" in result:
                    st.error("分析失敗")
                    st.code(result)
                else:
                    st.session_state.ai_prompt = result
                    st.success("Prompt 生成完成！")
                    st.rerun()

with col2:
    st.subheader("3. 渲染設定與執行")
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        season = st.selectbox("🍂 季節", ["無指定 (None)", "春季 (Spring)", "夏季 (Summer)", "秋季 (Autumn)", "冬季 (Winter)"])
        weather = st.selectbox("⛈️ 天氣", ["晴朗 (Sunny)", "多雲 (Cloudy)", "陰天 (Overcast)", "下雨 (Rainy)", "起霧 (Foggy)", "下雪 (Snowy)"])
    
    with col_opt2:
        resolution = st.selectbox("📐 出圖大小", ["512", "768", "1024"], index=1)
        quality_mode = st.radio("💎 出圖品質", ["標準 (快速)", "高品質 (較慢)"], index=0)

    base_prompt = st.text_area("AI 生成的基礎提示詞", value=st.session_state.ai_prompt, height=150)
    
    # 預設的負面提示詞
    default_negative = "low quality, blurry, text, watermark, bad perspective, deformed"
    n_prompt = st.text_input("負面提示詞", value=default_negative)
    
    with st.expander("🛠️ 進階參數"):
        creativity = st.slider("創意度 (Scale)", 5.0, 20.0, 9.0)
        strength = st.slider("線條鎖定強度", 0.0, 2.0, 1.0)

    if st.button("🎨 開始渲染 (Start Render)"):
        if not replicate_api or not uploaded_file:
            st.error("資料不全")
        else:
            with st.spinner("AI 正在繪圖中..."):
                try:
                    # 1. 處理 Prompt (加入季節天氣)
                    added_prompts = []
                    
                    # 如果開啟「專注模式」，強制加入攝影棚關鍵字
                    if clean_mode:
                        added_prompts.append("clean background, studio lighting, minimal environment, clear sky")
                    else:
                        # 只有在非專注模式下，才強調季節天氣 (避免衝突)
                        if "None" not in season: added_prompts.append(season.split("(")[1].replace(")", ""))
                        if "None" not in weather: added_prompts.append(weather.split("(")[1].replace(")", ""))
                    
                    added_prompts.append("photorealistic, 8k, masterpiece, highly detailed")
                    final_full_prompt = f"{base_prompt}, {', '.join(added_prompts)}"

                    # 2. 處理負面提示詞 (如果是專注模式，要加強禁止項目)
                    final_negative = n_prompt
                    if clean_mode:
                        final_negative += ", trees, forest, city, street, cars, people, landscape, complex background, busy street, mountains"

                    # 3. 設定品質
                    num_steps = 50 if quality_mode == "高品質 (較慢)" else 20

                    with open("temp_model.jpg", "wb") as f:
                        f.write(uploaded_file.getbuffer())
                    
                    with open("temp_model.jpg", "rb") as image_file:
                        output = replicate.run(
                            "jagilley/controlnet-canny:aff48af9c68d162388d230a2ab003f68d2638d88307bdaf1c2f1ac95079c9613",
                            input={
                                "image": image_file,
                                "prompt": final_full_prompt,
                                "negative_prompt": final_negative, # 使用加強版的負面提示詞
                                "image_resolution": resolution,
                                "scale": creativity,
                                "ddim_steps": num_steps,
                                "return_image": True 
                            }
                        )
                    
                    if isinstance(output, list):
                        image_url = str(output[1])
                    else:
                        image_url = str(output)
                        
                    st.success("渲染完成！")
                    st.image(image_url, use_column_width=True)
                    
                except Exception as e:
                    st.error(f"渲染失敗: {e}")
                    if "402" in str(e):
                        st.warning("💡 Replicate 額度不足。")
