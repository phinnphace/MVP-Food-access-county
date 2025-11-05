# ----- absolute data paths -----

import glob

import pandas as pd
import streamlit as st

st.write("Files in repo:", glob.glob("*.csv"))
from os import path
BASE_DIR = path.dirname("Users/phinnmarkson/PyCharmMiscProject/app.py")          # folder where app.py lives
HUD_ZIP_COUNTY = path.join(BASE_DIR, "HUDcrosswalkZip_COUNTY.csv")
ZIPT_ZCTA      = path.join(BASE_DIR, "ZiptoZCTA-Table 1.csv")
CSV_SCORES     = path.join(BASE_DIR, "county_vulnerability.csv")


@st.cache_data
def load():
    return pd.read_csv("county_vulnerability.csv")

df = load()

# ===== NEW: ZIP INPUT =====
st.title("Food Access Vulnerability")
zip_input = st.text_input("Enter a 5-digit ZIP code", placeholder="30601")
if zip_input and zip_input.isdigit() and len(zip_input) == 5:
    # 1. ZIP → ZCTA
    z2z = pd.read_csv(ZIPT_ZCTA)[["ZIP_CODE", "zcta"]]
    zcta_row = z2z.loc[z2z["ZIP_CODE"].astype(str) == zip_input]
    if not zcta_row.empty:
        zcta = str(zcta_row["zcta"].iloc[0])
        # 2. ZCTA → COUNTY (treat ZCTA as ZIP in HUD file)
        z2fips = pd.read_csv(HUD_ZIP_COUNTY)[["ZIP", "COUNTY"]]
        county_row = z2fips.loc[z2fips["ZIP"].astype(str) == zcta]
        if not county_row.empty:
            county_fips = str(county_row["COUNTY"].iloc[0]).zfill(5)
            match = df[df["fips_code"] == county_fips]
            if not match.empty:
                st.success(f"ZIP {zip_input} → {match.iloc[0]['County_Name']}, {match.iloc[0]['State']}")
                st.write(f"Score: {match.iloc[0]['Score']} | Label: {match.iloc[0]['Label']}")
                st.write(f"Median Income: ${match.iloc[0]['MedianIncome']:,.0f}")
                st.write(f"% Zero-Vehicle HH: {match.iloc[0]['PctZeroVehicleHH']:.1f}")
                st.write(f"Adjusted Supermarket Density: {match.iloc[0]['aden_supermarkets']:.2f}")
                st.write(f"% No Internet: {match.iloc[0]['PctNoInternet']:.1f}")
            else:
                st.warning("County not in our sample.")
        else:
            st.warning("ZCTA not found in county cross-walk.")
    else:
        st.warning("ZIP not found in ZCTA table.")
import streamlit as st
import pandas as pd
import plotly.express as px

@st.cache_data
def load():
    return pd.read_csv("county_vulnerability.csv")

df = load()

st.title("Food Access Vulnerability Map")
fig = px.choropleth(
    df,
    locations="fips_code",
    geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
    color="Score",
    color_continuous_scale="RdYlBu_r",
    scope="usa",
    hover_name="County_Name",
    hover_data={"State": True, "Score": True, "Label": True}
)
fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0})
st.plotly_chart(fig, use_container_width=True)