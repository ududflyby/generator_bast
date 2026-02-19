import streamlit as st
import pandas as pd
from datetime import datetime, time
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
import io

st.set_page_config(page_title="BAST Generator", layout="wide")
st.title("📦 Berita Acara Serah Terima (BAST) Generator")

# -----------------------
# Header Inputs
# -----------------------
st.header("Input Data Header")
col1, col2 = st.columns(2)

with col1:
    tanggal_only = st.date_input("Tanggal", datetime.now().date())
    warehouse = st.text_input("Warehouse")
    courier = st.text_input("Courier Name")

with col2:
    waktu_only = st.time_input("Waktu", value=time(0, 0))
    driver = st.text_input("Driver Name")
    police = st.text_input("Police Number")

def make_datetime(date_obj, time_obj):
    return datetime(date_obj.year, date_obj.month, date_obj.day,
                    time_obj.hour, time_obj.minute, time_obj.second)

tanggal = make_datetime(tanggal_only, waktu_only)

# -----------------------
# Upload
# -----------------------
st.header("Upload Excel / CSV Data")

header_fields = {
    "Warehouse": warehouse,
    "Courier Name": courier,
    "Driver Name": driver,
    "Police Number": police
}

missing = [f for f,v in header_fields.items() if not str(v).strip()]
if missing:
    st.warning(f"⚠️ Lengkapi header: {', '.join(missing)}")
    uploaded_file = None
else:
    uploaded_file = st.file_uploader("Pilih file", type=["xlsx", "xls", "csv"])

# -----------------------
# Validation
# -----------------------
def validate_file(df):
    errors = []
    if df is None or df.empty:
        errors.append("File kosong.")
        return False, errors

    if "KOLI QTY" not in df.columns:
        errors.append("Kolom KOLI QTY wajib ada.")

    return len(errors) == 0, errors


# -----------------------
# PDF Canvas + Page Numbers
# -----------------------
class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self.draw_page_number(total)
            super().showPage()
        super().save()

    def draw_page_number(self, total):
        page = self.getPageNumber()
        text = f"{page}/{total}"
        self.setFont("Helvetica", 9)
        self.drawRightString(A4[0] - 40, 0.5 * inch, text)


