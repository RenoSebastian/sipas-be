"""
============================================================================
SIPAS HTTP CONTROLLER — Executive Reports Router [reports.py]
============================================================================
Peran: Menyediakan REST endpoints untuk statistik laporan eksekutif,
       ekspor laporan ke format spreadsheet Microsoft Excel (XLS)
       dan dokumen cetak PDF.
============================================================================
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import datetime
import tempfile
import os

# Adapter Koneksi & Repositori Database
from src.infrastructure.database.connection import get_db
from src.infrastructure.database.models import PermohonanModel, UserModel
from src.infrastructure.document.pdf_engine import HtmlToPdfEngine

# Utilitas Keamanan / Autentikasi JWT
from src.infrastructure.security.auth import get_current_user

router = APIRouter(prefix="/api/v1/submissions", tags=["Submissions Reports"])

@router.get("/reports/stats", status_code=status.HTTP_200_OK)
def get_submission_report_stats(
    start_month: int,
    start_year: int,
    end_month: int,
    end_year: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """
    Mendapatkan statistik laporan eksekutif terkonsolidasi berdasarkan rentang Bulan/Tahun awal
    hingga Bulan/Tahun akhir. Mengonversi tanggal verifikasi UTC ke Asia/Jakarta untuk presisi
    filter tanggal bulanan.
    """
    # Konversi kolom DateTime (kkpr_verified_at) dari UTC ke Asia/Jakarta untuk filter periodik
    local_verified_at = func.timezone('Asia/Jakarta', func.timezone('UTC', PermohonanModel.kkpr_verified_at))

    # 0. Menghitung tanggal batas awal (start_date) dan batas akhir eksklusif (end_date)
    start_dt = datetime.date(start_year, start_month, 1)
    if end_month == 12:
        end_dt = datetime.date(end_year + 1, 1, 1)
    else:
        end_dt = datetime.date(end_year, end_month + 1, 1)

    # Akumulasi YTD (1 Januari s/d Bulan Akhir dari end_year)
    ytd_start_dt = datetime.date(end_year, 1, 1)
    ytd_end_dt = end_dt

    # 1. AKUMULASI YTD
    total_pengajuan_ytd = db.query(PermohonanModel).filter(
        PermohonanModel.submission_date >= ytd_start_dt,
        PermohonanModel.submission_date < ytd_end_dt
    ).count()

    total_disetujui_ytd = db.query(PermohonanModel).filter(
        PermohonanModel.status == 'Disetujui',
        local_verified_at >= ytd_start_dt,
        local_verified_at < ytd_end_dt
    ).count()

    # 2. DATA PERIODE TERPILIH (start_dt s/d end_dt)
    pengajuan_bulan_ini = db.query(PermohonanModel).filter(
        PermohonanModel.submission_date >= start_dt,
        PermohonanModel.submission_date < end_dt
    ).count()

    penyelesaian_bulan_ini = db.query(PermohonanModel).filter(
        PermohonanModel.status == 'Disetujui',
        local_verified_at >= start_dt,
        local_verified_at < end_dt
    ).count()

    # 3. REKAPITULASI SK TERBIT (Periode start_dt s/d end_dt)
    approved_submissions = db.query(PermohonanModel).filter(
        PermohonanModel.status == 'Disetujui',
        local_verified_at >= start_dt,
        local_verified_at < end_dt
    ).all()

    sk_recap = [
        {
            "submission_no": r.submission_no,
            "housing_name": r.housing_name or "-",
            "sk_number": r.sk_number or "-"
        }
        for r in approved_submissions
    ]

    # 4. ANALISIS KEPUTUSAN YTD (Januari s/d Bulan Akhir/end_dt)
    verdicts_ytd = db.query(PermohonanModel).filter(
        PermohonanModel.submission_date >= ytd_start_dt,
        PermohonanModel.submission_date < ytd_end_dt
    ).all()

    decision_analysis = {
        "SESUAI": 0,
        "SESUAI_BERSYARAT": 0,
        "TIDAK_SESUAI": 0
    }

    for r in verdicts_ytd:
        if r.status == 'Ditolak':
            decision_analysis["TIDAK_SESUAI"] += 1
        elif r.kkpr_verdict:
            verdict_val = r.kkpr_verdict.value
            if verdict_val == "SESUAI":
                decision_analysis["SESUAI"] += 1
            elif verdict_val == "SESUAI_BERSYARAT":
                decision_analysis["SESUAI_BERSYARAT"] += 1
            elif verdict_val in ["TIDAK_SESUAI", "PERLU_PERBAIKAN"]:
                decision_analysis["TIDAK_SESUAI"] += 1

    # 5. STATISTIK LAHAN YTD (Januari s/d Bulan Akhir/end_dt)
    land_area_sum = db.query(func.sum(PermohonanModel.land_area)).filter(
        PermohonanModel.submission_date >= ytd_start_dt,
        PermohonanModel.submission_date < ytd_end_dt
    ).scalar() or 0.0

    # 6. PIPELINE TAHAPAN (Snapshot Status Aktif Saat Ini)
    all_active = db.query(PermohonanModel).all()
    pipeline_snapshot = {
        "pemohon": 0,
        "admin": 0,
        "teknis": 0,
        "kabid": 0,
        "kadis": 0,
        "selesai": 0
    }

    for r in all_active:
        status_val = r.status
        if status_val in ['Draft', 'Menunggu Verifikasi']:
            pipeline_snapshot["pemohon"] += 1
        elif status_val == 'Verifikasi Administrasi':
            pipeline_snapshot["admin"] += 1
        elif status_val == 'Verifikasi Teknis':
            pipeline_snapshot["teknis"] += 1
        elif status_val in ['Menunggu Rekomendasi', 'Menunggu Persetujuan']:
            pipeline_snapshot["kabid"] += 1
        elif status_val == 'Proses TTE':
            pipeline_snapshot["kadis"] += 1
        elif status_val == 'Disetujui':
            pipeline_snapshot["selesai"] += 1

    return {
        "accumulation": {
            "total_pengajuan_ytd": total_pengajuan_ytd,
            "total_disetujui_ytd": total_disetujui_ytd
        },
        "monthly": {
            "pengajuan_bulan_ini": pengajuan_bulan_ini,
            "penyelesaian_bulan_ini": penyelesaian_bulan_ini
        },
        "sk_recap": sk_recap,
        "decision_analysis": decision_analysis,
        "land_statistics": {
            "total_land_area_ytd": float(land_area_sum)
        },
        "pipeline_snapshot": pipeline_snapshot
    }

@router.get("/reports/export/csv", status_code=status.HTTP_200_OK)
def export_submission_report_csv(
    start_month: int,
    start_year: int,
    end_month: int,
    end_year: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Ekspor Laporan Eksekutif Realisasi Site Plan ke format spreadsheet Microsoft Excel (XLS) berbasis HTML."""
    MONTH_NAMES = ["Januari", "Februari", "Maret", "April", "Mei", "Juni",
                   "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

    # ─── Kalkulasi Batas Tanggal ──────────────────────────────────────────────
    start_dt     = datetime.date(start_year, start_month, 1)
    end_dt       = datetime.date(end_year + 1, 1, 1) if end_month == 12 else datetime.date(end_year, end_month + 1, 1)
    ytd_start_dt = datetime.date(end_year, 1, 1)
    period_label = (
        f"{MONTH_NAMES[start_month - 1]} {start_year}"
        if (start_month == end_month and start_year == end_year)
        else f"{MONTH_NAMES[start_month - 1]} {start_year} - {MONTH_NAMES[end_month - 1]} {end_year}"
    )
    today      = datetime.date.today()
    print_date = f"{today.day} {MONTH_NAMES[today.month - 1]} {today.year}"
    operator_name = getattr(current_user, 'full_name', None) or getattr(current_user, 'username', 'Sistem')

    # ─── Query Data Utama ─────────────────────────────────────────────────────
    submissions = db.query(PermohonanModel).filter(
        PermohonanModel.submission_date >= start_dt,
        PermohonanModel.submission_date < end_dt
    ).order_by(PermohonanModel.submission_date.asc()).all()

    # ─── Statistik Ringkasan YTD ──────────────────────────────────────────────
    local_verified_at   = func.timezone('Asia/Jakarta', func.timezone('UTC', PermohonanModel.kkpr_verified_at))
    total_pengajuan_ytd = db.query(PermohonanModel).filter(
        PermohonanModel.submission_date >= ytd_start_dt,
        PermohonanModel.submission_date < end_dt
    ).count()
    total_disetujui_ytd = db.query(PermohonanModel).filter(
        PermohonanModel.status == 'Disetujui',
        local_verified_at >= ytd_start_dt,
        local_verified_at < end_dt
    ).count()
    total_ditolak_ytd   = db.query(PermohonanModel).filter(
        PermohonanModel.status == 'Ditolak',
        PermohonanModel.submission_date >= ytd_start_dt,
        PermohonanModel.submission_date < end_dt
    ).count()
    total_proses_ytd    = max(0, total_pengajuan_ytd - total_disetujui_ytd - total_ditolak_ytd)
    land_area_sum       = db.query(func.sum(PermohonanModel.land_area)).filter(
        PermohonanModel.submission_date >= start_dt,
        PermohonanModel.submission_date < end_dt
    ).scalar() or 0.0
    rasio_lulus = round(total_disetujui_ytd / total_pengajuan_ytd * 100, 1) if total_pengajuan_ytd > 0 else 0.0

    STATUS_LABEL = {
        'Disetujui': 'DISETUJUI', 'Ditolak': 'DITOLAK',
        'Verifikasi Teknis': 'Verifikasi Teknis',
        'Verifikasi Administrasi': 'Verifikasi Administrasi',
        'Menunggu Verifikasi': 'Menunggu Verifikasi',
        'Menunggu Persetujuan': 'Menunggu Persetujuan',
        'Menunggu Rekomendasi': 'Menunggu Rekomendasi',
        'Proses TTE': 'Proses TTE', 'Draft': 'Draft',
    }
    KKPR_LABEL = {
        'SESUAI': 'Sesuai', 'SESUAI_BERSYARAT': 'Sesuai Bersyarat',
        'PERLU_PERBAIKAN': 'Perlu Perbaikan', 'TIDAK_SESUAI': 'Tidak Sesuai',
    }

    # ─── Render HTML Spreadsheet (MSO Excel Compliant) ──────────────────────────
    excel_html = f"""<html xmlns:o="urn:schemas-microsoft-com:office:office"
      xmlns:x="urn:schemas-microsoft-com:office:excel"
      xmlns="http://www.w3.org/TR/REC-html40">
<head>
  <!--[if gte mso 9]>
  <xml>
    <x:ExcelWorkbook>
      <x:ExcelWorksheets>
        <x:ExcelWorksheet>
          <x:Name>Laporan Realisasi GEOSIPAS</x:Name>
          <x:WorksheetOptions>
            <x:DisplayGridlines/>
          </x:WorksheetOptions>
        </x:ExcelWorksheet>
      </x:ExcelWorksheets>
    </x:ExcelWorkbook>
  </xml>
  <![endif]-->
  <meta charset="utf-8">
  <style>
    body {{
      font-family: Arial, sans-serif;
      color: #111111;
    }}
    table {{
      border-collapse: collapse;
    }}
    td, th {{
      border: 0.5pt solid #cbd5e1;
      padding: 6px 8px;
      font-size: 10pt;
      font-family: Arial, sans-serif;
    }}
    .header-instansi {{
      font-size: 14pt;
      font-weight: bold;
      text-align: center;
    }}
    .header-sub {{
      font-size: 11pt;
      font-weight: bold;
      text-align: center;
      color: #222222;
    }}
    .header-desc {{
      font-size: 9pt;
      text-align: center;
      color: #555555;
    }}
    .title-laporan {{
      font-size: 12pt;
      font-weight: bold;
      text-align: center;
      color: #111d13;
    }}
    .bg-kop {{
      border: none !important;
    }}
    .kpi-label {{
      font-size: 9pt;
      font-weight: bold;
      color: #334155;
      background-color: #f1f5f4;
      border: 0.5pt solid #cbd5e1;
    }}
    .kpi-val {{
      font-size: 10pt;
      font-weight: bold;
      color: #111d13;
      border: 0.5pt solid #cbd5e1;
    }}
    .th-table {{
      background-color: #2d6a4f;
      color: #ffffff;
      font-weight: bold;
      font-size: 9.5pt;
      text-align: center;
      border: 0.5pt solid #2d6a4f;
    }}
    .text-center {{
      text-align: center;
    }}
    .text-right {{
      text-align: right;
    }}
    .font-bold {{
      font-weight: bold;
    }}
    .bg-subtotal {{
      background-color: #f1f5f4;
      font-weight: bold;
      border: 0.5pt solid #cbd5e1;
    }}
    .footer-note {{
      font-size: 8.5pt;
      color: #555555;
      font-style: italic;
      border: none !important;
    }}
    .mso-date {{
      mso-number-format: "dd\\/mm\\/yyyy";
      text-align: center;
    }}
    .mso-area {{
      mso-number-format: "\\#\\,\\#\\#0\\.00";
      text-align: right;
    }}
  </style>
</head>
<body>
  <table border="0">
    <colgroup>
      <col width="45" />
      <col width="130" />
      <col width="220" />
      <col width="200" />
      <col width="140" />
      <col width="110" />
      <col width="140" />
      <col width="110" />
      <col width="180" />
      <col width="130" />
      <col width="120" />
      <col width="120" />
    </colgroup>

    <!-- Kop Instansi -->
    <tr height="25">
      <td colspan="12" class="header-instansi bg-kop">PEMERINTAH KABUPATEN BOGOR</td>
    </tr>
    <tr height="25">
      <td colspan="12" class="header-sub bg-kop">DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU (DPMPTSP)</td>
    </tr>
    <tr height="20">
      <td colspan="12" class="header-desc bg-kop">Gedung Kesenian Kab. Bogor, Cibinong  |  Email: dpmptsp@bogorkab.go.id</td>
    </tr>
    <tr height="5">
      <td colspan="12" style="border-bottom: 2px solid #000; border-top:none; border-left:none; border-right:none; background-color: transparent;"></td>
    </tr>
    <tr height="15"><td colspan="12" class="bg-kop"></td></tr>
    
    <!-- Judul Dokumen -->
    <tr height="25">
      <td colspan="12" class="title-laporan bg-kop">LAPORAN EKSEKUTIF REALISASI PENGESAHAN RENCANA TAPAK (SITE PLAN)</td>
    </tr>
    <tr height="20">
      <td colspan="12" class="text-center bg-kop" style="font-size: 10pt;">Periode Laporan: <b>{period_label}</b></td>
    </tr>
    <tr height="20">
      <td colspan="12" class="text-center bg-kop" style="font-size: 9pt; color: #555555;">Tanggal Cetak: {print_date} &nbsp;|&nbsp; Dicetak Oleh: {operator_name}</td>
    </tr>
    <tr height="15"><td colspan="12" class="bg-kop"></td></tr>

    <!-- Section A: Statistik KPI YTD -->
    <tr height="22">
      <td colspan="12" style="background-color: #f1f5f4; font-weight: bold; font-size: 10.5pt; border: 0.5pt solid #cbd5e1;">A. RINGKASAN STATISTIK EKSEKUTIF (Year-to-Date)</td>
    </tr>
    <tr height="22">
      <td colspan="4" class="kpi-label text-center">Indikator Kinerja Utama (KPI)</td>
      <td colspan="3" class="kpi-label text-center">Nilai Akumulasi</td>
      <td colspan="5" class="kpi-label text-center">Keterangan Cakupan</td>
    </tr>
    <tr height="22">
      <td colspan="4" class="kpi-val">Total Berkas Masuk (YTD)</td>
      <td colspan="3" class="kpi-val text-center">{total_pengajuan_ytd} berkas</td>
      <td colspan="5" class="kpi-val" style="color:#555;">Akumulasi berkas masuk sejak 1 Januari {end_year}</td>
    </tr>
    <tr height="22">
      <td colspan="4" class="kpi-val">SK Site Plan Diterbitkan (YTD)</td>
      <td colspan="3" class="kpi-val text-center" style="color: #2d6a4f;">{total_disetujui_ytd} SK</td>
      <td colspan="5" class="kpi-val" style="color:#555;">Berkas berstatus Disetujui</td>
    </tr>
    <tr height="22">
      <td colspan="4" class="kpi-val">Berkas Ditolak / Perbaikan (YTD)</td>
      <td colspan="3" class="kpi-val text-center" style="color: #be123c;">{total_ditolak_ytd} berkas</td>
      <td colspan="5" class="kpi-val" style="color:#555;">Berkas berstatus Ditolak</td>
    </tr>
    <tr height="22">
      <td colspan="4" class="kpi-val">Berkas Dalam Proses (Aktif)</td>
      <td colspan="3" class="kpi-val text-center" style="color: #b45309;">{total_proses_ytd} berkas</td>
      <td colspan="5" class="kpi-val" style="color:#555;">Berkas masih dalam peninjauan verifikator dinas</td>
    </tr>
    <tr height="22">
      <td colspan="4" class="kpi-val">Total Luas Lahan Diajukan</td>
      <td colspan="3" class="kpi-val text-right mso-area">{land_area_sum}</td>
      <td colspan="5" class="kpi-val" style="color:#555;">Setara dengan ~{land_area_sum / 10000:.2f} Hektar (periode ini)</td>
    </tr>
    <tr height="22">
      <td colspan="4" class="kpi-val">Rasio Kelulusan Berkas YTD</td>
      <td colspan="3" class="kpi-val text-center">{rasio_lulus}%</td>
      <td colspan="5" class="kpi-val" style="color:#555;">SK Diterbitkan / Total Berkas Masuk x 100%</td>
    </tr>
    <tr height="15"><td colspan="12" class="bg-kop"></td></tr>

    <!-- Section B: Tabel Rincian Data -->
    <tr height="22">
      <td colspan="12" style="background-color: #f1f5f4; font-weight: bold; font-size: 10.5pt; border: 0.5pt solid #cbd5e1;">B. DAFTAR RINCIAN BERKAS PERMOHONAN</td>
    </tr>
    <tr height="20">
      <td colspan="12" class="bg-kop" style="font-size: 9.5pt; color: #555555;">Total berkas pada periode ini: {len(submissions)} berkas</td>
    </tr>

    <!-- Table Header -->
    <tr height="26">
      <th class="th-table">No.</th>
      <th class="th-table">No. Berkas</th>
      <th class="th-table">Nama Perumahan / Kegiatan</th>
      <th class="th-table">Nama Pengembang / Pemohon</th>
      <th class="th-table">Luas Lahan (m²)</th>
      <th class="th-table">Tgl. Pengajuan</th>
      <th class="th-table">Status Berkas</th>
      <th class="th-table">Kategori</th>
      <th class="th-table">Nomor SK</th>
      <th class="th-table">Verdict KKPR</th>
      <th class="th-table">Kecamatan</th>
      <th class="th-table">Desa / Kelurahan</th>
    </tr>
"""

    total_lahan_periode = 0.0
    cnt_disetujui = cnt_ditolak = cnt_proses = 0

    # ─── Data Loop ────────────────────────────────────────────────────────────
    for idx, sub in enumerate(submissions, start=1):
        lahan     = float(sub.land_area or 0.0)
        total_lahan_periode += lahan
        sts       = sub.status or "-"
        if sts == 'Disetujui':  cnt_disetujui += 1
        elif sts == 'Ditolak':  cnt_ditolak   += 1
        else:                   cnt_proses    += 1

        kkpr_raw   = sub.kkpr_verdict.value if sub.kkpr_verdict else "-"
        tgl        = sub.submission_date.strftime("%d/%m/%Y") if sub.submission_date else "-"
        kategori   = (sub.submission_category or "-").replace("_", " ").title()

        status_lbl = STATUS_LABEL.get(sts, sts)
        kkpr_lbl = KKPR_LABEL.get(kkpr_raw, kkpr_raw)

        # Penentuan warna untuk status
        color_status = "#475569"
        if sts == 'Disetujui':
            color_status = "#2d6a4f"
        elif sts == 'Ditolak':
            color_status = "#be123c"

        excel_html += f"""
    <tr height="22">
      <td class="text-center">{idx}</td>
      <td class="text-center">{sub.submission_no or "-"}</td>
      <td><b>{sub.housing_name or "-"}</b></td>
      <td>{sub.developer_name or "-"}</td>
      <td class="mso-area">{lahan}</td>
      <td class="mso-date">{tgl}</td>
      <td class="text-center font-bold" style="color: {color_status};">{status_lbl}</td>
      <td class="text-center">{kategori}</td>
      <td class="text-center font-bold" style="color: #2d6a4f;">{sub.sk_number or "-"}</td>
      <td class="text-center">{kkpr_lbl}</td>
      <td>{sub.location_district or "-"}</td>
      <td>{sub.location_village or "-"}</td>
    </tr>"""

    # ─── Subtotal / Summary Rows ──────────────────────────────────────────────
    excel_html += f"""
    <tr height="24" class="bg-subtotal">
      <td class="text-center bg-subtotal"></td>
      <td colspan="3" class="bg-subtotal">TOTAL LUAS LAHAN PERIODE</td>
      <td class="mso-area bg-subtotal font-bold">{total_lahan_periode}</td>
      <td colspan="7" class="bg-subtotal"></td>
    </tr>
    <tr height="24" class="bg-subtotal">
      <td class="text-center bg-subtotal"></td>
      <td colspan="11" class="bg-subtotal">
        Rekap Status Periode: &nbsp;&nbsp;&nbsp;
        Disetujui: <b>{cnt_disetujui}</b> &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
        Ditolak: <b>{cnt_ditolak}</b> &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;
        Dalam Proses: <b>{cnt_proses}</b>
      </td>
    </tr>
    <tr height="15"><td colspan="12" class="bg-kop"></td></tr>

    <!-- Section C: Catatan Kaki -->
    <tr height="22">
      <td colspan="12" style="background-color: #f1f5f4; font-weight: bold; font-size: 10.5pt; border: 0.5pt solid #cbd5e1;">C. CATATAN DAN KETENTUAN</td>
    </tr>
    <tr height="20">
      <td colspan="12" class="footer-note">1. Dokumen ini digenerate secara otomatis oleh GEOSIPAS (Sistem Informasi Pelayanan Pengesahan Site Plan Digital) Kab. Bogor.</td>
    </tr>
    <tr height="20">
      <td colspan="12" class="footer-note">2. Data bersumber dari basis data real-time DPMPTSP. Keabsahan data mengikuti rekaman sistem.</td>
    </tr>
    <tr height="20">
      <td colspan="12" class="footer-note">3. Angka luas lahan dinyatakan dalam meter persegi (m²) dengan format ribuan dan desimal terstandardisasi Excel.</td>
    </tr>
    <tr height="20">
      <td colspan="12" class="footer-note">4. YTD (Year-to-Date) = akumulasi data sejak 1 Januari tahun berjalan hingga akhir periode yang dipilih.</td>
    </tr>
    <tr height="20">
      <td colspan="12" class="footer-note">5. Dokumen ini bukan merupakan surat resmi dan tidak memerlukan tanda tangan basah.</td>
    </tr>
    <tr height="20"><td colspan="12" class="bg-kop"></td></tr>
    <tr height="20">
      <td colspan="12" class="text-center bg-kop" style="font-size: 9.5pt; font-style: italic; color: #777777;">--- Akhir Laporan GEOSIPAS  |  Dicetak: {print_date} ---</td>
    </tr>
  </table>
</body>
</html>
"""

    # ─── Return Response ──────────────────────────────────────────────────────
    fname = f"GEOSIPAS_Laporan_{MONTH_NAMES[start_month-1]}_{start_year}"
    if not (start_month == end_month and start_year == end_year):
        fname += f"_sd_{MONTH_NAMES[end_month-1]}_{end_year}"
    fname += ".xls"

    response = HTMLResponse(content=excel_html, status_code=200)
    response.headers["Content-Disposition"] = f'attachment; filename="{fname}"'
    response.headers["Content-Type"] = "application/vnd.ms-excel; charset=utf-8"
    return response

@router.get("/reports/export/pdf", status_code=status.HTTP_200_OK)
def export_submission_report_pdf(
    start_month: int,
    start_year: int,
    end_month: int,
    end_year: int,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(get_current_user)
):
    """Merender dan mengekspor Laporan Eksekutif Terkonsolidasi ke format berkas cetak PDF."""
    from fastapi.responses import FileResponse as FileResponsePdf
    from sqlalchemy import func
    import tempfile
    import datetime

    local_verified_at = func.timezone('Asia/Jakarta', func.timezone('UTC', PermohonanModel.kkpr_verified_at))

    start_dt = datetime.date(start_year, start_month, 1)
    if end_month == 12:
        end_dt = datetime.date(end_year + 1, 1, 1)
    else:
        end_dt = datetime.date(end_year, end_month + 1, 1)

    ytd_start_dt = datetime.date(end_year, 1, 1)
    ytd_end_dt = end_dt

    total_pengajuan_ytd = db.query(PermohonanModel).filter(
        PermohonanModel.submission_date >= ytd_start_dt,
        PermohonanModel.submission_date < ytd_end_dt
    ).count()

    total_disetujui_ytd = db.query(PermohonanModel).filter(
        PermohonanModel.status == 'Disetujui',
        local_verified_at >= ytd_start_dt,
        local_verified_at < ytd_end_dt
    ).count()

    pengajuan_bulan_ini = db.query(PermohonanModel).filter(
        PermohonanModel.submission_date >= start_dt,
        PermohonanModel.submission_date < end_dt
    ).count()

    penyelesaian_bulan_ini = db.query(PermohonanModel).filter(
        PermohonanModel.status == 'Disetujui',
        local_verified_at >= start_dt,
        local_verified_at < end_dt
    ).count()

    approved_submissions = db.query(PermohonanModel).filter(
        PermohonanModel.status == 'Disetujui',
        local_verified_at >= start_dt,
        local_verified_at < end_dt
    ).all()

    sk_recap = [
        {"submission_no": r.submission_no, "housing_name": r.housing_name or "-", "sk_number": r.sk_number or "-"}
        for r in approved_submissions
    ]

    verdicts_ytd = db.query(PermohonanModel).filter(
        PermohonanModel.submission_date >= ytd_start_dt,
        PermohonanModel.submission_date < ytd_end_dt
    ).all()

    sesuai_ytd = 0
    sesuai_bersyarat_ytd = 0
    tidak_sesuai_ytd = 0
    for r in verdicts_ytd:
        if r.status == 'Ditolak':
            tidak_sesuai_ytd += 1
        elif r.kkpr_verdict:
            verdict_val = r.kkpr_verdict.value
            if verdict_val == "SESUAI":
                sesuai_ytd += 1
            elif verdict_val == "SESUAI_BERSYARAT":
                sesuai_bersyarat_ytd += 1
            elif verdict_val in ["TIDAK_SESUAI", "PERLU_PERBAIKAN"]:
                tidak_sesuai_ytd += 1

    total_decisions = sesuai_ytd + sesuai_bersyarat_ytd + tidak_sesuai_ytd
    sesuai_pct = round((sesuai_ytd / total_decisions * 100), 1) if total_decisions > 0 else 0.0
    sesuai_bersyarat_pct = round((sesuai_bersyarat_ytd / total_decisions * 100), 1) if total_decisions > 0 else 0.0
    tidak_sesuai_pct = round((tidak_sesuai_ytd / total_decisions * 100), 1) if total_decisions > 0 else 0.0
    success_rate = round(((sesuai_ytd + sesuai_bersyarat_ytd) / total_decisions * 100), 1) if total_decisions > 0 else 0.0

    land_area_sum = db.query(func.sum(PermohonanModel.land_area)).filter(
        PermohonanModel.submission_date >= ytd_start_dt,
        PermohonanModel.submission_date < ytd_end_dt
    ).scalar() or 0.0

    all_active = db.query(PermohonanModel).all()
    pipeline = {"pemohon": 0, "admin": 0, "teknis": 0, "kabid": 0, "kadis": 0, "selesai": 0}
    for r in all_active:
        status_val = r.status
        if status_val in ['Draft', 'Menunggu Verifikasi']:
            pipeline["pemohon"] += 1
        elif status_val == 'Verifikasi Administrasi':
            pipeline["admin"] += 1
        elif status_val == 'Verifikasi Teknis':
            pipeline["teknis"] += 1
        elif status_val in ['Menunggu Rekomendasi', 'Menunggu Persetujuan']:
            pipeline["kabid"] += 1
        elif status_val == 'Proses TTE':
            pipeline["kadis"] += 1
        elif status_val == 'Disetujui':
            pipeline["selesai"] += 1

    MONTH_NAMES = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]

    if start_month == end_month and start_year == end_year:
        month_name = MONTH_NAMES[start_month - 1]
        pdf_year = str(start_year)
    else:
        month_name = f"{MONTH_NAMES[start_month - 1]} {start_year} - {MONTH_NAMES[end_month - 1]} {end_year}"
        pdf_year = ""

    today = datetime.date.today()
    print_date = f"{today.day} {MONTH_NAMES[today.month - 1]} {today.year}"
    land_area_formatted = "{:,.2f}".format(land_area_sum).replace(",", "X").replace(".", ",").replace("X", ".")
    land_area_ha = "{:.2f}".format(land_area_sum / 10000).replace(".", ",")

    context = {
        "month_name": month_name,
        "year": pdf_year,
        "print_date": print_date,
        "land_area_formatted": land_area_formatted,
        "land_area_ha": land_area_ha,
        "total_pengajuan_ytd": total_pengajuan_ytd,
        "pengajuan_bulan_ini": pengajuan_bulan_ini,
        "total_disetujui_ytd": total_disetujui_ytd,
        "penyelesaian_bulan_ini": penyelesaian_bulan_ini,
        "success_rate": success_rate,
        "approved_decisions": sesuai_ytd + sesuai_bersyarat_ytd,
        "sesuai_ytd": sesuai_ytd,
        "sesuai_pct": sesuai_pct,
        "sesuai_bersyarat_ytd": sesuai_bersyarat_ytd,
        "sesuai_bersyarat_pct": sesuai_bersyarat_pct,
        "tidak_sesuai_ytd": tidak_sesuai_ytd,
        "tidak_sesuai_pct": tidak_sesuai_pct,
        "pipeline": pipeline,
        "sk_recap": sk_recap
    }

    pdf_engine = HtmlToPdfEngine()
    html_content = pdf_engine.render_html("report_template.html", context)

    temp_dir = tempfile.gettempdir()
    temp_pdf_path = os.path.join(temp_dir, f"report_{start_month}_{start_year}_{end_month}_{end_year}.pdf")
    pdf_engine.compile_to_pdf(html_content, temp_pdf_path)

    return FileResponsePdf(
        path=temp_pdf_path,
        media_type="application/pdf",
        filename=f"laporan_eksekutif_geosipas_{start_month}_{start_year}_{end_month}_{end_year}.pdf"
    )
