# doctor_portal.py
import streamlit as st
from patient_db import load_all, search, find_by_id
from utils import timestamp_now

DOCTOR_CREDENTIALS = {
    "general": {"username": "general_doc", "password": "general123"},
    "cardiologist": {"username": "cardio_doc", "password": "cardio123"},
    "orthologist": {"username": "ortho_doc", "password": "ortho123"},
    "pulmonologist": {"username": "pulmo_doc", "password": "pulmo123"},
}


if "doctor_logged_in" not in st.session_state:
    st.session_state.doctor_logged_in=False
if "doctor_specialization" not in st.session_state:
    st.session_state.doctor_specialization=None

st.set_page_config(page_title="Doctor Portal", layout="wide")
st.title("🏥 Doctor Portal")

with st.sidebar:
    st.header("Login")
    if not st.session_state.doctor_logged_in:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            for spec,creds in DOCTOR_CREDENTIALS.items():
                if creds["username"]==username and creds["password"]==password:
                    st.session_state.doctor_logged_in=True
                    st.session_state.doctor_specialization=spec
                    st.experimental_rerun()
            st.error("Invalid credentials.")
    else:
        st.success(f"Logged in as {st.session_state.doctor_specialization}")

if st.session_state.doctor_logged_in:
    st.subheader(f"Records - {st.session_state.doctor_specialization}")
    q = st.text_input("Search (name / id / disease)")
    if q:
        results = search(q, specialization=st.session_state.doctor_specialization)
    else:
        results = [r for r in load_all() if r.get("specialization","General").lower()==st.session_state.doctor_specialization.lower()]
    if results:
        import pandas as pd
        st.dataframe(pd.DataFrame(results), use_container_width=True)
        sel = st.selectbox("Open record", options=[r["id"] for r in results], format_func=lambda v: v)
        if sel:
            rec = find_by_id(sel)
            st.json(rec)
    else:
        st.info("No records found.")
