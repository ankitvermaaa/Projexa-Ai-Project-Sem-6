# MediScan AI 🩺

MediScan AI is an AI-powered medical scan analysis system built using Python and Streamlit.  
The application allows doctors to upload medical scans, analyze them, and generate structured patient reports.

---

## Features: 

- Medical scan upload and analysis
- Patient information management
- Doctor portal interface
- Automatic medical report generation (PDF)
- Local patient database storage
- Clean and interactive Streamlit UI

---

## Project Structure
mediscan-ai
│
├── medi_scan_app.py # Main Streamlit application  
├── doctor_portal.py # Doctor interface  
├── patient_db.py # Patient database handling  
├── pdf_gen.py # PDF report generation  
├── utils.py  
├── patient_data.json # Patient records  
├── requirements.txt  
├── .gitignore  
└── README.md

---

### Installation

1. Clone the repository
   git clone https://github.com/YOUR-USERNAME/mediscan-ai.git
2. Navigate to the project
   cd mediscan-ai
3. Install Required Dependencies
   pip install -r requirements.txt
   
### Running the Application

Start the Streamlit server with:
streamlit run medi_scan_app.py

After running the command, Streamlit will automatically open the application in your browser.

---
### How the System Works

The doctor enters patient information in the interface.  
Medical scan images can be uploaded for analysis.  
The system processes the input data.  
Patient information is stored in a local JSON database.  
A structured medical report can be generated and exported as a PDF.


