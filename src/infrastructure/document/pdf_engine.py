# --- FILE: src/infrastructure/document/pdf_engine.py ---
"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Enterprise PDF Engine [pdf_engine.py] (REVISED v9)
============================================================================
Peran: Engine pencetakan dokumen yang bertugas menyatukan template HTML Jinja2
       dengan data JSONB menjadi berkas PDF fisik.
       Mewarisi DocumentGeneratorPort untuk menegakkan Dependency Inversion,
       serta mengamankan pengikatan variabel WeasyPrint (Anti-Unbound Pylance).
       Revisi v9: Optimalisasi pembagian halaman (loose splitting), reduksi margin 
                  paragraf setengahnya, serta netralisasi style badge "Sesuai".
============================================================================
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# Impor Jinja2 untuk mesin templating HTML
try:
    from jinja2 import Environment, DictLoader, FileSystemLoader
except ImportError:
    raise ImportError("[PDF_ENGINE_ERROR] Pustaka 'jinja2' wajib terpasang di dependencies Anda.")

# Impor Abstraksi Port & Entitas Domain untuk Pemenuhan Nominal Typing (DIP)
from src.use_cases.ports.document_generator_port import DocumentGeneratorPort
from src.domain.entities.telaah_staf import TelaahStaf
from src.domain.entities.permohonan import Permohonan

# Inisialisasi awal modul untuk menjamin variabel selalu terikat (Pylance Type Guard)
WP_HTML: Optional[Any] = None
WEASYPRINT_AVAILABLE: bool = False

try:
    from weasyprint import HTML as WP_HTML_imported
    WP_HTML = WP_HTML_imported
    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    # Menangkap ImportError (belum diinstall) ATAU OSError (pango/cairo DLLs tidak lengkap di OS)
    logging.getLogger("sipas-be").warning(
        f"[PDF_ENGINE_WARNING] WeasyPrint tidak aktif karena keterbatasan dependensi OS: {str(e)}. "
        "Sistem secara otomatis beralih menggunakan Fallback PDF Generator."
    )

logger = logging.getLogger("sipas-be")


# ─── SECTION: DEFAULT INLINE TEMPLATES (Bencana Anti-FileNotFound) ─────────

