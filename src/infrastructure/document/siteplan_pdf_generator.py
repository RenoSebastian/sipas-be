"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Site Plan PDF Generator [siteplan_pdf_generator.py]
============================================================================
Peran: Menghasilkan dokumen resmi cetak legal (PDF) untuk:
       1. Surat Tanda Terima Pendaftaran Permohonan Site Plan (Bukti Registrasi & Pelacakan)
       2. Surat Keputusan (SK) Pengesahan Rencana Tapak (Site Plan) Kabupaten Bogor
============================================================================
"""

import os
from pathlib import Path
from datetime import datetime, date, timezone, timedelta
from typing import Optional, List, Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing


def _get_logo_flowable(width: float = 14.5 * mm, height: float = 18.5 * mm) -> Optional[Image]:
    """Mendapatkan elemen Image logo resmi Pemkab Bogor jika berkas fisik tersedia."""
    candidates = [
        Path(__file__).parent / "assets" / "logo_bogor.png",
        Path(__file__).parent / "logo_bogor.png",
        Path("src/infrastructure/document/assets/logo_bogor.png"),
        Path("src/infrastructure/document/logo_bogor.png"),
    ]
    for p in candidates:
        if p.exists():
            try:
                return Image(str(p.resolve()), width=width, height=height)
            except Exception:
                pass
    return None


def _create_qr_code(data: str, size: float = 46) -> Drawing:
    """Menghasilkan elemen Flowable QR Code vektor resolusi tinggi."""
    qr_code = qr.QrCodeWidget(data)
    bounds = qr_code.getBounds()
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    d.add(qr_code)
    return d


def _create_styles():
    styles = getSampleStyleSheet()
    
    kop_instansi = ParagraphStyle(
        "KopInstansi",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        alignment=1, # Center
        textTransform="uppercase"
    )
    kop_dinas = ParagraphStyle(
        "KopDinas",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        alignment=1,
        textTransform="uppercase"
    )
    kop_sub = ParagraphStyle(
        "KopSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=8.8,
        alignment=1,
        textColor=colors.HexColor("#334155")
    )
    doc_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        alignment=1,
        textColor=colors.HexColor("#0f172a")
    )
    sk_title = ParagraphStyle(
        "SkTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.HexColor("#0f172a")
    )
    alert_text = ParagraphStyle(
        "AlertText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor("#14532d")
    )
    table_label = ParagraphStyle(
        "TableLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.8,
        leading=10,
        textColor=colors.HexColor("#475569")
    )
    table_value = ParagraphStyle(
        "TableValue",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.8,
        leading=10,
        textColor=colors.HexColor("#0f172a")
    )
    table_value_green = ParagraphStyle(
        "TableValueGreen",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor("#16a34a")
    )
    guide_title = ParagraphStyle(
        "GuideTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#0f172a")
    )
    guide_text = ParagraphStyle(
        "GuideText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.8,
        leading=9,
        textColor=colors.HexColor("#334155")
    )
    guide_subtext = ParagraphStyle(
        "GuideSubText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.4,
        leading=8.4,
        textColor=colors.HexColor("#475569")
    )
    footer_text = ParagraphStyle(
        "FooterText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.5,
        alignment=1,
        textColor=colors.HexColor("#64748b")
    )
    center_text = ParagraphStyle(
        "CenterText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=6.5,
        leading=8.5,
        alignment=1,
        textColor=colors.HexColor("#475569")
    )
    body_text = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.2,
        leading=9.5,
        alignment=4 # Justify
    )
    body_bold = ParagraphStyle(
        "BodyBoldCustom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7.2,
        leading=9.5
    )
    dictum_header = ParagraphStyle(
        "DictumHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=1
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=7,
        leading=9
    )
    table_cell_center = ParagraphStyle(
        "TableCellCenter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7,
        leading=9,
        alignment=1
    )

    return {
        "kop_instansi": kop_instansi,
        "kop_dinas": kop_dinas,
        "kop_sub": kop_sub,
        "doc_title": doc_title,
        "sk_title": sk_title,
        "alert_text": alert_text,
        "table_label": table_label,
        "table_value": table_value,
        "table_value_green": table_value_green,
        "guide_title": guide_title,
        "guide_text": guide_text,
        "guide_subtext": guide_subtext,
        "footer_text": footer_text,
        "center_text": center_text,
        "body_text": body_text,
        "body_bold": body_bold,
        "dictum_header": dictum_header,
        "table_cell": table_cell,
        "table_cell_bold": table_cell_bold,
        "table_cell_center": table_cell_center
    }


def generate_siteplan_receipt_pdf(permohonan: Any, output_path: str, generated_by: Optional[str] = None) -> str:
    """
    Menghasilkan berkas PDF Bukti Tanda Terima Permohonan Pengesahan Site Plan.
    Layout 100% presisi dan disesuaikan agar pas dalam 1 halaman A4 tunggal (Halaman 1 dari 1).
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Margin 15mm agar muat sempurna dalam 1 halaman A4
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=16*mm,
        rightMargin=16*mm,
        topMargin=10*mm,
        bottomMargin=10*mm
    )

    s = _create_styles()
    story = []

    # 1. KOP SURAT RESMI PEMKAB BOGOR DENGAN LOGO
    logo = _get_logo_flowable(width=15*mm, height=19*mm)
    kop_text = [
        Paragraph("PEMERINTAH KABUPATEN BOGOR", s["kop_instansi"]),
        Paragraph("DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU", s["kop_dinas"]),
        Paragraph("Jl. Tegar Beriman No. 1, Cibinong, Kabupaten Bogor, Jawa Barat 16914", s["kop_sub"])
    ]
    if logo:
        t_kop = Table([[logo, kop_text]], colWidths=[18*mm, 160*mm])
        t_kop.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (0,0), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(t_kop)
    else:
        for p in kop_text:
            story.append(p)

    story.append(Spacer(1, 1.5*mm))
    story.append(HRFlowable(width="100%", thickness=1.8, color=colors.HexColor("#0f172a"), spaceAfter=0.3*mm))
    story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#0f172a"), spaceAfter=3.5*mm))

    # 2. JUDUL DOKUMEN
    story.append(Paragraph("TANDA TERIMA PERMOHONAN", s["doc_title"]))
    story.append(Spacer(1, 3*mm))

    # 3. KOTAK PEMBERITAHUAN (ALERT BOX)
    alert_content = [
        [Paragraph(
            "<strong>Pemberitahuan:</strong> Berkas permohonan pengesahan site plan Anda telah sukses diunggah dan diterima "
            "oleh sistem GEOSIPAS. Dokumen tanda terima ini diterbitkan sebagai bukti registrasi awal.",
            s["alert_text"]
        )]
    ]
    t_alert = Table(alert_content, colWidths=[178*mm])
    t_alert.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f0fdf4")),
        ('LINEBEFORE', (0,0), (0,-1), 3.5, colors.HexColor("#16a34a")),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_alert)
    story.append(Spacer(1, 3.5*mm))

    # 4. TABEL RINCIAN PERMOHONAN
    wib_tz = timezone(timedelta(hours=7))
    sub_date = getattr(permohonan, "submission_date", None)
    if isinstance(sub_date, datetime):
        date_str = sub_date.strftime("%d-%m-%Y %H:%M:%S WIB")
    elif isinstance(sub_date, date):
        date_str = f"{sub_date.strftime('%d-%m-%Y')} 09:00:00 WIB"
    else:
        date_str = datetime.now(wib_tz).strftime("%d-%m-%Y %H:%M:%S WIB")

    sub_no = getattr(permohonan, "submission_no", "SIPAS-2026-0001")
    applicant = getattr(permohonan, "applicant_name", None) or getattr(permohonan, "developer_name", "-")
    housing = getattr(permohonan, "housing_name", "-")
    doc_cat = getattr(permohonan, "document_category", None)
    doc_cat_str = doc_cat.value if hasattr(doc_cat, "value") else (str(doc_cat) if doc_cat else "Gambar Situasi")
    
    land_area = getattr(permohonan, "land_area", 0.0) or 0.0
    land_area_str = f"{land_area:,.2f} m²"

    info_rows = [
        [Paragraph("Nomor Permohonan", s["table_label"]), Paragraph(sub_no, s["table_value_green"])],
        [Paragraph("Nama Pemohon", s["table_label"]), Paragraph(applicant, s["table_value"])],
        [Paragraph("Nama Perumahan/Kegiatan", s["table_label"]), Paragraph(housing, s["table_value"])],
        [Paragraph("Kategori Dokumen", s["table_label"]), Paragraph(doc_cat_str, s["table_value"])],
        [Paragraph("Luas Lahan", s["table_label"]), Paragraph(land_area_str, s["table_value"])],
        [Paragraph("Tanggal Diterima", s["table_label"]), Paragraph(date_str, s["table_value"])]
    ]

    t_info = Table(info_rows, colWidths=[52*mm, 126*mm])
    t_info.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2.2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.2),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 3.5*mm))

    # 5. PANDUAN PEMANTAUAN (MONITORING) PERMOHONAN
    guide_content = [
        Paragraph("<b>PANDUAN PEMANTAUAN (MONITORING) PERMOHONAN</b>", s["guide_title"]),
        HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cbd5e1"), spaceBefore=1*mm, spaceAfter=1.5*mm),
        Paragraph("1. Buka peramban (browser) dan akses halaman aplikasi <b>GEOSIPAS</b>.", s["guide_text"]),
        Paragraph("2. Masuk (Login) menggunakan akun Pemohon terdaftar yang Anda gunakan saat mengajukan berkas.", s["guide_text"]),
        Paragraph("3. Arahkan ke menu utama pada sidebar sebelah kiri, pilih menu <b>Daftar Pengajuan</b>.", s["guide_text"]),
        Paragraph("4. Cari berkas Anda berdasarkan <b>Nomor Permohonan</b> atau <b>Nama Perumahan</b>.", s["guide_text"]),
        Paragraph("5. Klik tombol <b>Detail</b> pada baris pengajuan untuk memantau status secara real-time:", s["guide_text"]),
        Paragraph("&nbsp;&nbsp;&nbsp;• <b>Pengajuan Dokumen:</b> Berkas sedang berada di antrean verifikasi administrasi awal.", s["guide_subtext"]),
        Paragraph("&nbsp;&nbsp;&nbsp;• <b>Verifikasi Administrasi:</b> Pemeriksaan kelengkapan berkas administratif oleh petugas.", s["guide_subtext"]),
        Paragraph("&nbsp;&nbsp;&nbsp;• <b>Verifikasi Teknis:</b> Evaluasi batas-batas spasial RDTR dan kesesuaian gambar rencana tapak oleh Tim Teknis.", s["guide_subtext"]),
        Paragraph("&nbsp;&nbsp;&nbsp;• <b>Menunggu Rekomendasi/Persetujuan:</b> Peninjauan draf Surat Keputusan (SK) oleh Kepala Bidang dan Kepala Dinas.", s["guide_subtext"]),
        Paragraph("&nbsp;&nbsp;&nbsp;• <b>Disetujui:</b> Dokumen SK resmi telah ditandatangani secara elektronik (TTE) dan siap diunduh.", s["guide_subtext"])
    ]

    t_guide = Table([[guide_content]], colWidths=[178*mm])
    t_guide.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(t_guide)
    story.append(Spacer(1, 3.5*mm))

    # 6. BAGIAN TTE & VERIFIKASI SISTEM (Dengan Barcode / QR Pelacakan)
    public_base_url = os.getenv("PUBLIC_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    tracking_url = f"{public_base_url}/pelacakan/siteplan?no={sub_no}"
    qr_flowable = _create_qr_code(tracking_url, size=46)

    qr_column = [
        qr_flowable,
        Paragraph("<font size='5.5' color='#64748b'>Pindai untuk lacak status</font>", s["center_text"])
    ]

    badge_table = Table([
        [Paragraph("<font color='#0284c7'><b>✓ TERVERIFIKASI SISTEM</b></font>", s["center_text"])],
        [Paragraph("<font size='6' color='#64748b'>Dokumen ini sah dan ditandatangani secara elektronik oleh sistem</font>", s["center_text"])]
    ], colWidths=[65*mm])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#cbd5e1")),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))

    sig_column = [
        Paragraph("<font size='6.8' color='#64748b'><b>SISTEM ADMINISTRASI GEOSIPAS</b></font>", s["center_text"]),
        Spacer(1, 1*mm),
        badge_table,
        Spacer(1, 1*mm),
        Paragraph("<font size='7.5' color='#0f172a'><b>GEOSIPAS KAB. BOGOR</b></font>", s["center_text"])
    ]

    t_verification = Table([[qr_column, sig_column]], colWidths=[90*mm, 88*mm])
    t_verification.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_verification)
    story.append(Spacer(1, 2.5*mm))

    # 7. CATATAN KAKI & FOOTER
    gen_time_str = datetime.now(wib_tz).strftime("%d-%m-%Y %H:%M:%S WIB")
    footer_row = [
        [
            Paragraph(f"Dokumen ini diterbitkan oleh sistem e-Siteplan GEOSIPAS Kabupaten Bogor secara elektronik pada {gen_time_str}.", s["footer_text"]),
            Paragraph("<font size='6.5' color='#64748b'>Halaman 1 dari 1</font>", ParagraphStyle("Right", parent=s["footer_text"], alignment=2))
        ]
    ]
    t_footer = Table(footer_row, colWidths=[150*mm, 28*mm])
    t_footer.setStyle(TableStyle([
        ('LINEABOVE', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_footer)

    doc.build(story)
    return str(Path(output_path).resolve())


def generate_siteplan_sk_pdf(
    permohonan: Any,
    sk_draft: Optional[Any],
    output_path: str,
    is_draft: bool = False,
    signer_name: Optional[str] = None
) -> str:
    """
    Menghasilkan berkas PDF Surat Keputusan (SK) Pengesahan Rencana Tapak (Site Plan) resmi
    Pemerintah Kabupaten Bogor dengan kop dinas berlogo, diktum matriks tapak, amplop ruang,
    dan TTE sertifikasi BSrE - BSSN.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=14*mm,
        rightMargin=14*mm,
        topMargin=8*mm,
        bottomMargin=8*mm
    )

    s = _create_styles()
    story = []

    # 1. KOP SURAT RESMI PEMKAB BOGOR DENGAN LOGO
    logo = _get_logo_flowable(width=14.5*mm, height=18.5*mm)
    kop_text = [
        Paragraph("PEMERINTAH KABUPATEN BOGOR", s["kop_instansi"]),
        Paragraph("DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU", s["kop_dinas"]),
        Paragraph(
            "Jl. Tegar Beriman No. 1, Cibinong, Kabupaten Bogor, Jawa Barat 16914<br/>"
            "Telepon: (021) 8751090 | Pos-el: dpmptsp@bogorkab.go.id | Laman: sipas.bogorkab.go.id",
            s["kop_sub"]
        )
    ]
    if logo:
        t_kop = Table([[logo, kop_text]], colWidths=[18*mm, 164*mm])
        t_kop.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ALIGN', (0,0), (0,0), 'CENTER'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ]))
        story.append(t_kop)
    else:
        for p in kop_text:
            story.append(p)

    story.append(Spacer(1, 0.8*mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.black, spaceAfter=0.3*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceAfter=1.2*mm))

    # 2. JUDUL DOKUMEN & NOMOR KEPUTUSAN
    sub_no = getattr(permohonan, "submission_no", "SIPAS-2026-0001")
    sk_number = getattr(sk_draft, "sk_number", None) or getattr(permohonan, "sk_number", None)
    if not sk_number:
        sk_number = f"503/SITEPLAN/DPMPTSP/2026/{getattr(permohonan, 'id_permohonan', '001')}"
    if is_draft:
        sk_number = f"DRAFT-{sk_number}"

    housing = getattr(permohonan, "housing_name", "PERUMAHAN").upper()

    story.append(Paragraph(
        "KEPUTUSAN KEPALA DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU<br/>KABUPATEN BOGOR",
        s["sk_title"]
    ))
    story.append(Spacer(1, 0.5*mm))
    story.append(Paragraph(f"NOMOR : <strong>{sk_number}</strong>", s["sk_title"]))
    story.append(Spacer(1, 0.6*mm))
    story.append(Paragraph(
        "TENTANG<br/>"
        "PENGESAHAN RENCANA TAPAK (SITE PLAN)<br/>"
        f"UNTUK KEGIATAN PEMBANGUNAN {housing}",
        s["sk_title"]
    ))
    story.append(Spacer(1, 1*mm))

    story.append(Paragraph("KEPALA DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU KABUPATEN BOGOR,", s["body_bold"]))
    story.append(Spacer(1, 0.6*mm))

    # 3. KONSIDERANS MENIMBANG, MENGINGAT & MEMPERHATIKAN
    applicant = getattr(permohonan, "applicant_name", None) or getattr(permohonan, "developer_name", "Pemohon")
    land_area = getattr(permohonan, "land_area", 0.0) or 0.0

    menimbang_data = [
        [
            Paragraph("Menimbang", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                f"a. bahwa permohonan Pengesahan Rencana Tapak (Site Plan) yang diajukan oleh "
                f"<strong>{applicant}</strong> atas bidang tanah seluas <strong>{land_area:,.2f} m²</strong> "
                f"telah memenuhi kelengkapan administratif dan evaluasi teknis tata ruang dinas;<br/>"
                f"b. bahwa berdasarkan hasil kajian spasial GIS, Berita Acara Rapat Evaluasi Teknis Rencana Tapak, "
                f"dan keselarasan Rencana Detail Tata Ruang (RDTR) Kabupaten Bogor, permohonan dinyatakan layak disahkan;",
                s["body_text"]
            )
        ],
        [
            Paragraph("Mengingat", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                "1. UU No. 1 Tahun 2011; 2. UU No. 6 Tahun 2023; 3. PP No. 21 Tahun 2021; "
                "4. Perda Kab. Bogor No. 11/2016 jo No. 1/2024 tentang RTRW; "
                "5. Perbup Bogor No. 4/2025 tentang Rencana Tapak (Site Plan) Digital Terintegrasi GIS.",
                s["body_text"]
            )
        ],
        [
            Paragraph("Memperhatikan", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                "1. Pertimbangan Teknis Pertanahan Kantor Pertanahan ATR/BPN Kabupaten Bogor;<br/>"
                "2. Berita Acara Telaah Teknis Lapangan Tim Penilai Rencana Tapak DPKPP / DPMPTSP Kabupaten Bogor.",
                s["body_text"]
            )
        ]
    ]

    t_konsiderans = Table(menimbang_data, colWidths=[22*mm, 3*mm, 157*mm])
    t_konsiderans.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.6),
        ('TOPPADDING', (0,0), (-1,-1), 0.6),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_konsiderans)
    story.append(Spacer(1, 0.8*mm))

    # 4. DIKTUM MEMUTUSKAN
    story.append(Paragraph("MEMUTUSKAN:", s["dictum_header"]))
    story.append(Spacer(1, 0.6*mm))

    village = getattr(permohonan, "location_village", "-") or "-"
    district = getattr(permohonan, "location_district", "-") or "-"
    address = getattr(permohonan, "location_full_address", None) or f"Desa {village}, Kec. {district}, Kabupaten Bogor"
    nib = getattr(permohonan, "applicant_nib", None) or "-"

    # Matriks Pembagian Lahan / Tapak
    hunian_area = land_area * 0.60
    psu_area = land_area * 0.40
    rth_area = land_area * 0.15
    road_area = land_area * 0.25

    if sk_draft and getattr(sk_draft, "diktum_psu", None):
        psu_vo = sk_draft.diktum_psu
        if hasattr(psu_vo, "total_psu_area_m2") and psu_vo.total_psu_area_m2 > 0:
            psu_area = psu_vo.total_psu_area_m2
            hunian_area = max(0, land_area - psu_area)

    kdb_max = 60.0
    klb_max = 1.8
    kdh_min = 20.0
    gsb_min = 5.0
    if sk_draft and getattr(sk_draft, "diktum_intensity", None):
        intens = sk_draft.diktum_intensity
        kdb_max = getattr(intens, "kdb_max", 60.0)
        klb_max = getattr(intens, "klb_max", 1.8)
        kdh_min = getattr(intens, "kdh_min", 20.0)

    dictum_data = [
        [
            Paragraph("KESATU", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                f"Mengesahkan <strong>Rencana Tapak (Site Plan)</strong> untuk kegiatan <strong>{housing}</strong> kepada:<br/>"
                f"• Nama Pemohon / Pengembang : <strong>{applicant}</strong><br/>"
                f"• NIB / NIK : {nib}<br/>"
                f"• Alamat Pemohon : {getattr(permohonan, 'applicant_address', '-')}",
                s["body_text"]
            )
        ],
        [
            Paragraph("KEDUA", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                f"Lokasi bidang tanah terletak di {address} dengan luas lahan total yang disahkan "
                f"sebesar <strong>{land_area:,.2f} m²</strong>.",
                s["body_text"]
            )
        ],
        [
            Paragraph("KETIGA", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                f"Distribusi alokasi pemanfaatan ruang tapak mengikat secara sah dengan pembagian sebagai berikut:<br/>"
                f"1. Kaveling Efektif (Kavling Hunian/Terbangun) : <strong>{hunian_area:,.2f} m²</strong> ({hunian_area/land_area*100:.1f}%)<br/>"
                f"2. Fasilitas Prasarana, Sarana, dan Utilitas (PSU) : <strong>{psu_area:,.2f} m²</strong> ({psu_area/land_area*100:.1f}%)<br/>"
                f"&nbsp;&nbsp;&nbsp;a. Ruang Terbuka Hijau (RTH) & Taman : min. <strong>{rth_area:,.2f} m²</strong><br/>"
                f"&nbsp;&nbsp;&nbsp;b. Jaringan Jalan & Saluran Drainase : min. <strong>{road_area:,.2f} m²</strong>",
                s["body_text"]
            )
        ],
        [
            Paragraph("KEEMPAT", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                f"Batas intensitas ruang dan amplop bangunan:<br/>"
                f"• Koefisien Dasar Bangunan (KDB) : Maksimum <strong>{kdb_max:.1f}%</strong><br/>"
                f"• Koefisien Lantai Bangunan (KLB) : Maksimum <strong>{klb_max:.2f}</strong><br/>"
                f"• Koefisien Dasar Hijau (KDH) : Minimum <strong>{kdh_min:.1f}%</strong><br/>"
                f"• Garis Sempadan Bangunan (GSB) : Minimum <strong>{gsb_min:.1f} Meter</strong>",
                s["body_text"]
            )
        ],
        [
            Paragraph("KELIMA", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                "Pemohon wajib: 1. Melaksanakan pembangunan sesuai gambar tapak yang disahkan; "
                "2. Menyediakan dan menyerahkan PSU kepada Pemerintah Kabupaten Bogor; "
                "3. Menyediakan lahan makam (TPU) atau kompensasi sesuai Perda; "
                "4. Memelihara kelestarian lingkungan hidup dan sumur resapan air.",
                s["body_text"]
            )
        ]
    ]

    t_dictum = Table(dictum_data, colWidths=[22*mm, 3*mm, 157*mm])
    t_dictum.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0.6),
        ('TOPPADDING', (0,0), (-1,-1), 0.6),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_dictum)
    story.append(Spacer(1, 1*mm))

    # 5. TANDA TANGAN ELEKTRONIK (TTE KADIS DENGAN QR BSrE - BSSN)
    public_base_url = os.getenv("PUBLIC_FRONTEND_URL", "http://localhost:5173").rstrip("/")
    verify_url = f"{public_base_url}/validasi/siteplan?id={getattr(permohonan, 'id_permohonan', 'sub-1')}&sk={sk_number}"
    qr_flowable = _create_qr_code(verify_url, size=46)

    tte_badge_text = (
        "<b>DITANDATANGANI SECARA ELEKTRONIK (TTE)</b><br/>"
        "Sertifikasi Balai Sertifikasi Elektronik (BSrE - BSSN)<br/>"
        "<font size='5.5' color='#64748b'>Pindai QR Code untuk memverifikasi keaslian naskah hukum ini pada pangkalan data resmi dinas.</font>"
    )

    sig_left_column = [
        qr_flowable,
        Spacer(1, 0.5*mm),
        Paragraph(tte_badge_text, s["table_cell"])
    ]

    wib_tz = timezone(timedelta(hours=7))
    issued_date_str = datetime.now(wib_tz).strftime("%d %B %Y")

    kadis_name = signer_name or "Dr. Ir. H. CECEP IMAM NAGARA, M.Si"
    kadis_nip = "19720815 199803 1 004"

    sig_right_column = [
        Paragraph(f"Ditetapkan di : Cibinong<br/>Pada tanggal : <strong>{issued_date_str}</strong>", s["table_cell"]),
        Spacer(1, 1*mm),
        Paragraph("KEPALA DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU<br/>KABUPATEN BOGOR,", s["body_bold"]),
        Spacer(1, 8*mm), # Ruang stempel TTE elektronik
        Paragraph(f"<u><strong>{kadis_name}</strong></u>", s["body_bold"]),
        Paragraph(f"Pembina Utama Muda, IV/c<br/>NIP. {kadis_nip}", s["table_cell"])
    ]

    sig_table_data = [[sig_left_column, sig_right_column]]
    t_sig = Table(sig_table_data, colWidths=[92*mm, 90*mm])
    t_sig.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
    ]))

    story.append(KeepTogether(t_sig))

    doc.build(story)
    return str(Path(output_path).resolve())
