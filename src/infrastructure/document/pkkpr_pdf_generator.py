"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — PKKPR PDF Generator [pkkpr_pdf_generator.py]
============================================================================
Peran: Menghasilkan dokumen resmi cetak legal (PDF) untuk:
       1. Surat Keputusan (SK) PKKPR Resmi Kabupaten Bogor (dengan TTE & Amplop Ruang)
       2. Lembar Tanda Terima Pendaftaran Permohonan PKKPR (Bukti Registrasi)
============================================================================
"""

import os
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List, Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm, mm


def _create_styles():
    styles = getSampleStyleSheet()
    
    kop_instansi = ParagraphStyle(
        "KopInstansi",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        alignment=1, # Center
        textTransform="uppercase"
    )
    kop_dinas = ParagraphStyle(
        "KopDinas",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        alignment=1,
        textTransform="uppercase"
    )
    kop_sub = ParagraphStyle(
        "KopSub",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=7.5,
        leading=10,
        alignment=1
    )
    doc_title = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=10.5,
        leading=13.5,
        alignment=1
    )
    body_text = ParagraphStyle(
        "BodyTextCustom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        alignment=4 # Justify
    )
    body_bold = ParagraphStyle(
        "BodyBoldCustom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12
    )
    dictum_header = ParagraphStyle(
        "DictumHeader",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        alignment=1
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11
    )
    table_cell_center = ParagraphStyle(
        "TableCellCenter",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        alignment=1
    )

    return {
        "kop_instansi": kop_instansi,
        "kop_dinas": kop_dinas,
        "kop_sub": kop_sub,
        "doc_title": doc_title,
        "body_text": body_text,
        "body_bold": body_bold,
        "dictum_header": dictum_header,
        "table_cell": table_cell,
        "table_cell_bold": table_cell_bold,
        "table_cell_center": table_cell_center
    }


def generate_pkkpr_sk_pdf(pkkpr: Any, output_path: str) -> str:
    """
    Menghasilkan berkas PDF Surat Keputusan (SK) PKKPR resmi berstandar Pemkab Bogor.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=18*mm,
        rightMargin=18*mm,
        topMargin=12*mm,
        bottomMargin=12*mm
    )

    s = _create_styles()
    story = []

    # 1. KOP SURAT RESMI PEMKAB BOGOR
    story.append(Paragraph("PEMERINTAH KABUPATEN BOGOR", s["kop_instansi"]))
    story.append(Paragraph("DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU", s["kop_dinas"]))
    story.append(Paragraph(
        "Jl. Raya Tegar Beriman No. 25, Cibinong, Kabupaten Bogor, Jawa Barat 16914<br/>"
        "Telepon: (021) 8751090 | Pos-el: dpmptsp@bogorkab.go.id | Laman: sipas.bogorkab.go.id",
        s["kop_sub"]
    ))
    story.append(Spacer(1, 1.5*mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.black, spaceAfter=0.5*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.black, spaceAfter=3*mm))

    # 2. JUDUL DOKUMEN & NOMOR KEPUTUSAN
    sk_no = getattr(pkkpr, "sk_number", None) or f"DRAFT-{getattr(pkkpr, 'submission_no', 'PKKPR')}"
    is_approved = getattr(pkkpr, "status", "") == "DISETUJUI"
    
    story.append(Paragraph(
        "KEPUTUSAN KEPALA DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU<br/>KABUPATEN BOGOR",
        s["doc_title"]
    ))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(f"NOMOR : <strong>{sk_no}</strong>", s["doc_title"]))
    story.append(Spacer(1, 1.5*mm))
    story.append(Paragraph(
        "TENTANG<br/>"
        "PERSETUJUAN KESESUAIAN KEGIATAN PEMANFAATAN RUANG (PKKPR)<br/>"
        f"UNTUK KEGIATAN {getattr(pkkpr, 'activity_description', '').upper()}",
        s["doc_title"]
    ))
    story.append(Spacer(1, 3.5*mm))

    story.append(Paragraph("KEPALA DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU KABUPATEN BOGOR,", s["body_bold"]))
    story.append(Spacer(1, 1.5*mm))

    # 3. KONSIDERANS MENIMBANG & MENGINGAT
    fpr_reviews = getattr(pkkpr, "fpr_reviews", [])
    fpr_info = fpr_reviews[0] if fpr_reviews else None
    fpr_report_no = getattr(fpr_info, "official_report_no", "503/BA-FPR/2026")
    ptp_bpn = getattr(fpr_info, "ptp_bpn_number", None) or getattr(pkkpr, "certificate_number", "PTP-BPN/BOGOR/2026")

    menimbang_data = [
        [
            Paragraph("Menimbang", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                f"a. bahwa permohonan Persetujuan Kesesuaian Kegiatan Pemanfaatan Ruang yang diajukan oleh "
                f"<strong>{getattr(pkkpr, 'applicant_name', '-')}</strong> telah memenuhi persyaratan administratif dan verifikasi formal dinas;<br/>"
                f"b. bahwa berdasarkan Risalah Sidang Komite Forum Penataan Ruang (FPR) Kabupaten Bogor Nomor "
                f"<strong>{fpr_report_no}</strong> dan Pertimbangan Teknis Pertanahan Kantor Pertanahan ATR/BPN Kabupaten Bogor Nomor <strong>{ptp_bpn}</strong>, "
                f"rencana pemanfaatan ruang dinyatakan selaras dengan pola tata ruang daerah;<br/>"
                f"c. bahwa berdasarkan pertimbangan sebagaimana dimaksud pada huruf a dan huruf b, perlu menetapkan Keputusan Kepala Dinas.",
                s["body_text"]
            )
        ],
        [
            Paragraph("Mengingat", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                "1. Undang-Undang Nomor 6 Tahun 2023 tentang Penetapan Perppu Cipta Kerja;<br/>"
                "2. Peraturan Pemerintah Nomor 21 Tahun 2021 tentang Penyelenggaraan Penataan Ruang;<br/>"
                "3. Peraturan Menteri ATR/BPN Nomor 13 Tahun 2021 tentang Pelaksanaan KKPR;<br/>"
                "4. Peraturan Daerah Kabupaten Bogor Nomor 11 Tahun 2016 jo Nomor 1 Tahun 2024 tentang RTRW Kabupaten Bogor;<br/>"
                "5. Peraturan Bupati Bogor Nomor 4 Tahun 2025 tentang Pedoman Penyelenggaraan Rencana Tapak (Site Plan) Digital Terpadu.",
                s["body_text"]
            )
        ]
    ]

    t_konsiderans = Table(menimbang_data, colWidths=[24*mm, 4*mm, 146*mm])
    t_konsiderans.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_konsiderans)
    story.append(Spacer(1, 2*mm))

    # 4. DIKTUM MEMUTUSKAN
    story.append(Paragraph("MEMUTUSKAN:", s["dictum_header"]))
    story.append(Spacer(1, 1.5*mm))

    proposed_m2 = getattr(pkkpr, "proposed_land_area_m2", 0)
    approved_m2 = getattr(pkkpr, "approved_land_area_m2", None) or proposed_m2
    kdb_max = getattr(pkkpr, "approved_kdb_max", 60.0) or 60.0
    klb_max = getattr(pkkpr, "approved_klb_max", 1.8) or 1.8
    kdh_min = getattr(pkkpr, "approved_kdh_min", 20.0) or 20.0
    gsb_min = getattr(pkkpr, "approved_gsb_min", 5.0) or 5.0
    max_floors = getattr(pkkpr, "approved_max_floors", 4) or 4
    zone_code = getattr(pkkpr, "spatial_zone_code", "-") or "-"
    zone_name = getattr(pkkpr, "spatial_zone_name", "-") or "Zona Peruntukan Permukiman"

    dictum_data = [
        [
            Paragraph("KESATU", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                f"Memberikan <strong>Persetujuan Kesesuaian Kegiatan Pemanfaatan Ruang (PKKPR)</strong> kepada:<br/>"
                f"• Nama Pemohon / Perusahaan : <strong>{getattr(pkkpr, 'applicant_name', '-')}</strong><br/>"
                f"• Jenis Pemohon : {getattr(pkkpr, 'applicant_type', 'BADAN_USAHA')}<br/>"
                f"• NIB / NIK : {getattr(pkkpr, 'applicant_nib', None) or getattr(pkkpr, 'applicant_nik', '-')}<br/>"
                f"• Nomor Pokok Wajib Pajak (NPWP) : {getattr(pkkpr, 'applicant_npwp', '-')}<br/>"
                f"• Rencana Kegiatan : {getattr(pkkpr, 'activity_description', '-')}<br/>"
                f"• Kode KBLI : <strong>{getattr(pkkpr, 'kbli_code', '-')}</strong>",
                s["body_text"]
            )
        ],
        [
            Paragraph("KEDUA", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                f"Menetapkan lokasi dan status penguasaan bidang tanah yang disetujui:<br/>"
                f"• Lokasi : {getattr(pkkpr, 'location_address', '-')}<br/>"
                f"• Desa/Kelurahan : {getattr(pkkpr, 'location_village', '-')}, Kecamatan {getattr(pkkpr, 'location_district', '-')}<br/>"
                f"• Bukti Hak Atas Tanah : {getattr(pkkpr, 'land_ownership_status', 'SHM')} No. {getattr(pkkpr, 'certificate_number', '-')} "
                f"a.n. {getattr(pkkpr, 'certificate_owner', getattr(pkkpr, 'applicant_name', '-'))}<br/>"
                f"• Luas Lahan Dimohonkan : {proposed_m2:,.2f} m²<br/>"
                f"• <strong>Luas Lahan Disetujui : {approved_m2:,.2f} m²</strong>",
                s["body_text"]
            )
        ],
        [
            Paragraph("KETIGA", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                "Menetapkan batas amplop parameter teknis pemanfaatan ruang (Spatial Envelope) yang "
                "<strong>mengikat dan wajib dipatuhi secara absolut</strong> dalam penyusunan Rencana Tapak (Site Plan):",
                s["body_text"]
            )
        ]
    ]

    t_dictum = Table(dictum_data, colWidths=[24*mm, 4*mm, 146*mm])
    t_dictum.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_dictum)
    story.append(Spacer(1, 1.5*mm))

    # TABEL AMPLOP RUANG DIKTUM KETIGA
    table_envelope_data = [
        [
            Paragraph("No", s["table_cell_bold"]),
            Paragraph("Parameter Tata Ruang", s["table_cell_bold"]),
            Paragraph("Ketentuan Batas SK PKKPR", s["table_cell_bold"]),
            Paragraph("Keterangan Kepatuhan", s["table_cell_bold"])
        ],
        [
            Paragraph("1", s["table_cell_center"]),
            Paragraph("Pola / Zona Ruang RDTR", s["table_cell"]),
            Paragraph(f"<strong>{zone_code}</strong> ({zone_name})", s["table_cell"]),
            Paragraph("Sesuai Rencana Detail Tata Ruang", s["table_cell"])
        ],
        [
            Paragraph("2", s["table_cell_center"]),
            Paragraph("Koefisien Dasar Bangunan (KDB)", s["table_cell"]),
            Paragraph(f"<strong>Maksimal {kdb_max:.1f}%</strong>", s["table_cell"]),
            Paragraph("Batas maksimal tutupan tapak terbangun", s["table_cell"])
        ],
        [
            Paragraph("3", s["table_cell_center"]),
            Paragraph("Koefisien Lantai Bangunan (KLB)", s["table_cell"]),
            Paragraph(f"<strong>Maksimal {klb_max:.2f}</strong>", s["table_cell"]),
            Paragraph("Batas rasio total luas lantai", s["table_cell"])
        ],
        [
            Paragraph("4", s["table_cell_center"]),
            Paragraph("Koefisien Daerah Hijau (KDH)", s["table_cell"]),
            Paragraph(f"<strong>Minimal {kdh_min:.1f}%</strong>", s["table_cell"]),
            Paragraph("Wajib berupa resapan tanah terbuka", s["table_cell"])
        ],
        [
            Paragraph("5", s["table_cell_center"]),
            Paragraph("Garis Sempadan Bangunan (GSB)", s["table_cell"]),
            Paragraph(f"<strong>Minimal {gsb_min:.1f} meter</strong>", s["table_cell"]),
            Paragraph("Jarak bebas dari as jalan / sempadan", s["table_cell"])
        ],
        [
            Paragraph("6", s["table_cell_center"]),
            Paragraph("Ketinggian Bangunan", s["table_cell"]),
            Paragraph(f"<strong>Maksimal {max_floors} Lantai</strong>", s["table_cell"]),
            Paragraph("Kesesuaian daya dukung kawasan", s["table_cell"])
        ]
    ]

    t_envelope = Table(table_envelope_data, colWidths=[10*mm, 52*mm, 52*mm, 60*mm])
    t_envelope.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2.5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2.5),
    ]))
    story.append(t_envelope)
    story.append(Spacer(1, 2*mm))

    # DIKTUM KEEMPAT & KELIMA
    dictum_closing_data = [
        [
            Paragraph("KEEMPAT", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                "Pemegang Persetujuan ini diwajibkan:<br/>"
                "1. Mengalokasikan lahan untuk Prasarana, Sarana, dan Utilitas Umum (PSU) sekurang-kurangnya 30% s.d. 40% "
                "dari total luas lahan yang disetujui sesuai Perbup Bogor No. 4/2025;<br/>"
                "2. Menyediakan sistem drainase terpadu dan sumur resapan air hujan berstandar teknis dinas;<br/>"
                "3. Mengajukan permohonan pengesahan Rencana Tapak (Site Plan) digital melalui sistem GEOSIPAS sebelum pelaksanaan fisik.",
                s["body_text"]
            )
        ],
        [
            Paragraph("KELIMA", s["body_bold"]),
            Paragraph(":", s["body_bold"]),
            Paragraph(
                "Keputusan ini berlaku selama 3 (tiga) tahun terhitung sejak tanggal ditetapkan. "
                "Apabila di kemudian hari terdapat kekeliruan atau pelanggaran peruntukan ruang, "
                "maka Keputusan ini akan ditinjau kembali sesuai peraturan perundang-undangan.",
                s["body_text"]
            )
        ]
    ]

    t_closing = Table(dictum_closing_data, colWidths=[24*mm, 4*mm, 146*mm])
    t_closing.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_closing)
    story.append(Spacer(1, 3*mm))

    # 5. BLOK TANDA TANGAN ELEKTRONIK (TTE KADIS)
    issued_date_raw = getattr(pkkpr, "sk_issued_date", None)
    if issued_date_raw:
        issued_date_str = issued_date_raw.strftime("%d %B %Y")
    else:
        issued_date_str = date.today().strftime("%d %B %Y")

    qr_hash = getattr(pkkpr, "qr_code_hash", None) or "INTEGRITAS-KAB-BOGOR-PKKPR-TTE"
    qr_short = qr_hash[:24]

    tte_box_html = (
        f"<div style='border: 1px solid #0f766e; background-color: #f0fdf4; padding: 4px; text-align: center;'>"
        f"<font size='7' color='#065f46'><strong>DITANDATANGANI SECARA ELEKTRONIK (TTE)</strong><br/>"
        f"Sertifikat Digital BSrE BSSN<br/>"
        f"Kode Validasi: <code>{qr_short}...</code></font>"
        f"</div>"
    )

    signature_table_data = [
        [
            Paragraph(
                f"<font size='7' color='#64748b'>"
                f"Sistem Informasi GEOSIPAS Kabupaten Bogor<br/>"
                f"Dicetak otomatis pada: {datetime.now().strftime('%d-%m-%Y %H:%M:%S WIB')}<br/>"
                f"Status Berkas: <strong>{getattr(pkkpr, 'status', 'DISETUJUI')}</strong>"
                f"</font>",
                s["table_cell"]
            ),
            Paragraph(
                f"Ditetapkan di Cibinong<br/>"
                f"pada tanggal {issued_date_str}<br/>"
                f"<strong>KEPALA DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU<br/>KABUPATEN BOGOR</strong><br/>"
                f"{tte_box_html}<br/>"
                f"<strong><u>IR. H. KEPALA DINAS, M.Si.</u></strong><br/>"
                f"<font size='7'>NIP. 19740512 199803 1 002</font>",
                s["table_cell_center"]
            )
        ]
    ]

    t_sig = Table(signature_table_data, colWidths=[90*mm, 84*mm])
    t_sig.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))

    story.append(KeepTogether(t_sig))

    doc.build(story)
    return str(Path(output_path).resolve())