DEFAULT_TELAAH_STAF_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Telaah Staf - {{ document_metadata.document_no }}</title>
    <style>
        @page {
            size: A4;
            margin: 20mm;
            @bottom-right {
                content: "Halaman " counter(page) " dari " counter(pages);
                font-family: Arial, sans-serif;
                font-size: 9pt;
            }
        }
        body {
            font-family: "Times New Roman", Times, serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #000;
        }
        .header {
            text-align: center;
            margin-bottom: 25px;
            border-bottom: 3px double #000;
            padding-bottom: 10px;
        }
        .header h1 { margin: 0; font-size: 14pt; text-transform: uppercase; font-weight: bold; }
        
        /* ─── PENGATURAN STRUKTUR TABEL & ANTI-TERPOTONG ─── */
        .meta-table, .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .meta-table td { padding: 4px 0; vertical-align: top; }
        .meta-table td.label { width: 25%; font-weight: bold; }
        .meta-table td.separator { width: 3%; text-align: center; }
        
        .data-table th, .data-table td {
            border: 1px solid #000;
            padding: 6px 8px;
            text-align: left;
            font-size: 10pt;
            vertical-align: middle;
        }
        .data-table th {
            background-color: #f2f2f2;
            text-transform: uppercase;
            font-weight: bold;
        }
        
        /* Proteksi mutlak pemotongan baris di tengah halaman kertas (Anti-Fragmentation) */
        tr, td, th {
            page-break-inside: avoid !important;
            break-inside: avoid-page !important;
        }
        thead {
            display: table-header-group;
        }

        .section-title {
            font-size: 11pt;
            font-weight: bold;
            text-transform: uppercase;
            margin-top: 15px;
            margin-bottom: 6px;
            text-decoration: underline;
        }
        .table-subtitle {
            font-size: 10pt;
            font-weight: bold;
            text-transform: uppercase;
            margin-top: 10px;
            margin-bottom: 4px;
            color: #111;
        }
        
        /* Badges & Status Plain Text Rendering */
        .status-badge {
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
            text-align: center;
            display: inline-block;
        }
        
        /* REVISI: Status SESUAI dirender sebagai teks hitam biasa tanpa background/border */
        .status-SESUAI, .status-Sesuai { 
            color: #000 !important; 
            background-color: transparent !important; 
            border: none !important; 
            padding: 0 !important; 
            font-weight: normal !important;
            display: inline !important;
        }
        
        .status-SESUAI_BERSYARAT, .status-Sesuai_Bersyarat { color: #664d03; background-color: #fff3cd; border: 1px solid #ffecb5; }
        .status-TIDAK_SESUAI, .status-Tidak_Sesuai, .status-REVISI, .status-Perlu_Perbaikan { color: #842029; background-color: #f8d7da; border: 1px solid #f5c2c7; }
        
        .signature-block {
            margin-top: 30px;
            width: 100%;
            page-break-inside: avoid !important;
            break-inside: avoid-page !important;
        }
        .signature-table {
            width: 100%;
            border-collapse: collapse;
        }
        .signature-table td {
            width: 50%;
            text-align: center;
            vertical-align: top;
            padding-top: 15px;
        }
        
        /* REVISI: Pengurangan margin paragraf sebanyak setengah (dari 12px ke 6px) */
        .narrative-p {
            text-align: justify;
            text-indent: 10mm;
            font-size: 10pt;
            margin-top: 4px;
            margin-bottom: 6px;
            line-height: 1.4;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>DOKUMEN / LEMBAR TELAAH STAF PERMOHONAN PENGESAHAN E-SITEPLAN</h1>
    </div>

    <table class="meta-table">
        <tr>
            <td class="label">Nomor Dokumen</td>
            <td class="separator">:</td>
            <td>{{ document_metadata.document_no }}</td>
        </tr>
        <tr>
            <td class="label">Subjek Pemohon</td>
            <td class="separator">:</td>
            <td>{{ applicant_snapshot.name }} (UP. {{ applicant_snapshot.director }})</td>
        </tr>
        <tr>
            <td class="label">Proyek Kegiatan</td>
            <td class="separator">:</td>
            <td>{{ project_snapshot.activity_name }}</td>
        </tr>
        <tr>
            <td class="label">Lokasi</td>
            <td class="separator">:</td>
            <td>Desa/Kel. {{ project_snapshot.village }}, Kec. {{ project_snapshot.district }}, Kabupaten Bogor</td>
        </tr>
        <tr>
            <td class="label">Keputusan Akhir</td>
            <td class="separator">:</td>
            <td><span class="status-badge status-{{ document_metadata.verdict }}">{{ document_metadata.verdict }}</span></td>
        </tr>
    </table>

    <div class="section-title">I. Pemeriksaan Administrasi Formal</div>
    <p class="narrative-p">
        Menindaklanjuti berkas permohonan yang diajukan oleh pemohon, Tim Administrasi DPMPTSP telah melakukan verifikasi dokumen formal guna memastikan legalitas subjek hukum dan objek bidang tanah. Pemeriksaan meliputi keabsahan sertifikat hak atas tanah dari BPN, kesesuaian dokumen identitas, serta pemenuhan komitmen legalitas dasar lainnya dengan hasil evaluasi sebagai berikut:
    </p>
    <table class="data-table">
        <thead>
            <tr>
                <th style="width: 5%;">No</th>
                <th style="width: 40%;">Uraian Persyaratan Dokumen</th>
                <th style="width: 20%;">Status</th>
                <th style="width: 35%;">Keterangan</th>
            </tr>
        </thead>
        <tbody>
            {% for item in administrative_checklist %}
            <tr>
                <td>{{ loop.index }}</td>
                <td>{{ item.doc_label }}</td>
                <td><span class="status-badge status-{{ item.status }}">{{ item.status }}</span></td>
                <td>{{ item.notes or "-" }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="section-title">II. Matriks Komparasi Parameter Teknis Spasial</div>
    <p class="narrative-p">
        Berdasarkan hasil pemetaan batas koordinat bidang tanah menggunakan kalibrasi parameter Helmert 2D terhitung, Tim Teknis Dinas PUPR melakukan analisis spasial tumpang tindih (overlay) terhadap dokumen rencana tapak (site plan) CAD yang disandingkan dengan Rencana Detail Tata Ruang (RDTR) Kabupaten Bogor dengan rincian evaluasi sebagai berikut:
    </p>

    <!-- TABEL II-A: SANDINGAN METRIK TAPAK (3-SISI) - BIARKAN MENGALIR SECARA NATURAL -->
    <div class="table-subtitle">Tabel II-A. Sandingan Metrik Tapak (3-Sisi)</div>
    <table class="data-table">
        <thead>
            <tr>
                <th style="width: 25%;">Parameter</th>
                <th style="width: 25%;">Proposed (Usulan)</th>
                <th style="width: 25%;">Bylaws (Aturan)</th>
                <th style="width: 25%;">Verified (Dinas)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td style="font-weight: bold;">KDB (Koefisien Dasar Bangunan)</td>
                <td>
                    {% if sandingan_3sisi.kdb.proposed_m2 is not none %}
                        {{ sandingan_3sisi.kdb.proposed_m2 }} m²
                        <br><span style="font-size: 8.5pt; color: #555;">({{ sandingan_3sisi.kdb.proposed_pct }}%)</span>
                    {% else %}
                        -
                    {% endif %}
                </td>
                <td>Maks {{ sandingan_3sisi.kdb.bylaw }}%</td>
                <td style="font-weight: bold;">
                    {{ sandingan_3sisi.kdb.verified if sandingan_3sisi.kdb.verified is not none else "-" }}
                </td>
            </tr>
            <tr>
                <td style="font-weight: bold;">KLB (Koefisien Lantai Bangunan)</td>
                <td>
                    {% if sandingan_3sisi.klb.proposed_m2 is not none %}
                        {{ sandingan_3sisi.klb.proposed_m2 }} m²
                        <br><span style="font-size: 8.5pt; color: #555;">({{ sandingan_3sisi.klb.proposed_pct }}x)</span>
                    {% else %}
                        -
                    {% endif %}
                </td>
                <td>Maks {{ sandingan_3sisi.klb.bylaw }}</td>
                <td style="font-weight: bold;">
                    {{ sandingan_3sisi.klb.verified if sandingan_3sisi.klb.verified is not none else "-" }}
                </td>
            </tr>
            <tr>
                <td style="font-weight: bold;">KDH (Koefisien Dasar Hijau)</td>
                <td>
                    {% if sandingan_3sisi.kdh.proposed_m2 is not none %}
                        {{ sandingan_3sisi.kdh.proposed_m2 }} m²
                        <br><span style="font-size: 8.5pt; color: #555;">({{ sandingan_3sisi.kdh.proposed_pct }}%)</span>
                    {% else %}
                        -
                    {% endif %}
                </td>
                <td>Min {{ sandingan_3sisi.kdh.bylaw }}%</td>
                <td style="font-weight: bold;">
                    {{ sandingan_3sisi.kdh.verified if sandingan_3sisi.kdh.verified is not none else "-" }}
                </td>
            </tr>
            <tr>
                <td style="font-weight: bold;">GSB (Garis Sempadan Bangunan)</td>
                <td>
                    {% if sandingan_3sisi.gsb.proposed is not none %}
                        {{ sandingan_3sisi.gsb.proposed }} m
                    {% else %}
                        -
                    {% endif %}
                </td>
                <td>Min {{ sandingan_3sisi.gsb.bylaw }} m</td>
                <td style="font-weight: bold;">
                    {{ sandingan_3sisi.gsb.verified if sandingan_3sisi.gsb.verified is not none else "-" }}
                </td>
            </tr>
            <tr>
                <td style="font-weight: bold;">RTH (Ruang Terbuka Hijau)</td>
                <td>
                    {% if sandingan_3sisi.rth.proposed is not none %}
                        {{ sandingan_3sisi.rth.proposed }} m²
                    {% else %}
                        -
                    {% endif %}
                </td>
                <td>Min {{ sandingan_3sisi.rth.bylaw }} m²</td>
                <td style="font-weight: bold;">
                    {{ sandingan_3sisi.rth.verified if sandingan_3sisi.rth.verified is not none else "-" }}
                </td>
            </tr>
        </tbody>
    </table>

    <!-- TABEL II-B: EVALUASI KELAYAKAN 13-ASPEK TEKNIS SPASIAL -->
    <div class="table-subtitle" style="margin-top: 25px;">Tabel II-B. Evaluasi Kelayakan Aspek Teknis Spasial</div>
    <table class="data-table">
        <thead>
            <tr>
                <th style="width: 45%;">Parameter Teknis</th>
                <th style="width: 15%;">Status</th>
                <th style="width: 40%;">Analisis Lapangan</th>
            </tr>
        </thead>
        <tbody>
            {% for metric in technical_comparison.matrix %}
            <tr>
                <td style="font-weight: bold;">{{ metric.label }}</td>
                <td><span class="status-badge status-{{ metric.status }}">{{ metric.status }}</span></td>
                <td>{{ metric.notes or "-" }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="section-title">III. Kesimpulan Dan Narasi Rekomendasi</div>
    <p style="text-align: justify; text-indent: 10mm; font-size: 11pt; margin-top: 10px;">
        {{ recommendation_summary.verdict_narrative }}
    </p>
    {% if recommendation_summary.verifikator_conclusion_notes and recommendation_summary.verifikator_conclusion_notes != "-" %}
    <p style="font-style: italic; font-size: 10pt; color: #444; border-left: 3px solid #000; padding-left: 10px; margin-top: 12px; page-break-inside: avoid;">
        Catatan Peninjauan Khusus: {{ recommendation_summary.verifikator_conclusion_notes }}
    </p>
    {% endif %}

    <div class="signature-block">
        <table class="signature-table">
            <tr>
                <td style="width: 50%;"></td>
                <td style="width: 50%; text-align: center;">
                    <p>Diformulasikan Oleh,<br><strong>TIM TEKNIS TATA RUANG</strong></p>
                    {% if verification_audit.technical.verified_at %}
                        <p style="font-size: 8pt; color: #555; margin: -5px 0 10px 0;">Tanggal: {{ verification_audit.technical.verified_at }}</p>
                    {% endif %}
                    {% if verification_audit.technical.verifier_signature %}
                        <div style="height: 60px; margin: 5px auto;">
                            <img src="{{ verification_audit.technical.verifier_signature }}" style="max-height: 60px; max-width: 150px; display: block; margin: 0 auto;" />
                        </div>
                    {% else %}
                        <br><br><br>
                    {% endif %}
                    <p><strong>{{ verification_audit.technical.verifier_name }}</strong><br>NIP. {{ verification_audit.technical.verifier_nip }}</p>
                </td>
            </tr>
        </table>
    </div>
</body>
</html>
"""


# ─── SECTION: ENGINE ADAPTER IMPLEMENTATION (Mewarisi DIP Port) ────────────

class HtmlToPdfEngine(DocumentGeneratorPort):
    """
    Engine terisolasi (Pure Fabrication) untuk merender draf dokumen cetak.
    Menggunakan Jinja2 untuk injeksi data dinamis dan WeasyPrint untuk ekspor PDF.
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        # Definisikan folder template fisik jika disuplai
        self.template_dir = Path(template_dir) if template_dir else Path("templates")
        
        # Inisialisasi Jinja2 Environment dengan toleransi kegagalan folder fisik
        if self.template_dir.exists() and self.template_dir.is_dir():
            self.jinja_env = Environment(loader=FileSystemLoader(str(self.template_dir)))
        else:
            # Fallback loader jika folder templates belum dibuat secara fisik
            self.jinja_env = Environment(loader=DictLoader({
                "telaah_staf.html": DEFAULT_TELAAH_STAF_TEMPLATE
            }))

    def render_html(self, template_name: str, context: Dict[str, Any]) -> str:
        """Menggabungkan data model konteks dengan template HTML Jinja2."""
        try:
            try:
                template = self.jinja_env.get_template(template_name)
            except Exception:
                # Jika template fisik tidak ditemukan di disk, gunakan fallback internal
                if "telaah" in template_name.lower():
                    logger.warning(f"[PDF_ENGINE] Template '{template_name}' tidak ditemukan di disk. Menggunakan draf bawaan.")
                    fallback_env = Environment(loader=DictLoader({"telaah_staf.html": DEFAULT_TELAAH_STAF_TEMPLATE}))
                    template = fallback_env.get_template("telaah_staf.html")
                else:
                    raise FileNotFoundError(f"Template '{template_name}' tidak terdaftar di server.")

            return template.render(**context)
        except Exception as e:
            logger.error(f"[PDF_ENGINE_ERROR] Gagal merender template HTML: {str(e)}", exc_info=True)
            raise RuntimeError(f"Gagal mengompilasi lembar HTML dokumen: {str(e)}")

    def compile_to_pdf(self, html_content: str, output_pdf_path: str) -> str:
        """
        Mengompilasi lembar kode HTML menjadi berkas biner PDF fisik.
        Menggunakan pengaman tipe statis yang ketat untuk menguji keberadaan WP_HTML.
        """
        output_path = Path(output_pdf_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # TYPE NARROWING CHECK: Menjamin WP_HTML bukan bertipe 'None' sebelum dipanggil
        if WEASYPRINT_AVAILABLE and WP_HTML is not None:
            try:
                logger.info(f"[PDF_ENGINE] Memulai kompilasi WeasyPrint untuk output: {output_pdf_path}")
                # Kompilasi HTML String -> PDF Fisik secara instan menggunakan rendering Cairo
                WP_HTML(string=html_content).write_pdf(str(output_path))
                logger.info("[PDF_ENGINE] Kompilasi WeasyPrint sukses.")
                return str(output_path.resolve())
            except Exception as e:
                logger.error(f"[PDF_ENGINE_CRASH] Gagal mengompilasi PDF via WeasyPrint: {str(e)}", exc_info=True)

        # ─── FALLBACK PDF GENERATOR (Jika WeasyPrint rusak/tidak terinstal) ─────
        logger.warning("[PDF_ENGINE_FALLBACK] Mengaktifkan penulisan dokumen Fail-Safe.")
        return self._generate_fallback_pdf(html_content, output_path)

    def _generate_fallback_pdf(self, html_content: str, output_path: Path) -> str:
        """
        Fallback Engine: Menuliskan dokumen PDF valid secara hukum yang berisi 
        informasi kegagalan rendering visual, serta mengamankan draf kode HTML.
        """
        stream_content = (
            "BT\n"
            "/F1 16 Tf\n"
            "50 800 Td\n"
            "(GEOSIPAS - DRAFT DOKUMEN (FAIL-SAFE)) Tj\n"
            "/F1 10 Tf\n"
            "0 -40 Td\n"
            "(Dokumen berhasil diproses oleh sistem backend.) Tj\n"
            "0 -20 Td\n"
            "(Namun, visualisasi PDF tidak dapat dirender secara sempurna karena server kekurangan dependensi Pango/Cairo.) Tj\n"
            "0 -20 Td\n"
            "(Silakan hubungi administrator dinas untuk menginstal WeasyPrint.) Tj\n"
            "0 -30 Td\n"
            "(Catatan: Salinan data mentah HTML lengkap disimpan di file .html di direktori yang sama.) Tj\n"
            "ET"
        )
        
        objects = []
        objects.append("1 0 obj\n<</Type /Catalog /Pages 2 0 R>>\nendobj\n")
        objects.append("2 0 obj\n<</Type /Pages /Kids [3 0 R] /Count 1>>\nendobj\n")
        objects.append(
            "3 0 obj\n"
            "<</Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            "/Resources <</Font <</F1 <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>>>>>> "
            "/Contents 4 0 R>>\n"
            "endobj\n"
        )
        
        stream_bytes = stream_content.encode("ascii", errors="ignore")
        stream_len = len(stream_bytes)
        obj4_header = f"4 0 obj\n<</Length {stream_len}>>\nstream\n".encode("ascii")
        obj4_footer = "\nendstream\nendobj\n".encode("ascii")
        obj4_bytes = obj4_header + stream_bytes + obj4_footer
        
        header = b"%PDF-1.4\n"
        offsets = []
        current_offset = len(header)
        
        offsets.append(current_offset)
        obj1_bytes = objects[0].encode("ascii")
        current_offset += len(obj1_bytes)
        
        offsets.append(current_offset)
        obj2_bytes = objects[1].encode("ascii")
        current_offset += len(obj2_bytes)
        
        offsets.append(current_offset)
        obj3_bytes = objects[2].encode("ascii")
        current_offset += len(obj3_bytes)
        
        offsets.append(current_offset)
        current_offset += len(obj4_bytes)
        
        xref_offset = current_offset
        
        # 20 bytes entry: 10-digit offset, space, 5-digit generation, space, n/f, space, eol
        xref_table = "xref\n0 5\n"
        xref_table += "0000000000 65535 f \r\n"
        for offset in offsets:
            xref_table += f"{offset:010d} 00000 n \r\n"
            
        trailer = (
            f"trailer\n"
            f"<</Size 5 /Root 1 0 R>>\n"
            f"startxref\n"
            f"{xref_offset}\n"
            f"%%EOF\n"
        )
        
        pdf_data = (
            header +
            obj1_bytes +
            obj2_bytes +
            obj3_bytes +
            obj4_bytes +
            xref_table.encode("ascii") +
            trailer.encode("ascii")
        )
        
        try:
            output_path.write_bytes(pdf_data)
            
            # Amankan salinan draf kode HTML
            html_debug_path = output_path.with_suffix(".html")
            html_debug_path.write_text(html_content, encoding="utf-8")
            
            logger.info(f"[PDF_ENGINE_FALLBACK] Sukses mengamankan draf HTML cadangan di: {html_debug_path}")
            return str(output_path.resolve())
        except Exception as e:
            logger.error(f"[PDF_ENGINE_FATAL] Fallback engine pun mengalami kegagalan I/O: {str(e)}")
            raise IOError(f"Sistem gagal menuliskan berkas cadangan ke disk: {str(e)}")

    # ─── SECTION: PORT METHOD IMPLEMENTATIONS (DIP Compliance) ─────────────────

    def generate_telaah_staf_pdf(
        self, 
        telaah_staf: TelaahStaf, 
        permohonan: Permohonan
    ) -> str:
        """Mengonversi data domain murni TelaahStaf dan Permohonan menjadi lembar cetak PDF fisik."""
        
        # Kalkulasi manual untuk proposed area metrik 3-sisi [569881990be1, pdf_engine.py]
        applicant_land_area = permohonan.applicant_land_area or permohonan.land_area or 0.0
        
        # KDB Proposed Area = (applicant_kdb / 100) * land_area
        kdb_proposed_m2 = None
        if permohonan.applicant_building_area is not None:
            kdb_proposed_m2 = permohonan.applicant_building_area
        elif permohonan.applicant_kdb is not None and applicant_land_area > 0:
            kdb_proposed_m2 = (permohonan.applicant_kdb / 100.0) * applicant_land_area

        # KLB Proposed Area = applicant_klb * land_area (or using tech_total_floor_area)
        klb_proposed_m2 = None
        if permohonan.tech_total_floor_area is not None:
            klb_proposed_m2 = permohonan.tech_total_floor_area
        elif permohonan.applicant_klb is not None and applicant_land_area > 0:
            klb_proposed_m2 = permohonan.applicant_klb * applicant_land_area

        # KDH Proposed Area = (applicant_kdh / 100) * land_area (or using green_area)
        kdh_proposed_m2 = None
        if permohonan.spatial_green_area is not None and permohonan.spatial_green_area > 0:
            kdh_proposed_m2 = permohonan.spatial_green_area
        elif permohonan.applicant_kdh is not None and applicant_land_area > 0:
            kdh_proposed_m2 = (permohonan.applicant_kdh / 100.0) * applicant_land_area

        # Pemetaan dynamic data Sandingan 3-Sisi [569881990be1, pdf_engine.py]
        sandingan_context = {
            "kdb": {
                "proposed_m2": f"{kdb_proposed_m2:,.1f}" if kdb_proposed_m2 is not None else None,
                "proposed_pct": f"{permohonan.applicant_kdb:.1f}" if permohonan.applicant_kdb is not None else None,
                "bylaw": f"{permohonan.bylaw_max_kdb:.1f}" if permohonan.bylaw_max_kdb is not None else "-",
                "verified": f"{permohonan.verified_kdb:.1f}%" if permohonan.verified_kdb is not None else None
            },
            "klb": {
                "proposed_m2": f"{klb_proposed_m2:,.1f}" if klb_proposed_m2 is not None else None,
                "proposed_pct": f"{permohonan.applicant_klb:.2f}" if permohonan.applicant_klb is not None else None,
                "bylaw": f"{permohonan.bylaw_max_klb:.1f}" if permohonan.bylaw_max_klb is not None else "-",
                "verified": f"{permohonan.verified_klb:.1f}" if permohonan.verified_klb is not None else None
            },
            "kdh": {
                "proposed_m2": f"{kdh_proposed_m2:,.1f}" if kdh_proposed_m2 is not None else None,
                "proposed_pct": f"{permohonan.applicant_kdh:.1f}" if permohonan.applicant_kdh is not None else None,
                "bylaw": f"{permohonan.bylaw_min_kdh:.1f}" if permohonan.bylaw_min_kdh is not None else "-",
                "verified": f"{permohonan.verified_kdh:.1f}%" if permohonan.verified_kdh is not None else None
            },
            "gsb": {
                "proposed": f"{permohonan.applicant_gsb:.1f}" if permohonan.applicant_gsb is not None else None,
                "bylaw": f"{permohonan.bylaw_min_gsb:.1f}" if permohonan.bylaw_min_gsb is not None else "-",
                "verified": f"{permohonan.verified_gsb:.1f} m" if permohonan.verified_gsb is not None else None
            },
            "rth": {
                "proposed": f"{permohonan.applicant_rth_area:,.1f}" if permohonan.applicant_rth_area is not None else None,
                "bylaw": f"{permohonan.bylaw_min_rth_area:,.1f}" if permohonan.bylaw_min_rth_area is not None else "-",
                "verified": f"{permohonan.verified_rth_area:,.1f} m²" if permohonan.verified_rth_area is not None else None
            }
        }

        context = {
            "document_metadata": {
                "title": "Telaah Staf Permohonan Ijin e-Siteplan",
                "document_no": f"TS-{permohonan.submission_no}",
                "created_at": telaah_staf.created_at.strftime("%d-%m-%Y %H:%M") if telaah_staf.created_at else "-",
                "verdict": permohonan.kkpr_verdict.value if permohonan.kkpr_verdict else telaah_staf.verdict.value
            },
            "applicant_snapshot": {
                "name": permohonan.applicant_name or permohonan.developer_name or "Pemohon",
                "director": permohonan.applicant_director_name or "-",
                "nib": permohonan.applicant_nib or "-",
                "phone": permohonan.applicant_phone or "-",
                "email": permohonan.applicant_email or "-"
            },
            "project_snapshot": {
                "activity_name": permohonan.housing_name or "Proyek",
                "village": permohonan.location_village or "-",
                "district": permohonan.location_district or "-"
            },
            "administrative_checklist": [
                {
                    "doc_label": item.doc_label,
                    "status": item.status,
                    "notes": item.notes or "-"
                } for item in telaah_staf.administrative_checklist
            ],
            "sandingan_3sisi": sandingan_context,
            "technical_comparison": {
                "matrix": [
                    {
                        "label": item.label,
                        "proposed_val": item.proposed_val,
                        "bylaw_val": item.bylaw_val,
                        "verified_val": item.verified_val,
                        "unit": item.unit,
                        "status": item.status,
                        "notes": item.notes or "-"
                    } for item in telaah_staf.technical_matrix
                ]
            },
            "recommendation_summary": {
                "verdict_narrative": telaah_staf.dynamic_narrative,
                "verifikator_conclusion_notes": telaah_staf.override_reason or "-"
            },
            "verification_audit": {
                "administrative": {
                    "verifier_name": telaah_staf.admin_verifier_name or "Rian Hidayat (Admin SIPAS)",
                    "verifier_nip": telaah_staf.admin_verifier_nip or "199208152018032001",
                    "verified_at": telaah_staf.admin_verified_at or "-"
                },
                "technical": {
                    "verifier_name": telaah_staf.verifier.name,
                    "verifier_nip": telaah_staf.verifier.nip,
                    "verified_at": telaah_staf.verifier.timestamp.strftime("%d-%m-%Y %H:%M") if telaah_staf.verifier.timestamp else "-",
                    "verifier_signature": getattr(telaah_staf.verifier, "signature_base64", None)
                }
            }
        }
        
        html_content = self.render_html("telaah_staf.html", context)
        output_dir = Path("docs")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"Telaah_Staf_{permohonan.id_permohonan}.pdf"
        return self.compile_to_pdf(html_content, str(output_path))

    def generate_draft_sk_siteplan(
        self, 
        permohonan: Permohonan, 
        notes_by_kabid: Optional[str] = None
    ) -> str:
        """Menghasilkan draf cetak visual dokumen Surat Keputusan (SK) Pengesahan."""
        output_dir = Path("docs")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"DRAFT_SK_Pengesahan_Site_Plan_{permohonan.id_permohonan}.pdf"
        
        html_content = (
            "<!DOCTYPE html><html><body>"
            f"<div style='text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px;'>"
            "<h2>DRAFT SURAT KEPUTUSAN KEPALA DINAS (DPMPTSP)</h2>"
            f"<h3>NOMOR: SK/{permohonan.submission_no}</h3></div>"
            f"<p>Tentang: Pengesahan Rencana Tapak (Site Plan) Perumahan '{permohonan.housing_name}'</p>"
            f"<p>Subjek Pemohon: {permohonan.applicant_name}</p>"
            f"<p>Lokasi Lahan: Desa {permohonan.location_village}, Kec. {permohonan.location_district}</p>"
            f"<p>Paraf Rekomendasi Kabid: [DIPARAF] {notes_by_kabid or ''}</p>"
            "</body></html>"
        )
        return self.compile_to_pdf(html_content, str(output_path))

    def generate_final_sk_siteplan(self, permohonan: Permohonan) -> str:
        """Menghasilkan dokumen SK final tanpa embel-embel cap draf, siap untuk TTE Kadis."""
        output_dir = Path("docs")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"SK_Pengesahan_Site_Plan_{permohonan.id_permohonan}.pdf"
        
        html_content = (
            "<!DOCTYPE html><html><body>"
            f"<div style='text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px;'>"
            "<h2>SURAT KEPUTUSAN BUPATI KABUPATEN BOGOR</h2>"
            "<h3>DINAS PENANAMAN MODAL DAN PELAYANAN TERPADU SATU PINTU</h3>"
            f"<h4>NOMOR: SK/{permohonan.submission_no}</h4></div>"
            f"<p>Menimbang dst... Mengesahkan gambar rencana tapak perumahan '{permohonan.housing_name}' "
            f"atas nama '{permohonan.applicant_name}' seluas {permohonan.land_area} m2.</p>"
            "<br><br><p style='text-align: right;'>Ditetapkan di: Cibinong</p>"
            "</body></html>"
        )
        return self.compile_to_pdf(html_content, str(output_path))