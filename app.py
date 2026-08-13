import os
import json
import sqlite3
import requests
import streamlit as st
from datetime import datetime

st.set_page_config(page_title="MacroSnap", page_icon="⚡", layout="centered")

# --- Custom Dark Theme & CSS ---
st.markdown("""
<style>
    .stApp {
        background-color: #0E0E11;
        color: #FFFFFF;
    }
    .block-container {
        padding-top: 3rem !important;
        padding-bottom: 3rem !important;
        padding-left: 1.2rem !important;
        padding-right: 1.2rem !important;
    }
    .main-title {
        font-size: 32px;
        font-weight: 800;
        margin-bottom: 2px;
        color: #FFFFFF;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    .sub-title {
        color: #8E8E93;
        font-size: 15px;
        margin-bottom: 20px;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    div[data-baseweb="textarea"] {
        background-color: #1C1C22 !important;
        border: 1px solid #2C2C34 !important;
        border-radius: 14px !important;
        padding: 4px !important;
    }
    div[data-baseweb="textarea"] textarea {
        color: #FFFFFF !important;
        background-color: transparent !important;
        font-size: 15px !important;
    }
    div.stButton > button {
        width: 100%;
        background-color: #272730;
        color: #FFFFFF;
        border: 1px solid #3A3A46;
        border-radius: 12px;
        padding: 12px 16px;
        font-size: 16px;
        font-weight: 600;
        margin-top: 8px;
        margin-bottom: 16px;
    }
    div.stButton > button:hover {
        background-color: #32323E;
        color: #FFFFFF;
    }
    div[data-testid="stMetricValue"] {
        font-size: 22px !important;
        color: #FFFFFF !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 12px !important;
        color: #8E8E93 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- SQLite Database Helper Functions ---
DB_FILE = "meals.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            meal_input TEXT,
            calories INTEGER,
            protein REAL,
            carbs REAL,
            fat REAL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS prep_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            prep_input TEXT,
            servings INTEGER,
            total_cals INTEGER,
            total_protein REAL,
            total_carbs REAL,
            total_fat REAL,
            per_cals INTEGER,
            per_protein REAL,
            per_carbs REAL,
            per_fat REAL
        )
    ''')
    conn.commit()
    conn.close()

def save_meal(meal_input, cals, protein, carbs, fat):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute('''
        INSERT INTO history (timestamp, meal_input, calories, protein, carbs, fat)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (now, meal_input, cals, protein, carbs, fat))
    conn.commit()
    conn.close()

def save_prep(prep_input, servings, total_cals, total_protein, total_carbs, total_fat, per_cals, per_protein, per_carbs, per_fat):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    c.execute('''
        INSERT INTO prep_history (timestamp, prep_input, servings, total_cals, total_protein, total_carbs, total_fat, per_cals, per_protein, per_carbs, per_fat)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (now, prep_input, servings, total_cals, total_protein, total_carbs, total_fat, per_cals, per_protein, per_carbs, per_fat))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT timestamp, meal_input, calories, protein, carbs, fat FROM history ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    return rows

def get_prep_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT timestamp, prep_input, servings, total_cals, total_protein, total_carbs, total_fat, per_cals, per_protein, per_carbs, per_fat FROM prep_history ORDER BY id DESC')
    rows = c.fetchall()
    conn.close()
    return rows

def clear_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM history')
    conn.commit()
    conn.close()

def clear_prep_history():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM prep_history')
    conn.commit()
    conn.close()

init_db()

# --- API Keys & Helper Functions ---
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

# --- UI Header & Tabs ---
st.markdown('<div class="main-title">MacroSnap</div>', unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["⚡ Log Meal", "🥘 Meal Prep", "📋 Daily History"])

# --- TAB 1: Log Single Meal ---
with tab1:
    st.markdown('<div class="sub-title">Describe what you ate</div>', unsafe_allow_html=True)
    
    meal_input = st.text_area(
        label="Describe what you ate", 
        placeholder="e.g. 2 eggs, toast with butter, orange juice...", 
        height=100,
        label_visibility="collapsed"
    )

    if st.button("⚡ Analyze & Save", type="primary", key="single_meal_btn"):
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

                save_meal(meal_input, total_cals, total_protein, total_carbs, total_fat)

                st.success("Meal analyzed & saved to history!")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Calories", f"{total_cals}")
                col2.metric("Protein", f"{total_protein:.0f}g")
                col3.metric("Carbs", f"{total_carbs:.0f}g")
                col4.metric("Fats", f"{total_fat:.0f}g")

                st.markdown("---")
                st.subheader("Itemized Breakdown")
                for line in breakdown_items:
                    st.info(line)

# --- TAB 2: Batch Meal Prep ---
with tab2:
    st.markdown('<div class="sub-title">Calculate Batch Meal Prep & Portions</div>', unsafe_allow_html=True)
    
    prep_input = st.text_area(
        label="Enter total cooked batch ingredients", 
        placeholder="e.g. 1000g chicken breast, 500g brown rice, 300g broccoli, 30g olive oil...", 
        height=110,
        key="prep_input_box"
    )

    servings = st.number_input("Number of Portions / Days", min_value=1, max_value=20, value=5, step=1)

    if st.button("🥘 Calculate & Save Bulk Prep", type="primary", key="batch_meal_btn"):
        if prep_input.strip():
            with st.spinner("Parsing bulk ingredients..."):
                parsed_data = ask_gemini_to_parse(prep_input)
                
            if not parsed_data or "ingredients" not in parsed_data:
                st.error("Failed to parse batch data. Check API keys.")
            else:
                batch_cals, batch_protein, batch_carbs, batch_fat = 0, 0.0, 0.0, 0.0

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

                        batch_cals += cals
                        batch_protein += prot
                        batch_carbs += carb
                        batch_fat += fat

                per_serving_cals = round(batch_cals / servings)
                per_serving_prot = batch_protein / servings
                per_serving_carb = batch_carbs / servings
                per_serving_fat = batch_fat / servings

                save_prep(prep_input, servings, batch_cals, batch_protein, batch_carbs, batch_fat, per_serving_cals, per_serving_prot, per_serving_carb, per_serving_fat)

                st.success("Meal prep saved to history!")

                st.markdown("### 🍽️ Per Serving (1 of " + str(servings) + " Portions)")
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Calories", f"{per_serving_cals}")
                col2.metric("Protein", f"{per_serving_prot:.0f}g")
                col3.metric("Carbs", f"{per_serving_carb:.0f}g")
                col4.metric("Fats", f"{per_serving_fat:.0f}g")

                st.markdown("---")
                st.markdown("### 📦 Total Batch Macros")
                b_col1, b_col2, b_col3, b_col4 = st.columns(4)
                b_col1.metric("Total Cals", f"{batch_cals}")
                b_col2.metric("Total Prot", f"{batch_protein:.0f}g")
                b_col3.metric("Total Carbs", f"{batch_carbs:.0f}g")
                b_col4.metric("Total Fat", f"{batch_fat:.0f}g")

    st.markdown("---")
    st.markdown("### 📜 Saved Meal Preps")
    prep_records = get_prep_history()

    if not prep_records:
        st.info("No meal preps saved yet.")
    else:
        for record in prep_records:
            timestamp, input_text, serv, t_cals, t_prot, t_carb, t_fat, p_cals, p_prot, p_carb, p_fat = record
            with st.expander(f"🥘 {timestamp} — {serv} Servings ({p_cals} kcal/portion)"):
                st.write(f"**Ingredients:** {input_text}")
                
                st.write("**Per Serving:**")
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Calories", f"{p_cals}")
                col_b.metric("Protein", f"{p_prot:.0f}g")
                col_c.metric("Carbs", f"{p_carb:.0f}g")
                col_d.metric("Fats", f"{p_fat:.0f}g")

                st.write("**Full Batch:**")
                b_a, b_b, b_c, b_d = st.columns(4)
                b_a.metric("Batch Cals", f"{t_cals}")
                b_b.metric("Batch Prot", f"{t_prot:.0f}g")
                b_c.metric("Batch Carbs", f"{t_carb:.0f}g")
                b_d.metric("Batch Fats", f"{t_fat:.0f}g")

                if st.button(f"Log 1 Portion to Daily Log", key=f"log_prep_{record[0]}"):
                    save_meal(f"Meal Prep Portion ({input_text[:25]}...)", p_cals, p_prot, p_carb, p_fat)
                    st.success("Added 1 portion to Daily History!")

        if st.button("Clear Meal Prep History", key="clear_prep_hist_btn"):
            clear_prep_history()
            st.rerun()

# --- TAB 3: Daily History ---
with tab3:
    st.markdown('<div class="sub-title">Your Logged Meals</div>', unsafe_allow_html=True)
    
    history_records = get_history()
    
    if not history_records:
        st.info("No meals logged yet.")
    else:
        for record in history_records:
            timestamp, meal_text, cals, prot, carb, fat = record
            with st.expander(f"🕒 {timestamp} — {cals} kcal"):
                st.write(f"**Meal:** {meal_text}")
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("Calories", f"{cals}")
                col_b.metric("Protein", f"{prot:.0f}g")
                col_c.metric("Carbs", f"{carb:.0f}g")
                col_d.metric("Fats", f"{fat:.0f}g")

        st.markdown("---")
        if st.button("Clear Daily History", key="clear_hist_btn"):
            clear_history()
            st.rerun()
