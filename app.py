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
FINAL_DATA_PATH = os.path.join(os.path.dirname(__file__), 'tracts_with_scores.geojson')
JOIN_COLUMN = 'GEOID'

@st.cache_data
def load_final_geodata(filepath):
    """Loads the final scored GeoDataFrame."""
    try:
        final_geodf = gpd.read_file(filepath)
        final_geodf[JOIN_COLUMN] = final_geodf[JOIN_COLUMN].astype(str)
        return final_geodf
    except Exception as e:
        st.error(f"Error loading geospatial data: {e}")
        return gpd.GeoDataFrame()

final_geodf = load_final_geodata(FINAL_DATA_PATH)

if final_geodf.empty:
    st.error("No data loaded. Please check the file path.")
    st.stop()

# --- 2. MAP VISUALIZATION ---
st.title("🍎 Food Access Vulnerability: Contextual Scoring in Decatur County, GA")

st.markdown("""
**RUCA (Rural-Urban Commuting Area)** codes classify census tracts based on how people live and travel. 
Unlike county-level categories, RUCA identifies whether a tract is urban, suburban, rural, or remote 
by looking at commuting patterns and local connectivity. It gives a more realistic picture of access 
conditions, especially in areas where a single county includes both dense urban centers and isolated 
rural communities. RUCA helps interpret food access barriers in context rather than treating all 
"rural" or all "urban" places the same.

This dashboard demonstrates an **Equity-Centered Scoring Model** where context (RUCA classification) 
is used to weight components, correcting for the flaws of 'one-size-fits-all' vulnerability indices. 
The model incorporates **Composite Economic** and **Systemic Transit Penalty** factors.
""")

# --- A. Create Plotly Choropleth Map ---
st.subheader("1. Final Contextual Vulnerability Score (V_final_Weighted)")

MIN_SCORE = final_geodf['V_final_Weighted'].min()
MAX_SCORE = final_geodf['V_final_Weighted'].max()

st.caption(f"Score Range: {MIN_SCORE:.2f} (Green/Low Vulnerability) to {MAX_SCORE:.2f} (Red/High Vulnerability)")

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
    color='V_final_Weighted',
    color_continuous_scale='RdYlGn_r',  # Red-Yellow-Green reversed (red = high)
    range_color=[MIN_SCORE, MAX_SCORE],
    mapbox_style='carto-positron',
    zoom=9,
    center={"lat": center_lat, "lon": center_lon},
    opacity=0.7,
    hover_data={
        'GEOID': True,
        'V_final_Weighted': ':.2f',
        'V_final_Unweighted': ':.2f',
        'poverty_pct': ':.1f'
    },
    labels={
        'V_final_Weighted': 'Weighted Score',
        'V_final_Unweighted': 'Unweighted Score',
        'poverty_pct': 'Poverty %'
    }
)

fig.update_layout(
    margin={"r": 0, "t": 0, "l": 0, "b": 0},
    height=500,
    coloraxis_colorbar=dict(
        title="Vulnerability<br>Score",
        tickformat=".1f"
    )
)

st.plotly_chart(fig, use_container_width=True)

# --- 3. COMPARATIVE ANALYSIS ---
st.markdown("---")
st.subheader("2. Context vs. Flattening: Comparison of Scoring Models")

st.markdown("""
The comparison shows the difference between the **Unweighted Score** (simple additive) 
and the **Weighted Score** (using Transport Vulnerability Score with RUCA context weights).
""")

comparison_data = final_geodf[['GEOID', 'V_final_Unweighted', 'V_final_Weighted']].melt(
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

# --- 4. COMPONENT BREAKDOWN ---
st.markdown("---")
st.subheader("3. Component Breakdown: Identifying Specific Vulnerability Drivers")

st.markdown("""
This view is critical for **anti-erasure practice**, showing exactly which component 
(Economic, Geographic, Vehicle, Transit, Internet, Roads) drives the score for each tract.
""")

selected_geoid = st.selectbox(
    "Select a Tract GEOID:",
    final_geodf['GEOID'].sort_values()
)

components = ['C_Economic', 'C_Geographic', 'C_Vehicle_A', 'C_Transit_B', 'C_Internet_C', 'C_Roads_D']
available_components = [c for c in components if c in final_geodf.columns]

if available_components:
    breakdown_data_row = final_geodf[final_geodf['GEOID'] == selected_geoid].iloc[0]
    
    breakdown_data = pd.DataFrame({
        'Component': available_components,
        'Vulnerability Score': [float(breakdown_data_row[c]) for c in available_components]
    })
    
    chart_breakdown = alt.Chart(breakdown_data).mark_bar().encode(
        x=alt.X('Vulnerability Score:Q', title='Z-Score (Higher = More Vulnerable)'),
        y=alt.Y('Component:N', sort=None, title=''),
        color=alt.condition(
            alt.datum['Vulnerability Score'] > 0,
            alt.value('#D34D4D'),
            alt.value('#2E8B57')
        ),
        tooltip=['Component', alt.Tooltip('Vulnerability Score', format=".2f")]
    ).properties(
        title=f"Component Scores for Tract {selected_geoid}",
        height=300
    )
    
    st.altair_chart(chart_breakdown, use_container_width=True)
    
    # Show tract details
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Weighted Score", f"{breakdown_data_row['V_final_Weighted']:.2f}")
    with col2:
        st.metric("Unweighted Score", f"{breakdown_data_row['V_final_Unweighted']:.2f}")
    with col3:
        st.metric("Poverty Rate", f"{breakdown_data_row['poverty_pct']:.1f}%")
else:
    st.warning("Component scores not found. Please re-run: python3 vulnerability_scoring_weighted.py && python3 merge_geometry.py")

# --- 5. DATA TABLE ---
st.markdown("---")
st.subheader("4. Full Data Table")

display_cols = ['GEOID', 'TRACT_LABEL', 'poverty_pct', 'C_Economic', 'C_Geographic', 
                'C_Vehicle_A', 'C_Transit_B', 'C_Internet_C', 'C_Roads_D', 'TVS',
                'V_final_Unweighted', 'V_final_Weighted']
available_display = [c for c in display_cols if c in final_geodf.columns]

st.dataframe(
    final_geodf[available_display].round(3),
    use_container_width=True
)

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
