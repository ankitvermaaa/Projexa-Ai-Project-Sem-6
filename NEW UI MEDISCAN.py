import os
import json
import re
import streamlit as st
from PIL import Image, ImageDraw

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from patient_db import make_patient_entry, add_record, load_all, update_record
from pdf_gen    import create_medical_pdf
from utils      import sanitize_text, timestamp_now, simulate_progress_bar
from styles     import get_css

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MediScan AI",
    page_icon="🩺",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── GEMINI ────────────────────────────────────────────────────────────────────
GEMINI_MODEL_VERSION = "gemini-2.5-flash-lite"
GEMINI_AVAILABLE     = False
GEMINI_MODEL         = None
try:
    import google.generativeai as genai
    API_KEY = os.getenv("GEMINI_API_KEY")
    if API_KEY:
        genai.configure(api_key=API_KEY)
        GEMINI_MODEL     = genai.GenerativeModel(GEMINI_MODEL_VERSION)
        GEMINI_AVAILABLE = True
except ImportError:
    pass

# ── CONSTANTS ─────────────────────────────────────────────────────────────────
ORGAN_SPEC_MAP = {
    "heart":   "cardiologist",
    "lungs":   "pulmonologist", "lung":  "pulmonologist", "chest": "pulmonologist",
    "bone":    "orthopedist",   "hand":  "orthopedist",   "wrist": "orthopedist",
    "forearm": "orthopedist",   "elbow": "orthopedist",   "shoulder": "orthopedist",
    "knee":    "orthopedist",   "leg":   "orthopedist",   "ankle": "orthopedist",
    "foot":    "orthopedist",   "spine": "orthopedist",   "ribs":  "orthopedist",
    "brain":   "neurologist",   "skull": "neurologist",   "head":  "neurologist",
    "nerves":  "neurologist",   "cancer": "oncologist",
    "stomach": "gastroenterologist", "abdomen":   "gastroenterologist",
    "liver":   "hepatologist",        "intestine": "gastroenterologist",
    "ear":     "ent specialist", "nose":   "ent specialist",
    "throat":  "ent specialist", "sinus":  "ent specialist",
    "eye":     "ophthalmologist", "vision": "ophthalmologist",
    "skin":    "dermatologist",  "hair":   "dermatologist",
    "nails":   "dermatologist",  "rashes": "dermatologist",
    "kidney":  "nephrologist",   "urine":  "urologist", "bladder":   "urologist",
    "ovary":   "gynecologist",   "uterus": "gynecologist",
    "testicles": "urologist",    "prostate": "urologist",
}

DOCTOR_CREDENTIALS = {
    "general":            {"u": "doc",    "p": "123"},
    "cardiologist":       {"u": "cardio", "p": "123"},
    "orthopedist":        {"u": "ortho",  "p": "123"},
    "pulmonologist":      {"u": "pulmo",  "p": "123"},
    "neurologist":        {"u": "neuro",  "p": "123"},
    "gastroenterologist": {"u": "gastro", "p": "123"},
    "hepatologist":       {"u": "hepato", "p": "123"},
    "ent specialist":     {"u": "entdoc", "p": "123"},
    "ophthalmologist":    {"u": "ophtha", "p": "123"},
    "dermatologist":      {"u": "derma",  "p": "123"},
    "nephrologist":       {"u": "nephro", "p": "123"},
    "urologist":          {"u": "uro",    "p": "123"},
    "gynecologist":       {"u": "gyno",   "p": "123"},
    "oncologist":         {"u": "onco",   "p": "123"},
}

