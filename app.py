import streamlit as st
import geopandas as gpd
import pandas as pd
import altair as alt
import plotly.express as px
import json
import os

# --- 1. CONFIGURATION AND DATA LOADING ---
st.set_page_config(layout="wide", page_title="Decatur County Contextual Vulnerability Score")

# Works for both local development and Streamlit Cloud
FINAL_DATA_PATH = os.path.join(os.path.dirname(__file__), 'tracts_data.geojson') # Updated to match your repo filename
JOIN_COLUMN = 'GEOID'

@st.cache_data
def load_final_geodata(filepath):
    """Loads the final scored GeoDataFrame."""
    try:
        final_geodf = gpd.read_file(filepath)
        # Ensure GEOID is a string for consistent merging/tooltip display
        if JOIN_COLUMN in final_geodf.columns:
            final_geodf[JOIN_COLUMN] = final_geodf[JOIN_COLUMN].astype(str)
        return final_geodf
    except Exception as e:
        st.error(f"Error loading geospatial data: {e}")
        return gpd.GeoDataFrame()

final_geodf = load_final_geodata(FINAL_DATA_PATH)

if final_geodf.empty:
    st.error("No data loaded. Please check that 'tracts_data.geojson' is in your repository.")
    st.stop()

# --- 2. SIDEBAR CONTROLS ---
st.sidebar.header("Map Controls")

# A. Layer Selection
layer_config = {
    "Overall Weighted (V_final_Weighted)": {
        "field": "V_final_Weighted",
        "colorscale": "RdYlGn_r", # Red = High Vulnerability
        "label": "Weighted Vulnerability Score",
        "description": "**Final contextual vulnerability score** incorporating RUCA-based weighting of transport components."
    },
    "Economic (C_Economic)": {
        "field": "C_Economic",
        "colorscale": "Oranges",
        "label": "Economic Vulnerability (Z-score)",
        "description": "**Economic vulnerability composite** = -Z(Income) + Z(Poverty Rate). Captures both affluence and deprivation."
    },
    "Geographic (C_Geographic)": {
        "field": "C_Geographic",
        "colorscale": "Purples",
        "label": "Geographic Vulnerability (Z-score)",
        "description": "**Geographic access vulnerability** = -Z(Grocery Store Density). Lower density = higher vulnerability."
    },
    "Transport Composite (TVS)": {
        "field": "TVS",
        "colorscale": "Blues",
        "label": "Transport Vulnerability Score",
        "description": "**Transport Vulnerability Score** = 0.5×Vehicle + 0.2×Transit + 0.2×Internet + 0.1×Roads (RUCA-weighted)."
    },
    "Vehicle Access (C_Vehicle_A)": {
        "field": "C_Vehicle_A",
        "colorscale": "Reds",
        "label": "Vehicle Access Vulnerability (Z-score)",
        "description": "**Vehicle access vulnerability** = Z(% Households with No Vehicle). Heavily weighted (50%) in rural contexts."
    },
    "Internet Access (C_Internet_C)": {
        "field": "C_Internet_C",
        "colorscale": "Greens", # Reverse this if High Score = Bad, usually Greens is Good=Dark
        "label": "Internet Access Vulnerability (Z-score)",
        "description": "**Internet access vulnerability** = Z(No Internet) + Z(No Broadband) - Z(Cellular Only)."
    },
    "Road Infrastructure (C_Roads_D)": {
        "field": "C_Roads_D",
        "colorscale": "Greys",
        "label": "Road Infrastructure Vulnerability (Z-score)",
        "description": "**Road infrastructure vulnerability** = -Z(% Primary/Secondary Roads). Lower road density = higher vulnerability."
    }
}

selected_layer = st.sidebar.radio(
    "Select Vulnerability Layer:",
    options=list(layer_config.keys())
)

# Get selected config
config = layer_config[selected_layer]

# B. Basemap Selection
basemap_styles = {
    "Light (carto-positron)": "carto-positron",
    "OpenStreetMap": "open-street-map",
    "Dark": "carto-darkmatter",
    "Satellite": "white-bg"
}
selected_basemap = st.sidebar.selectbox(
    "Select Basemap Style:",
    options=list(basemap_styles.keys())
)

# --- 3. MAIN DASHBOARD ---
st.title("🍎 Food Access Vulnerability: Contextual Scoring in Decatur County, GA")

st.markdown("""
**RUCA (Rural-Urban Commuting Area)** codes classify census tracts based on how people live and travel. 
Unlike county-level categories, RUCA identifies whether a tract is urban, suburban, rural, or remote 
by looking at commuting patterns and local connectivity. It gives a more realistic picture of access 
conditions, especially in areas where a single county includes both dense urban centers and isolated 
rural communities.
""")

# --- MAP VISUALIZATION ---
st.subheader(f"1. {selected_layer.split('(')[0].strip()}")

