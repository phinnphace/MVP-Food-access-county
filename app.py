# --- imports ---
import os
import glob
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px

# --- paths / debug ---
BASE_DIR = Path(__file__).resolve().parent

st.write("CWD:", os.getcwd())
st.write("Files:", glob.glob("*"))
st.write("CSV files:", glob.glob("*.csv"))

CSV_SCORES   = BASE_DIR / "county_vulnerability.csv"
HUD_ZIP_CNTY = BASE_DIR / "HUDcrosswalkZip_COUNTY.csv"       # expects at least: ZIP, county_fips (or state_fips+county_code), res_ratio (optional)
ZIP_ZCTA     = BASE_DIR / "ZiptoZCTA-Table 1 2.csv"          # expects at least: ZIP, ZCTA (column names normalized below)

# --- helpers ---
def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    # lower-case, strip spaces, unify common column names
    df = df.copy()
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[^a-z0-9]+", "_", regex=True)
    )
    # common renames
    renames = {
        "zip_code": "zip",
        "zipcode": "zip",
        "zcta5": "zcta",
        "zcta_code": "zcta",
        "zcta5ce10": "zcta",
        "county": "county_fips",   # some HUD files ship 'county' as 5-digit FIPS
        "countyfp": "county_code", # 3-digit county code only
        "statefp": "state_fips",
    }
    for k, v in renames.items():
        if k in df.columns and v not in df.columns:
            df = df.rename(columns={k: v})
    return df

def as_5(s):
    """Return a zero-padded 5-char string if possible, else None."""
    try:
        s = str(s).strip()
        digits = "".join(ch for ch in s if ch.isdigit())
        if not digits:
            return None
        return digits.zfill(5)[:5]
    except Exception:
        return None

# --- data ---
@st.cache_data
def load_scores(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path, dtype={"fips_code": str})
    df["fips_code"] = df["fips_code"].apply(as_5)
    return df

@st.cache_data
def load_hud_zip_county(hud_path: Path) -> pd.DataFrame:
    hud = pd.read_csv(hud_path, dtype=str)
    hud = normalize_cols(hud)
    # Try to build a 5-digit FIPS if not present
    if "county_fips" not in hud.columns:
        # many HUD files have state_fips (2) + county_code (3)
        if {"state_fips", "county_code"}.issubset(hud.columns):
            hud["county_fips"] = hud["state_fips"].str.zfill(2) + hud["county_code"].str.zfill(3)
    # zip should be 5-digit
    if "zip" in hud.columns:
        hud["zip"] = hud["zip"].apply(as_5)
    # optional numeric weights
    for col in ("res_ratio", "tot_ratio", "bus_ratio"):
        if col in hud.columns:
            hud[col] = pd.to_numeric(hud[col], errors="coerce")
    return hud

@st.cache_data
def load_zip_zcta(z_path: Path) -> pd.DataFrame:
    z = pd.read_csv(z_path, dtype=str)
    z = normalize_cols(z)
    # normalize keys
    if "zip" in z.columns:
        z["zip"] = z["zip"].apply(as_5)
    if "zcta" in z.columns:
        z["zcta"] = z["zcta"].apply(as_5)
    return z

df         = load_scores(CSV_SCORES)
hud_cross  = load_hud_zip_county(HUD_ZIP_CNTY)
zip_to_zct = load_zip_zcta(ZIP_ZCTA)

# --- map ---
st.title("Food Access Vulnerability")

fig = px.choropleth(
    df,
    locations="fips_code",
    geojson="https://raw.githubusercontent.com/plotly/datasets/master/geojson-counties-fips.json",
    color="Score",
    color_continuous_scale="RdYlBu_r",
    scope="usa",
    hover_name="County_Name",
    hover_data={"State": True, "Score": True, "Label": True},
)
fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
st.plotly_chart(fig, use_container_width=True)

# --- user inputs (ZIP or ZCTA). If both provided, ZIP takes precedence ---
with st.container(border=True):
    st.subheader("Lookup by ZIP or ZCTA")
    zip_input  = st.text_input("Enter 5-digit ZIP", value=st.session_state.get("selected_zip", ""))
    zcta_input = st.text_input("Enter 5-digit ZCTA (optional)", value=st.session_state.get("selected_zcta", ""))

# keep session in sync so subsequent interactions can reuse
if zip_input:
    st.session_state["selected_zip"] = zip_input
if zcta_input:
    st.session_state["selected_zcta"] = zcta_input

zip_clean  = as_5(zip_input) if zip_input else None
zcta_clean = as_5(zcta_input) if zcta_input else None

# also allow map click
selected_fips_click = st.session_state.get("last_clicked")

