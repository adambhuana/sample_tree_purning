import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import pydeck as pdk
import json

# -----------------------------
# CONFIG
# -----------------------------
METEOBLUE_API_KEY = "MygwTmXLU3JYCHGO"
WIND_THRESHOLD = 30  # km/h
HEIGHT_THRESHOLD = 10  # meters
WO_MAX_HEIGHT = 20  # meter
TOLERANCE_MIN = 15  # meter

# -----------------------------
# LOAD DATA
# -----------------------------
@st.cache_data
def load_data():
    wo_locations = pd.read_csv("wo_locations.csv")
    tree_growth = pd.read_csv("tree_growth.csv")
    tree_data = pd.read_csv("tree_data.csv")
    return wo_locations, tree_growth, tree_data

wo_df, growth_df, tree_df = load_data()

# -----------------------------
# METEOBLUE API CALL
# -----------------------------
def get_wind_speed(lat, lon):
    url = f"https://my.meteoblue.com/packages/basic-day?lat={lat}&lon={lon}&apikey={METEOBLUE_API_KEY}&format=json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        # Tampilkan seluruh struktur JSON API
        st.subheader("📦 Respon JSON Meteoblue")
        st.code(json.dumps(data, indent=2))

        if "data_day" in data and "windspeed_max" in data["data_day"]:
            return data["data_day"]["windspeed_max"][0]
        else:
            st.warning("Field 'wind_speed_max' tidak ditemukan.")
            return None

    except Exception as e:
        st.error(f"API Error: {e}")
        try:
            st.code(response.text)
        except:
            pass
        return None

# -----------------------------
# RECOMMENDATION LOGIC
# -----------------------------
def recommend_pruning(wo_name):
    wo_info = wo_df[wo_df["name"] == wo_name].iloc[0]
    lat, lon = wo_info["latitude"], wo_info["longitude"]

    wind_speed = get_wind_speed(lat, lon)
    if wind_speed is None:
        st.error("Gagal mendapatkan data kecepatan angin dari Meteoblue.")
        return

    st.info(f"Kecepatan angin saat ini di sekitar {wo_name}: {wind_speed} km/h")

    current_year = datetime.now().year
    trees_near_wo = tree_df[tree_df["wo_name"] == wo_name]

    trees_merged = pd.merge(trees_near_wo, growth_df, on="species", how="left")
    trees_merged["age"] = current_year - trees_merged["planted_year"]
    trees_merged["current_height"] = trees_merged["initial_height"] + trees_merged["growth_per_year"] * trees_merged["age"]

    # Evaluasi
    trees_merged["prune_recommended"] = (
        (trees_merged["current_height"] > HEIGHT_THRESHOLD) & (wind_speed > WIND_THRESHOLD)
    )
    trees_merged["over_max_wo"] = trees_merged["current_height"] > WO_MAX_HEIGHT
    trees_merged["near_limit"] = (trees_merged["current_height"] >= TOLERANCE_MIN) & (trees_merged["current_height"] <= WO_MAX_HEIGHT)

    st.subheader("📋 Hasil Evaluasi Pohon")
    st.dataframe(trees_merged[["id", "species", "age", "current_height", "prune_recommended", "over_max_wo", "near_limit"]])

    st.subheader("✂️ Pohon Direkomendasikan untuk Dipangkas")
    st.table(trees_merged[trees_merged["prune_recommended"]][["id", "species", "current_height", "age"]])

    st.subheader("🚨 Pohon Melebihi Tinggi Maksimum WO (> 20 m)")
    st.table(trees_merged[trees_merged["over_max_wo"]][["id", "species", "current_height", "age"]])

    st.subheader("⚠️ Pohon Dalam Batas Toleransi (15–20 m)")
    st.table(trees_merged[trees_merged["near_limit"]][["id", "species", "current_height", "age"]])

    show_tree_map(trees_merged)

# -----------------------------
# MAP
# -----------------------------
def show_tree_map(tree_df):
    st.subheader("🗺️ Peta Pohon Sekitar WO")

    # Salin dataframe untuk manipulasi
    tree_df = tree_df.copy()

    # Warna berdasarkan tinggi pohon
    def assign_color(h):
        if h > WO_MAX_HEIGHT:
            return [255, 0, 0, 160]      # Merah
        elif h >= TOLERANCE_MIN:
            return [255, 255, 0, 160]    # Kuning
        else:
            return [0, 128, 0, 160]      # Hijau

    tree_df["color"] = tree_df["current_height"].apply(assign_color)

    st.pydeck_chart(pdk.Deck(
        map_style="road",
        initial_view_state=pdk.ViewState(
            latitude=tree_df["latitude"].mean(),
            longitude=tree_df["longitude"].mean(),
            zoom=13,
            pitch=0,
        ),
        layers=[
            pdk.Layer(
                "ScatterplotLayer",
                data=tree_df,
                get_position='[longitude, latitude]',
                get_color='color',
                get_radius=50,
                pickable=True,
            )
        ],
        tooltip={"text": "Lat: {latitude}\nLon: {longitude}\nTinggi: {current_height} m"},
    ))

# -----------------------------
# STREAMLIT UI
# -----------------------------
st.title("🌲 Rekomendasi Pemangkasan Pohon Sekitar WO")

wo_names = wo_df["name"].tolist()
selected_wo = st.selectbox("Pilih Lokasi WO", wo_names)

if st.button("Cek Rekomendasi"):
    recommend_pruning(selected_wo)