# Dynamic Description based on selection
st.info(config['description'])

# Calculate min/max for color scale
# Rigor Check: Handle missing columns gracefully
if config['field'] not in final_geodf.columns:
    st.error(f"Column '{config['field']}' not found in data. Please check your data export.")
    st.stop()

MIN_SCORE = final_geodf[config['field']].min()
MAX_SCORE = final_geodf[config['field']].max()

st.caption(f"Score Range: {MIN_SCORE:.2f} (Low Vulnerability) to {MAX_SCORE:.2f} (High Vulnerability)")

# Convert to GeoJSON for Plotly
geojson_data = json.loads(final_geodf.to_json())

# Calculate center
centroid = final_geodf.geometry.unary_union.centroid
center_lat, center_lon = centroid.y, centroid.x

# Create Plotly choropleth
fig = px.choropleth_mapbox(
    final_geodf,
    geojson=geojson_data,
    locations=final_geodf.index,
    color=config['field'],
    color_continuous_scale=config['colorscale'],
    range_color=[MIN_SCORE, MAX_SCORE],
    mapbox_style=basemap_styles[selected_basemap],
    zoom=9,
    center={"lat": center_lat, "lon": center_lon},
    opacity=0.7,
    hover_data={
        'GEOID': True,
        config['field']: ':.2f',
        'V_final_Weighted': ':.2f',
        'poverty_pct': ':.1f'
    },
    labels={
        config['field']: "Current Score",
        'V_final_Weighted': 'Overall Score',
        'poverty_pct': 'Poverty %'
    }
)

fig.update_layout(
    margin={"r": 0, "t": 0, "l": 0, "b": 0},
    height=500,
    coloraxis_colorbar=dict(
        title=config['label'][:20] + "<br>" + config['label'][20:] if len(config['label']) > 20 else config['label'],
        tickformat=".1f"
    )
)

st.plotly_chart(fig, use_container_width=True)

# --- 4. COMPARATIVE ANALYSIS (Unchanged for Rigor) ---
st.markdown("---")
st.subheader("2. Context vs. Flattening: Comparison of Scoring Models")

st.markdown("""
The comparison shows the difference between the **Unweighted Score** (simple additive) 
and the **Weighted Score** (using Transport Vulnerability Score with RUCA context weights).
""")

# Melt data for Altair
comparison_cols = ['GEOID', 'V_final_Unweighted', 'V_final_Weighted']
if all(col in final_geodf.columns for col in comparison_cols):
    comparison_data = final_geodf[comparison_cols].melt(
        id_vars='GEOID', var_name='Score Type', value_name='Score'
    )

    chart_comp = alt.Chart(comparison_data).mark_bar().encode(
        x=alt.X('GEOID:N', sort=alt.EncodingSortField(field="Score", op="max", order="descending"), title='Tract GEOID'),
        y=alt.Y('Score:Q', title='Vulnerability Score (Higher = More Vulnerable)'),
        color=alt.Color('Score Type:N', scale=alt.Scale(range=['#007ACC', '#D34D4D']), 
                        legend=alt.Legend(title="Score Type")),
        xOffset='Score Type:N',
        tooltip=['GEOID', 'Score Type', alt.Tooltip('Score', format=".2f")]
    ).properties(
        title="Unweighted vs. Weighted (TVS) Vulnerability Scores",
        height=400
    ).interactive()

    st.altair_chart(chart_comp, use_container_width=True)
else:
    st.warning("Comparison columns not found in dataset.")

# --- SECTIONS 5 & 6: METHODOLOGY, DATASETS, AND FOOTER ---
st.markdown("---")
st.subheader("5. Model Methodology")

st.markdown(r"""
All standardized variables use global mean ($\mu$) and global standard deviation ($\sigma$) from the master dataset.  
This ensures Decatur County's tracts (N=8) are evaluated relative to the broader landscape rather than an artificially small local sample.
""")

st.markdown("#### Model Formulas")

st.markdown("**Final Weighted Model**")
st.latex(r"V_{final\_W} = C_{Eco} + C_{Geo} + TVS")

st.markdown("**Transport Vulnerability Score**")
st.latex(r"TVS = 0.5\,C_A + 0.2\,C_B + 0.2\,C_{Internet\_C} + 0.1\,C_{Roads\_D}")

st.markdown("**Transit Absence Penalty**")
st.latex(r"C_{Transit\_B} = +3.0")

st.markdown("**Unweighted Model (for comparison)**")
st.latex(r"V_{final\_UW} = C_{Eco} + C_{Geo} + C_A + C_{Transit\_B} + C_{Internet\_C} + C_{Roads\_D}")

st.markdown("---")
st.markdown("#### Component Definitions")