# --- derive flags and a candidate county_fips to display ---
county_not_in_sample = False
zcta_not_found = False
zip_not_found = False
resolved_county_fips = None
resolution_note = None  # tell the user how we resolved ambiguity

def resolve_county_from_zip(zip5: str):
    """Resolve county FIPS from ZIP using HUD. Prefer highest residential ratio, else most frequent."""
    if not zip5 or "zip" not in hud_cross.columns:
        return None, None
    sub = hud_cross[hud_cross["zip"] == zip5].copy()
    if sub.empty:
        return None, None
    if "county_fips" not in sub.columns:
        return None, None

    if "res_ratio" in sub.columns and sub["res_ratio"].notna().any():
        sub = sub.sort_values(["res_ratio", "county_fips"], ascending=[False, True])
        note = "Resolved by highest residential ratio in HUD ZIP–County crosswalk."
        return sub.iloc[0]["county_fips"], note

    # fallback: most frequent county for that ZIP
    counts = sub["county_fips"].value_counts()
    top = counts.index[0]
    note = "Resolved by most frequent county in HUD ZIP–County crosswalk (no residential ratio available)."
    return top, note

def resolve_zcta_from_zip(zip5: str):
    """Resolve ZCTA from ZIP using ZIP–ZCTA table. Returns the most common mapping if multiple."""
    if not zip5 or {"zip", "zcta"}.issubset(zip_to_zct.columns) is False:
        return None
    sub = zip_to_zct[zip_to_zct["zip"] == zip5]
    if sub.empty:
        return None
    # If multiple ZCTAs for a ZIP, take the mode
    zcta_mode = sub["zcta"].mode(dropna=True)
    return zcta_mode.iloc[0] if not zcta_mode.empty else None

# Priority: ZIP input > ZCTA input > map click
if zip_clean:
    # 1) ZIP -> ZCTA (for messaging), 2) ZIP -> County FIPS -> df
    zcta_guess = resolve_zcta_from_zip(zip_clean)
    if zcta_guess is None:
        zip_not_found = True
    resolved_county_fips, resolution_note = resolve_county_from_zip(zip_clean)
    if resolved_county_fips:
        county_not_in_sample = df.loc[df["fips_code"] == resolved_county_fips].empty
else:
    if zcta_clean:
        # ZCTA provided directly; try to find counties that contain that ZCTA via HUD by first mapping ZIPs -> counties
        # Step A: ZIPs that map to this ZCTA
        if {"zip", "zcta"}.issubset(zip_to_zct.columns):
            z_zips = zip_to_zct.loc[zip_to_zct["zcta"] == zcta_clean, "zip"].dropna().unique().tolist()
        else:
            z_zips = []
        if not z_zips:
            zcta_not_found = True
        else:
            # Step B: resolve a county from those ZIPs. Prefer the county that appears most after ZIP->county resolution.
            resolved = []
            for z in z_zips:
                cfips, _ = resolve_county_from_zip(z)
                if cfips:
                    resolved.append(cfips)
            if resolved:
                # choose the mode county across ZIPs
                resolved_county_fips = pd.Series(resolved).mode().iloc[0]
                resolution_note = "Resolved by ZIPs linked to the provided ZCTA using HUD ZIP–County crosswalk."
                county_not_in_sample = df.loc[df["fips_code"] == resolved_county_fips].empty
            else:
                zcta_not_found = True
    else:
        # no manual input; fall back to map click if present
        if selected_fips_click:
            resolved_county_fips = as_5(selected_fips_click)
            county_not_in_sample = df.loc[df["fips_code"] == resolved_county_fips].empty

# --- details panel with proper control flow ---
if resolved_county_fips and not county_not_in_sample:
    row = df.loc[df["fips_code"] == resolved_county_fips].iloc[0]

    st.subheader(f"{row['County_Name']}, {row['State']} ({resolved_county_fips})")
    if resolution_note:
        st.caption(resolution_note)

    st.write(f"**Score:** {row['Score']} | **Label:** {row['Label']}")
    st.write(f"**Median Income:** ${row['MedianIncome']:,.0f}")
    st.write(f"**% Zero-Vehicle HH:** {row['PctZeroVehicleHH']:.1f}")
    st.write(f"**Adjusted Supermarket Density:** {row['aden_supermarkets']:.2f}")
    st.write(f"**% No Internet:** {row['PctNoInternet']:.1f}")

elif county_not_in_sample:
    st.warning("County not in our sample.")
elif zcta_not_found:
    st.warning("ZCTA not found in county cross-walk.")
elif zip_not_found:
    st.warning("ZIP not found in ZCTA table.")
else:
    st.info("Enter a ZIP or ZCTA, or click a county on the map to view details.")
