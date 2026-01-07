import streamlit as st
import geopandas as gpd
import pandas as pd
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
import json
import os

# --- 1. CONFIGURATION AND DATA LOADING ---
st.set_page_config(
    layout="wide", 
    page_title="Seeing through the Map"
)

FINAL_DATA_PATH = os.path.join(os.path.dirname(__file__), 'tracts_data.geojson')
JOIN_COLUMN = 'GEOID'

@st.cache_data
def load_final_geodata(filepath):
    try:
        final_geodf = gpd.read_file(filepath)
        if JOIN_COLUMN in final_geodf.columns:
            final_geodf[JOIN_COLUMN] = final_geodf[JOIN_COLUMN].astype(str)
        return final_geodf
    except Exception as e:
        st.error(f"Error loading geospatial data: {e}")
        return gpd.GeoDataFrame()

final_geodf = load_final_geodata(FINAL_DATA_PATH)

if final_geodf.empty:
    st.error("No data loaded. Please check 'tracts_data.geojson' in repo.")
    st.stop()

# --- 2. SIDEBAR CONTROLS ---
st.sidebar.header("Explore the Model")

# Narrative Structure
layer_structure = {
    "1. Composite Vulnerability Drivers": {
        "Economic Vulnerability": "C_Economic",
        "Geographic (Food) Vulnerability": "C_Geographic",
        "Transportation Vulnerability (TVS)": "TVS"
    },
    "2. Systemic Transit Impact Components": {
        "Transit Access": "C_Transit_B", # Renamed from "Penalty Score"
        "Vehicle Access": "C_Vehicle_A",
        "Internet Access": "C_Internet_C",
        "Walkability (Road Density)": "C_Roads_D"
    },
    "3. Assessment Models": {
        "Final Unweighted Score": "V_final_Unweighted",
        "Final Weighted Score (RUCA Adjusted)": "V_final_Weighted"
    }
}

selected_category = st.sidebar.selectbox("Select Analysis Dimension:", list(layer_structure.keys()))
selected_label = st.sidebar.radio("Select Layer:", list(layer_structure[selected_category].keys()))
selected_col = layer_structure[selected_category][selected_label]

# Layer Styling
layer_details = {
    "C_Economic": {"colorscale": "Oranges", "desc": "**Economic Vulnerability** = -Z(Income) + Z(Poverty). High values indicate high poverty/low income."},
    "C_Geographic": {"colorscale": "Purples", "desc": "**Geographic Vulnerability** = -Z(Food Store Density). Captures the physical distance barrier."},
    "TVS": {"colorscale": "Blues", "desc": "**Transport Vulnerability Score (TVS)** = Weighted composite of Vehicle, Transit, Internet, and Roads."},
    "C_Transit_B": {"colorscale": "Reds", "desc": "**Transit Access Score.** Measures availability of public transit infrastructure. (See methodology for weighting details)."},
    "C_Vehicle_A": {"colorscale": "YlOrBr", "desc": "**Vehicle Access.** Measures % of households without a vehicle."},
    "C_Internet_C": {"colorscale": "Greens", "desc": "**Internet Access.** Digital connectivity as a substitute for physical access."},
    "C_Roads_D": {"colorscale": "Greys", "desc": "**Walkability.** Primary/secondary road density as infrastructure proxy."},
    "V_final_Unweighted": {"colorscale": "RdYlGn_r", "desc": "**Unweighted Score.** Simple sum of vulnerabilities."},
    "V_final_Weighted": {"colorscale": "RdYlGn_r", "desc": "**Final Weighted Score.** Adjusts for RUCA context."}
}
current_config = layer_details.get(selected_col, {"colorscale": "Viridis", "desc": ""})

# --- 3. MAIN DASHBOARD ---
# New Title reflecting the methodological focus
st.title("Seeing through the Map: A Static Test of Classification, Measurement, and Proxy Logic")

st.markdown("""
### An Invitation to Critique
This dashboard is not a statement of fact, but a **proposal for measurement**. 
Standard USDA maps often erase local nuance. This model attempts to correct that by introducing **Contextual Weighting (RUCA)** and accounting for systemic infrastructure gaps.

**How to use this tool:**
1.  **Deconstruct:** Use the sidebar to view the raw components (like Transit or Internet).
2.  **Compare:** Look at how the *Unweighted* score differs from the *Weighted* score.
3.  **Ask:** Does this classification logic hold up? Where does the proxy logic fail?
""")

st.info(f"**Viewing: {selected_label}**\n\n{current_config['desc']}")

# Map Logic
if selected_col not in final_geodf.columns:
    st.error(f"Column '{selected_col}' missing.")
    st.stop()

# 1. Base Choropleth Layer
fig = px.choropleth_mapbox(
    final_geodf,
    geojson=json.loads(final_geodf.to_json()),
    locations=final_geodf.index,
    color=selected_col,
    color_continuous_scale=current_config['colorscale'],
    mapbox_style="open-street-map", # Hardcoded to OSM as requested
    zoom=9.2,
    center={"lat": final_geodf.geometry.centroid.y.mean(), "lon": final_geodf.geometry.centroid.x.mean()},
    opacity=0.6,
    hover_data={'GEOID': True, selected_col: ':.2f'}
)

# 2. ADDING STATIC LABELS (FIPS Codes)
final_geodf['centroid_lat'] = final_geodf.geometry.centroid.y
final_geodf['centroid_lon'] = final_geodf.geometry.centroid.x

fig.add_trace(go.Scattermapbox(
    lat=final_geodf['centroid_lat'],
    lon=final_geodf['centroid_lon'],
    mode='text',
    text=final_geodf['GEOID'],
    textposition="middle center",
    textfont=dict(size=12, color='black', weight='bold'), # Slightly bumped size/weight for readability on OSM
    showlegend=False,
    hoverinfo='none'
))

# 3. ADDING STATIC OUTLINES
# Apply the outline ONLY to the Choropleth (the polygons), not the text layer
fig.update_traces(
    marker_line_width=2, 
    marker_line_color="white", 
    selector=dict(type='choroplethmapbox')
)

fig.update_layout(margin={"r":0,"t":0,"l":0,"b":0}, height=600)
st.plotly_chart(fig, use_container_width=True)

# --- 4. COMPONENT BREAKDOWN ---
st.markdown("---")
st.subheader("Trace the Score: Component Breakdown")
st.write("Select a tract to see exactly how its score was built.")

selected_geoid = st.selectbox("Select Tract (FIPS):", final_geodf['GEOID'].sort_values())

comp_list = ['C_Economic', 'C_Geographic', 'C_Vehicle_A', 'C_Transit_B', 'C_Internet_C', 'C_Roads_D']
available_comps = [c for c in comp_list if c in final_geodf.columns]

if available_comps:
    row = final_geodf[final_geodf['GEOID'] == selected_geoid].iloc[0]
    chart_data = pd.DataFrame({'Component': available_comps, 'Score': [row[c] for c in available_comps]})
    
    c = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Score', title='Vulnerability Contribution'),
        y=alt.Y('Component', sort=None),
        color=alt.condition(alt.datum.Score > 0, alt.value('#D34D4D'), alt.value('#2E8B57')),
        tooltip=['Component', 'Score']
    ).properties(height=300)
    st.altair_chart(c, use_container_width=True)

# --- SECTIONS 5 & 6: METHODOLOGY ---
st.markdown("---")
st.subheader("5. Model Methodology")

st.markdown(r"""
All standardized variables use global mean ($\mu$) and global standard deviation ($\sigma$) from the master dataset.  
This ensures these tracts are evaluated relative to the broader landscape.
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
