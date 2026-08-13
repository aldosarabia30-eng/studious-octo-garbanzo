import os
import json
import requests
import streamlit as st

st.set_page_config(page_title="MacroSnap", page_icon="🔥", layout="centered")

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

st.title("🔥 MacroSnap Dashboard")
st.caption("AI-Powered Macro Parsing + USDA Database")

meal_input = st.text_area("What did you eat?", placeholder="e.g., 100g oats, 2 large eggs...")

if st.button("Analyze & Log Macros", type="primary"):
    if meal_input.strip():
        with st.spinner("AI is calculating macro distributions..."):
            parsed_data = ask_gemini_to_parse(meal_input)
            
        if not parsed_data or "ingredients" not in parsed_data:
            st.error("Failed to parse data. Verify your Gemini API Key configuration.")
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

                    breakdown_items.append(f"**{usda_data['name']}** ({qty}{unit})  \n🔥 {cals} kcal | 🍖 P: {prot}g | 🍞 C: {carb}g | 🥑 F: {fat}g")

            st.success("Meal analysis completed successfully!")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Calories", f"{total_cals} kcal")
            col2.metric("Protein", f"{total_protein:.1f}g")
            col3.metric("Carbs", f"{total_carbs:.1f}g")
            col4.metric("Fats", f"{total_fat:.1f}g")

            st.subheader("Itemized Breakdown")
            for line in breakdown_items:
                st.info(line)
