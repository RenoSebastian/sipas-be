"""
============================================================================
SIPAS REPOSITORY — PKKPR PostGIS Repository [pkkpr_repository.py]
============================================================================
Peran: Adapter akses data ke PostgreSQL & PostGIS untuk modul PKKPR.
       Menangani persistensi transaksional, komputasi spasial PostGIS,
       dan penegakan integritas data.
============================================================================
"""

import json
from typing import List, Optional, Tuple, Dict, Any
from datetime import datetime, date
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func, text, update

from src.infrastructure.database.models import (
    PKKPRSubmissionModel,
    PKKPRFileModel,
    PKKPRFprReviewModel,
    PKKPRSkDraftModel,
    UserModel,
    PermohonanModel
)
from src.domain.entities.pkkpr import PermohonanPKKPR, FPRReview, PKKPRDraftSK, PKKPRFile
from src.domain.value_objects.pkkpr_status import (
    PKKPRStatus,
    PKKPRCategory,
    FPRRecommendation,
    PKKPRFileType,
    SpatialEnvelope
)


class PKKPRRepository:
    def __init__(self, db: Session):
        self.db = db

    def generate_submission_no(self) -> str:
        """Menghasilkan nomor pendaftaran registrasi PKKPR yang unik dan atomik."""
        year = date.today().year
        month = date.today().month
        # Hitung urutan berdasarkan transaksi
        count = self.db.query(func.count(PKKPRSubmissionModel.id)).filter(
            func.extract('year', PKKPRSubmissionModel.created_at) == year
        ).scalar() or 0
        return f"REG-PKKPR/{year}/{month:02d}/{count + 1:04d}"

    def generate_id(self) -> str:
        """Menghasilkan ID unik primer PKKPR."""
        year = date.today().year
        month = date.today().month
        count = self.db.query(func.count(PKKPRSubmissionModel.id)).scalar() or 0
        return f"PKKPR-{year}{month:02d}-{count + 1:04d}"

    def save_submission(
        self,
        submission: PermohonanPKKPR,
        files: Optional[List[Dict[str, Any]]] = None
    ) -> PKKPRSubmissionModel:
        """Menyimpan entitas permohonan baru atau memperbarui yang sudah ada."""
        geom_json_str = json.dumps(submission.geom_geojson)

        model = self.db.query(PKKPRSubmissionModel).filter(
            PKKPRSubmissionModel.id == submission.id
        ).first()

        if not model:
            # Gunakan ST_SetSRID(ST_Multi(ST_GeomFromGeoJSON(:geom)), 4326)
            geom_expr = func.ST_SetSRID(
                func.ST_Multi(func.ST_GeomFromGeoJSON(geom_json_str)),
                4326
            )
            model = PKKPRSubmissionModel(
                id=submission.id,
                submission_no=submission.submission_no,
                user_id=submission.user_id,
                category=submission.category.value,
                status=submission.status.value,
                sla_start_date=submission.sla_start_date,
                elapsed_days=submission.elapsed_days,
                buffer_sla=submission.buffer_sla,
                applicant_type=submission.applicant_type,
                applicant_name=submission.applicant_name,
                applicant_nik=submission.applicant_nik,
                applicant_nib=submission.applicant_nib,
                applicant_npwp=submission.applicant_npwp,
                applicant_phone=submission.applicant_phone,
                applicant_email=submission.applicant_email,
                activity_description=submission.activity_description,
                kbli_code=submission.kbli_code,
                location_address=submission.location_address,
                location_village=submission.location_village,
                location_district=submission.location_district,
                location_city=submission.location_city,
                land_ownership_status=submission.land_ownership_status,
                certificate_number=submission.certificate_number,
                certificate_owner=submission.certificate_owner,
                geom=geom_expr,
                proposed_land_area_m2=submission.proposed_land_area_m2,
                approved_land_area_m2=submission.approved_land_area_m2,
                approved_kdb_max=submission.envelope.kdb_max_percent if submission.envelope else None,
                approved_klb_max=submission.envelope.klb_max if submission.envelope else None,
                approved_kdh_min=submission.envelope.kdh_min_percent if submission.envelope else None,
                approved_gsb_min=submission.envelope.gsb_min_meters if submission.envelope else None,
                approved_max_floors=submission.envelope.max_floors if submission.envelope else None,
                spatial_zone_code=submission.envelope.zone_code if submission.envelope else None,
                spatial_zone_name=submission.envelope.zone_name if submission.envelope else None,
                admin_lock_id=submission.admin_lock_id,
                technical_lock_id=submission.technical_lock_id,
                sk_number=submission.sk_number,
                sk_issued_date=submission.sk_issued_date,
                signed_pdf_url=submission.signed_pdf_url,
                qr_code_hash=submission.qr_code_hash
            )
            self.db.add(model)
        else:
            model.status = submission.status.value
            model.elapsed_days = submission.elapsed_days
            model.buffer_sla = submission.buffer_sla
            model.approved_land_area_m2 = submission.approved_land_area_m2
            if submission.land_ownership_status:
                model.land_ownership_status = submission.land_ownership_status
            if submission.certificate_number:
                model.certificate_number = submission.certificate_number
            if submission.certificate_owner:
                model.certificate_owner = submission.certificate_owner
            if submission.envelope:
                model.approved_kdb_max = submission.envelope.kdb_max_percent
                model.approved_klb_max = submission.envelope.klb_max
                model.approved_kdh_min = submission.envelope.kdh_min_percent
                model.approved_gsb_min = submission.envelope.gsb_min_meters
                model.approved_max_floors = submission.envelope.max_floors
                model.spatial_zone_code = submission.envelope.zone_code
                model.spatial_zone_name = submission.envelope.zone_name
            model.admin_lock_id = submission.admin_lock_id
            model.technical_lock_id = submission.technical_lock_id
            model.sk_number = submission.sk_number
            model.sk_issued_date = submission.sk_issued_date
            model.signed_pdf_url = submission.signed_pdf_url
            model.qr_code_hash = submission.qr_code_hash

        if files:
            for f in files:
                file_model = PKKPRFileModel(
                    pkkpr_id=submission.id,
                    file_type=f.get("file_type") or "LAMPIRAN",
                    file_name=f.get("file_name") or "file",
                    file_path=f.get("file_path") or "",
                    file_size=int(f.get("file_size") or 0),
                    mime_type=f.get("mime_type") or "application/octet-stream",
                    uploaded_at=datetime.utcnow()
                )
                self.db.add(file_model)

        self.db.commit()
        self.db.refresh(model)
        return model

    def get_by_id(self, pkkpr_id: str) -> Optional[PKKPRSubmissionModel]:
        """Mengambil permohonan PKKPR lengkap beserta relasinya."""
        return self.db.query(PKKPRSubmissionModel).options(
            joinedload(PKKPRSubmissionModel.files),
            joinedload(PKKPRSubmissionModel.fpr_reviews),
            joinedload(PKKPRSubmissionModel.sk_draft),
            joinedload(PKKPRSubmissionModel.admin_lock),
            joinedload(PKKPRSubmissionModel.technical_lock)
        ).filter(PKKPRSubmissionModel.id == pkkpr_id).first()

    def get_geojson_geometry(self, pkkpr_id: str) -> Optional[Dict[str, Any]]:
        """Mengambil representasi GeoJSON poligon batas lahan via PostGIS ST_AsGeoJSON."""
        query = text("SELECT ST_AsGeoJSON(geom) FROM pkkpr_submissions WHERE id = :id")
        result = self.db.execute(query, {"id": pkkpr_id}).scalar()
        if result:
            return json.loads(result)
        return None

    def list_submissions(
        self,
        user_id: Optional[int] = None,
        role: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Tuple[PKKPRSubmissionModel, Optional[str], Optional[str]]]:
        """
        Mengambil daftar permohonan sesuai role dan filter.
        Mengembalikan tuple: (Model, Nama Admin Pengunci, Nama Teknisi Pengunci).
        """
        AdminUser = UserModel
        TeknisiUser = UserModel

        query = self.db.query(
            PKKPRSubmissionModel,
            UserModel.full_name.label("admin_name")
        ).outerjoin(
            UserModel, PKKPRSubmissionModel.admin_lock_id == UserModel.id
        )

        if user_id and role == "PEMOHON":
            query = query.filter(PKKPRSubmissionModel.user_id == user_id)
        elif status:
            query = query.filter(PKKPRSubmissionModel.status == status)

        query = query.order_by(PKKPRSubmissionModel.created_at.desc())
        results = query.all()

        formatted_list = []
        for row in results:
            submission_model = row[0]
            admin_name = row[1]
            tech_name = None
            if submission_model.technical_lock_id:
                tech_user = self.db.query(UserModel).filter(UserModel.id == submission_model.technical_lock_id).first()
                if tech_user:
                    tech_name = tech_user.full_name
            formatted_list.append((submission_model, admin_name, tech_name))

        return formatted_list

    def check_spatial_overlap(self, geom_geojson: Dict[str, Any], exclude_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Mendeteksi tumpang tindih spasial terhadap poligon PKKPR aktif lainnya.
        Menggunakan PostGIS ST_Intersects & ST_Intersection untuk kalkulasi luas benturan.
        """
        geom_json_str = json.dumps(geom_geojson)
        query = text("""
            SELECT 
                p.id,
                p.submission_no,
                p.applicant_name,
                p.status,
                ST_Area(ST_Intersection(p.geom, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))::geography) as overlap_area_m2
            FROM pkkpr_submissions p
            WHERE p.status NOT IN ('DRAFT', 'DITOLAK', 'TIDAK_BERLAKU')
              AND (:exclude_id IS NULL OR p.id != :exclude_id)
              AND ST_Intersects(p.geom, ST_SetSRID(ST_GeomFromGeoJSON(:geom), 4326))
        """)
        rows = self.db.execute(query, {"geom": geom_json_str, "exclude_id": exclude_id}).fetchall()
        
        conflicts = []
        for r in rows:
            conflicts.append({
                "id": r.id,
                "submission_no": r.submission_no,
                "applicant_name": r.applicant_name,
                "status": r.status,
                "overlap_area_m2": float(r.overlap_area_m2)
            })
        return conflicts

    def validate_siteplan_inside_pkkpr(
        self,
        pkkpr_id: str,
        siteplan_geom_geojson: Dict[str, Any]
    ) -> Tuple[bool, float]:
        """
        Memvalidasi apakah denah Site Plan sepenuhnya berada di dalam poligon izin SK PKKPR.
        Menerapkan toleransi buffer 10 cm (0.1 meter) untuk mengantisipasi deviasi pembulatan
        koordinat antara CAD DXF/DWG dan PostGIS WGS84.
        Mengembalikan (is_fully_covered, area_outside_m2).
        """
        siteplan_json_str = json.dumps(siteplan_geom_geojson)
        query = text("""
            SELECT 
                ST_Covers(
                    ST_Buffer(p.geom::geography, 0.10)::geometry, 
                    ST_SetSRID(ST_GeomFromGeoJSON(:sp_geom), 4326)
                ) as is_covered,
                ST_Area(
                    ST_Difference(
                        ST_SetSRID(ST_GeomFromGeoJSON(:sp_geom), 4326), 
                        ST_Buffer(p.geom::geography, 0.10)::geometry
                    )::geography
                ) as area_outside_m2
            FROM pkkpr_submissions p
            WHERE p.id = :pkkpr_id
        """)
        row = self.db.execute(query, {"pkkpr_id": pkkpr_id, "sp_geom": siteplan_json_str}).fetchone()
        if not row:
            return (False, 0.0)
        return (bool(row.is_covered), float(row.area_outside_m2 or 0.0))

    def get_quota_summary(self, pkkpr_id: str) -> Optional[Dict[str, Any]]:
        """
        Menghitung akumulasi kuota lahan yang telah terpakai oleh Site Plan bertahap
        dan sisa kuota yang masih dapat dimanfaatkan sesuai Perbup Bogor No. 4/2025.
        """
        pkkpr = self.db.query(PKKPRSubmissionModel).filter(PKKPRSubmissionModel.id == pkkpr_id).first()
        if not pkkpr:
            return None

        total_area = float(pkkpr.approved_land_area_m2 or pkkpr.proposed_land_area_m2 or 0.0)

        # Ambil geometri batas luar SK PKKPR Induk (SRID 4326)
        pkkpr_geom_row = self.db.execute(
            text("SELECT ST_AsGeoJSON(geom) as geom_geojson FROM pkkpr_submissions WHERE id = :id"),
            {"id": pkkpr.id}
        ).fetchone()
        pkkpr_geometry = json.loads(pkkpr_geom_row.geom_geojson) if pkkpr_geom_row and pkkpr_geom_row.geom_geojson else None

        # Ambil daftar Site Plan anak beserta geometri masing-masing
        sp_rows = self.db.execute(text("""
            SELECT 
                sp.id_permohonan,
                sp.submission_no,
                sp.housing_name,
                sp.developer_name,
                sp.land_area,
                sp.status,
                sp.submission_date,
                sp.sk_number,
                COALESCE(
                    (SELECT ST_AsGeoJSON(sg.geom) FROM site_plan_geometries sg WHERE sg.id_permohonan = sp.id_permohonan AND sg.layer_name = 'PTSP_BATAS_LAHAN' LIMIT 1),
                    ST_AsGeoJSON(sp.geom)
                ) as geom_geojson
            FROM permohonan sp
            WHERE sp.pkkpr_id = :pkkpr_id
              AND sp.status NOT IN ('Ditolak', 'Tidak Berlaku')
            ORDER BY sp.submission_date ASC
        """), {"pkkpr_id": pkkpr_id}).fetchall()

        used_area = sum(float(r.land_area or 0.0) for r in sp_rows)
        remaining_area = max(0.0, round(total_area - used_area, 2))
        utilization_pct = round((used_area / total_area * 100.0), 2) if total_area > 0 else 0.0

        sp_list = []
        for r in sp_rows:
            geom_data = json.loads(r.geom_geojson) if r.geom_geojson else None
            sp_list.append({
                "id_permohonan": r.id_permohonan,
                "submission_no": r.submission_no,
                "housing_name": r.housing_name,
                "developer_name": r.developer_name,
                "land_area": float(r.land_area or 0.0),
                "status": r.status,
                "submission_date": r.submission_date.isoformat() if r.submission_date else None,
                "sk_number": r.sk_number,
                "geometry": geom_data
            })

        envelope = {
            "approved_kdb_max": pkkpr.approved_kdb_max,
            "approved_klb_max": pkkpr.approved_klb_max,
            "approved_kdh_min": pkkpr.approved_kdh_min,
            "approved_gsb_min": pkkpr.approved_gsb_min,
            "approved_max_floors": pkkpr.approved_max_floors,
            "spatial_zone_code": pkkpr.spatial_zone_code,
            "spatial_zone_name": pkkpr.spatial_zone_name
        }

        return {
            "pkkpr_id": pkkpr.id,
            "submission_no": pkkpr.submission_no,
            "applicant_name": pkkpr.applicant_name,
            "status": pkkpr.status,
            "sk_number": pkkpr.sk_number,
            "sk_issued_date": pkkpr.sk_issued_date.isoformat() if pkkpr.sk_issued_date else None,
            "total_approved_area_m2": total_area,
            "used_area_m2": round(used_area, 2),
            "remaining_area_m2": remaining_area,
            "utilization_percent": utilization_pct,
            "siteplans_count": len(sp_list),
            "siteplans": sp_list,
            "pkkpr_geometry": pkkpr_geometry,
            "envelope": envelope
        }

    def validate_phased_siteplan(
        self,
        pkkpr_id: str,
        new_siteplan_geom: Optional[Dict[str, Any]],
        new_area_m2: float,
        exclude_permohonan_id: Optional[str] = None,
        for_update: bool = False
    ) -> Dict[str, Any]:
        """
        Validasi kepatuhan hukum & spasial berlapis untuk pengajuan Site Plan bertahap (Perbup Bogor No. 4/2025):
        1. Status legalitas PKKPR wajib 'DISETUJUI'.
        2. Akumulasi kuota luas Site Plan tidak boleh melampaui alokasi SK PKKPR.
        3. Spasial: Bidang tapak Site Plan wajib 100% berada di dalam poligon PKKPR (toleransi buffer 10 cm).
        4. Spasial: Batas tapak Site Plan bertahap tidak boleh tumpang tindih dengan tahap sebelumnya.
        """
        pkkpr_query = self.db.query(PKKPRSubmissionModel).filter(PKKPRSubmissionModel.id == pkkpr_id)
        if for_update:
            pkkpr_query = pkkpr_query.with_for_update()
        pkkpr = pkkpr_query.first()
        if not pkkpr:
            return {
                "is_valid": False,
                "error": f"Permohonan PKKPR dengan ID '{pkkpr_id}' tidak ditemukan di sistem database.",
                "details": {"error_type": "NOT_FOUND"}
            }

        # 1. Validasi Status Legalitas
        if pkkpr.status != "DISETUJUI":
            return {
                "is_valid": False,
                "error": f"Pengajuan Site Plan ditolak. SK PKKPR ({pkkpr.submission_no}) belum berstatus 'DISETUJUI' (status saat ini: {pkkpr.status}).",
                "details": {"error_type": "INVALID_STATUS", "current_status": pkkpr.status}
            }

        total_area = float(pkkpr.approved_land_area_m2 or pkkpr.proposed_land_area_m2 or 0.0)

        # 2. Validasi Kuota Luas Kumulatif
        active_query = self.db.query(PermohonanModel).filter(
            PermohonanModel.pkkpr_id == pkkpr_id,
            PermohonanModel.status.notin_(["Ditolak", "Tidak Berlaku"])
        )
        if exclude_permohonan_id:
            active_query = active_query.filter(PermohonanModel.id_permohonan != exclude_permohonan_id)
        active_siteplans = active_query.all()

        current_used_area = sum(float(sp.land_area or 0.0) for sp in active_siteplans)
        remaining_quota = max(0.0, round(total_area - current_used_area, 2))

        # Toleransi 0.01 m² untuk menghindari pembulatan presisi desimal
        if (current_used_area + new_area_m2) > (total_area + 0.01):
            return {
                "is_valid": False,
                "error": f"Alokasi luas Site Plan ({new_area_m2:.2f} m²) melampaui sisa kuota SK PKKPR ({remaining_quota:.2f} m² dari total izin {total_area:.2f} m²).",
                "details": {
                    "error_type": "QUOTA_EXCEEDED",
                    "total_approved_area_m2": total_area,
                    "current_used_area_m2": current_used_area,
                    "remaining_quota_m2": remaining_quota,
                    "requested_area_m2": new_area_m2
                }
            }

        # 3. Validasi Containment Spasial PostGIS (Jika geometri polygon tersedia)
        if new_siteplan_geom:
            is_covered, outside_area = self.validate_siteplan_inside_pkkpr(pkkpr_id, new_siteplan_geom)
            if not is_covered and outside_area > 0.05:
                return {
                    "is_valid": False,
                    "error": f"Batas tapak bidang Site Plan melanggar batas izin SK PKKPR seluas {outside_area:.2f} m².",
                    "details": {
                        "error_type": "SPATIAL_BOUNDARY_VIOLATION",
                        "area_outside_m2": outside_area
                    }
                }

            # 4. Validasi Tumpang Tindih Antar Tahap (Non-overlapping sibling phases)
            geom_json_str = json.dumps(new_siteplan_geom)
            overlap_query = text("""
                SELECT 
                    sp.id_permohonan,
                    sp.submission_no,
                    sp.housing_name,
                    ST_Area(ST_Intersection(sp.geom, ST_SetSRID(ST_GeomFromGeoJSON(:sp_geom), 4326))::geography) as overlap_area_m2
                FROM permohonan sp
                WHERE sp.pkkpr_id = :pkkpr_id
                  AND sp.geom IS NOT NULL
                  AND sp.status NOT IN ('Ditolak', 'Tidak Berlaku')
                  AND (:exclude_id IS NULL OR sp.id_permohonan != :exclude_id)
                  AND ST_Intersects(sp.geom, ST_SetSRID(ST_GeomFromGeoJSON(:sp_geom), 4326))
            """)
            rows = self.db.execute(overlap_query, {
                "pkkpr_id": pkkpr_id,
                "sp_geom": geom_json_str,
                "exclude_id": exclude_permohonan_id
            }).fetchall()

            for r in rows:
                overlap_m2 = float(r.overlap_area_m2 or 0.0)
                if overlap_m2 > 0.05:
                    return {
                        "is_valid": False,
                        "error": f"Tumpang tindih spasial terdeteksi terhadap Site Plan Tahap Sebelumnya: '{r.submission_no} - {r.housing_name or ''}' seluas {overlap_m2:.2f} m².",
                        "details": {
                            "error_type": "SIBLING_OVERLAP_CONFLICT",
                            "conflicting_submission_id": r.id_permohonan,
                            "conflicting_submission_no": r.submission_no,
                            "overlap_area_m2": overlap_m2
                        }
                    }

        return {
            "is_valid": True,
            "error": None,
            "details": {
                "total_approved_area_m2": total_area,
                "current_used_area_m2": current_used_area,
                "remaining_quota_m2": round(remaining_quota - new_area_m2, 2),
                "is_within_boundary": True
            }
        }

    def add_fpr_review(self, review: FPRReview) -> PKKPRFprReviewModel:
        """Menyimpan Berita Acara dan rekomendasi sidang komite FPR."""
        model = PKKPRFprReviewModel(
            pkkpr_id=review.pkkpr_id,
            meeting_date=review.meeting_date,
            official_report_no=review.official_report_no,
            recommendation=review.recommendation.value,
            ptp_bpn_number=review.ptp_bpn_number,
            ptp_bpn_date=review.ptp_bpn_date,
            ptp_notes=review.ptp_notes,
            zoning_compliance_notes=review.zoning_compliance_notes,
            infrastructure_notes=review.infrastructure_notes,
            environmental_notes=review.environmental_notes,
            minutes_pdf_url=review.minutes_pdf_url,
            created_by_id=review.created_by_id
        )
        self.db.add(model)
        self.db.commit()
        self.db.refresh(model)
        return model

    def save_sk_draft(self, draft: PKKPRDraftSK) -> PKKPRSkDraftModel:
        """Menyimpan atau memperbarui formulasi draf SK penetapan PKKPR."""
        model = self.db.query(PKKPRSkDraftModel).filter(
            PKKPRSkDraftModel.pkkpr_id == draft.pkkpr_id
        ).first()

        if not model:
            model = PKKPRSkDraftModel(
                pkkpr_id=draft.pkkpr_id,
                draft_sk_number=draft.draft_sk_number,
                considerations=draft.considerations,
                legal_bases=draft.legal_bases,
                dictum_clauses=draft.dictum_clauses,
                obligations=draft.obligations,
                prepared_by_id=draft.prepared_by_id,
                kabid_notes=draft.kabid_notes,
                kabid_paraf_hash=draft.kabid_paraf_hash
            )
            self.db.add(model)
        else:
            model.draft_sk_number = draft.draft_sk_number
            model.considerations = draft.considerations
            model.legal_bases = draft.legal_bases
            model.dictum_clauses = draft.dictum_clauses
            model.obligations = draft.obligations
            model.kabid_notes = draft.kabid_notes
            model.kabid_paraf_hash = draft.kabid_paraf_hash

        self.db.commit()
        self.db.refresh(model)
        return model

    def get_siteplans_geojson(self, pkkpr_id: str) -> Dict[str, Any]:
        """
        Mengompilasi seluruh poligon CAD dari seluruh permohonan Site Plan (tahap 1, 2, dst)
        yang berafiliasi dengan SK PKKPR ini menjadi satu GeoJSON FeatureCollection terpadu.
        """
        query = text("""
            SELECT jsonb_build_object(
                'type', 'FeatureCollection',
                'features', COALESCE(jsonb_agg(features.feature), '[]'::jsonb)
            )
            FROM (
                SELECT jsonb_build_object(
                    'type', 'Feature',
                    'id', id,
                    'geometry', ST_AsGeoJSON(geom)::jsonb,
                    'properties', jsonb_build_object(
                        'id_permohonan', id_permohonan,
                        'submission_no', submission_no,
                        'housing_name', housing_name,
                        'layer_name', layer_name,
                        'color', CASE 
                            WHEN layer_name = 'PTSP_KDB' THEN '#475569'
                            WHEN layer_name = 'PTSP_PSU_JALAN' THEN '#cbd5e1'
                            WHEN layer_name = 'PTSP_KDH' THEN '#10b981'
                            WHEN layer_name = 'PTSP_PSU_MAKAM' THEN '#eab308'
                            WHEN layer_name = 'PTSP_BATAS_LAHAN' THEN '#0284c7'
                            ELSE '#14b8a6'
                        END,
                        'fillOpacity', CASE 
                            WHEN layer_name = 'PTSP_BATAS_LAHAN' THEN 0.15
                            WHEN layer_name = 'PTSP_PSU_JALAN' THEN 0.50
                            ELSE 0.70
                        END
                    )
                ) AS feature
                FROM (
                    SELECT
                        site_plan_geometries.id::text,
                        site_plan_geometries.id_permohonan,
                        permohonan.submission_no,
                        permohonan.housing_name,
                        site_plan_geometries.layer_name,
                        CASE
                            WHEN site_plan_geometries.layer_name = 'PTSP_BATAS_LAHAN'
                                THEN COALESCE(site_plan_geometries.geom, permohonan.geom)
                            ELSE COALESCE(
                                ST_CollectionExtract(
                                    ST_Intersection(site_plan_geometries.geom, COALESCE(permohonan.geom, site_plan_geometries.geom)),
                                    3
                                ),
                                site_plan_geometries.geom
                            )
                        END AS geom
                    FROM site_plan_geometries
                    JOIN permohonan
                        ON permohonan.id_permohonan = site_plan_geometries.id_permohonan
                    WHERE permohonan.pkkpr_id = :pkkpr_id
                        AND permohonan.status NOT IN ('Ditolak', 'Tidak Berlaku')
                        AND permohonan.geom IS NOT NULL

                    UNION ALL

                    SELECT
                        p.id_permohonan as id,
                        p.id_permohonan,
                        p.submission_no,
                        p.housing_name,
                        'PTSP_BATAS_LAHAN' as layer_name,
                        p.geom
                    FROM permohonan p
                    WHERE p.pkkpr_id = :pkkpr_id
                      AND p.status NOT IN ('Ditolak', 'Tidak Berlaku')
                      AND p.geom IS NOT NULL
                      AND NOT EXISTS (
                          SELECT 1 FROM site_plan_geometries sg WHERE sg.id_permohonan = p.id_permohonan
                      )
                ) clipped_siteplan
                WHERE NOT ST_IsEmpty(geom)
            ) features;
        """)
        try:
            raw_result = self.db.execute(query, {"pkkpr_id": pkkpr_id}).scalar()
            if not raw_result:
                return {"type": "FeatureCollection", "features": []}
            if isinstance(raw_result, str):
                return json.loads(raw_result)
            return raw_result
        except Exception as e:
            self.db.rollback()
            raise RuntimeError(f"Gagal memproses kompilasi CAD GeoJSON siteplans PKKPR: {str(e)}")

