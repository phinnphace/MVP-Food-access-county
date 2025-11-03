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