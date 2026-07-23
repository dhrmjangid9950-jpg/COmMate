from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from django.http import HttpResponse
from datetime import datetime

def generate_po_pdf(po):
    """Generate PDF for Purchase Order"""
    
    # Create buffer
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=72)
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a237e'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=10
    )
    
    normal_style = styles['Normal']
    
    # Content
    story = []
    
    # Title
    story.append(Paragraph("PURCHASE ORDER", title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # PO Header Info
    po_data = [
        ['PO Number:', po.po_number],
        ['Order Date:', po.order_date.strftime('%d-%m-%Y') if po.order_date else 'N/A'],
        ['Expected Delivery:', po.expected_delivery.strftime('%d-%m-%Y') if po.expected_delivery else 'N/A'],
        ['Status:', po.status.upper()],
    ]
    
    po_table = Table(po_data, colWidths=[2*inch, 3*inch])
    po_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOLD', (0, 0), (0, -1), 1),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
    ]))
    story.append(po_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Vendor Info
    story.append(Paragraph("Vendor Details", heading_style))
    vendor_data = [
        ['Name:', po.vendor.name],
        ['Contact Person:', po.vendor.contact_person or 'N/A'], 
        ['Email:', po.vendor.email or 'N/A'],
        ['Phone:', po.vendor.phone or 'N/A'],
        ['Address:', po.vendor.address or 'N/A'],
    ]
    
    vendor_table = Table(vendor_data, colWidths=[1.5*inch, 3.5*inch])
    vendor_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOLD', (0, 0), (0, -1), 1),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
    ]))
    story.append(vendor_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Items Table
    story.append(Paragraph("Items Details", heading_style))
    
    # Table header
    items_data = [
        ['S.No', 'Product', 'HSN', 'GST%', 'Qty', 'Unit Price', 'Subtotal', 'Tax', 'Total']
    ]
    
    # Add items
    for idx, item in enumerate(po.items.all(), 1):
        items_data.append([
            str(idx),
            item.product_name,
            item.hsn_code or '-',
            f"{item.gst_rate or 0}%",
            str(item.quantity),
            f"₹{item.unit_price:.2f}",
            f"₹{item.subtotal:.2f}",
            f"₹{item.tax_amount:.2f}",
            f"₹{item.total_price:.2f}",
        ])
    
    # Add totals row
    items_data.append([
        '', '', '', '', '', '', 
        f"₹{po.subtotal:.2f}", 
        f"₹{po.tax_total:.2f}", 
        f"₹{po.total_amount:.2f}"
    ])
    
    items_table = Table(items_data, colWidths=[0.5*inch, 1.5*inch, 0.8*inch, 0.6*inch, 0.6*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch])
    items_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-2, -2), 1, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 9),
        ('SPAN', (0, -1), (5, -1)),  # Merge empty cells in totals row
    ]))
    story.append(items_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Footer
    story.append(Paragraph("Terms & Conditions:", heading_style))
    story.append(Paragraph("1. This is a system generated purchase order.", normal_style))
    story.append(Paragraph("2. Please deliver as per the above mentioned schedule.", normal_style))
    story.append(Paragraph("3. All disputes subject to local jurisdiction.", normal_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Signature
    story.append(Paragraph("Authorized Signature", normal_style))
    story.append(Paragraph("_____________________", normal_style))
    story.append(Paragraph(f"Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}", normal_style))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer

def generate_vendor_pdf(vendor):
    """Generate PDF for Vendor Registration"""
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=72)
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a237e'),
        alignment=TA_CENTER,
        spaceAfter=10
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a237e'),
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=10
    )
    
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        spaceAfter=4
    )
    
    value_style = ParagraphStyle(
        'Value',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#000000'),
        spaceAfter=4
    )
    
    story = []
    
    # Title
    story.append(Paragraph("VENDOR REGISTRATION CERTIFICATE", title_style))
    story.append(Paragraph("Purchase Order System", subtitle_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Registration Number Box
    reg_data = [
        ['REGISTRATION NO.', vendor.registration_no or 'Not Assigned']
    ]
    reg_table = Table(reg_data, colWidths=[2*inch, 3*inch])
    reg_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
        ('ALIGN', (1, 0), (1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#1a237e')),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
        ('BACKGROUND', (1, 0), (1, 0), colors.HexColor('#e3f2fd')),
        ('TEXTCOLOR', (1, 0), (1, 0), colors.HexColor('#1a237e')),
        ('GRID', (0, 0), (-1, -1), 2, colors.HexColor('#1a237e')),
    ]))
    story.append(reg_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Vendor Details Section
    story.append(Paragraph("VENDOR DETAILS", heading_style))
    story.append(Spacer(1, 0.1*inch))
    
    # Two column layout for details
    vendor_details = [
        ['Company Name:', vendor.name],
        ['Contact Person:', vendor.contact_person or 'N/A'],
        ['Email:', vendor.email or 'N/A'],
        ['Phone:', vendor.phone or 'N/A'],
        ['Address:', vendor.address or 'N/A'],
        ['GST No.:', vendor.gst_no or 'N/A'],
        ['PAN No.:', vendor.pan_no or 'N/A'],
    ]
    
    vendor_table = Table(vendor_details, colWidths=[2*inch, 3.5*inch])
    vendor_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOLD', (0, 0), (0, -1), 1),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(vendor_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Bank Details Section
    story.append(Paragraph("BANK DETAILS", heading_style))
    story.append(Spacer(1, 0.1*inch))
    
    bank_details = [
        ['Bank Name:', vendor.bank_name or 'N/A'],
        ['Account No.:', vendor.bank_account_no or 'N/A'],
        ['IFSC Code:', vendor.bank_ifsc or 'N/A'],
    ]
    
    bank_table = Table(bank_details, colWidths=[2*inch, 3.5*inch])
    bank_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOLD', (0, 0), (0, -1), 1),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(bank_table)
    story.append(Spacer(1, 0.5*inch))
    
    # Authorised Signatory Section
    story.append(Paragraph("AUTHORISED SIGNATORY", heading_style))
    story.append(Spacer(1, 0.2*inch))
    
    sign_data = [
        ['', ''],
        ['Signature:', '_____________________'],
        ['Name:', '_____________________'],
        ['Designation:', '_____________________'],
        ['Date:', f"{datetime.now().strftime('%d-%m-%Y')}"],
    ]
    
    sign_table = Table(sign_data, colWidths=[2*inch, 3.5*inch])
    sign_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOLD', (0, 0), (0, -1), 1),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (1, 1), (1, 3), 1, colors.black),
    ]))
    story.append(sign_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Footer
    story.append(Paragraph(
        f"Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M:%S')}",
        ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=8,
            textColor=colors.grey,
            alignment=TA_CENTER
        )
    ))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    return buffer