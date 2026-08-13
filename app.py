import os
import json
import requests
import streamlit as st

st.set_page_config(page_title="MacroSnap", page_icon="⚡", layout="centered")

# --- Custom Fixed Mobile Layout & Hidden Streamlit UI ---
st.markdown("""
<style>
    /* Lock viewport height and disable scrolling */
    html, body, [data-testid="stAppViewContainer"], .main {
        height: 100vh !important;
        max-height: 100vh !important;
        overflow: hidden !important;
        background-color: #0E0E11;
        color: #FFFFFF;
    }

    /* Remove default Streamlit top/bottom padding */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 0rem !important;
        padding-left: 1rem !important;
        padding-right: 1rem !important;
    }

    /* Completely hide Streamlit cloud overlays & banners */
    div[data-testid="stToolbar"],
    div[data-testid="stDecoration"],
    div[data-testid="stStatusWidget"],
    #MainMenu, footer, header {
        display: none !important;
        visibility: hidden !important;
        height: 0px !important;
    }
    
    /* Title & Subtitle Styling */
    .main-title {
        font-size: 28px;
        font-weight: 800;
        margin-bottom: 0px;
        color: #FFFFFF;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .sub-title {
        color: #8E8E93;
        font-size: 14px;
        margin-bottom: 12px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .section-label {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1px;
        color: #6E6E73;
        margin-top: 12px;
        margin-bottom: 8px;
        text-transform: uppercase;
    }

    /* Text Area Styling */
    div[data-baseweb="textarea"] {
        background-color: #1C1C22 !important;
        border: 1px solid #2C2C34 !important;
        border-radius: 14px !important;
        padding: 4px !important;
    }
    div[data-baseweb="textarea"] textarea {
        color: #FFFFFF !important;
        background-color: transparent !important;
        font-size: 14px !important;
    }

    /* Analyze Button */
    div.stButton > button {
        width: 100%;
        background-color: #272730;
        color: #FFFFFF;
        border: 1px solid #3A3A46;
        border-radius: 12px;
        padding: 10px 16px;
        font-size: 15px;
        font-weight: 600;
        margin-top: 6px;
    }

    /* Example Chips */
    div[data-testid="column"] button {
        background-color: #1C1C22;
        color: #E5E5EA;
        border: 1px solid #2C2C34;
        border-radius: 10px;
        text-align: left;
        padding: 8px 12px;
        font-size: 13px;
        margin-bottom: 4px;
    }

    /* Fixed Bottom Navigation Bar */
    .bottom-nav {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #16161B;
        border-top: 1px solid #26262D;
        display: flex;
        justify-content: space-around;
        padding: 8px 0 12px 0;
        z-index: 999999;
    }
    .nav-item {
        text-align: center;
        color: #6E6E73;
        font-size: 11px;
        text-decoration: none;
    }
    .nav-item.active {
        color: #FF6200;
    }
    .nav-icon {
        font-size: 18px;
        display: block;
        margin-bottom: 2px;
    }
</style>
""", unsafe_allow_html=True)

# API Keys setup
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
USDA_KEY = os.getenv("USDA_API_KEY", "DEMO_KEY")

def ask_gemini_to_parse(text_entry):
    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
    prompt = f"""
    Analyze this food entry: "{text_entry}"
    Extract each ingredient, its numeric quantity, and unit.
    Return strictly as JSON matching this format:
    {{
      "ingredients": [{{"name": "oats", "quantity": 100, "unit": "g"}}]
    }}
    Do not add backticks or code markdown blocks.
    """
    headers = {"Content-Type": "application/json", "x-goog-api-key": GEMINI_KEY}
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    try:
        res = requests.post(url, headers=headers, json=payload).json()
        raw_text = res['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw_text)
    except Exception:
        return None

def fetch_usda_macros(food_name):
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={USDA_KEY}&query={food_name}&pageSize=1"
    try:
        res = requests.get(url).json()
        if res.get("foods"):
            top_match = res["foods"][0]
            nutrients = top_match.get("foodNutrients", [])
            def get_val(id_num):
                for n in nutrients:
                    if n.get("nutrientId") == id_num: return n.get("value", 0.0)
                return 0.0
            return {
                "name": top_match.get("description", food_name),
                "calories": get_val(1008),
                "protein": get_val(1003),
                "carbs": get_val(1005),
                "fat": get_val(1004)
            }
    except Exception:
        pass
    return None

# --- UI Layout ---
st.markdown('<div class="main-title">MacroSnap</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Describe what you ate</div>', unsafe_allow_html=True)

if "meal_text" not in st.session_state:
    st.session_state["meal_text"] = ""

meal_input = st.text_area(
    label="Describe what you ate", 
    value=st.session_state["meal_text"],
    placeholder="e.g. 2 eggs, toast with butter, orange juice...", 
    height=90,
    label_visibility="collapsed"
)

if st.button("⚡ Analyze", type="primary"):
    if meal_input.strip():
        with st.spinner("Calculating macros..."):
            parsed_data = ask_gemini_to_parse(meal_input)
            
        if not parsed_data or "ingredients" not in parsed_data:
            st.error("Failed to parse data. Check API keys.")
        else:
            total_cals, total_protein, total_carbs, total_fat = 0, 0.0, 0.0, 0.0
            breakdown_items = []

            for item in parsed_data["ingredients"]:
                name = item.get("name", "Unknown")
                qty = item.get("quantity", 1.0)
                unit = item.get("unit", "g")
                
                usda_data = fetch_usda_macros(name)
                if usda_data:
                    multiplier = qty / 100.0 if unit.lower() == 'g' else 1.0
                    cals = round(usda_data["calories"] * multiplier)
                    prot = round(usda_data["protein"] * multiplier, 1)
                    carb = round(usda_data["carbs"] * multiplier, 1)
                    fat = round(usda_data["fat"] * multiplier, 1)

                    total_cals += cals
                    total_protein += prot
                    total_carbs += carb
                    total_fat += fat

                    breakdown_items.append(f"**{usda_data['name']}** ({qty}{unit})  \n⚡ {cals} kcal | 🥩 P: {prot}g | 🍞 C: {carb}g | 🥑 F: {fat}g")

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Cals", f"{total_cals}")
            col2.metric("Protein", f"{total_protein:.0f}g")
            col3.metric("Carbs", f"{total_carbs:.0f}g")
            col4.metric("Fats", f"{total_fat:.0f}g")

st.markdown('<div class="section-label">TRY AN EXAMPLE</div>', unsafe_allow_html=True)

examples = [
    "2 eggs, 2 slices whole wheat toast, 1 tbsp butter",
    "Grilled chicken breast 150g with brown rice 200g",
    "Greek yogurt 200g with honey and granola"
]

for ex in examples:
    if st.button(ex, key=ex):
        st.session_state["meal_text"] = ex
        st.rerun()

# Bottom Mobile Navigation Bar
st.markdown("""
<div class="bottom-nav">
    <div class="nav-item active">
        <span class="nav-icon">⚡</span>
        Log
    </div>
    <div class="nav-item">
        <span class="nav-icon">📋</span>
        History
    </div>
    <div class="nav-item">
        <span class="nav-icon">📊</span>
        Weekly
    </div>
</div>
""", unsafe_allow_html=True)
