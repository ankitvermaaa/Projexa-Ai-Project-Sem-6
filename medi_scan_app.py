import os
import json
import random
import re
import pandas as pd
import streamlit as st
from PIL import Image, ImageDraw

# NEW: Import dotenv to read .env file
try:
    from dotenv import load_dotenv
    load_dotenv() # Load variables from .env into environment
except ImportError:
    pass # python-dotenv might not be installed

# --- Custom Module Imports ---
from patient_db import (
    make_patient_entry, add_record, load_all, 
    find_by_id, search, update_record, delete_record
)
from pdf_gen import create_medical_pdf
from utils import sanitize_text, timestamp_now, simulate_progress_bar

# --- Configuration ---
st.set_page_config(
    page_title="MediScan AI", 
    page_icon="🩺", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# You can change this string to "gemini-2.0-flash-exp" or "gemini-3.0-flash" as they become available
GEMINI_MODEL_VERSION = "gemini-2.5-flash-lite"

# --- Gemini Setup ---
GEMINI_AVAILABLE = False
GEMINI_MODEL = None

try:
    import google.generativeai as genai
    # Attempt to get key from environment, but don't crash if missing
    API_KEY = os.getenv("GEMINI_API_KEY") 
    if API_KEY:
        genai.configure(api_key=API_KEY)
        GEMINI_MODEL = genai.GenerativeModel(GEMINI_MODEL_VERSION)
        GEMINI_AVAILABLE = True
except ImportError:
    pass

# --- Constants & Mappings ---
ORGAN_SPECIALIZATION_MAP = {
    # Cardiovascular
    "heart": "cardiologist",

    # Respiratory
    "lungs": "pulmonologist",
    "lung": "pulmonologist",
    "chest": "pulmonologist",

    # Bones & Joints (Orthopedic)
    "bone": "orthopedist",
    "hand": "orthopedist",
    "wrist": "orthopedist",
    "forearm": "orthopedist",
    "elbow": "orthopedist",
    "shoulder": "orthopedist",
    "knee": "orthopedist",
    "leg": "orthopedist",
    "ankle": "orthopedist",
    "foot": "orthopedist",
    "spine": "orthopedist",
    "ribs": "orthopedist",

    # Neurological
    "brain": "neurologist",
    "skull": "neurologist",
    "head": "neurologist",
    "nerves": "neurologist",
    "cancer": "oncologist",

    # Gastrointestinal
    "stomach": "gastroenterologist",
    "abdomen": "gastroenterologist",
    "liver": "hepatologist",
    "intestine": "gastroenterologist",

    # ENT
    "ear": "ent specialist",
    "nose": "ent specialist",
    "throat": "ent specialist",
    "sinus": "ent specialist",

    # Eyes
    "eye": "ophthalmologist",
    "vision": "ophthalmologist",

    # Skin
    "skin": "dermatologist",
    "hair": "dermatologist",
    "nails": "dermatologist",
    "rashes": "dermatologist",

    # Urinary & Kidneys
    "kidney": "nephrologist",
    "urine": "urologist",
    "bladder": "urologist",

    # Reproductive
    "ovary": "gynecologist",
    "uterus": "gynecologist",
    "testicles": "urologist",
    "prostate": "urologist"
}


DOCTOR_CREDENTIALS = {
    "general": {"u": "doc", "p": "123"}, # Simplified for demo
    "cardiologist": {"u": "cardio", "p": "123"},
    "orthopedist": {"u": "ortho", "p": "123"},
    "pulmonologist": {"u": "pulmo", "p": "123"},
    "neurologist": {"u": "neuro", "p": "123"},
    "gastroenterologist": {"u": "gastro", "p": "123"},
    "hepatologist": {"u": "hepato", "p": "123"},
    "ent specialist": {"u": "entdoc", "p": "123"},
    "ophthalmologist": {"u": "ophtha", "p": "123"},
    "dermatologist": {"u": "derma", "p": "123"},
    "nephrologist": {"u": "nephro", "p": "123"},
    "urologist": {"u": "uro", "p": "123"},
    "gynecologist": {"u": "gyno", "p": "123"},
    "oncologist": {"u": "onco", "p": "123"},
}

# --- CSS Styling (Glassmorphism & Dark Navy) ---
CSS = """
<style>
    /* Main Background */
    .stApp {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
        color: #e2e8f0;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #0B1120;
        border-right: 1px solid #1e293b;
    }

    /* Card Containers */
    .metric-card {
        background-color: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        backdrop-filter: blur(10px);
        transition: transform 0.2s;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #3b82f6;
    }
    
    /* Typography */
    h1, h2, h3 { color: #f8fafc !important; }
    .big-stat { font-size: 28px; font-weight: 800; color: #3b82f6; }
    .label-stat { font-size: 13px; text-transform: uppercase; color: #94a3b8; letter-spacing: 1px; }

    /* Custom Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #3b82f6 0%, #2563eb 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        box-shadow: 0 4px 12px rgba(59, 130, 246, 0.5);
    }
    
    /* Upload Box */
    .stFileUploader {
        background-color: rgba(30, 41, 59, 0.4);
        border-radius: 10px;
        padding: 20px;
        border: 2px dashed #334155;
    }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# --- Session State Initialization ---
if "patient_counter" not in st.session_state:
    # Get the highest patient ID from existing records
    existing_records = load_all()
    if existing_records:
        max_id = 0
        for rec in existing_records:
            pid = rec.get('id', 'PID-0')
            try:
                num = int(pid.split('-')[1])
                max_id = max(max_id, num)
            except:
                pass
        st.session_state.patient_counter = max_id + 1
    else:
        st.session_state.patient_counter = 1000
if "report_id" not in st.session_state:
    st.session_state.report_id = f"PID-{st.session_state.patient_counter}"
if "last_uploaded_file" not in st.session_state:
    st.session_state.last_uploaded_file = None
if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None
if "deep_eval_result" not in st.session_state:
    st.session_state.deep_eval_result = None
if "doctor_logged_in" not in st.session_state:
    st.session_state.doctor_logged_in = False
if "doctor_specialization" not in st.session_state:
    st.session_state.doctor_specialization = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- SIDEBAR (Navigation & Context) ---
with st.sidebar:
    st.markdown("## 🩺 MediScan AI")
    st.caption("Advanced Diagnostic Imaging")
    st.divider()

    st.markdown("### Patient Context")
    p_name = st.text_input("Name", value="Rahul Kumar")
    c1, c2 = st.columns(2)
    p_age = c1.number_input("Age", 0, 120, 27)
    p_sex = c2.selectbox("Sex", ["Male", "Female", "Other"])
    
    st.divider()
    
    st.info(f"**Current Session:** {st.session_state.report_id}")
    
    if st.button("New Patient Session", use_container_width=True):
        st.session_state.patient_counter += 1
        st.session_state.report_id = f"PID-{st.session_state.patient_counter}"
        st.session_state.analysis_result = None
        st.session_state.deep_eval_result = None
        st.session_state.chat_history = []
        st.session_state.last_uploaded_file = None
        st.rerun()

    st.markdown("---")
    st.caption(f"System Status: {'🟢 Online' if GEMINI_AVAILABLE else '🟠 Offline (Simulation Mode)'}")

# --- MAIN CONTENT ---

# 1. Top Metrics Bar
m1, m2, m3, m4 = st.columns(4)

# Calculate Risk safely
risk_val = "N/A"
if st.session_state.deep_eval_result:
    m = re.search(r"Risk_Percentage[:\s]*([0-9]{1,3})", st.session_state.deep_eval_result)
    risk_val = f"{m.group(1)}%" if m else "Low"

organ_val = st.session_state.analysis_result.get("organ", "Scan Required").capitalize() if st.session_state.analysis_result else "--"
findings_val = len(st.session_state.analysis_result.get("findings", [])) if st.session_state.analysis_result else 0

def metric_card(col, label, value):
    col.markdown(f"""
    <div class="metric-card">
        <div class="label-stat">{label}</div>
        <div class="big-stat">{value}</div>
    </div>
    """, unsafe_allow_html=True)

metric_card(m1, "Patient ID", st.session_state.report_id)
metric_card(m2, "Target Organ", organ_val)
metric_card(m3, "Anomalies", findings_val)
metric_card(m4, "AI Risk Score", risk_val)

st.write("") # Spacer

# 2. Tabs for Workflow
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🔍 Visual Scan", "📄 Clinical Report", "🤖 Doctor AI", "👨‍⚕️ Doctor Portal", "📊 Analytics"
])

# --- TAB 1: VISUAL SCAN ---
with tab1:
    col_upload, col_preview = st.columns([1, 2])
    
    with col_upload:
        st.subheader("Upload Imaging")
        uploaded_file = st.file_uploader("Drop X-Ray/MRI here", type=["jpg", "png", "jpeg"])
        
        if uploaded_file:
            if uploaded_file.name != st.session_state.last_uploaded_file:
                st.session_state.last_uploaded_file = uploaded_file.name
                # Reset analysis on new file
                st.session_state.analysis_result = None 
                st.session_state.deep_eval_result = None
            
            if st.button("🚀 Run Diagnostic Scan", use_container_width=True):
                with st.status("Initializing MediScan Engine...", expanded=True) as status:
                    st.write("Preprocessing image...")
                    pil_img = Image.open(uploaded_file).convert("RGB")
                    
                    st.write("Analyzing patterns...")
                    simulate_progress_bar(st, "Scanning pixels...", speed=0.02)
                    
                    # --- AI LOGIC OR MOCK FALLBACK ---
                    if GEMINI_AVAILABLE and GEMINI_MODEL:
                        try:
                            prompt = """
                            Analyze this medical image. Return JSON ONLY:
                            {"organ":"Name","findings":[{"condition":"Name","severity":"Low/Med/High","box":[ymin,xmin,ymax,xmax]}]}
                            Coordinates 0-1000 scale.
                            """
                            resp = GEMINI_MODEL.generate_content([prompt, pil_img])
                            txt = sanitize_text(resp.text)
                            res = json.loads(txt)
                        except Exception as e:
                            st.error(f"AI Error: {e}")
                            res = None
                    else:
                        # Simulation fallback
                        res = {
                            "organ": "Lungs", 
                            "findings": [
                                {"condition": "Opacification", "severity": "High", "box": [200, 300, 600, 700]}
                            ]
                        }
                    
                    st.session_state.analysis_result = res
                    status.update(label="Scan Complete", state="complete", expanded=False)
    
    with col_preview:
        if uploaded_file:
            pil_img = Image.open(uploaded_file).convert("RGB")
            
            # If we have results, draw boxes
            if st.session_state.analysis_result:
                # Create a copy for annotation
                annotated_img = pil_img.copy()
                draw = ImageDraw.Draw(annotated_img)
                w, h = annotated_img.size
                
                for f in st.session_state.analysis_result.get("findings", []):
                    if "box" in f:
                        ymin, xmin, ymax, xmax = f["box"]
                        # Scale 1000 to image size
                        box = [(xmin/1000)*w, (ymin/1000)*h, (xmax/1000)*w, (ymax/1000)*h]
                        draw.rectangle(box, outline="#ef4444", width=5)
                
                # Save annotated image for PDF
                annotated_img.save("temp_scan.jpg")
                st.image(annotated_img, caption="AI Annotated Analysis", use_container_width=True)
            else:
                # Save original for PDF if no analysis yet
                pil_img.save("temp_scan.jpg")
                st.image(pil_img, caption="Original Source", use_container_width=True)
        else:
            st.info("Awaiting Image Upload")

# --- TAB 2: CLINICAL REPORT ---
with tab2:
    if not st.session_state.analysis_result:
        st.warning("Please complete a Visual Scan first.")
    else:
        r_col1, r_col2 = st.columns([2, 1])
        
        with r_col1:
            st.subheader("Deep Clinical Analysis")
            
            if not st.session_state.deep_eval_result:
                if st.button("⚡ Generate Clinical Narrative"):
                    with st.spinner("Synthesizing medical literature..."):
                        if GEMINI_AVAILABLE and GEMINI_MODEL:
                            try:
                                # Real AI Call with detailed medical analysis prompt
                                organ = st.session_state.analysis_result.get('organ', 'Unknown')
                                findings = st.session_state.analysis_result.get('findings', [])
                                findings_text = ", ".join([f"{f.get('condition')} ({f.get('severity')} severity)" for f in findings])
                                
                                prompt = f"""You are a medical AI assistant. Analyze this diagnostic scan and provide a detailed clinical report.

Scan Details:
- Target Organ: {organ}
- Detected Conditions: {findings_text}

Provide a structured clinical analysis with the following sections:
1. Observation: Detailed description of what is seen in the scan
2. Severity: Assessment of the condition severity (Low/Medium/High)
3. Recommendation: Specific medical recommendations and next steps
4. Risk_Percentage: Estimated risk percentage (0-100)

Format your response with clear section headers."""
                                
                                resp = GEMINI_MODEL.generate_content(prompt)
                                st.session_state.deep_eval_result = resp.text
                            except Exception as e:
                                st.error(f"AI Error: {e}")
                                # Fallback to mock
                                st.session_state.deep_eval_result = """
**Observation:** The scan demonstrates a localized region of increased density in the lower lobe, suggestive of consolidation.

**Severity:** Moderate to High. Requires clinical correlation.

**Recommendation:**
- Complete blood count (CBC)
- Sputum culture
- Pulmonology consultation

**Risk_Percentage:** 78%
                                """
                        else:
                            # Mock
                            simulate_progress_bar(st, "Thinking...", speed=0.03)
                            st.session_state.deep_eval_result = """
**Observation:** The scan demonstrates a localized region of increased density in the lower lobe, suggestive of consolidation.

**Severity:** Moderate to High. Requires clinical correlation.

**Recommendation:**
- Complete blood count (CBC)
- Sputum culture
- Pulmonology consultation

**Risk_Percentage:** 78%
                            """
                        st.rerun()
            
            if st.session_state.deep_eval_result:
                st.markdown(st.session_state.deep_eval_result)
        
        with r_col2:
            st.subheader("Actions")
            with st.container(border=True):
                st.markdown("**Save to Registry**")
                
                # Auto-detect specialization based on organ
                detected_organ = st.session_state.analysis_result.get("organ", "").lower()
                auto_spec = ORGAN_SPECIALIZATION_MAP.get(detected_organ, "general")
                
                st.success(f"🎯 Auto-assigned Department: **{auto_spec.capitalize()}**")
                st.caption(f"Based on detected organ: {detected_organ.capitalize() if detected_organ else 'Unknown'}")
                
                if st.button("💾 Save Record", use_container_width=True):
                    # Safely handle empty findings list
                    findings_list = st.session_state.analysis_result.get("findings", [])
                    disease = findings_list[0].get("condition", "Unknown") if findings_list else "Unknown"
                    
                    # Use auto-assigned specialization
                    rec = make_patient_entry(p_name, p_age, p_sex, st.session_state.report_id, disease, auto_spec)
                    add_record(rec)
                    
                    # Increment patient counter for next patient
                    st.session_state.patient_counter += 1
                    
                    st.toast(f"✅ Record {rec['id']} saved to {auto_spec.upper()} department!", icon="✅")
                    st.balloons()

            st.write("")
            if os.path.exists("temp_scan.jpg"):
                pdf_data = create_medical_pdf(
                    {"name": p_name, "age": p_age, "sex": p_sex, "id": st.session_state.report_id, "date": timestamp_now()},
                    st.session_state.analysis_result,
                    st.session_state.deep_eval_result,
                    image_path="temp_scan.jpg"
                )
                st.download_button(
                    label="📄 Download PDF Report",
                    data=pdf_data,
                    file_name=f"Report_{st.session_state.report_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

# --- TAB 3: DOCTOR AI ASSISTANT ---
with tab3:
    st.subheader("AI Consultant")
    
    # Render chat history
    for msg in st.session_state.chat_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about the diagnosis, treatment plan, or differential..."):
        # User message
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # AI Response
        with st.chat_message("assistant"):
            with st.spinner("Consulting medical database..."):
                response_text = "I recommend further testing to confirm the diagnosis." # Default
                
                if GEMINI_AVAILABLE and GEMINI_MODEL and st.session_state.deep_eval_result:
                    try:
                        ctx = f"Context: {st.session_state.deep_eval_result}\nUser: {prompt}"
                        resp = GEMINI_MODEL.generate_content(ctx)
                        response_text = resp.text
                    except:
                        pass
                
                st.markdown(response_text)
                st.session_state.chat_history.append({"role": "assistant", "content": response_text})

# --- TAB 4: DOCTOR PORTAL ---
with tab4:
    if not st.session_state.doctor_logged_in:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("### 👨‍⚕️ Doctor Portal Login")
            st.caption("Login with your department credentials")
            
            with st.form("login"):
                dept_choice = st.selectbox(
                    "Department",
                    options=list(DOCTOR_CREDENTIALS.keys()),
                    format_func=lambda x: x.capitalize()
                )
                u = st.text_input("Username", placeholder=f"Try: {DOCTOR_CREDENTIALS[dept_choice]['u']}")
                p = st.text_input("Password", type="password", placeholder="Try: 123")
                
                if st.form_submit_button("🔐 Access Portal", use_container_width=True):
                    # Check credentials for selected department
                    if (u == DOCTOR_CREDENTIALS[dept_choice]['u'] and p == DOCTOR_CREDENTIALS[dept_choice]['p']):
                        st.session_state.doctor_logged_in = True
                        st.session_state.doctor_specialization = dept_choice
                        st.rerun()
                    else:
                        st.error("❌ Invalid credentials for this department")
            
            # Show credentials hint
            with st.expander("💡 Demo Credentials"):
                for dept, creds in DOCTOR_CREDENTIALS.items():
                    st.caption(f"**{dept.capitalize()}**: {creds['u']} / {creds['p']}")
    
    else:
        # Doctor is logged in
        col_header1, col_header2 = st.columns([3, 1])
        with col_header1:
            st.success(f"👨‍⚕️ Welcome, Dr. {st.session_state.doctor_specialization.capitalize()}")
            st.caption(f"Department: {st.session_state.doctor_specialization.upper()}")
        with col_header2:
            if st.button("🚪 Logout", use_container_width=True):
                st.session_state.doctor_logged_in = False
                st.session_state.doctor_specialization = None
                st.rerun()
        
        st.divider()
        
        # Load records for this department only
        all_records = load_all()
        dept_records = [r for r in all_records if r.get('specialization', '').lower() == st.session_state.doctor_specialization.lower()]
        
        if dept_records:
            # Summary metrics for department
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            with metric_col1:
                st.metric("Total Patients", len(dept_records))
            with metric_col2:
                pending_count = sum(1 for r in dept_records if r.get('status') == 'Pending Review')
                st.metric("Pending Reviews", pending_count)
            with metric_col3:
                reviewed_count = sum(1 for r in dept_records if r.get('status') == 'Reviewed')
                st.metric("Reviewed", reviewed_count)
            
            st.divider()
            
            # Patient list and editing
            st.markdown("### 📋 Patient Records")
            
            # Initialize edit mode in session state
            if "editing_patient" not in st.session_state:
                st.session_state.editing_patient = None
            
            # Display each patient record
            for idx, record in enumerate(dept_records):
                with st.expander(f"🏥 {record['id']} - {record['name']} ({record['disease']})", expanded=(st.session_state.editing_patient == record['id'])):
                    
                    # Display mode vs Edit mode
                    edit_col, action_col = st.columns([3, 1])
                    
                    with action_col:
                        if st.session_state.editing_patient == record['id']:
                            if st.button("❌ Cancel", key=f"cancel_{idx}", use_container_width=True):
                                st.session_state.editing_patient = None
                                st.rerun()
                        else:
                            if st.button("✏️ Edit", key=f"edit_{idx}", use_container_width=True):
                                st.session_state.editing_patient = record['id']
                                st.rerun()
                    
                    with edit_col:
                        if st.session_state.editing_patient == record['id']:
                            # EDIT MODE
                            st.markdown("**Edit Patient Information**")
                            
                            with st.form(key=f"form_{idx}"):
                                form_col1, form_col2 = st.columns(2)
                                
                                with form_col1:
                                    new_name = st.text_input("Name", value=record['name'], key=f"name_{idx}")
                                    new_age = st.number_input("Age", min_value=0, max_value=120, value=record['age'], key=f"age_{idx}")
                                    new_sex = st.selectbox("Sex", ["Male", "Female", "Other"], 
                                                          index=["Male", "Female", "Other"].index(record['sex']) if record['sex'] in ["Male", "Female", "Other"] else 0,
                                                          key=f"sex_{idx}")
                                
                                with form_col2:
                                    # Read-only fields
                                    st.text_input("Patient ID (Read-only)", value=record['id'], disabled=True, key=f"pid_{idx}")
                                    st.text_input("Disease (Read-only)", value=record['disease'], disabled=True, key=f"disease_{idx}")
                                    st.text_input("Department (Read-only)", value=record['specialization'], disabled=True, key=f"spec_{idx}")
                                
                                st.text_input("Date (Read-only)", value=record['date'], disabled=True, key=f"date_{idx}")
                                
                                # Status update
                                current_status = record.get('status', 'Pending Review')
                                new_status = st.selectbox(
                                    "Review Status",
                                    ["Pending Review", "Reviewed", "Discharged"],
                                    index=["Pending Review", "Reviewed", "Discharged"].index(current_status) if current_status in ["Pending Review", "Reviewed", "Discharged"] else 0,
                                    key=f"status_{idx}"
                                )
                                
                                # Submit button
                                submit_col1, submit_col2 = st.columns([1, 1])
                                with submit_col1:
                                    if st.form_submit_button("💾 Save Changes", use_container_width=True):
                                        # Update the record
                                        updates = {
                                            'name': new_name,
                                            'age': new_age,
                                            'sex': new_sex,
                                            'status': new_status
                                        }
                                        
                                        if update_record(record['id'], updates):
                                            st.success("✅ Patient record updated successfully!")
                                            st.session_state.editing_patient = None
                                            st.rerun()
                                        else:
                                            st.error("❌ Failed to update record")
                        
                        else:
                            # DISPLAY MODE
                            info_col1, info_col2 = st.columns(2)
                            
                            with info_col1:
                                st.markdown(f"**Patient ID:** {record['id']}")
                                st.markdown(f"**Name:** {record['name']}")
                                st.markdown(f"**Age:** {record['age']} years")
                                st.markdown(f"**Sex:** {record['sex']}")
                            
                            with info_col2:
                                st.markdown(f"**Disease:** {record['disease']}")
                                st.markdown(f"**Department:** {record['specialization'].capitalize()}")
                                st.markdown(f"**Date:** {record['date']}")
                                
                                # Status badge with color
                                status = record.get('status', 'Pending Review')
                                if status == 'Reviewed':
                                    st.success(f"✅ Status: {status}")
                                elif status == 'Discharged':
                                    st.info(f"🏠 Status: {status}")
                                else:
                                    st.warning(f"⏳ Status: {status}")
        
        else:
            st.info(f"📋 No patients found in {st.session_state.doctor_specialization.capitalize()} department.")
            st.caption("Patients will appear here once they are assigned to your department.")

# --- TAB 5: ANALYTICS ---
with tab5:
    st.subheader("📊 Medical Analytics Dashboard")
    records = load_all()
    
    if records:
        df = pd.DataFrame(records)
        
        # === TOP METRICS ROW ===
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Total Patients", len(df))
        with col2:
            st.metric("Departments", df['specialization'].nunique())
        with col3:
            avg_age = int(df['age'].mean()) if 'age' in df.columns else 0
            st.metric("Avg Age", f"{avg_age} yrs")
        with col4:
            pending = len(df[df.get('status', 'Pending Review') == 'Pending Review']) if 'status' in df.columns else 0
            st.metric("Pending Reviews", pending)
        with col5:
            unique_diseases = df['disease'].nunique() if 'disease' in df.columns else 0
            st.metric("Unique Conditions", unique_diseases)
        
        st.divider()
        
        # === DEPARTMENT ANALYSIS ===
        st.markdown("### 🏥 Department Analysis")
        dept_col1, dept_col2 = st.columns(2)
        
        with dept_col1:
            st.markdown("**Patient Distribution by Department**")
            dept_counts = df['specialization'].value_counts()
            st.bar_chart(dept_counts)
            
            # Department workload table
            st.markdown("**Department Workload**")
            dept_summary = df.groupby('specialization').agg({
                'id': 'count',
                'age': 'mean'
            }).round(1)
            dept_summary.columns = ['Patient Count', 'Avg Age']
            st.dataframe(dept_summary, use_container_width=True)
        
        with dept_col2:
            st.markdown("**Gender Distribution by Department**")
            if 'sex' in df.columns:
                gender_dept = pd.crosstab(df['specialization'], df['sex'])
                st.bar_chart(gender_dept)
            else:
                st.info("Gender data not available")
            
            st.markdown("**Status Overview**")
            if 'status' in df.columns:
                status_counts = df['status'].value_counts()
                st.bar_chart(status_counts)
            else:
                st.info("Status data not available")
        
        st.divider()
        
        # === DISEASE ANALYSIS ===
        st.markdown("### 🔬 Disease & Condition Analysis")
        disease_col1, disease_col2 = st.columns(2)
        
        with disease_col1:
            st.markdown("**Top 10 Most Common Conditions**")
            if 'disease' in df.columns:
                disease_counts = df['disease'].value_counts().head(10)
                st.bar_chart(disease_counts)
                
                # Disease by department
                st.markdown("**Conditions by Department**")
                disease_dept = df.groupby('specialization')['disease'].value_counts().head(15)
                st.dataframe(disease_dept.reset_index(name='Count'), use_container_width=True, hide_index=True)
        
        with disease_col2:
            st.markdown("**Disease Severity Distribution**")
            # Simulate severity based on keywords (in real app, this would come from analysis)
            severity_keywords = {
                'High': ['fracture', 'opacity', 'infiltration', 'pneumonia', 'tumor'],
                'Medium': ['congestion', 'inflammation', 'infection'],
                'Low': ['minor', 'slight', 'mild']
            }
            
            severity_counts = {'High': 0, 'Medium': 0, 'Low': 0}
            for disease in df['disease']:
                disease_lower = str(disease).lower()
                classified = False
                for severity, keywords in severity_keywords.items():
                    if any(keyword in disease_lower for keyword in keywords):
                        severity_counts[severity] += 1
                        classified = True
                        break
                if not classified:
                    severity_counts['Medium'] += 1
            
            severity_df = pd.DataFrame.from_dict(severity_counts, orient='index', columns=['Count'])
            st.bar_chart(severity_df)
            
            st.markdown("**Recent Critical Cases**")
            critical_keywords = ['high', 'fracture', 'opacity', 'infiltration']
            critical_cases = df[df['disease'].str.lower().str.contains('|'.join(critical_keywords), na=False)]
            if not critical_cases.empty:
                st.dataframe(critical_cases[['id', 'name', 'disease', 'specialization']].head(5), 
                           use_container_width=True, hide_index=True)
            else:
                st.info("No critical cases identified")
        
        st.divider()
        
        # === DEMOGRAPHIC ANALYSIS ===
        st.markdown("### 👥 Demographic Analysis")
        demo_col1, demo_col2, demo_col3 = st.columns(3)
        
        with demo_col1:
            st.markdown("**Age Distribution**")
            st.bar_chart(df['age'].value_counts().sort_index())
            
            # Age groups
            st.markdown("**Age Groups**")
            age_bins = [0, 18, 35, 50, 65, 120]
            age_labels = ['0-18', '19-35', '36-50', '51-65', '65+']
            df['age_group'] = pd.cut(df['age'], bins=age_bins, labels=age_labels, right=False)
            age_group_counts = df['age_group'].value_counts().sort_index()
            st.bar_chart(age_group_counts)
        
        with demo_col2:
            st.markdown("**Gender Distribution**")
            if 'sex' in df.columns:
                gender_counts = df['sex'].value_counts()
                st.bar_chart(gender_counts)
                
                # Gender ratio
                if len(gender_counts) >= 2:
                    male_count = gender_counts.get('Male', 0)
                    female_count = gender_counts.get('Female', 0)
                    st.metric("Male:Female Ratio", f"{male_count}:{female_count}")
            else:
                st.info("Gender data not available")
        
        with demo_col3:
            st.markdown("**Patient Timeline**")
            if 'date' in df.columns:
                # Extract date from datetime string
                df['date_only'] = pd.to_datetime(df['date'], errors='coerce').dt.date
                daily_patients = df['date_only'].value_counts().sort_index()
                st.line_chart(daily_patients)
                
                st.markdown("**Busiest Days**")
                top_days = daily_patients.head(5)
                st.dataframe(top_days.reset_index().rename(columns={'index': 'Date', 'date_only': 'Patients'}), 
                           use_container_width=True, hide_index=True)
        
        st.divider()
        
        # === DETAILED RECORDS TABLE ===
        st.markdown("### 📋 Detailed Patient Records")
        
        # Filters
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            dept_filter = st.selectbox("Filter by Department", ["All"] + list(df['specialization'].unique()))
        with filter_col2:
            if 'status' in df.columns:
                status_filter = st.selectbox("Filter by Status", ["All"] + list(df['status'].unique()))
            else:
                status_filter = "All"
        with filter_col3:
            search_term = st.text_input("Search by Name/ID", "")
        
        # Apply filters
        filtered_df = df.copy()
        if dept_filter != "All":
            filtered_df = filtered_df[filtered_df['specialization'] == dept_filter]
        if status_filter != "All" and 'status' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['status'] == status_filter]
        if search_term:
            filtered_df = filtered_df[
                filtered_df['name'].str.contains(search_term, case=False, na=False) | 
                filtered_df['id'].str.contains(search_term, case=False, na=False)
            ]
        
        st.caption(f"Showing {len(filtered_df)} of {len(df)} records")
        
        # Display table
        display_columns = ['id', 'name', 'age', 'sex', 'disease', 'specialization', 'date']
        if 'status' in filtered_df.columns:
            display_columns.append('status')
        
        st.dataframe(
            filtered_df[display_columns].sort_values('date', ascending=False),
            use_container_width=True,
            hide_index=True,
            column_config={
                "id": "Patient ID",
                "name": "Name",
                "age": "Age",
                "sex": "Gender",
                "disease": "Condition",
                "specialization": "Department",
                "date": "Date",
                "status": "Status"
            }
        )
        
        # Export option
        st.download_button(
            label="📥 Export Data as CSV",
            data=filtered_df.to_csv(index=False).encode('utf-8'),
            file_name=f"mediscan_analytics_{timestamp_now().replace(' ', '_').replace(':', '-')}.csv",
            mime="text/csv",
            use_container_width=True
        )
        
    else:
        st.info("📊 No patient data available yet. Start by scanning and saving patient records.")
        st.caption("Analytics will appear here once you have patient data.")
