from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, Frame
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import re

def create_medical_pdf(patient_data, scan_results, deep_analysis, image_path=None):
    """
    Generates a professional medical PDF report using ReportLab.
    Returns bytes.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Professional Header with Blue Background
    c.setFillColor(colors.HexColor("#1e3a8a"))
    c.rect(0, height - 80, width, 80, fill=True, stroke=False)
    
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 24)
    c.drawString(50, height - 45, "MediScan AI")
    c.setFont("Helvetica", 12)
    c.drawString(50, height - 65, "Clinical Diagnostic Report")
    
    # Date on right side
    c.setFont("Helvetica", 10)
    c.drawRightString(width - 50, height - 50, f"Generated: {patient_data.get('date')}")
    
    # Patient Information Section
    y_pos = height - 120
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y_pos, "Patient Information")
    
    # Draw a subtle line
    y_pos -= 5
    c.setStrokeColor(colors.HexColor("#3b82f6"))
    c.setLineWidth(2)
    c.line(50, y_pos, width - 50, y_pos)
    
    y_pos -= 25
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y_pos, "Name:")
    c.setFont("Helvetica", 11)
    c.drawString(150, y_pos, str(patient_data.get('name')))
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(350, y_pos, "Patient ID:")
    c.setFont("Helvetica", 11)
    c.drawString(450, y_pos, str(patient_data.get('id')))
    
    y_pos -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y_pos, "Age:")
    c.setFont("Helvetica", 11)
    c.drawString(150, y_pos, f"{patient_data.get('age')} years")
    
    c.setFont("Helvetica-Bold", 11)
    c.drawString(350, y_pos, "Sex:")
    c.setFont("Helvetica", 11)
    c.drawString(450, y_pos, str(patient_data.get('sex')))
    
    # Diagnostic Findings Section
    y_pos -= 40
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y_pos, "Diagnostic Findings")
    y_pos -= 5
    c.setStrokeColor(colors.HexColor("#3b82f6"))
    c.line(50, y_pos, width - 50, y_pos)
    
    y_pos -= 25
    organ = scan_results.get('organ', 'Unknown')
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y_pos, "Target Organ:")
    c.setFont("Helvetica", 11)
    c.drawString(150, y_pos, organ)
    
    y_pos -= 25
    findings = scan_results.get('findings', [])
    if findings:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y_pos, "Detected Conditions:")
        y_pos -= 20
        
        for f in findings:
            condition = f.get('condition', 'Unknown')
            severity = f.get('severity', 'Unknown')
            
            # Color code severity
            if severity.lower() == 'high':
                severity_color = colors.red
            elif severity.lower() == 'med' or severity.lower() == 'medium':
                severity_color = colors.orange
            else:
                severity_color = colors.green
            
            c.setFont("Helvetica", 10)
            c.drawString(70, y_pos, f"• {condition}")
            c.setFillColor(severity_color)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(350, y_pos, f"Severity: {severity}")
            c.setFillColor(colors.black)
            y_pos -= 18
    
    # Clinical Analysis Section
    y_pos -= 20
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y_pos, "Clinical Analysis")
    y_pos -= 5
    c.setStrokeColor(colors.HexColor("#3b82f6"))
    c.line(50, y_pos, width - 50, y_pos)
    y_pos -= 20
    
    # Parse and format the deep analysis
    if deep_analysis:
        # Remove markdown formatting
        clean_text = deep_analysis.replace("**", "")
        lines = clean_text.split('\n')
        
        c.setFont("Helvetica", 10)
        for line in lines:
            line = line.strip()
            if not line:
                y_pos -= 10
                continue
                
            # Check if we need a new page
            if y_pos < 100:
                c.showPage()
                y_pos = height - 50
            
            # Bold section headers
            if line.startswith("Observation:") or line.startswith("Severity:") or line.startswith("Recommendation:") or line.startswith("Risk_Percentage:"):
                c.setFont("Helvetica-Bold", 10)
                c.drawString(50, y_pos, line)
                c.setFont("Helvetica", 10)
                y_pos -= 15
            else:
                # Wrap long lines
                if len(line) > 85:
                    words = line.split()
                    current_line = ""
                    for word in words:
                        if len(current_line + word) < 85:
                            current_line += word + " "
                        else:
                            c.drawString(70, y_pos, current_line.strip())
                            y_pos -= 15
                            current_line = word + " "
                    if current_line:
                        c.drawString(70, y_pos, current_line.strip())
                        y_pos -= 15
                else:
                    c.drawString(70, y_pos, line)
                    y_pos -= 15
    
    # Visual Evidence Section
    if image_path:
        try:
            y_pos -= 20
            if y_pos < 350:
                c.showPage()
                y_pos = height - 50
            
            c.setFont("Helvetica-Bold", 16)
            c.setFillColor(colors.black)
            c.drawString(50, y_pos, "Visual Evidence")
            y_pos -= 5
            c.setStrokeColor(colors.HexColor("#3b82f6"))
            c.line(50, y_pos, width - 50, y_pos)
            y_pos -= 15
            
            # Draw annotated image
            img_width = width - 100
            img_height = 300
            c.drawImage(image_path, 50, y_pos - img_height, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')
            
        except Exception as e:
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.red)
            c.drawString(50, y_pos - 20, f"Error: Could not attach visual evidence image. {str(e)}")
    
    # Footer
    c.setFont("Helvetica-Oblique", 8)
    c.setFillColor(colors.grey)
    c.drawString(50, 30, "This report is generated by MediScan AI for diagnostic assistance purposes.")
    c.drawRightString(width - 50, 30, "Confidential Medical Document")
    
    c.save()
    buffer.seek(0)
    return buffer.getvalue()