# ── SESSION STATE ─────────────────────────────────────────────────────────────
def init_state():
    existing = load_all()
    max_id   = 9906
    for rec in existing:
        try:
            max_id = max(max_id, int(rec.get("id","PID-0").split("-")[1]))
        except:
            pass

    defaults = {
        "patient_counter":    max_id + 1,
        "last_uploaded_file": None,
        "analysis_result":    None,
        "deep_eval_result":   None,
        "doctor_logged_in":   False,
        "doctor_spec":        None,
        "chat_history":       [],
        "editing_patient":    None,
        "chat_open":          False,
        "p_name":             "Rahul Kumar",
        "p_age":              27,
        "p_sex":              "Male",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    if "report_id" not in st.session_state:
        st.session_state.report_id = f"PID-{st.session_state.patient_counter}"

init_state()

# ── INJECT CSS ────────────────────────────────────────────────────────────────
st.markdown(get_css(), unsafe_allow_html=True)

# ── LIVE STATS ────────────────────────────────────────────────────────────────
all_recs = load_all()
pending  = sum(1 for r in all_recs if r.get("status") == "Pending Review")
dot_cls  = "sg" if GEMINI_AVAILABLE else "sa"
dot_txt  = "Gemini Active" if GEMINI_AVAILABLE else "Simulation Mode"

# ══════════════════════════════════════════════════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("""
    <div class="ms-sb-logo">Medi<span>Scan</span></div>
    <div class="ms-sb-tagline">AI Medical Imaging Platform</div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="ms-sb-sec">Navigation</div>', unsafe_allow_html=True)

    nav = [
        ("🏠", "Home",          "#ms-hero"),
        ("👤", "Patient Info",  "#ms-patient"),
        ("🔬", "Visual Scan",   "#ms-scan"),
        ("📄", "Clinical Report","#ms-report"),
        ("👨‍⚕️", "Doctor Portal", "#ms-doctor"),
        ("📊", "Analytics",     "#ms-analytics"),
    ]
    for ico, label, href in nav:
        st.markdown(
            f'<a href="{href}" class="ms-sb-link"><span class="ico">{ico}</span>{label}</a>',
            unsafe_allow_html=True
        )

    st.markdown('<hr class="ms-sb-divider">', unsafe_allow_html=True)
    st.markdown('<div class="ms-sb-sec">Current Session</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div style="padding:4px 20px 12px;">
        <div style="font-size:9px;letter-spacing:2px;color:#1E4060;text-transform:uppercase;margin-bottom:2px;">Active ID</div>
        <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:700;color:#00E5FF;">
            {st.session_state.report_id}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("＋  New Session", use_container_width=True, key="sb_new_session"):
        st.session_state.patient_counter    += 1
        st.session_state.report_id          = f"PID-{st.session_state.patient_counter}"
        st.session_state.analysis_result    = None
        st.session_state.deep_eval_result   = None
        st.session_state.chat_history       = []
        st.session_state.last_uploaded_file = None
        st.rerun()

    st.markdown('<hr class="ms-sb-divider">', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="ms-sb-status">
        <span class="ms-sdot {dot_cls}"></span>{dot_txt}
    </div>
    <div style="padding:2px 20px 18px;font-size:11px;color:#1A3040;">
        {len(all_recs)} records &nbsp;·&nbsp;
        <span style="color:#FBBF24;">{pending} pending</span>
    </div>
    """, unsafe_allow_html=True)

# ── TOP BAR ────────────────────────────────────────────────────────────────────
st.markdown(f"""
<div class="ms-topbar">
    <div class="ms-logo">Medi<span>Scan</span>
        <span style="font-size:11px;font-weight:400;color:#1E4060;margin-left:8px;letter-spacing:0;">AI</span>
    </div>
    <div class="ms-topbar-right">
        <span class="ms-sdot {dot_cls}"></span>{dot_txt}
        &nbsp;·&nbsp; {len(all_recs)} records
        &nbsp;·&nbsp; <span style="color:#FBBF24;">{pending} pending</span>
    </div>
</div>
<div style="height:54px;"></div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  §1  HERO
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div id="ms-hero" class="ms-hero">
    <div class="ms-hero-grid"></div>
    <div class="ms-hero-glow"></div>
    <div class="ms-scanline"></div>
    <div style="position:relative;z-index:2;width:100%;max-width:820px;margin:0 auto;">
        <div class="ms-badge-pill"><span class="bb"></span>AI-Powered Medical Imaging</div>
        <div class="ms-h1">Read Every<br><span class="cy">Scan Instantly.</span></div>
        <p class="ms-sub">
            Upload any <strong>X-Ray, MRI, or CT scan</strong> and receive an
            AI-generated clinical report in seconds — reviewed by real doctors.
        </p>
        <a href="#ms-patient" class="ms-cta">Get Started &rarr;</a>
        <div class="ms-pills">
            <div class="ms-pill"><div class="pv">X-Ray</div><div class="pl">Supported</div></div>
            <div class="ms-pill"><div class="pv">MRI</div><div class="pl">Supported</div></div>
            <div class="ms-pill"><div class="pv">CT</div><div class="pl">Supported</div></div>
            <div class="ms-pill"><div class="pv">AI</div><div class="pl">Analysis</div></div>
        </div>
    </div>
    <div class="ms-scroll"><span>Scroll</span><div class="ms-arr"></div></div>
</div>
""", unsafe_allow_html=True)

st.markdown('<hr>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  §2  PATIENT INFORMATION
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div id="ms-patient"></div>', unsafe_allow_html=True)
st.markdown("""
<div style="padding:48px 0 16px;">
    <div class="ms-lbl">Step 01</div>
    <div class="ms-stitle">Patient Information</div>
    <p class="ms-sdesc">Enter patient details before uploading and running the diagnostic scan.</p>
</div>
""", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns([2, 1, 1, 1.6])
with c1:
    n = st.text_input("Full Name", value=st.session_state.p_name, placeholder="Patient full name")
    st.session_state.p_name = n
with c2:
    a = st.number_input("Age", 0, 120, st.session_state.p_age)
    st.session_state.p_age = a
with c3:
    s = st.selectbox("Sex", ["Male", "Female", "Other"],
                     index=["Male","Female","Other"].index(st.session_state.p_sex))
    st.session_state.p_sex = s
with c4:
    st.markdown(f"""
    <div class="ms-pid" style="margin-top:22px;">
        <div class="ms-pid-lbl">Session ID</div>
        <div class="ms-pid-val">{st.session_state.report_id}</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<hr>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  §3  VISUAL SCAN
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div id="ms-scan"></div>', unsafe_allow_html=True)
st.markdown("""
<div style="padding:8px 0 16px;">
    <div class="ms-lbl">Step 02</div>
    <div class="ms-stitle">Visual Scan</div>
    <p class="ms-sdesc">Upload your medical image — AI detects and annotates anomalies.</p>
</div>
""", unsafe_allow_html=True)

sl, sr = st.columns([1, 1], gap="large")

with sl:
    uploaded_file = st.file_uploader(
        "Drop X-Ray / MRI / CT  (JPG or PNG)",
        type=["jpg", "png", "jpeg"]
    )

    if uploaded_file:
        if uploaded_file.name != st.session_state.last_uploaded_file:
            st.session_state.last_uploaded_file = uploaded_file.name
            st.session_state.analysis_result    = None
            st.session_state.deep_eval_result   = None

        st.markdown(f"""
        <div style="background:rgba(0,229,255,.05);border:1px solid rgba(0,229,255,.12);
             border-radius:8px;padding:9px 13px;margin:8px 0 12px;">
            <span style="color:#00E5FF;font-size:12px;font-weight:600;">📎 {uploaded_file.name}</span>
            <span style="color:#4A7A9B;font-size:11px;margin-left:10px;">
                {round(uploaded_file.size / 1024, 1)} KB
            </span>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚀  Run Diagnostic Scan", use_container_width=True):
            with st.status("Initialising MediScan Engine...", expanded=True) as status:
                st.write("Pre-processing image...")
                pil_img = Image.open(uploaded_file).convert("RGB")
                st.write("Running AI analysis...")
                simulate_progress_bar(st, "Scanning...", speed=0.02)

                res = None
                if GEMINI_AVAILABLE and GEMINI_MODEL:
                    try:
                        prompt = (
                            'Analyze this medical image. Return JSON ONLY:\n'
                            '{"organ":"Name","findings":[{"condition":"Name",'
                            '"severity":"Low/Med/High","box":[ymin,xmin,ymax,xmax]}]}\n'
                            'Coordinates on 0-1000 scale.'
                        )
                        resp = GEMINI_MODEL.generate_content([prompt, pil_img])
                        res  = json.loads(sanitize_text(resp.text))
                    except Exception as e:
                        st.warning(f"AI error ({e}) — using simulation fallback.")

                if res is None:
                    res = {"organ": "Lungs", "findings": [
                        {"condition": "Opacification", "severity": "High", "box": [200,300,600,700]}
                    ]}

                st.session_state.analysis_result = res
                status.update(label="✅ Scan complete", state="complete", expanded=False)

    # Findings chips
    if st.session_state.analysis_result:
        organ = st.session_state.analysis_result.get("organ", "Unknown")
        st.markdown(f"""
        <div class="ms-card" style="margin-top:14px;">
            <div class="ms-lbl">Detected organ</div>
            <div style="font-family:'Syne',sans-serif;font-size:20px;font-weight:700;color:#00E5FF;">
                {organ}
            </div>
        </div>
        """, unsafe_allow_html=True)

        for f in st.session_state.analysis_result.get("findings", []):
            sv   = f.get("severity", "").lower()
            bcls = "br" if sv == "high" else "bam" if sv in ("med","medium") else "bg"
            st.markdown(f"""
            <div class="ms-card" style="margin-top:8px;display:flex;align-items:center;
                 justify-content:space-between;padding:12px 16px;">
                <span style="color:#E8F4FF;font-weight:500;">{f.get("condition","?")}</span>
                <span class="ms-badge {bcls}">{f.get("severity","?")}</span>
            </div>
            """, unsafe_allow_html=True)

with sr:
    if uploaded_file:
        pil_img = Image.open(uploaded_file).convert("RGB")
        if st.session_state.analysis_result:
            ann = pil_img.copy()
            drw = ImageDraw.Draw(ann)
            W, H = ann.size
            for f in st.session_state.analysis_result.get("findings", []):
                if "box" in f:
                    ymin, xmin, ymax, xmax = f["box"]
                    bx = [(xmin/1000)*W,(ymin/1000)*H,(xmax/1000)*W,(ymax/1000)*H]
                    sv = f.get("severity","").lower()
                    cl = "#FF6B6B" if sv=="high" else "#FBBF24" if sv in ("med","medium") else "#34D399"
                    drw.rectangle(bx, outline=cl, width=4)
            ann.save("temp_scan.jpg")
            st.image(ann, caption="AI-annotated — anomalies highlighted", use_container_width=True)
        else:
            pil_img.save("temp_scan.jpg")
            st.image(pil_img, caption="Original — run scan to annotate", use_container_width=True)
    else:
        st.markdown("""
        <div style="min-height:360px;display:flex;flex-direction:column;align-items:center;
             justify-content:center;background:rgba(6,21,37,.5);
             border:1px dashed rgba(0,229,255,.12);border-radius:14px;">
            <div style="font-size:56px;opacity:.15;margin-bottom:12px;">🫁</div>
            <div style="font-size:13px;color:#1E3A50;">Upload a scan to preview here</div>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<hr>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  §4  CLINICAL REPORT
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div id="ms-report"></div>', unsafe_allow_html=True)
st.markdown("""
<div style="padding:8px 0 16px;">
    <div class="ms-lbl">Step 03</div>
    <div class="ms-stitle">Clinical Report</div>
    <p class="ms-sdesc">Generate a full AI clinical narrative and download the PDF.</p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.analysis_result:
    st.markdown("""
    <div class="ms-card" style="text-align:center;padding:40px;color:#2A4A6B;">
        <div style="font-size:36px;opacity:.2;margin-bottom:12px;">📄</div>
        Complete the Visual Scan above to unlock the Clinical Report.
    </div>
    """, unsafe_allow_html=True)
else:
    rl, rr = st.columns([2, 1], gap="large")

    with rl:
        if not st.session_state.deep_eval_result:
            if st.button("⚡  Generate Clinical Narrative", use_container_width=True):
                with st.spinner("Synthesising clinical analysis..."):
                    organ = st.session_state.analysis_result.get("organ","Unknown")
                    flist = st.session_state.analysis_result.get("findings",[])
                    ftxt  = ", ".join(f"{f.get('condition')} ({f.get('severity')} severity)" for f in flist)

                    MOCK = """**Observation:** The scan demonstrates a localised region of increased density in the lower lobe, suggestive of consolidation.

**Severity:** Moderate to High — requires clinical correlation.

**Recommendation:**
- Complete blood count (CBC)
- Sputum culture and sensitivity
- Pulmonology consultation within 48 hours

**Risk_Percentage:** 78"""

                    if GEMINI_AVAILABLE and GEMINI_MODEL:
                        try:
                            prompt = f"""You are a medical AI assistant. Analyze this diagnostic scan result.

Scan Details:
- Target Organ: {organ}
- Detected Conditions: {ftxt}

Provide a structured clinical analysis with:
1. Observation: Detailed description of findings
2. Severity: Low/Medium/High with justification
3. Recommendation: Specific actionable next steps
4. Risk_Percentage: integer 0-100 only

Use bold section headers."""
                            resp = GEMINI_MODEL.generate_content(prompt)
                            st.session_state.deep_eval_result = resp.text
                        except:
                            st.session_state.deep_eval_result = MOCK
                    else:
                        simulate_progress_bar(st, "Generating...", speed=0.03)
                        st.session_state.deep_eval_result = MOCK
                st.rerun()

        if st.session_state.deep_eval_result:
            st.markdown(
                f'<div class="ms-card" style="line-height:1.95;">'
                f'{st.session_state.deep_eval_result}</div>',
                unsafe_allow_html=True
            )

    with rr:
        det_organ = st.session_state.analysis_result.get("organ","").lower()
        auto_spec = ORGAN_SPEC_MAP.get(det_organ, "general")
        risk_pct  = None
        if st.session_state.deep_eval_result:
            m = re.search(r"Risk_Percentage[:\s]*([0-9]{1,3})", st.session_state.deep_eval_result)
            if m:
                risk_pct = int(m.group(1))

        rm1, rm2 = st.columns(2)
        rm1.metric("Organ",      det_organ.capitalize() or "—")
        rm2.metric("Risk Score", f"{risk_pct}%" if risk_pct is not None else "N/A")

        st.markdown(f"""
        <div class="ms-card" style="margin-top:12px;">
            <div class="ms-lbl">Auto-assigned dept.</div>
            <div style="font-family:'Syne',sans-serif;font-size:19px;font-weight:700;
                 color:#00E5FF;margin:5px 0 3px;">{auto_spec.capitalize()}</div>
            <div style="font-size:11px;color:#4A7A9B;">
                Organ detected: {det_organ.capitalize() or "Unknown"}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("💾  Save to Patient Registry", use_container_width=True):
            flist   = st.session_state.analysis_result.get("findings",[])
            disease = flist[0].get("condition","Unknown") if flist else "Unknown"
            rec     = make_patient_entry(
                st.session_state.p_name, st.session_state.p_age,
                st.session_state.p_sex,  st.session_state.report_id,
                disease, auto_spec
            )
            add_record(rec)
            st.session_state.patient_counter += 1
            st.success(f"✅ Saved {rec['id']} → {auto_spec.upper()}")
            st.balloons()

        if os.path.exists("temp_scan.jpg") and st.session_state.deep_eval_result:
            pdf_data = create_medical_pdf(
                {
                    "name": st.session_state.p_name, "age":  st.session_state.p_age,
                    "sex":  st.session_state.p_sex,  "id":   st.session_state.report_id,
                    "date": timestamp_now()
                },
                st.session_state.analysis_result,
                st.session_state.deep_eval_result,
                image_path="temp_scan.jpg"
            )
            st.download_button(
                label="📄  Download PDF Report",
                data=pdf_data,
                file_name=f"Report_{st.session_state.report_id}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
        else:
            st.caption("Generate the clinical narrative first to enable PDF export.")

st.markdown('<hr>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  §5  DOCTOR PORTAL
# ══════════════════════════════════════════════════════════════════════════════
st.markdown('<div id="ms-doctor"></div>', unsafe_allow_html=True)
st.markdown("""
<div style="padding:8px 0 16px;">
    <div class="ms-lbl">Step 04</div>
    <div class="ms-stitle">Doctor Portal</div>
    <p class="ms-sdesc">Login with department credentials to review and manage patient records.</p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.doctor_logged_in:
    _, dc, _ = st.columns([1, 1.2, 1])
    with dc:
        with st.form("doctor_login"):
            dept_ch = st.selectbox("Department", list(DOCTOR_CREDENTIALS.keys()),
                                   format_func=lambda x: x.capitalize())
            du = st.text_input("Username", placeholder=f"Hint: {DOCTOR_CREDENTIALS[dept_ch]['u']}")
            dp = st.text_input("Password", type="password", placeholder="Hint: 123")
            if st.form_submit_button("🔐  Access Portal", use_container_width=True):
                creds = DOCTOR_CREDENTIALS.get(dept_ch, {})
                if du == creds.get("u") and dp == creds.get("p"):
                    st.session_state.doctor_logged_in = True
                    st.session_state.doctor_spec      = dept_ch
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
        with st.expander("💡 Demo credentials"):
            for dept, creds in DOCTOR_CREDENTIALS.items():
                st.caption(f"**{dept.capitalize()}** → {creds['u']} / {creds['p']}")
else:
    dh1, dh2 = st.columns([5, 1])
    with dh1:
        st.markdown(f"""
        <div class="ms-card" style="padding:14px 20px;">
            <div class="ms-lbl">Logged in as</div>
            <div style="font-family:'Syne',sans-serif;font-size:20px;font-weight:700;color:#E8F4FF;">
                Dr. {st.session_state.doctor_spec.capitalize()}
            </div>
            <div style="font-size:11px;color:#4A7A9B;margin-top:2px;">
                Department: {st.session_state.doctor_spec.upper()}
            </div>
        </div>
        """, unsafe_allow_html=True)
    with dh2:
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        if st.button("Logout", use_container_width=True):
            st.session_state.doctor_logged_in = False
            st.session_state.doctor_spec      = None
            st.rerun()

    dept_recs = [
        r for r in load_all()
        if r.get("specialization","").lower() == st.session_state.doctor_spec.lower()
    ]

    if dept_recs:
        dm1, dm2, dm3 = st.columns(3)
        dm1.metric("Total Patients",  len(dept_recs))
        dm2.metric("Pending Reviews", sum(1 for r in dept_recs if r.get("status")=="Pending Review"))
        dm3.metric("Reviewed",        sum(1 for r in dept_recs if r.get("status")=="Reviewed"))

        st.markdown("<br>", unsafe_allow_html=True)

        for idx, rec in enumerate(dept_recs):
            status = rec.get("status","Pending Review")
            bcls   = "bam" if status=="Pending Review" else "bg" if status=="Reviewed" else "bc"

            with st.expander(
                f"{rec['id']}  ·  {rec['name']}  ·  {rec['disease']}",
                expanded=(st.session_state.editing_patient == rec["id"])
            ):
                ea, eb = st.columns([4, 1])
                with ea:
                    st.markdown(f'<span class="ms-badge {bcls}">{status}</span>', unsafe_allow_html=True)
                with eb:
                    if st.session_state.editing_patient == rec["id"]:
                        if st.button("✕ Cancel", key=f"can_{idx}", use_container_width=True):
                            st.session_state.editing_patient = None
                            st.rerun()
                    else:
                        if st.button("✏️ Edit", key=f"edi_{idx}", use_container_width=True):
                            st.session_state.editing_patient = rec["id"]
                            st.rerun()

                if st.session_state.editing_patient == rec["id"]:
                    with st.form(key=f"frm_{idx}"):
                        fc1, fc2 = st.columns(2)
                        with fc1:
                            nn = st.text_input("Name",  value=rec["name"],  key=f"nn_{idx}")
                            na = st.number_input("Age", 0, 120, rec["age"], key=f"na_{idx}")
                            ns = st.selectbox("Sex", ["Male","Female","Other"],
                                index=["Male","Female","Other"].index(rec["sex"])
                                      if rec["sex"] in ["Male","Female","Other"] else 0,
                                key=f"ns_{idx}")
                        with fc2:
                            st.text_input("Patient ID",  value=rec["id"],            disabled=True, key=f"ni_{idx}")
                            st.text_input("Disease",     value=rec["disease"],        disabled=True, key=f"nd_{idx}")
                            st.text_input("Department",  value=rec["specialization"], disabled=True, key=f"nsp_{idx}")
                            st.text_input("Date",        value=rec["date"],           disabled=True, key=f"ndt_{idx}")
                        nst = st.selectbox("Review Status",
                            ["Pending Review","Reviewed","Discharged"],
                            index=["Pending Review","Reviewed","Discharged"].index(status)
                                  if status in ["Pending Review","Reviewed","Discharged"] else 0,
                            key=f"nst_{idx}")
                        if st.form_submit_button("💾  Save Changes", use_container_width=True):
                            if update_record(rec["id"],{"name":nn,"age":na,"sex":ns,"status":nst}):
                                st.success("Record updated.")
                                st.session_state.editing_patient = None
                                st.rerun()
                            else:
                                st.error("Update failed.")
                else:
                    ri1, ri2 = st.columns(2)
                    with ri1:
                        st.markdown(f"**Patient ID:** {rec['id']}")
                        st.markdown(f"**Name:** {rec['name']}")
                        st.markdown(f"**Age:** {rec['age']} yrs")
                        st.markdown(f"**Sex:** {rec['sex']}")
                    with ri2:
                        st.markdown(f"**Disease:** {rec['disease']}")
                        st.markdown(f"**Dept:** {rec['specialization'].capitalize()}")
                        st.markdown(f"**Date:** {rec['date']}")
    else:
        st.info(f"No patients assigned to {st.session_state.doctor_spec.capitalize()} yet.")

st.markdown('<hr>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  §6  ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
import pandas as pd

st.markdown('<div id="ms-analytics"></div>', unsafe_allow_html=True)
st.markdown("""
<div style="padding:8px 0 16px;">
    <div class="ms-lbl">Overview</div>
    <div class="ms-stitle">Analytics Dashboard</div>
    <p class="ms-sdesc">Live statistics across all departments and patient records.</p>
</div>
""", unsafe_allow_html=True)

records = load_all()
if records:
    df = pd.DataFrame(records)

    am1, am2, am3, am4, am5 = st.columns(5)
    am1.metric("Total Patients",    len(df))
    am2.metric("Departments",       df["specialization"].nunique())
    am3.metric("Avg Age",           f"{int(df['age'].mean())} yrs" if "age" in df.columns else "—")
    am4.metric("Pending Reviews",   sum(1 for r in records if r.get("status")=="Pending Review"))
    am5.metric("Unique Conditions", df["disease"].nunique() if "disease" in df.columns else "—")

    st.markdown("<br>", unsafe_allow_html=True)

    ac1, ac2 = st.columns(2, gap="large")
    with ac1:
        st.caption("Patient distribution by department")
        st.bar_chart(df["specialization"].value_counts())
    with ac2:
        if "status" in df.columns:
            st.caption("Status overview")
            st.bar_chart(df["status"].value_counts())

    st.markdown("<br>", unsafe_allow_html=True)

    ac3, ac4 = st.columns(2, gap="large")
    with ac3:
        st.caption("Top 10 conditions")
        st.bar_chart(df["disease"].value_counts().head(10))
    with ac4:
        if "sex" in df.columns:
            st.caption("Gender by department")
            st.bar_chart(pd.crosstab(df["specialization"], df["sex"]))

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Patient Records")

    tf1, tf2, tf3 = st.columns(3)
    df_f = tf1.selectbox("Department", ["All"]+list(df["specialization"].unique()), key="af1")
    sf_f = tf2.selectbox("Status", ["All"]+(list(df["status"].unique()) if "status" in df.columns else []), key="af2")
    sr_f = tf3.text_input("Search name / ID", "", key="af3")

    fdf = df.copy()
    if df_f != "All": fdf = fdf[fdf["specialization"]==df_f]
    if sf_f != "All" and "status" in fdf.columns: fdf = fdf[fdf["status"]==sf_f]
    if sr_f:
        fdf = fdf[
            fdf["name"].str.contains(sr_f, case=False, na=False) |
            fdf["id"].str.contains(sr_f,   case=False, na=False)
        ]

    st.caption(f"Showing {len(fdf)} of {len(df)} records")
    dcols = ["id","name","age","sex","disease","specialization","date"]
    if "status" in fdf.columns: dcols.append("status")
    st.dataframe(
        fdf[dcols].sort_values("date", ascending=False),
        use_container_width=True, hide_index=True,
        column_config={
            "id":"Patient ID","name":"Name","age":"Age","sex":"Gender",
            "disease":"Condition","specialization":"Department","date":"Date","status":"Status"
        }
    )
    st.download_button(
        label="📥  Export as CSV",
        data=fdf.to_csv(index=False).encode("utf-8"),
        file_name=f"mediscan_{timestamp_now().replace(' ','_').replace(':','-')}.csv",
        mime="text/csv",
        use_container_width=True
    )
else:
    st.info("No patient data yet. Complete a scan and save a record to see analytics.")


# ══════════════════════════════════════════════════════════════════════════════
#  AI CHAT BOT  — toggle at bottom of page, chat_input at top level
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown('<hr>', unsafe_allow_html=True)

st.markdown("""
<div style="padding:8px 0 14px;">
    <div class="ms-lbl">AI Consultant</div>
    <div class="ms-stitle" style="font-size:26px;">Ask MediScan AI</div>
    <p class="ms-sdesc">Ask anything about the scan, diagnosis, treatment, or risks.</p>
</div>
""", unsafe_allow_html=True)

# Context status
if st.session_state.analysis_result or st.session_state.deep_eval_result:
    ctx_parts = []
    if st.session_state.analysis_result:
        ctx_parts.append(f"🔬 Scan: {st.session_state.analysis_result.get('organ','?')} — "
                         + ", ".join(f.get("condition","?") for f in st.session_state.analysis_result.get("findings",[])))
    if st.session_state.deep_eval_result:
        ctx_parts.append("📄 Clinical report generated")
    st.markdown(
        f'<div style="background:rgba(0,229,255,.05);border:1px solid rgba(0,229,255,.12);'
        f'border-radius:8px;padding:10px 14px;margin-bottom:16px;font-size:13px;color:#7FA8C9;">'
        f'<span style="color:#00E5FF;">●</span> Context loaded &nbsp;·&nbsp; '
        + " &nbsp;·&nbsp; ".join(ctx_parts) +
        f'</div>',
        unsafe_allow_html=True
    )
else:
    st.info("💡 Upload and analyse a scan first for context-aware answers. You can still ask general medical questions.")

# Render chat history
for msg in st.session_state.chat_history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Chat input — at top level, always visible
chat_in = st.chat_input("Ask about diagnosis, treatment, risks, medications...")

if chat_in:
    st.session_state.chat_history.append({"role": "user", "content": chat_in})

    resp_txt = ("I can help with medical questions. "
                "Upload and scan an image first for context-aware answers.")

    if GEMINI_AVAILABLE and GEMINI_MODEL:
        try:
            ctx_parts = []
            if st.session_state.deep_eval_result:
                ctx_parts.append(f"Clinical report:\n{st.session_state.deep_eval_result}")
            if st.session_state.analysis_result:
                ctx_parts.append(f"Scan findings:\n{json.dumps(st.session_state.analysis_result)}")
            ctx = "\n\n".join(ctx_parts) if ctx_parts else "No scan context available yet."
            full_prompt = (
                f"You are MediScan AI, a concise and helpful medical assistant.\n"
                f"Context: {ctx}\n\n"
                f"User question: {chat_in}\n\n"
                f"Respond clearly in 2-4 sentences. Be medically accurate."
            )
            r        = GEMINI_MODEL.generate_content(full_prompt)
            resp_txt = r.text
        except Exception as e:
            resp_txt = f"AI error: {e}. Please try again."
    elif st.session_state.deep_eval_result:
        resp_txt = ("Based on the scan analysis, I recommend following the clinical "
                    "report's recommendations and consulting with the assigned specialist.")

    st.session_state.chat_history.append({"role": "assistant", "content": resp_txt})
    st.rerun()

# Clear chat button
if st.session_state.chat_history:
    if st.button("🗑️  Clear Chat", key="clear_chat"):
        st.session_state.chat_history = []
        st.rerun()


# ── FOOTER ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="border-top:1px solid rgba(0,229,255,.05);padding:28px 0;margin-top:40px;
     display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px;">
    <div style="font-family:'Syne',sans-serif;font-weight:800;font-size:17px;color:#E8F4FF;">
        Medi<span style="color:#00E5FF;">Scan</span>
    </div>
    <div style="font-size:11px;color:#152840;">
        Not a replacement for professional medical advice. Always consult a licensed physician.
    </div>
</div>
""", unsafe_allow_html=True)
