"""
Professional PDF Template Service
Creates a professional offer letter PDF matching Levitica template design
Generates from scratch with exact colors, fonts, and layout
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Image, KeepTogether
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfgen import canvas
from io import BytesIO
from typing import Optional, Dict, Any
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


class ProfessionalLetterhead(object):
    """Professional letterhead matching Levitica design"""
    
    def __init__(self, logo_path: str = "uploads/levitica_logo.png"):
        self.logo_path = logo_path
        
        # Exact colors from template
        self.header_purple = HexColor('#2E1A47')  # Dark purple header
        self.heading_blue = HexColor('#0066CC')   # Blue headings
        self.text_black = HexColor('#000000')     # Black text
        self.text_gray = HexColor('#333333')      # Gray text
        self.watermark_color = Color(0.95, 0.95, 0.95, alpha=0.1)
        
        # Company details
        self.company_name = "Levitica Technologies Pvt. Ltd"
        self.company_full = "Levitica Technologies Private Limited"
        self.address_line1 = "Office #409, 4th Floor, Jain Sadguru Image's, Capital Pk Rd, Ayyappa Society,"
        self.address_line2 = "Madhapur, Hyderabad, Telangana 500081"
        self.phone = "+91 9032503559"
        self.website = "www.leviticatechnologies.com"
        self.email = "hr@leviticatechnologies.com"
        self.cin = "U72200TG2013PTC091836"
    
    def draw_header(self, canvas_obj, doc):
        """Draw professional header"""
        canvas_obj.saveState()
        
        # Purple header box on right
        canvas_obj.setFillColor(self.header_purple)
        canvas_obj.rect(A4[0] - 240, A4[1] - 105, 240, 105, fill=1, stroke=0)
        
        # Logo on left
        if os.path.exists(self.logo_path):
            try:
                canvas_obj.drawImage(
                    self.logo_path,
                    45, A4[1] - 100,
                    width=130, height=65,
                    preserveAspectRatio=True,
                    mask='auto'
                )
            except Exception as e:
                logger.warning(f"Could not load logo: {e}")
        
        # Contact details in purple box (white text)
        canvas_obj.setFillColor(HexColor('#FFFFFF'))
        canvas_obj.setFont("Helvetica", 9)
        
        y_pos = A4[1] - 45
        canvas_obj.drawString(A4[0] - 225, y_pos, f"📞  {self.phone}")
        
        y_pos -= 16
        canvas_obj.drawString(A4[0] - 225, y_pos, f"🌐  {self.website}")
        
        y_pos -= 16
        canvas_obj.drawString(A4[0] - 225, y_pos, f"✉  {self.email}")
        
        y_pos -= 16
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.drawString(A4[0] - 225, y_pos, "CIN")
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.drawString(A4[0] - 200, y_pos, self.cin)
        
        canvas_obj.restoreState()
    
    def draw_footer(self, canvas_obj, doc):
        """Draw professional footer"""
        canvas_obj.saveState()
        
        y_pos = 65
        
        # Horizontal lines with company name
        canvas_obj.setStrokeColor(self.text_black)
        canvas_obj.setLineWidth(1)
        
        # Left line
        canvas_obj.line(45, y_pos, 220, y_pos)
        
        # Company name
        canvas_obj.setFont("Helvetica-Bold", 10)
        canvas_obj.setFillColor(self.text_black)
        canvas_obj.drawCentredString(A4[0] / 2, y_pos - 3, self.company_full)
        
        # Right line
        canvas_obj.line(A4[0] - 220, y_pos, A4[0] - 45, y_pos)
        
        # Address
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(self.text_gray)
        canvas_obj.drawCentredString(A4[0] / 2, y_pos - 18, self.address_line1)
        canvas_obj.drawCentredString(A4[0] / 2, y_pos - 30, self.address_line2)
        
        canvas_obj.restoreState()
    
    def draw_watermark(self, canvas_obj, doc):
        """Draw subtle logo watermark"""
        canvas_obj.saveState()
        
        if os.path.exists(self.logo_path):
            try:
                canvas_obj.setFillColor(self.watermark_color)
                canvas_obj.drawImage(
                    self.logo_path,
                    A4[0] / 2 - 180,
                    A4[1] / 2 - 180,
                    width=360,
                    height=360,
                    preserveAspectRatio=True,
                    mask='auto'
                )
            except Exception as e:
                pass
        
        canvas_obj.restoreState()
    
    def draw_small_logo(self, canvas_obj, doc):
        """Draw small logo on subsequent pages"""
        canvas_obj.saveState()
        
        if os.path.exists(self.logo_path):
            try:
                canvas_obj.drawImage(
                    self.logo_path,
                    A4[0] - 160,
                    A4[1] - 145,
                    width=110, height=55,
                    preserveAspectRatio=True,
                    mask='auto'
                )
            except Exception as e:
                pass
        
        canvas_obj.restoreState()
    
    def __call__(self, canvas_obj, doc):
        """Called for each page"""
        self.draw_watermark(canvas_obj, doc)
        
        if doc.page == 1:
            self.draw_header(canvas_obj, doc)
        else:
            self.draw_small_logo(canvas_obj, doc)
        
        self.draw_footer(canvas_obj, doc)



class ProfessionalPDFService:
    """Professional PDF generation service"""
    
    def __init__(self):
        self.page_width, self.page_height = A4
        self.left_margin = 45
        self.right_margin = 45
        self.top_margin = 125
        self.bottom_margin = 95
        
        # Company details
        self.company_name = "Levitica Technologies Pvt. Ltd"
        self.company_full = "Levitica Technologies Private Limited"
        
    def create_styles(self):
        """Create professional styles"""
        styles = getSampleStyleSheet()
        
        # Company title
        styles.add(ParagraphStyle(
            name='CompanyTitle',
            parent=styles['Heading1'],
            fontSize=14,
            textColor=HexColor('#0066CC'),
            spaceAfter=20,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Section heading
        styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=styles['Heading2'],
            fontSize=11,
            textColor=HexColor('#0066CC'),
            spaceBefore=14,
            spaceAfter=10,
            fontName='Helvetica-Bold',
            alignment=TA_LEFT
        ))
        
        # Body text
        styles.add(ParagraphStyle(
            name='BodyJustify',
            parent=styles['BodyText'],
            fontSize=10,
            leading=15,
            textColor=HexColor('#000000'),
            alignment=TA_JUSTIFY,
            fontName='Helvetica'
        ))
        
        # Bullet text
        styles.add(ParagraphStyle(
            name='BulletText',
            parent=styles['BodyText'],
            fontSize=10,
            leading=15,
            textColor=HexColor('#000000'),
            leftIndent=20,
            bulletIndent=10,
            fontName='Helvetica',
            alignment=TA_JUSTIFY
        ))
        
        # Confidential box
        styles.add(ParagraphStyle(
            name='ConfidentialBox',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=HexColor('#0066CC'),
            spaceAfter=15,
            spaceBefore=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        return styles
    
    def generate_offer_letter_pdf(
        self,
        candidate_data: Dict[str, Any],
        logo_path: str = "uploads/levitica_logo.png"
    ) -> Optional[BytesIO]:
        """
        Generate professional offer letter PDF
        
        Args:
            candidate_data: Dictionary with candidate information
            logo_path: Path to company logo
            
        Returns:
            BytesIO buffer with PDF
        """
        try:
            logger.info(f"Generating professional PDF for: {candidate_data.get('candidate_name', 'Unknown')}")
            
            buffer = BytesIO()
            
            # Create document
            letterhead = ProfessionalLetterhead(logo_path)
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                leftMargin=self.left_margin,
                rightMargin=self.right_margin,
                topMargin=self.top_margin,
                bottomMargin=self.bottom_margin
            )
            
            styles = self.create_styles()
            
            # Build content
            story = []
            story.extend(self._build_content(candidate_data, styles))
            
            # Generate PDF
            doc.build(story, onFirstPage=letterhead, onLaterPages=letterhead)
            
            buffer.seek(0)
            logger.info("Professional PDF generated successfully")
            return buffer
            
        except Exception as e:
            logger.error(f"Failed to generate professional PDF: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _build_content(self, data: Dict, styles) -> list:
        """Build all PDF content"""
        content = []
        
        # Extract data
        candidate_name = data.get('candidate_name', 'Candidate Name')
        position = data.get('position', 'Position')
        ctc = data.get('ctc', '3,00,000')
        training_salary = data.get('training_salary', '17,500')
        joining_date = data.get('joining_date', 'Date')
        offer_date = data.get('offer_date', datetime.now().strftime('%B %d, %Y'))
        candidate_address = data.get('candidate_address', 'Address')
        
        # Company title
        content.append(Paragraph(self.company_name, styles['CompanyTitle']))
        content.append(Spacer(1, 20))
        
        # Date
        content.append(Paragraph(f"<b>Date:</b> {offer_date}", styles['BodyJustify']))
        content.append(Spacer(1, 15))
        
        # Candidate details
        content.append(Paragraph("To,", styles['BodyJustify']))
        content.append(Paragraph(f"<b>Mr. {candidate_name},</b>", styles['BodyJustify']))
        
        # Address
        for line in candidate_address.split('\n'):
            content.append(Paragraph(line, styles['BodyJustify']))
        
        content.append(Spacer(1, 20))
        
        # Confidential letter box
        content.append(Paragraph("Confidential Letter!", styles['ConfidentialBox']))
        content.append(Spacer(1, 15))
        
        # Offer text
        offer_text = f"""We are pleased to extend an offer for the position of <b>"{position}"</b> 
        at Levitica Technologies Pvt. Ltd., with your confirmed joining date of <b>{joining_date}</b>. 
        This offer is subject to the following terms and conditions."""
        content.append(Paragraph(offer_text, styles['BodyJustify']))
        content.append(Spacer(1, 15))
        
        # Section 1: Compensation
        content.append(Paragraph("1. Compensation & Benefits", styles['SectionHeading']))
        
        comp_points = [
            f"Your total Annual Cost to Company (CTC) will be INR <b>{ctc}</b>, detailed in Annexure - A.",
            f"During the training period, you will receive a salary of INR <b>{training_salary}</b> per month. Upon successful completion of training, your annual CTC will be revised to INR {ctc}.",
            "Salary will be reviewed periodically based on performance and company policies.",
            "Provident Fund contributions will be based on the Basic component as per statutory rules.",
            "Remuneration may be altered without prior notice depending on company policies and legal guidelines.",
            "Compensation details are confidential and must not be disclosed to others.",
            "Employees are paid monthly via bank transfer.",
            "Additional: Performance bonuses and employee benefits (health insurance, training) may be provided at the company's discretion."
        ]
        
        for point in comp_points:
            content.append(Paragraph(f"• {point}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(PageBreak())
        
        # Continue with remaining sections...
        content.extend(self._build_remaining_sections(styles))
        
        # Add salary annexure
        content.extend(self._build_salary_annexure(data, styles))
        
        return content

    
    def _build_remaining_sections(self, styles) -> list:
        """Build remaining sections from template"""
        content = []
        
        # Section 2: Period of Service
        content.append(Paragraph("2. Period of Service", styles['SectionHeading']))
        
        service_points = [
            "You are required to sign a one-year training-cum-service agreement.",
            "A six-month probation period will apply. Your performance will be assessed before confirmation.",
            "If performance is unsatisfactory, probation may be extended or employment terminated.",
            "Additional: Breach of the service agreement during this period may result in legal consequences or compensation recovery."
        ]
        
        for point in service_points:
            content.append(Paragraph(f"• {point}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(Spacer(1, 12))
        
        # Section 3: Hours of Work
        content.append(Paragraph("3. Hours of Work", styles['SectionHeading']))
        
        work_points = [
            "Workdays: 5 days/week. Working hours depend on your project or client location.",
            "Shift work or weekend duty may be required.",
            "The company does not provide overtime compensation.",
            "Additional: Flexible work arrangements may be granted based on managerial approval and project requirements."
        ]
        
        for point in work_points:
            content.append(Paragraph(f"• {point}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(Spacer(1, 12))
        
        # Section 4: Leaves & Holidays
        content.append(Paragraph("4. Leaves & Holidays", styles['SectionHeading']))
        
        leave_points = [
            "You are entitled to 18 days of leave per year (12 paid + 6 casual), pro-rated from the date of joining.",
            "Earned leaves are credited monthly and can be en-cashed as per policy.",
            "Holidays depend on the location of your posting.",
            "Additional: All leave requests must be applied through the company leave management system."
        ]
        
        for point in leave_points:
            content.append(Paragraph(f"• {point}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(Spacer(1, 12))
        
        # Section 5: Unauthorized Absence
        content.append(Paragraph("5. Unauthorized Absence from Work", styles['SectionHeading']))
        
        absence_text = "Any unauthorized absence for three or more consecutive days will be deemed as absconding and may result in disciplinary action or legal proceedings."
        content.append(Paragraph(f"• {absence_text}", styles['BulletText']))
        
        content.append(PageBreak())
        
        # Continue with more sections...
        content.extend(self._build_legal_sections(styles))
        
        return content
    
    def _build_legal_sections(self, styles) -> list:
        """Build legal and policy sections"""
        content = []
        
        # Section 6: Disputes
        content.append(Paragraph("6. Disputes", styles['SectionHeading']))
        
        dispute_text = """All employment matters shall be governed in accordance with Indian laws, 
        including but not limited to the Indian Contract Act, 1872 and the relevant State Shops and Establishments Act. 
        The Company encourages amicable resolution of disputes through internal grievance redressal mechanisms or 
        arbitration before initiating litigation."""
        
        content.append(Paragraph(f"• {dispute_text}", styles['BulletText']))
        content.append(Spacer(1, 4))
        content.append(Paragraph("• Legal disputes will fall under Hyderabad jurisdiction unless otherwise specified for overseas assignments.", styles['BulletText']))
        content.append(Spacer(1, 4))
        content.append(Paragraph("• In case of non-compete violations, the company may seek damages and injunctive relief.", styles['BulletText']))
        content.append(Spacer(1, 4))
        content.append(Paragraph("• Additional: Disputes should first be addressed through mediation or arbitration before legal recourse.", styles['BulletText']))
        
        content.append(Spacer(1, 12))
        
        # Section 7: Background Verification
        content.append(Paragraph("7. Background Verification", styles['SectionHeading']))
        
        bg_text = """All background checks will be carried out in compliance with relevant privacy laws. 
        Drug screening, if performed, shall follow best practices and medical confidentiality standards. 
        You are expected to disclose any prior legal issues or employment history honestly as per company norms."""
        
        content.append(Paragraph(f"• {bg_text}", styles['BulletText']))
        
        content.append(PageBreak())
        
        # More sections...
        content.extend(self._build_final_sections(styles))
        
        return content
    
    def _build_final_sections(self, styles) -> list:
        """Build final sections"""
        content = []
        
        # Section 8: Confidentiality
        content.append(Paragraph("8. Confidentiality", styles['SectionHeading']))
        
        conf_points = [
            "You must maintain strict confidentiality regarding company information, trade secrets, and client data.",
            "Unauthorized disclosure may result in legal action and termination.",
            "This obligation continues even after employment ends.",
            "Additional: Confidentiality extends to all proprietary information, including but not limited to business strategies, financial data, and technical specifications."
        ]
        
        for point in conf_points:
            content.append(Paragraph(f"• {point}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(Spacer(1, 12))
        
        # Section 9: Intellectual Property
        content.append(Paragraph("9. Intellectual Property", styles['SectionHeading']))
        
        ip_text = """All work products, inventions, and intellectual property created during your employment 
        belong to the company. You agree to assign all rights to the company and assist in securing patents, 
        copyrights, or other protections as needed."""
        
        content.append(Paragraph(f"• {ip_text}", styles['BulletText']))
        
        content.append(Spacer(1, 12))
        
        # Section 10: Termination
        content.append(Paragraph("10. Termination", styles['SectionHeading']))
        
        term_points = [
            "Either party may terminate employment with appropriate notice as per company policy.",
            "The company reserves the right to terminate immediately for misconduct, breach of contract, or poor performance.",
            "Upon termination, you must return all company property and complete exit formalities.",
            "Additional: Notice period requirements and severance terms will be governed by applicable labor laws and company policies."
        ]
        
        for point in term_points:
            content.append(Paragraph(f"• {point}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(PageBreak())
        
        # Section 11: Non-Compete & Non-Solicitation
        content.append(Paragraph("11. Non-Compete & Non-Solicitation", styles['SectionHeading']))
        
        noncomp_points = [
            "During employment and for a specified period after, you agree not to engage in competing business activities.",
            "You shall not solicit company clients, employees, or contractors for competing purposes.",
            "Violation may result in legal action and claims for damages.",
            "Additional: The non-compete period and geographic scope will be reasonable and enforceable under applicable law."
        ]
        
        for point in noncomp_points:
            content.append(Paragraph(f"• {point}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(Spacer(1, 12))
        
        # Section 12: Code of Conduct
        content.append(Paragraph("12. Code of Conduct", styles['SectionHeading']))
        
        conduct_points = [
            "You are expected to maintain professional behavior and adhere to company policies.",
            "Harassment, discrimination, or unethical conduct will not be tolerated.",
            "Compliance with all applicable laws and regulations is mandatory.",
            "Additional: Regular training on code of conduct and ethics will be provided."
        ]
        
        for point in conduct_points:
            content.append(Paragraph(f"• {point}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(Spacer(1, 12))
        
        # Section 13: Data Protection & Privacy
        content.append(Paragraph("13. Data Protection & Privacy", styles['SectionHeading']))
        
        privacy_text = """You must comply with all data protection laws and company privacy policies. 
        Personal data of employees, clients, and stakeholders must be handled with care and only for 
        legitimate business purposes. Unauthorized access or misuse will result in disciplinary action."""
        
        content.append(Paragraph(f"• {privacy_text}", styles['BulletText']))
        
        content.append(Spacer(1, 12))
        
        # Section 14: Amendments
        content.append(Paragraph("14. Amendments", styles['SectionHeading']))
        
        amend_text = """The company reserves the right to modify these terms and conditions at any time. 
        You will be notified of significant changes, and continued employment constitutes acceptance of 
        the revised terms."""
        
        content.append(Paragraph(f"• {amend_text}", styles['BulletText']))
        
        content.append(Spacer(1, 12))
        
        # Section 15: Final Clauses
        content.append(Paragraph("15. Final Clauses", styles['SectionHeading']))
        
        final_points = [
            "Full and final settlement will be processed within 45 days from your last working day.",
            "PAN submission is mandatory; failure will result in TDS deduction at higher rates.",
            "You must devote your full time and attention to company business.",
            "This letter is governed by company policy, and Levitica reserves the right to modify any part of it."
        ]
        
        for point in final_points:
            content.append(Paragraph(f"• {point}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(Spacer(1, 20))
        
        # Closing
        closing_text = "We take this opportunity to welcome you to the Levitica family and wish you a satisfying engagement with us."
        content.append(Paragraph(closing_text, styles['BodyJustify']))
        
        content.append(Spacer(1, 20))
        
        # Acceptance
        content.append(Paragraph("<b>Acceptance of Joining</b>", styles['SectionHeading']))
        
        acceptance_text = "The terms and conditions of this Appointment Letter are fully acceptable to me. I shall report for duties on"
        content.append(Paragraph(acceptance_text, styles['BodyJustify']))
        
        content.append(Spacer(1, 30))
        
        # Signatures
        sig_data = [
            ['Sincerely,', '', 'Employee Name'],
            ['For Levitica Technologies Pvt. Ltd', '', ''],
            ['', '', ''],
            ['', '', ''],
            ['Authorized Signature:', '', 'Employee Signature']
        ]
        
        sig_table = Table(sig_data, colWidths=[220, 80, 220])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        content.append(sig_table)
        
        content.append(PageBreak())
        
        return content
    
    def _build_salary_annexure(self, data: Dict, styles) -> list:
        """Build salary annexure page"""
        content = []
        
        salary_breakdown = data.get('salary_breakdown') or {}
        joining_date = data.get('joining_date', 'Date')
        candidate_name = data.get('candidate_name', 'Employee Name')
        
        # Annexure title
        content.append(Paragraph("Annexure - A", styles['CompanyTitle']))
        content.append(Spacer(1, 10))
        content.append(Paragraph(f"<b>Salary Breakup (Effective {joining_date})</b>", styles['SectionHeading']))
        content.append(Spacer(1, 20))
        
        # Salary table
        table_data = [
            ['Particulars', 'Monthly (INR)'],
            ['Basic', salary_breakdown.get('basic_monthly', '12,000')],
            ['HRA', salary_breakdown.get('hra_monthly', '3,600')],
            ['Special Allowance', salary_breakdown.get('special_monthly', '4,260')],
            ['Conveyance', salary_breakdown.get('conveyance_monthly', '1,000')],
            ['Telephone', salary_breakdown.get('telephone_monthly', '900')],
            ['Medical', salary_breakdown.get('medical_monthly', '1,000')],
            ['Gross Salary', salary_breakdown.get('gross_monthly', '22,760')],
            ['Employee PF', salary_breakdown.get('employee_pf', '1,440')],
            ['Professional Tax', salary_breakdown.get('professional_tax', '200')],
            ['Gratuity', salary_breakdown.get('gratuity', '577')],
            ['Net Take Home', salary_breakdown.get('net_take_home', '20,543')],
            ['Employer PF', salary_breakdown.get('employer_pf', '1,440')],
            ['Group Insurance', salary_breakdown.get('group_insurance', '800')],
            ['Total CTC (Monthly)', salary_breakdown.get('total_ctc_monthly', '25,000')],
        ]
        
        salary_table = Table(table_data, colWidths=[280, 150])
        salary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0066CC')),
            ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, HexColor('#CCCCCC')),
            ('BACKGROUND', (0, 1), (-1, -2), HexColor('#F5F5F5')),
            ('BACKGROUND', (0, -1), (-1, -1), HexColor('#E0E0E0')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ]))
        
        content.append(salary_table)
        content.append(Spacer(1, 20))
        
        # Notes
        notes = [
            "This offer carries a 6-month probation period. Salary will not be revised post confirmation; any salary hike will be considered only after completion of one year.",
            "Health insurance premiums, if opted, will be deducted accordingly.",
            "Annual performance bonus is discretionary and not payable on a pro-rata basis for incomplete cycles.",
            "Salary structure is confidential and should not be disclosed."
        ]
        
        content.append(Paragraph("<b>Note:</b>", styles['BodyJustify']))
        for note in notes:
            content.append(Paragraph(f"• {note}", styles['BulletText']))
            content.append(Spacer(1, 4))
        
        content.append(Spacer(1, 30))
        
        # Signatures
        sig_data = [
            ['Sincerely,', '', 'Employee Name'],
            ['For Levitica Technologies Pvt. Ltd', '', candidate_name],
            ['', '', ''],
            ['', '', ''],
            ['Authorized Signature:', '', 'Employee Signature']
        ]
        
        sig_table = Table(sig_data, colWidths=[220, 80, 220])
        sig_table.setStyle(TableStyle([
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
        ]))
        
        content.append(sig_table)
        
        return content
    
    def generate_filename(self, candidate_name: str, prefix: str = "Offer_Letter") -> str:
        """Generate filename"""
        date_str = datetime.now().strftime('%Y%m%d')
        safe_name = candidate_name.replace(' ', '_').replace('.', '')
        return f"{prefix}_{safe_name}_{date_str}.pdf"


# Create singleton instance
professional_pdf_service = ProfessionalPDFService()