# -----------------------
# PDF Generator
# -----------------------
def generate_pdf(df, tanggal, warehouse, courier, driver, police, total_koli):
    buffer = io.BytesIO()

    margin = 0.5 * inch
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=margin, rightMargin=margin,
        topMargin=margin, bottomMargin=margin
    )

    styles = getSampleStyleSheet()
    elements = []

    # Title
    title_style = ParagraphStyle(
        "CenteredTitle",
        parent=styles["Title"],
        alignment=1,
        fontSize=18,
        spaceAfter=10
    )
    elements.append(Paragraph("<b>BERITA ACARA SERAH TERIMA</b>", title_style))
    elements.append(Spacer(1, 10))

    # Header text
    tanggal_str = tanggal.strftime('%d/%m/%Y %H:%M:%S')
    header_left = f"""
        <b>Tanggal:</b> {tanggal_str}<br/>
        <b>Warehouse:</b> {warehouse}<br/>
        <b>Courier Name:</b> {courier}<br/>
        <b>Driver Name:</b> {driver}<br/>
        <b>Police Number:</b> {police}<br/>
    """

    # -----------------------
    # TOTAL KOLI BOX
    # -----------------------
    koli_style = ParagraphStyle(
        "Koli",
        parent=styles["Normal"],
        alignment=1,
        fontSize=20,
        leading=22
    )

    label_style = ParagraphStyle(
        "Label",
        parent=styles["Normal"],
        alignment=1,
        fontSize=12,
        leading=14
    )

    total_box = Table(
        [
            [Paragraph("<b>TOTAL KOLI</b>", label_style)],
            [Paragraph(f"<b>{total_koli}</b>", koli_style)]
        ],
        colWidths=[150],
        rowHeights=[25, 35]
    )

    total_box.setStyle(TableStyle([
        ("BOX", (0,0), (-1,-1), 2, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.whitesmoke),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2)
    ]))

    page_width = A4[0] - (margin*2)
    header_width = page_width - 150

    header_table = Table([[Paragraph(header_left, styles["Normal"]), total_box]],
                         colWidths=[header_width, 150])

    elements.append(header_table)
    elements.append(Spacer(1, 10))

    # Clean DF
    df_clean = df.copy().fillna("")
    expected_order = ["NO", "DELIVERY ORDER", "AIRWAYBILL", "STATE", "PROVIDER", "KOLI QTY"]
    df_clean = df_clean[expected_order]

    header = list(df_clean.columns)
    data = df_clean.values.tolist()

    # Custom width mapping (%)
    column_width_percent = {
        "NO": 0.05,
        "DELIVERY ORDER": 0.20,
        "AIRWAYBILL": 0.25,
        "STATE": 0.10,
        "PROVIDER": 0.20,
        "KOLI QTY": 0.08
    }

    remaining_percent = 1.0 - sum(column_width_percent.get(col, 0) for col in header)
    undefined_cols = [col for col in header if col not in column_width_percent]

    col_widths = []
    for col in header:
        if col in column_width_percent:
            col_widths.append(page_width * column_width_percent[col])
        else:
            col_widths.append(page_width * (remaining_percent / len(undefined_cols)))

    # -----------------------
    # TABLE DATA (COMPACT VERSION)
    # -----------------------
    table = Table([header] + data, repeatRows=1, colWidths=col_widths)

    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.darkgrey),
        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
        ("GRID", (0,0), (-1,-1), 0.3, colors.black),
        ("FONTSIZE", (0,0), (-1,-1), 8),        # Font lebih kecil
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("LEFTPADDING", (0,0), (-1,-1), 1),    # Padding lebih kecil
        ("RIGHTPADDING", (0,0), (-1,-1), 1),
        ("TOPPADDING", (0,0), (-1,-1), 1),
        ("BOTTOMPADDING", (0,0), (-1,-1), 1)
    ]))

    elements.append(table)
    elements.append(Spacer(1, 15))

    # -----------------------
    # Signature section with centered note
    # -----------------------
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Normal"],
        alignment=1,  # center
        fontSize=8,
        leading=10
    )

    sign = Table(
        [
            ["Diperiksa oleh", "Diserahkan oleh", "Diterima oleh"],
            ["", "", ""], ["", "", ""], ["", "", ""],
            ["__________________", "__________________", "__________________"],
            ["(Security WH)", "(Dispatcher WH)", "(Driver Courier)"],
            [Paragraph("* BAST ini sebagai bukti bahwa paket sudah diserahkan dengan kondisi baik dan jumlah koli sesuai.", note_style)]
        ],
        colWidths=[page_width/3]*3
    )
    sign.setStyle(TableStyle([
        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("TOPPADDING", (0,0), (-1,-1), 4)
    ]))

    elements.append(sign)

    doc.build(elements, canvasmaker=NumberedCanvas)

    buffer.seek(0)
    return buffer


# -----------------------
# Handle Upload
# -----------------------
if uploaded_file:
    try:
        df = pd.read_csv(uploaded_file) if uploaded_file.name.lower().endswith("csv") else pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"❌ Gagal membaca file: {e}")
        st.stop()

    valid, errors = validate_file(df)
    if not valid:
        for err in errors:
            st.error("• " + err)
    else:
        total_koli = int(pd.to_numeric(df["KOLI QTY"], errors="coerce").fillna(0).sum())
        st.dataframe(df, use_container_width=True)

        if st.button("Generate PDF"):
            pdf_buffer = generate_pdf(df, tanggal, warehouse, courier, driver, police, total_koli)
            fname = f"BAST_{warehouse}_{courier}_{police}_{tanggal.strftime('%Y%m%d_%H%M%S')}.pdf"
            st.download_button("📥 Download PDF BAST", data=pdf_buffer, file_name=fname, mime="application/pdf")
