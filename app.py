import streamlit as st
import replicate
import google.generativeai as genai
import os
from PIL import Image

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="Revit 智慧渲染站", layout="wide", page_icon="🏢")
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""
st.markdown(hide_streamlit_style, unsafe_allow_html=True)

st.title("🏢 公司專用：Revit 模型 AI 渲染器")

# --- 2. 初始化 Session State ---
if "ai_prompt" not in st.session_state:
    st.session_state.ai_prompt = ""

# --- 3. 讀取金鑰 ---
replicate_api = st.secrets.get("REPLICATE_API_TOKEN")
gemini_key = st.secrets.get("GOOGLE_API_KEY")

# 備用輸入框
if not replicate_api:
    replicate_api = st.sidebar.text_input("Replicate Token", type="password")
if not gemini_key:
    gemini_key = st.sidebar.text_input("Gemini API Key", type="password")

if replicate_api:
    os.environ["REPLICATE_API_TOKEN"] = replicate_api
if gemini_key:
    genai.configure(api_key=gemini_key)

# --- 4. 介面佈局 ---
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
            ["現代玻璃帷幕 (Modern Glass)", "清水模建築 (Concrete)", "紅磚工業風 (Brick Industrial)", "森林度假屋 (Forest Resort)"]
        )
        
        if st.button("✨ 呼叫 Gemini 分析模型"):
            if not gemini_key:
                st.error("缺少 Gemini Key！")
            else:
                with st.spinner("Gemini 正在觀察你的設計..."):
                    try:
                        # 使用最新的 1.5 Flash
                        model = genai.GenerativeModel('gemini-pro')
                        
                        prompt_request = f"""
                        You are an architectural visualizer. Look at this building line drawing.
                        Create a prompt for ControlNet Stable Diffusion.
                        Describe the geometry seen in the image accurately.
                        Target Style: {style_option}.
                        Add details: lighting, sky, realistic textures, 8k, masterpiece.
                        Output format: English keywords separated by commas.
                        """
                        response = model.generate_content([prompt_request, image])
                        st.session_state.ai_prompt = response.text
                        st.success("分析完成！")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Gemini 錯誤: {e}")

with col2:
    st.subheader("3. 渲染操作")
    final_prompt = st.text_area("提示詞 (請保持英文)", value=st.session_state.ai_prompt, height=150)
    n_prompt = st.text_input("負面提示詞", "low quality, blurry, text, watermark, bad perspective, deformed")
    
    if st.button("🎨 開始渲染 (Start Render)"):
        if not replicate_api:
            st.error("缺少 Replicate Token！")
        elif not uploaded_file:
            st.error("請先上傳圖片！")
        else:
            with st.spinner("AI 正在繪圖中..."):
                try:
                    # 暫存圖片解決中文檔名問題
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