def generate_pkkpr_receipt_pdf(pkkpr: Any, output_path: str) -> str:
    """
    Menghasilkan berkas PDF Bukti Tanda Terima Pendaftaran Permohonan PKKPR.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=20*mm,
        rightMargin=20*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )

    s = _create_styles()
    story = []

    # 1. KOP SURAT
    story.append(Paragraph("PEMERINTAH KABUPATEN BOGOR", s["kop_instansi"]))
    story.append(Paragraph("SISTEM INFORMASI PELAYANAN PENGESAHAN DIGITAL (GEOSIPAS)", s["kop_dinas"]))
    story.append(Paragraph(
        "Dinas Perumahan, Kawasan Permukiman dan Pertanahan / DPMPTSP Kabupaten Bogor<br/>"
        "Komplek Pemda Jl. Tegar Beriman, Cibinong 16914",
        s["kop_sub"]
    ))
    story.append(Spacer(1, 2*mm))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#0f766e"), spaceAfter=1*mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#0f766e"), spaceAfter=4*mm))

    # 2. TITLE TANDA TERIMA
    story.append(Paragraph("TANDA TERIMA PENDAFTARAN PERMOHONAN PKKPR", s["doc_title"]))
    story.append(Paragraph(
        f"Nomor Registrasi Sistem: <font color='#0f766e'><strong>{getattr(pkkpr, 'submission_no', '-')}</strong></font>",
        s["doc_title"]
    ))
    story.append(Spacer(1, 4*mm))

    # 3. TABEL INFORMASI
    created_raw = getattr(pkkpr, "created_at", None)
    created_str = created_raw.strftime("%d %B %Y, %H:%M WIB") if created_raw else datetime.now().strftime("%d %B %Y, %H:%M WIB")

    info_data = [
        [Paragraph("1. Nomor Registrasi", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(f"<strong>{getattr(pkkpr, 'submission_no', '-')}</strong>", s["table_cell"])],
        [Paragraph("2. Tanggal Pendaftaran", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(created_str, s["table_cell"])],
        [Paragraph("3. Nama Pemohon / Badan", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(f"<strong>{getattr(pkkpr, 'applicant_name', '-')}</strong>", s["table_cell"])],
        [Paragraph("4. Jenis Pemohon", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(getattr(pkkpr, 'applicant_type', 'BADAN_USAHA'), s["table_cell"])],
        [Paragraph("5. NIB / NIK", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(getattr(pkkpr, 'applicant_nib', None) or getattr(pkkpr, 'applicant_nik', '-'), s["table_cell"])],
        [Paragraph("6. Telepon / WhatsApp", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(getattr(pkkpr, 'applicant_phone', '-'), s["table_cell"])],
        [Paragraph("7. Alamat Email", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(getattr(pkkpr, 'applicant_email', '-'), s["table_cell"])],
        [Paragraph("8. Rencana Kegiatan", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(getattr(pkkpr, 'activity_description', '-'), s["table_cell"])],
        [Paragraph("9. Lokasi Lahan", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(f"Desa {getattr(pkkpr, 'location_village', '-')}, Kec. {getattr(pkkpr, 'location_district', '-')}, Kab. Bogor", s["table_cell"])],
        [Paragraph("10. Bukti Hak Tanah", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(f"{getattr(pkkpr, 'land_ownership_status', 'SHM')} No. {getattr(pkkpr, 'certificate_number', '-')} a.n. {getattr(pkkpr, 'certificate_owner', '-')}", s["table_cell"])],
        [Paragraph("11. Luas Dimohonkan", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(f"<strong>{getattr(pkkpr, 'proposed_land_area_m2', 0):,.2f} m²</strong>", s["table_cell"])],
        [Paragraph("12. Status Terakhir", s["table_cell_bold"]), Paragraph(":", s["table_cell"]), Paragraph(f"<font color='#0f766e'><strong>{getattr(pkkpr, 'status', 'PENGAJUAN_BERKAS')}</strong></font>", s["table_cell"])]
    ]

    t_info = Table(info_data, colWidths=[45*mm, 6*mm, 123*mm])
    t_info.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 2),
        ('RIGHTPADDING', (0,0), (-1,-1), 2),
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f8fafc")),
        ('LINEBELOW', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 5*mm))

    # 4. DAFTAR BERKAS TERLAMPIR
    story.append(Paragraph("DAFTAR BERKAS DOKUMEN YANG DIUNGGAH:", s["body_bold"]))
    story.append(Spacer(1, 1.5*mm))

    files = getattr(pkkpr, "files", [])
    file_rows = [
        [
            Paragraph("No", s["table_cell_bold"]),
            Paragraph("Jenis Dokumen", s["table_cell_bold"]),
            Paragraph("Nama Berkas", s["table_cell_bold"]),
            Paragraph("Ukuran", s["table_cell_bold"]),
            Paragraph("Status", s["table_cell_bold"])
        ]
    ]

    if files:
        for idx, f in enumerate(files, 1):
            file_rows.append([
                Paragraph(str(idx), s["table_cell_center"]),
                Paragraph(getattr(f, "file_type", "-"), s["table_cell_bold"]),
                Paragraph(getattr(f, "file_name", "-"), s["table_cell"]),
                Paragraph(f"{(getattr(f, 'file_size', 0) / 1024):.0f} KB", s["table_cell"]),
                Paragraph("<font color='#059669'>Terunggah</font>", s["table_cell_center"])
            ])
    else:
        file_rows.append([
            Paragraph("1", s["table_cell_center"]),
            Paragraph("Dokumen Persyaratan", s["table_cell"]),
            Paragraph("KTP, Bukti Tanah & Proposal Teknis", s["table_cell"]),
            Paragraph("-", s["table_cell"]),
            Paragraph("<font color='#059669'>Tervalidasi</font>", s["table_cell_center"])
        ])

    t_files = Table(file_rows, colWidths=[10*mm, 45*mm, 70*mm, 24*mm, 25*mm])
    t_files.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#f1f5f9")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#cbd5e1")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    story.append(t_files)
    story.append(Spacer(1, 5*mm))

    # 5. CATATAN & PETUNJUK PEMOHON
    story.append(Paragraph("PETUNJUK BAGI PEMOHON:", s["body_bold"]))
    story.append(Spacer(1, 1*mm))
    story.append(Paragraph(
        "1. Berkas permohonan Anda telah resmi masuk ke antrean digital dinas dan akan diproses secara berjenjang "
        "(Verifikasi Formal Admin &rarr; Kajian Teknis Spasial PUPR &rarr; Sidang FPR &rarr; Otorisasi TTE Kadis).<br/>"
        "2. Waktu pemrosesan standar pelayanan (SLA) adalah <strong>12 (dua belas) hari kerja</strong> sejak berkas dinyatakan lengkap formal.<br/>"
        "3. Anda dapat memantau pergerakan berkas secara langsung melalui akun GEOSIPAS Anda pada menu <em>Daftar PKKPR</em>.<br/>"
        "4. Setelah SK PKKPR resmi terbit, Anda dapat langsung menggunakannya sebagai acuan validasi pada permohonan Pengesahan Rencana Tapak (Site Plan).",
        s["body_text"]
    ))
    story.append(Spacer(1, 6*mm))

    # FOOTER TANDA TERIMA
    footer_data = [
        [
            Paragraph(
                f"<font size='7' color='#64748b'>"
                f"Dicetak otomatis oleh Sistem GEOSIPAS Kabupaten Bogor<br/>"
                f"ID Berkas: <code>{getattr(pkkpr, 'id', '-')}</code><br/>"
                f"Dokumen ini sah sebagai bukti pendaftaran tanda terima daring."
                f"</font>",
                s["table_cell"]
            ),
            Paragraph(
                f"<div style='border: 1px dashed #0f766e; padding: 4px; text-align: center; background-color: #f8fafc;'>"
                f"<font size='7' color='#0f766e'><strong>TANDA TERIMA SAH ONLINE</strong><br/>"
                f"GEOSIPAS KABUPATEN BOGOR<br/>"
                f"<code>{getattr(pkkpr, 'submission_no', '-')}</code></font>"
                f"</div>",
                s["table_cell_center"]
            )
        ]
    ]
    t_foot = Table(footer_data, colWidths=[105*mm, 69*mm])
    t_foot.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(t_foot)

    doc.build(story)
    return str(Path(output_path).resolve())
