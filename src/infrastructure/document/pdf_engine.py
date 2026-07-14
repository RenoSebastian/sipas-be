"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Enterprise PDF Engine [pdf_engine.py] (REVISED v10)
============================================================================
Peran: Engine pencetakan dokumen yang bertugas menyatukan template HTML Jinja2 
       dengan data JSONB menjadi berkas PDF fisik.
       Mewarisi DocumentGeneratorPort untuk menegakkan Dependency Inversion,
       serta mengamankan pengikatan variabel WeasyPrint (Anti-Unbound Pylance).
       Membaca inline template cadangan dari modul terpisah guna menjaga
       prinsip High Cohesion dan kelegaan pembacaan kode.
============================================================================
"""

import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone, timedelta

# Impor loader konfigurasi sistem (logo & nama aplikasi) — lazy-import untuk menghindari circular
def _load_branding() -> Dict[str, Any]:
    """
    Membaca konfigurasi branding (logo + nama aplikasi) dari system_config.json.
    Mengembalikan dict dengan key: logo_base64, app_name.
    """
    try:
        from src.infrastructure.http.routes.auth import load_system_config
        cfg = load_system_config()
        return {
            "logo_base64": cfg.get("appLogo") or None,
            "app_name": cfg.get("appName") or "GEOSIPAS"
        }
    except Exception:
        return {"logo_base64": None, "app_name": "GEOSIPAS"}

# Impor Jinja2 untuk mesin templating HTML
try:
    from jinja2 import Environment, DictLoader, FileSystemLoader
except ImportError:
    raise ImportError("[PDF_ENGINE_ERROR] Pustaka 'jinja2' wajib terpasang di dependencies Anda.")

# Impor Abstraksi Port & Entitas Domain untuk Pemenuhan Nominal Typing (DIP)
from src.use_cases.ports.document_generator_port import DocumentGeneratorPort
from src.domain.entities.telaah_staf import TelaahStaf
from src.domain.entities.permohonan import Permohonan
from src.domain.entities.sk_draft import SkDraft

# Impor Template Inline Cadangan dari File Terpisah (Mencegah File Terlalu Panjang)
from src.infrastructure.document.templates.backup_templates import (
    DEFAULT_TELAAH_STAF_TEMPLATE,
    DEFAULT_SK_TEMPLATE,
    DEFAULT_REPORT_TEMPLATE,
    DEFAULT_RECEIPT_TEMPLATE
)


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


# ─── ENGINE ADAPTER IMPLEMENTATION (Mewarisi DIP Port) ─────────────────────

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
            # Fallback loader terintegrasi menggunakan backup_templates.py (Loose Coupling)
            self.jinja_env = Environment(loader=DictLoader({
                "telaah_staf.html": DEFAULT_TELAAH_STAF_TEMPLATE,
                "sk_draft.html": DEFAULT_SK_TEMPLATE,
                "report_template.html": DEFAULT_REPORT_TEMPLATE,
                "receipt.html": DEFAULT_RECEIPT_TEMPLATE
            }))

    def render_html(self, template_name: str, context: Dict[str, Any]) -> str:
        """Menggabungkan data model konteks dengan template HTML Jinja2."""
        try:
            try:
                template = self.jinja_env.get_template(template_name)
            except Exception:
                # Jika template fisik tidak ditemukan di disk, gunakan fallback internal dari backup_templates
                if "telaah" in template_name.lower():
                    logger.warning(f"[PDF_ENGINE] Template '{template_name}' tidak ditemukan di disk. Menggunakan fallback.")
                    fallback_env = Environment(loader=DictLoader({"telaah_staf.html": DEFAULT_TELAAH_STAF_TEMPLATE}))
                    template = fallback_env.get_template("telaah_staf.html")
                elif "sk" in template_name.lower():
                    logger.warning(f"[PDF_ENGINE] Template '{template_name}' tidak ditemukan di disk. Menggunakan fallback.")
                    fallback_env = Environment(loader=DictLoader({"sk_draft.html": DEFAULT_SK_TEMPLATE}))
                    template = fallback_env.get_template("sk_draft.html")
                elif "report" in template_name.lower():
                    logger.warning(f"[PDF_ENGINE] Template '{template_name}' tidak ditemukan di disk. Menggunakan fallback.")
                    fallback_env = Environment(loader=DictLoader({"report_template.html": DEFAULT_REPORT_TEMPLATE}))
                    template = fallback_env.get_template("report_template.html")
                elif "receipt" in template_name.lower():
                    logger.warning(f"[PDF_ENGINE] Template '{template_name}' tidak ditemukan di disk. Menggunakan fallback.")
                    fallback_env = Environment(loader=DictLoader({"receipt.html": DEFAULT_RECEIPT_TEMPLATE}))
                    template = fallback_env.get_template("receipt.html")
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

        if WEASYPRINT_AVAILABLE and WP_HTML is not None:
            try:
                logger.info(f"[PDF_ENGINE] Memulai kompilasi WeasyPrint untuk output: {output_pdf_path}")
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
        permohonan: Permohonan,
        generated_by: Optional[str] = None
    ) -> str:
        """Mengonversi data domain murni TelaahStaf dan Permohonan menjadi lembar cetak PDF fisik."""
        
        applicant_land_area = permohonan.applicant_land_area or permohonan.land_area or 0.0
        
        kdb_proposed_m2 = None
        if permohonan.applicant_building_area is not None:
            kdb_proposed_m2 = permohonan.applicant_building_area
        elif permohonan.applicant_kdb is not None and applicant_land_area > 0:
            kdb_proposed_m2 = (permohonan.applicant_kdb / 100.0) * applicant_land_area

        klb_proposed_m2 = None
        if permohonan.tech_total_floor_area is not None:
            klb_proposed_m2 = permohonan.tech_total_floor_area
        elif permohonan.applicant_klb is not None and applicant_land_area > 0:
            klb_proposed_m2 = permohonan.applicant_klb * applicant_land_area

        kdh_proposed_m2 = None
        if permohonan.spatial_green_area is not None and permohonan.spatial_green_area > 0:
            kdh_proposed_m2 = permohonan.spatial_green_area
        elif permohonan.applicant_kdh is not None and applicant_land_area > 0:
            kdh_proposed_m2 = (permohonan.applicant_kdh / 100.0) * applicant_land_area

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

        # ─── System Log (Generated User, Tanggal & Waktu) ───
        wib_tz = timezone(timedelta(hours=7))
        now = datetime.now(wib_tz)
        gen_user = generated_by or (telaah_staf.verifier.name if getattr(telaah_staf, "verifier", None) else None) or getattr(telaah_staf, "admin_verifier_name", None) or "Sistem"
        system_log = {
            "generated_by": gen_user,
            "generated_date": now.strftime("%d-%m-%Y"),
            "generated_time": now.strftime("%H:%M:%S WIB"),
            "generated_at": now.strftime("%d-%m-%Y %H:%M:%S WIB")
        }


        # ─── Inject Branding (Logo + App Name dari System Config Admin) ───
        branding = _load_branding()

        context = {
            "system_log": system_log,
            "document_metadata": {
                "title": "Telaah Staf Permohonan Ijin e-Siteplan",
                "document_no": f"TS-{permohonan.submission_no}",
                "created_at": telaah_staf.created_at.strftime("%d-%m-%Y %H:%M") if telaah_staf.created_at else "-",
                "verdict": permohonan.kkpr_verdict.value if permohonan.kkpr_verdict else telaah_staf.verdict.value
            },
            "logo_base64": branding["logo_base64"],
            "app_name": branding["app_name"],
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

    # ─── BARU: RENDER PDF DRAF SK & SK FINAL SECARA PRESISI (TAHAP 5) ───────────

    def _build_sk_context(self, permohonan: Permohonan, sk_draft: SkDraft, is_draft: bool, generated_by: Optional[str] = None) -> Dict[str, Any]:
        """Menyusun payload konteks data untuk dirender ke dalam Surat Keputusan HTML."""
        
        # 1. Mengumpulkan data kaveling hunian
        diktum_hunian_payload = []
        for item in sk_draft.diktum_hunian:
            diktum_hunian_payload.append({
                "tipe_rumah": item.tipe_rumah,
                "jumlah_unit": item.jumlah_unit,
                "luas_m2": f"{item.luas_m2:,.1f}"
            })

        # 2. Mengumpulkan parameter PSU
        diktum_psu_payload = {
            "total_psu_area_m2": "-",
            "allocation_details": "-",
            "cemetery_scheme": "-",
            "road_row_min": "0.0",
            "road_row_max": "0.0",
            "drainage_type": "-"
        }
        if sk_draft.diktum_psu:
            diktum_psu_payload = {
                "total_psu_area_m2": f"{sk_draft.diktum_psu.total_psu_area_m2:,.1f}",
                "allocation_details": sk_draft.diktum_psu.allocation_details,
                "cemetery_scheme": sk_draft.diktum_psu.cemetery_scheme,
                "road_row_min": f"{sk_draft.diktum_psu.road_row_min:.1f}",
                "road_row_max": f"{sk_draft.diktum_psu.road_row_max:.1f}",
                "drainage_type": sk_draft.diktum_psu.drainage_type
            }

        # 3. Mengumpulkan intensitas ruang
        diktum_intensity_payload = {
            "kdb_max": "-",
            "klb_max": "-",
            "kdh_min": "-"
        }
        if sk_draft.diktum_intensity:
            diktum_intensity_payload = {
                "kdb_max": f"{sk_draft.diktum_intensity.kdb_max:.1f}",
                "klb_max": f"{sk_draft.diktum_intensity.klb_max:.2f}",
                "kdh_min": f"{sk_draft.diktum_intensity.kdh_min:.1f}"
            }

        # 4. Mengumpulkan data penandatangan (Kadis)
        signer_payload = {
            "name": "Drs. H. Mulyana, M.Si.",
            "nip": "197503112000031001",
            "office_title": "Kepala Dinas Penanaman Modal dan PTSP",
            "signature_base64": None
        }
        if sk_draft.signer:
            signer_payload = {
                "name": sk_draft.signer.name,
                "nip": sk_draft.signer.nip,
                "office_title": sk_draft.signer.office_title,
                "signature_base64": sk_draft.signer.signature_base64
            }

        # 5. Merakit Konsiderans
        considerations_payload = {
            "menimbang": [],
            "mengingat": [],
            "memperhatikan": []
        }
        if sk_draft.considerations:
            considerations_payload = {
                "menimbang": sk_draft.considerations.menimbang,
                "mengingat": sk_draft.considerations.mengingat,
                "memperhatikan": sk_draft.considerations.memperhatikan
            }

        # ─── System Log (Generated User, Tanggal & Waktu) ───
        wib_tz = timezone(timedelta(hours=7))
        now = datetime.now(wib_tz)
        system_log = {
            "generated_by": generated_by or "Sistem",
            "generated_date": now.strftime("%d-%m-%Y"),
            "generated_time": now.strftime("%H:%M:%S WIB"),
            "generated_at": now.strftime("%d-%m-%Y %H:%M:%S WIB")
        }

        # ─── Inject Branding (Logo + App Name dari System Config Admin) ───
        branding = _load_branding()

        # Return payload lengkap terstruktur
        return {
            "system_log": system_log,
            "logo_base64": branding["logo_base64"],
            "app_name": branding["app_name"],
            "document_metadata": {
                "sk_number": sk_draft.sk_number,
                "created_at": sk_draft.created_at.strftime("%d %B %Y") if sk_draft.created_at else datetime.now().strftime("%d %B %Y"),
                "is_draft": is_draft,
                "verdict": sk_draft.verdict.value
            },
            "applicant_snapshot": {
                "name": permohonan.applicant_name or permohonan.developer_name or "Pemohon",
                "company_name": permohonan.location_certificate_owner or "Mitra Pembangunan",
                "nib": permohonan.applicant_nib or "-",
                "address": permohonan.applicant_address or "-"
            },
            "project_snapshot": {
                "activity_name": permohonan.housing_name or "Proyek Pembangunan",
                "village": permohonan.location_village or "-",
                "district": permohonan.location_district or "-",
                "land_area": f"{permohonan.land_area:,.2f}" if permohonan.land_area is not None else "0.0"
            },
            "considerations": considerations_payload,
            "diktum_hunian": diktum_hunian_payload,
            "diktum_psu": diktum_psu_payload,
            "diktum_intensity": diktum_intensity_payload,
            "signer": signer_payload
        }

    def generate_draft_sk_siteplan(
        self, 
        permohonan: Permohonan, 
        sk_draft: SkDraft,
        notes_by_kabid: Optional[str] = None,
        generated_by: Optional[str] = None
    ) -> str:
        """Menghasilkan draf cetak visual Surat Keputusan (SK) lengkap dengan cap DRAFT."""
        
        # Merakit payload konteks draf keputusan
        context = self._build_sk_context(permohonan, sk_draft, is_draft=True, generated_by=generated_by)
        
        # Tambahkan memo Kabid jika dilampirkan
        if notes_by_kabid:
            context["document_metadata"]["notes_by_kabid"] = notes_by_kabid

        html_content = self.render_html("sk_draft.html", context)
        
        output_dir = Path("docs")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"DRAFT_SK_Pengesahan_Site_Plan_{permohonan.id_permohonan}.pdf"
        
        return self.compile_to_pdf(html_content, str(output_path))

    def generate_final_sk_siteplan(
        self, 
        permohonan: Permohonan,
        sk_draft: SkDraft,
        generated_by: Optional[str] = None
    ) -> str:
        """Menghasilkan dokumen Surat Keputusan (SK) bersih (final) siap dibubuhi TTE Kadis."""
        
        # Merakit payload keputusan final bersih (is_draft=False)
        context = self._build_sk_context(permohonan, sk_draft, is_draft=False, generated_by=generated_by)

        html_content = self.render_html("sk_draft.html", context)
        
        output_dir = Path("docs")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"SK_Pengesahan_Site_Plan_{permohonan.id_permohonan}.pdf"
        
        return self.compile_to_pdf(html_content, str(output_path))

    def generate_receipt_pdf(
        self, 
        permohonan: Permohonan,
        generated_by: Optional[str] = None
    ) -> str:
        """Mengonversi data permohonan menjadi berkas PDF tanda terima (receipt) fisik."""
        
        # ─── System Log (Generated User, Tanggal & Waktu) ───
        wib_tz = timezone(timedelta(hours=7))
        now = datetime.now(wib_tz)
        system_log = {
            "generated_by": generated_by or "Sistem GEOSIPAS",
            "generated_date": now.strftime("%d-%m-%Y"),
            "generated_time": now.strftime("%H:%M:%S WIB"),
            "generated_at": now.strftime("%d-%m-%Y %H:%M:%S WIB")
        }

        # ─── Inject Branding (Logo + App Name dari System Config Admin) ───
        branding = _load_branding()

        context = {
            "system_log": system_log,
            "logo_base64": branding["logo_base64"],
            "app_name": branding["app_name"],
            "permohonan": {
                "id_permohonan": permohonan.id_permohonan,
                "submission_no": permohonan.submission_no,
                "submission_date": permohonan.submission_date.strftime("%d-%m-%Y") if permohonan.submission_date else "-",
                "housing_name": permohonan.housing_name or "-",
                "developer_name": permohonan.developer_name or "-",
                "applicant_name": permohonan.applicant_name or permohonan.developer_name or "-",
                "document_category": permohonan.document_category.value if permohonan.document_category else "-",
                "land_area": f"{permohonan.land_area:,.2f}" if permohonan.land_area is not None else "0.0"
            }
        }
        
        html_content = self.render_html("receipt.html", context)
        output_dir = Path("docs")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"Tanda_Terima_{permohonan.id_permohonan}.pdf"
        return self.compile_to_pdf(html_content, str(output_path))