st.markdown("**1. Economic Vulnerability (C_Economic)**")
st.markdown(r"""
**Concept:** Income alone hides deprivation. Pairing reversed income with positive poverty rate prevents flattening of economic reality.  
**Variables:** Median Household Income, Poverty Rate (%)
""")
st.latex(r"C_{Economic} = -Z_{Income} + Z_{Poverty\_Pct}")

st.markdown("**2. Geographic Vulnerability (C_Geo)**")
st.markdown(r"""
**Concept:** Store density directly indicates food resource availability. Low density increases vulnerability.  
**Variable:** den_totalfoodstores (density of all food stores)
""")
st.latex(r"C_{Geo} = -Z_{den\_totalfoodstores}")

st.markdown("**3. Vehicle Access Vulnerability (C_Vehicle_A)**")
st.markdown(r"""
**Concept:** In rural areas without transit, lacking a vehicle is one of the strongest predictors of limited access.  
**Variable:** Vehicles_PctHH_NoVehicle
""")
st.latex(r"C_{Vehicle\_A} = Z_{Vehicles\_PctHH\_NoVehicle}")

st.markdown("**4. Transit Access Vulnerability (C_Transit_B)**")
st.markdown(r"""
**Concept:** Transit stop availability is protective. Zero availability indicates systemic infrastructure failure.  
**Variable:** STOPS_PER_CAPITA  
For tracts with no transit, impute systemic penalty:
""")
st.latex(r"C_{Transit\_B} = +3.0 \quad \text{(when no transit exists)}")
st.markdown("Main formula:")
st.latex(r"C_{Transit\_B} = -Z_{STOPS\_PER\_CAPITA}")

st.markdown("**5. Internet Access Vulnerability (C_Internet_C)**")
st.markdown(r"""
**Concept:** Digital connectivity increasingly substitutes for physical access. Lack-of-access increases vulnerability; access variables reduce it.  
**Variables:** est_NO_INT, pct_no_internet, pct_cellular_broadband (protective)
""")
st.latex(r"C_{Internet\_C} = Z_{est\_NO\_INT} + Z_{pct\_no\_internet} - Z_{pct\_cellular\_broadband}")

st.markdown("**6. Roads / Walkability Vulnerability (C_Roads_D)**")
st.markdown(r"""
**Concept:** Primary and secondary roads serve as a proxy for mobility infrastructure. Low road density increases vulnerability.  
**Variable:** PROP_PRIM_SEC_ROADS
""")
st.latex(r"C_{Roads\_D} = -Z_{PROP\_PRIM\_SEC\_ROADS}")

st.markdown("---")
st.markdown("#### Interpretation Framework")
st.markdown(r"""
The comparison between **unweighted** and **RUCA-weighted** final scores reveals the necessity of context-sensitive weighting.  
The unweighted model treats all components equally, erasing rural conditions.  
The weighted model elevates the components that matter most in Micropolitan regions—vehicle access, roads—and down-weights structurally absent elements like transit.

This prevents the erasure of localized transport barriers and creates an equitable, context-aware food access vulnerability score.
""")

# --- DATASETS ---
st.markdown("---")
st.subheader("6. Datasets")

st.markdown("""
The following external datasets were used to construct the vulnerability index:

| Dataset | Contribution | Source |
|---------|--------------|--------|
| **ACS 5-Year Estimates (2019-2023)** | Socioeconomic indicators: median income, poverty status, vehicle availability, internet access | [U.S. Census Bureau](https://data.census.gov) |
| **NaNDA Grocery Stores (2020)** | Grocery store density by census tract | [ICPSR](https://doi.org/10.3886/E209313V1) |
| **NaNDA Transit Stops (2024)** | Public transit stop counts per tract | [ICPSR](https://doi.org/10.3886/ICPSR38605.v2) |
| **NaNDA Road Infrastructure (2020)** | Primary/secondary road density as walkability proxy | [ICPSR](https://doi.org/10.3886/ICPSR38585.v2) |
| **NaNDA Internet Access (2019)** | Household internet connectivity estimates | [ICPSR](https://doi.org/10.3886/ICPSR38559.v1) |
| **USDA RUCA Codes (2020)** | Rural-urban connectivity and commuting context | [USDA ERS](https://www.ers.usda.gov/data-products/rural-urban-commuting-area-codes/) |
| **USDA RUCC Codes (2023)** | County-level rural-urban classification | [USDA ERS](https://www.ers.usda.gov/data-products/rural-urban-continuum-codes/) |
| **HUD ZIP-Tract Crosswalk (2020)** | Geographic alignment for ZCTA-tract merges | [HUD User](https://www.huduser.gov/portal/datasets/usps_crosswalk.html) |
""")

# --- FOOTER ---
st.markdown(
    r"""
    <hr/>
    <p style='text-align:center'>
    <a href='https://github.com/phinnphace/MVP-Food-access-county' target='_blank'>GitHub Repository</a>
    </p>
    """,
    unsafe_allow_html=True,
)
