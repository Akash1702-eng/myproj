import streamlit as st
from PIL import Image
import google.generativeai as genai
from gtts import gTTS
import tempfile, base64, requests

# Attempt to import the JS helper
try:
    from streamlit_javascript import st_javascript
except Exception:
    st_javascript = None

st.set_page_config(page_title="Smart Dermatology Assistant", layout="centered")

# Load keys
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
    WEATHER_KEY = st.secrets["WEATHER_API_KEY"]
    IPINFO_TOKEN = st.secrets.get("IPINFO_TOKEN", None)
    genai.configure(api_key=API_KEY)
except Exception as e:
    st.error("Missing or invalid secrets. Make sure GEMINI_API_KEY and WEATHER_API_KEY are in .streamlit/secrets.toml")
    st.stop()

def ipinfo_fallback():
    try:
        url = f"https://ipinfo.io/json?token={IPINFO_TOKEN}" if IPINFO_TOKEN else "https://ipinfo.io/json"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            data = r.json()
            loc = data.get("loc")
            if loc:
                lat, lon = loc.split(",")
                return float(lat), float(lon)
    except Exception:
        pass
    return None, None

def fetch_coords_browser():
    if st_javascript is None:
        return None
    js = """
    new Promise((resolve) => {
      if (!navigator.geolocation) { resolve({error: 'not_supported'}); return; }
      navigator.geolocation.getCurrentPosition(
        (pos) => resolve({lat: pos.coords.latitude, lon: pos.coords.longitude}),
        (err) => resolve({error: err.message}),
        {enableHighAccuracy: true, timeout: 15000}
      );
    });
    """
    try:
        result = st_javascript(js)
        return result
    except Exception:
        return None

def get_weather(lat, lon):
    try:
        url = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_KEY}&units=metric"
        r = requests.get(url, timeout=6)
        data = r.json()
        weather = data["weather"][0]["description"].capitalize()
        temp = data["main"]["temp"]
        humidity = data["main"]["humidity"]
        return f"Weather: {weather}, Temp: {temp}°C, Humidity: {humidity}%"
    except Exception:
        return "Weather data unavailable"

def analyze_skin_image(image: Image.Image, user_name: str, language: str, weather: str):
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

def speak_text(text: str, language: str):
    try:
        tts = gTTS(text=text, lang=language)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)
        with open(tmp.name, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        return tmp.name, b64
    except Exception as e:
        st.error(f"TTS error: {e}")
        return None, None

# UI
st.title("🌤️ Smart Dermatology Assistant — Auto Location (Enable Location)")

user_name = st.text_input("Enter your name:", placeholder="e.g., Alex")
languages = {"English":"en","Hindi":"hi","Marathi":"mr","Spanish":"es","French":"fr","German":"de","Tamil":"ta","Telugu":"te"}
chosen_language = st.selectbox("Choose language:", list(languages.keys()))
lang_code = languages[chosen_language]

st.divider()

# Initialize session state for coords and permission messaging
if "coords" not in st.session_state:
    st.session_state.coords = None
if "last_error" not in st.session_state:
    st.session_state.last_error = None
if "tried_browser" not in st.session_state:
    st.session_state.tried_browser = False

col1, col2 = st.columns([3,1])

with col1:
    st.markdown("**Location status:**")
    if st.session_state.coords:
        lat, lon = st.session_state.coords
        st.success(f"Coordinates: {lat:.6f}, {lon:.6f}")
    else:
        st.info("No coordinates yet. Click **Enable Location** and allow location access in the browser when prompted.")

with col2:
    if st.button("Enable Location"):
        st.session_state.tried_browser = True
        with st.spinner("Requesting browser location permission..."):
            res = fetch_coords_browser()
        if res is None:
            st.session_state.last_error = "browser_unavailable"
            st.session_state.coords = None
        else:
            if isinstance(res, dict) and "lat" in res and "lon" in res:
                try:
                    lat = float(res["lat"]); lon = float(res["lon"])
                    st.session_state.coords = (lat, lon)
                    st.session_state.last_error = None
                except Exception:
                    st.session_state.coords = None
                    st.session_state.last_error = "parse_error"
            else:
                # Geolocation error returned by JS
                st.session_state.coords = None
                st.session_state.last_error = res.get("error") if isinstance(res, dict) else str(res)

# If browser attempt was made and failed, show clear instructions and retry option
if st.session_state.tried_browser and not st.session_state.coords:
    st.warning("Location was not retrieved. Please ensure browser location is turned ON and permission is ALLOWED for this site.")
    if st.session_state.last_error:
        st.info(f"Reason: {st.session_state.last_error}")

    st.markdown("""
    **How to enable location**
    - On Chrome: click the lock icon at the left of the URL bar → Site settings → Location → Allow, then retry.
    - On mobile: ensure Location/GPS is ON and the browser has permission.
    - Reload the page if needed after changing the permission.
    """)

    if st.button("Retry Browser Location"):
        with st.spinner("Retrying..."):
            res = fetch_coords_browser()
        if res and isinstance(res, dict) and "lat" in res and "lon" in res:
            try:
                lat = float(res["lat"]); lon = float(res["lon"])
                st.session_state.coords = (lat, lon)
                st.session_state.last_error = None
            except Exception:
                st.session_state.coords = None
                st.session_state.last_error = "parse_error"
        else:
            st.session_state.coords = None
            st.session_state.last_error = res.get("error") if isinstance(res, dict) else str(res)

st.markdown("---")

# If still no coords, offer IP fallback and manual input
if not st.session_state.coords:
    if st.button("Use IP-based fallback (approximate)"):
        with st.spinner("Fetching approximate location from IP..."):
            lat, lon = ipinfo_fallback()
            if lat is not None:
                st.session_state.coords = (lat, lon)
                st.success(f"Approximate coordinates from IP: {lat:.6f}, {lon:.6f}")
            else:
                st.error("IP-based location failed. Please enter coordinates manually below.")
    st.markdown("**Or enter coordinates manually:**")
    lat_manual = st.number_input("Latitude", format="%.6f", key="lat_manual")
    lon_manual = st.number_input("Longitude", format="%.6f", key="lon_manual")
    if st.button("Use manual coordinates"):
        st.session_state.coords = (lat_manual, lon_manual)
        st.success(f"Using manual coordinates: {lat_manual:.6f}, {lon_manual:.6f}")

# If we have coordinates, proceed to weather and analysis UI
if st.session_state.coords:
    lat, lon = st.session_state.coords
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
