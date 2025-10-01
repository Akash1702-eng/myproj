import streamlit as st
from PIL import Image
import google.generativeai as genai
from gtts import gTTS
import os, tempfile, base64, requests

# Page config
st.set_page_config(page_title="Smart Dermatology Assistant", layout="centered")

# Load API key for Gemini
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    WEATHER_KEY = st.secrets["WEATHER_API_KEY"]   # <-- Add your OpenWeatherMap API key here
    if not API_KEY:
        st.error("⚠ GEMINI_API_KEY not configured.")
        st.stop()
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error(f"Error: {e}")
    st.stop()


# ------------------- WEATHER FUNCTION -------------------
def get_weather(lat, lon):
    """Fetch weather info from OpenWeatherMap."""
    url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_KEY}&units=metric"
    try:
        res = requests.get(url).json()
        weather = res["weather"][0]["description"].capitalize()
        temp = res["main"]["temp"]
        humidity = res["main"]["humidity"]
        return f"Weather: {weather}, Temp: {temp}°C, Humidity: {humidity}%"
    except:
        return "Weather data unavailable"


# ------------------- GEMINI ANALYSIS -------------------
def analyze_skin_image(image: Image.Image, user_name: str, language: str, weather: str):
    """Call Gemini API with skin + weather context."""
    prompt = f"""
    You are a Smart Dermatology Assistant. Analyze the provided skin image.

    User: {user_name}
    Current Environment: {weather}

    Give analysis considering how weather (temperature, humidity, sun, pollution) can affect skin conditions.

    Translate entire response into {language}.
    Use this format:

    ---
    **Disease Name:** [Likely condition]

    **Severity Level:** [Mild/Moderate/Severe]

    **Description:** [2 paragraphs about disease, symptoms, and how weather may worsen/improve it]

    **Precautions/Recommendations:** 
    - At least 3-4 tips, including weather-related care.
    - Add a disclaimer: Not a substitute for professional medical diagnosis.
    ---
    """
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = model.generate_content([image, prompt])
    return response.text


# ------------------- TTS -------------------
def speak_text(text: str, language: str):
    try:
        tts = gTTS(text=text, lang=language)
        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp_file.name)
        with open(tmp_file.name, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return tmp_file.name, b64
    except Exception as e:
        st.error(f"TTS error: {e}")
        return None, None


# ------------------- UI -------------------
st.title("🌤️ Smart Dermatology Assistant with Weather Awareness")

user_name = st.text_input("Enter your name:", placeholder="e.g., Alex")

languages = {"English":"en","Hindi":"hi","Marathi":"mr","Spanish":"es","French":"fr","German":"de","Tamil":"ta","Telugu":"te"}
chosen_language = st.selectbox("Choose language:", list(languages.keys()))
lang_code = languages[chosen_language]

st.divider()

# ---- Get location manually (for simplicity, city/lat/lon input) ----
lat = st.number_input("Enter Latitude", value=19.076, format="%.6f")   # default Mumbai
lon = st.number_input("Enter Longitude", value=72.8777, format="%.6f")

weather_info = get_weather(lat, lon)
st.info(f"📍 Location Weather: {weather_info}")

uploaded_file = st.file_uploader("Upload skin image", type=["jpg","jpeg","png"])

if uploaded_file:
    image = Image.open(uploaded_file)
    st.image(image, caption="Uploaded Skin Image", use_column_width=True)

    if st.button("🔬 Analyze with Weather"):
        if not user_name:
            st.warning("Enter your name first.")
        else:
            with st.spinner("Analyzing..."):
                result = analyze_skin_image(image, user_name, chosen_language, weather_info)
                st.success("✅ Analysis Complete!")
                st.markdown(result)

                audio_path, b64_audio = speak_text(result, lang_code)
                if audio_path:
                    st.audio(audio_path, format="audio/mp3")
                    st.markdown(
                        f"""<audio autoplay>
                            <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
                        </audio>""",
                        unsafe_allow_html=True
                    )


st.markdown("<hr><p style='text-align:center;color:gray;'>*Disclaimer: AI tool. Not a medical substitute.*</p>", unsafe_allow_html=True)
