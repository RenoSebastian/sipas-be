"""
============================================================================
SIPAS INFRASTRUCTURE ADAPTER — Permohonan Repository [permohonan_repository.py]
============================================================================
Peran: Mengimplementasikan PermohonanRepositoryPort untuk berinteraksi dengan
       database transaksional PostgreSQL secara aman.
       Disesuaikan agar melindungi integritas data 10-tahap dari risiko
       terhapus secara tidak sengaja saat terjadi mutasi alur status berkas.
============================================================================
"""

from typing import Any, Optional, List
from sqlalchemy.orm import Session

from src.use_cases.submit_permohonan import PermohonanRepositoryPort
from src.domain.entities.permohonan import Permohonan, SubmissionStatus
from src.infrastructure.database.models import PermohonanModel

class PermohonanRepository(PermohonanRepositoryPort):
    def __init__(self, db: Session):
        self.db = db

    def _to_domain(self, model: PermohonanModel) -> Permohonan:
        """
        Konversi dari Model Database ke Entitas Domain Murni.
        Mengambil seluruh variabel yang dibutuhkan oleh domain logic dan administrative data.
        """
        polygon_coords = None
        if model.geom:
            from geoalchemy2.shape import to_shape
            try:
                shapely_poly = to_shape(model.geom)
                exterior = getattr(shapely_poly, "exterior", None)
                if exterior is not None:
                    polygon_coords = list(exterior.coords)
            except Exception:
                pass

        return Permohonan(
            id_permohonan=str(model.id_permohonan),
            submission_no=str(model.submission_no),
            housing_name=str(model.housing_name) if model.housing_name else None,
            developer_name=str(model.developer_name) if model.developer_name else None,
            land_area=float(model.land_area) if model.land_area is not None else None,
            submission_date=model.submission_date,
            status=SubmissionStatus(str(model.status)),
            buffer_sla=int(model.buffer_sla),
            elapsed_days=int(model.elapsed_days),
            
            # Tahap 1
            applicant_type=str(model.applicant_type) if model.applicant_type else None,
            applicant_name=str(model.applicant_name) if model.applicant_name else None,
            applicant_nik=str(model.applicant_nik) if model.applicant_nik else None,
            applicant_nib=str(model.applicant_nib) if model.applicant_nib else None,
            applicant_npwp=str(model.applicant_npwp) if model.applicant_npwp else None,
            applicant_director_name=str(model.applicant_director_name) if model.applicant_director_name else None,
            applicant_phone=str(model.applicant_phone) if model.applicant_phone else None,
            applicant_email=str(model.applicant_email) if model.applicant_email else None,
            applicant_address=str(model.applicant_address) if model.applicant_address else None,
            
            # Tahap 2
            submission_type=str(model.submission_type) if model.submission_type else None,
            submission_category=str(model.submission_category) if model.submission_category else None,
            
            # Tahap 3
            location_name=str(model.location_name) if model.location_name else None,
            location_village=str(model.location_village) if model.location_village else None,
            location_district=str(model.location_district) if model.location_district else None,
            location_city=str(model.location_city) if model.location_city else None,
            location_province=str(model.location_province) if model.location_province else None,
            location_full_address=str(model.location_full_address) if model.location_full_address else None,
            location_ownership_status=str(model.location_ownership_status) if model.location_ownership_status else None,
            location_certificate_number=str(model.location_certificate_number) if model.location_certificate_number else None,
            location_certificate_owner=str(model.location_certificate_owner) if model.location_certificate_owner else None,
            
            # Tahap 4 (CAD Helmert parameters)
            cad_file_name=str(model.cad_file_name) if model.cad_file_name else None,
            cad_param_a=float(model.cad_param_a) if model.cad_param_a is not None else None,
            cad_param_b=float(model.cad_param_b) if model.cad_param_b is not None else None,
            cad_param_tx=float(model.cad_param_tx) if model.cad_param_tx is not None else None,
            cad_param_ty=float(model.cad_param_ty) if model.cad_param_ty is not None else None,
            cad_scale=float(model.cad_scale) if model.cad_scale is not None else None,
            cad_rotation=float(model.cad_rotation) if model.cad_rotation is not None else None,
            
            # Tahap 5
            spatial_kkpr_number=str(model.spatial_kkpr_number) if model.spatial_kkpr_number else None,
            spatial_land_use=str(model.spatial_land_use) if model.spatial_land_use else None,
            spatial_green_area=float(model.spatial_green_area),
            
            # Tahap 6
            tech_lot_count=int(model.tech_lot_count) if model.tech_lot_count is not None else None,
            tech_housing_type=str(model.tech_housing_type) if model.tech_housing_type else None,
            tech_cemetery_area=float(model.tech_cemetery_area) if model.tech_cemetery_area is not None else None,
            tech_road_row_main=str(model.tech_road_row_main) if model.tech_road_row_main else None,
            tech_road_row_local=str(model.tech_road_row_local) if model.tech_road_row_local else None,
            tech_water_system=str(model.tech_water_system) if model.tech_water_system else None,
            
            tech_building_blocks=int(model.tech_building_blocks) if model.tech_building_blocks is not None else None,
            tech_kdb=float(model.tech_kdb) if model.tech_kdb is not None else None,
            tech_klb=float(model.tech_klb) if model.tech_klb is not None else None,
            tech_kdh=float(model.tech_kdh) if model.tech_kdh is not None else None,
            tech_parking_capacity=int(model.tech_parking_capacity) if model.tech_parking_capacity is not None else None,
            tech_max_floors=int(model.tech_max_floors) if model.tech_max_floors is not None else None,
            tech_total_floor_area=float(model.tech_total_floor_area) if model.tech_total_floor_area is not None else None,
            
            tech_facility_type=str(model.tech_facility_type) if model.tech_facility_type else None,
            tech_capacity=int(model.tech_capacity) if model.tech_capacity is not None else None,
            tech_disabled_access=str(model.tech_disabled_access) if model.tech_disabled_access else None,
            tech_special_parking=str(model.tech_special_parking) if model.tech_special_parking else None,
            tech_fire_protection=str(model.tech_fire_protection) if model.tech_fire_protection else None,
            
            tech_warehouse_count=int(model.tech_warehouse_count) if model.tech_warehouse_count is not None else None,
            tech_road_load_mst=str(model.tech_road_load_mst) if model.tech_road_load_mst else None,
            tech_electricity_power=str(model.tech_electricity_power) if model.tech_electricity_power else None,
            tech_ipal_capacity=str(model.tech_ipal_capacity) if model.tech_ipal_capacity else None,
            tech_green_buffer_area=float(model.tech_green_buffer_area) if model.tech_green_buffer_area is not None else None,
            tech_tps_b3_provision=str(model.tech_tps_b3_provision) if model.tech_tps_b3_provision else None,
            
            # Tahap 7
            consultant_name=str(model.consultant_name) if model.consultant_name else None,
            consultant_company_name=str(model.consultant_company_name) if model.consultant_company_name else None,
            consultant_pic_name=str(model.consultant_pic_name) if model.consultant_pic_name else None,
            

            
            # Tahap 10
            statement_agreed=bool(model.statement_agreed),
            polygon=polygon_coords,
            user_id=int(model.user_id) if model.user_id is not None else None,
            signature_hash=model.signature_hash,
            signed_pdf_url=model.signed_pdf_url,
            kabid_signature=model.kabid_signature
        )

    def _to_model(self, entity: Permohonan) -> PermohonanModel:
        """
        Konversi dari Entitas Domain ke Model Database.
        """
        geom = None
        if entity.polygon:
            from shapely.geometry import Polygon as ShapelyPolygon
            from geoalchemy2.shape import from_shape
            try:
                coords = [(float(pt[0]), float(pt[1])) for pt in entity.polygon]
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                geom = from_shape(ShapelyPolygon(coords), srid=4326)
            except Exception:
                pass

        return PermohonanModel(
            id_permohonan=entity.id_permohonan,
            submission_no=entity.submission_no,
            housing_name=entity.housing_name,
            developer_name=entity.developer_name,
            land_area=entity.land_area,
            submission_date=entity.submission_date,
            status=entity.status.value,
            buffer_sla=entity.buffer_sla,
            elapsed_days=entity.elapsed_days,
            
            # Tahap 1
            applicant_type=entity.applicant_type,
            applicant_name=entity.applicant_name,
            applicant_nik=entity.applicant_nik,
            applicant_nib=entity.applicant_nib,
            applicant_npwp=entity.applicant_npwp,
            applicant_director_name=entity.applicant_director_name,
            applicant_phone=entity.applicant_phone,
            applicant_email=entity.applicant_email,
            applicant_address=entity.applicant_address,
            
            # Tahap 2
            submission_type=entity.submission_type,
            submission_category=entity.submission_category,
            
            # Tahap 3
            location_name=entity.location_name,
            location_village=entity.location_village,
            location_district=entity.location_district,
            location_city=entity.location_city,
            location_province=entity.location_province,
            location_full_address=entity.location_full_address,
            location_ownership_status=entity.location_ownership_status,
            location_certificate_number=entity.location_certificate_number,
            location_certificate_owner=entity.location_certificate_owner,
            
            # Tahap 4
            geom=geom,
            cad_file_name=entity.cad_file_name,
            cad_param_a=entity.cad_param_a,
            cad_param_b=entity.cad_param_b,
            cad_param_tx=entity.cad_param_tx,
            cad_param_ty=entity.cad_param_ty,
            cad_scale=entity.cad_scale,
            cad_rotation=entity.cad_rotation,
            
            # Tahap 5
            spatial_kkpr_number=entity.spatial_kkpr_number,
            spatial_land_use=entity.spatial_land_use,
            spatial_green_area=entity.spatial_green_area,
            
            # Tahap 6
            tech_lot_count=entity.tech_lot_count,
            tech_housing_type=entity.tech_housing_type,
            tech_cemetery_area=entity.tech_cemetery_area,
            tech_road_row_main=entity.tech_road_row_main,
            tech_road_row_local=entity.tech_road_row_local,
            tech_water_system=entity.tech_water_system,
            
            tech_building_blocks=entity.tech_building_blocks,
            tech_kdb=entity.tech_kdb,
            tech_klb=entity.tech_klb,
            tech_kdh=entity.tech_kdh,
            tech_parking_capacity=entity.tech_parking_capacity,
            tech_max_floors=entity.tech_max_floors,
            tech_total_floor_area=entity.tech_total_floor_area,
            
            tech_facility_type=entity.tech_facility_type,
            tech_capacity=entity.tech_capacity,
            tech_disabled_access=entity.tech_disabled_access,
            tech_special_parking=entity.tech_special_parking,
            tech_fire_protection=entity.tech_fire_protection,
            
            tech_warehouse_count=entity.tech_warehouse_count,
            tech_road_load_mst=entity.tech_road_load_mst,
            tech_electricity_power=entity.tech_electricity_power,
            tech_ipal_capacity=entity.tech_ipal_capacity,
            tech_green_buffer_area=entity.tech_green_buffer_area,
            tech_tps_b3_provision=entity.tech_tps_b3_provision,
            
            # Tahap 7
            consultant_name=entity.consultant_name,
            consultant_company_name=entity.consultant_company_name,
            consultant_pic_name=entity.consultant_pic_name,
            

            
            # Tahap 10
            statement_agreed=entity.statement_agreed,
            user_id=entity.user_id,
            signature_hash=entity.signature_hash,
            signed_pdf_url=entity.signed_pdf_url,
            kabid_signature=entity.kabid_signature
        )

    def find_by_id(self, id_permohonan: str) -> Optional[Permohonan]:
        """Menemukan data permohonan berdasarkan ID."""
        model = self.db.query(PermohonanModel).filter(PermohonanModel.id_permohonan == id_permohonan).first()
        if not model:
            return None
        return self._to_domain(model)

    def save(self, permohonan: Permohonan, commit: bool = True) -> Permohonan:
        """Menyimpan atau memperbarui data permohonan secara transaksional."""
        existing_model = self.db.query(PermohonanModel).filter(
            PermohonanModel.id_permohonan == permohonan.id_permohonan
        ).first()

        if existing_model:
            # Perbarui seluruh kolom domain model (inklusif 10-tahap & Helmert)
            existing_model.status = permohonan.status.value
            existing_model.buffer_sla = permohonan.buffer_sla
            existing_model.elapsed_days = permohonan.elapsed_days
            existing_model.housing_name = permohonan.housing_name
            existing_model.developer_name = permohonan.developer_name
            existing_model.land_area = permohonan.land_area
            
            # Tahap 1
            existing_model.applicant_type = permohonan.applicant_type
            existing_model.applicant_name = permohonan.applicant_name
            existing_model.applicant_nik = permohonan.applicant_nik
            existing_model.applicant_nib = permohonan.applicant_nib
            existing_model.applicant_npwp = permohonan.applicant_npwp
            existing_model.applicant_director_name = permohonan.applicant_director_name
            existing_model.applicant_phone = permohonan.applicant_phone
            existing_model.applicant_email = permohonan.applicant_email
            existing_model.applicant_address = permohonan.applicant_address
            
            # Tahap 2
            existing_model.submission_type = permohonan.submission_type
            existing_model.submission_category = permohonan.submission_category
            
            # Tahap 3
            existing_model.location_name = permohonan.location_name
            existing_model.location_village = permohonan.location_village
            existing_model.location_district = permohonan.location_district
            existing_model.location_city = permohonan.location_city
            existing_model.location_province = permohonan.location_province
            existing_model.location_full_address = permohonan.location_full_address
            existing_model.location_ownership_status = permohonan.location_ownership_status
            existing_model.location_certificate_number = permohonan.location_certificate_number
            existing_model.location_certificate_owner = permohonan.location_certificate_owner
            
            # Tahap 4 (CAD Helmert parameters)
            existing_model.cad_file_name = permohonan.cad_file_name
            existing_model.cad_param_a = permohonan.cad_param_a
            existing_model.cad_param_b = permohonan.cad_param_b
            existing_model.cad_param_tx = permohonan.cad_param_tx
            existing_model.cad_param_ty = permohonan.cad_param_ty
            existing_model.cad_scale = permohonan.cad_scale
            existing_model.cad_rotation = permohonan.cad_rotation
            
            # Tahap 5
            existing_model.spatial_kkpr_number = permohonan.spatial_kkpr_number
            existing_model.spatial_land_use = permohonan.spatial_land_use
            existing_model.spatial_green_area = permohonan.spatial_green_area
            
            # Tahap 6
            existing_model.tech_lot_count = permohonan.tech_lot_count
            existing_model.tech_housing_type = permohonan.tech_housing_type
            existing_model.tech_cemetery_area = permohonan.tech_cemetery_area
            existing_model.tech_road_row_main = permohonan.tech_road_row_main
            existing_model.tech_road_row_local = permohonan.tech_road_row_local
            existing_model.tech_water_system = permohonan.tech_water_system
            
            existing_model.tech_building_blocks = permohonan.tech_building_blocks
            existing_model.tech_kdb = permohonan.tech_kdb
            existing_model.tech_klb = permohonan.tech_klb
            existing_model.tech_kdh = permohonan.tech_kdh
            existing_model.tech_parking_capacity = permohonan.tech_parking_capacity
            existing_model.tech_max_floors = permohonan.tech_max_floors
            existing_model.tech_total_floor_area = permohonan.tech_total_floor_area
            
            existing_model.tech_facility_type = permohonan.tech_facility_type
            existing_model.tech_capacity = permohonan.tech_capacity
            existing_model.tech_disabled_access = permohonan.tech_disabled_access
            existing_model.tech_special_parking = permohonan.tech_special_parking
            existing_model.tech_fire_protection = permohonan.tech_fire_protection
            
            existing_model.tech_warehouse_count = permohonan.tech_warehouse_count
            existing_model.tech_road_load_mst = permohonan.tech_road_load_mst
            existing_model.tech_electricity_power = permohonan.tech_electricity_power
            existing_model.tech_ipal_capacity = permohonan.tech_ipal_capacity
            existing_model.tech_green_buffer_area = permohonan.tech_green_buffer_area
            existing_model.tech_tps_b3_provision = permohonan.tech_tps_b3_provision
            
            # Tahap 7
            existing_model.consultant_name = permohonan.consultant_name
            existing_model.consultant_company_name = permohonan.consultant_company_name
            existing_model.consultant_pic_name = permohonan.consultant_pic_name
            

            
            # Tahap 10
            existing_model.statement_agreed = permohonan.statement_agreed
            existing_model.user_id = permohonan.user_id
            existing_model.signature_hash = permohonan.signature_hash
            existing_model.signed_pdf_url = permohonan.signed_pdf_url
            existing_model.kabid_signature = permohonan.kabid_signature

            # Save polygon geom if updated
            if permohonan.polygon:
                from shapely.geometry import Polygon as ShapelyPolygon
                from geoalchemy2.shape import from_shape
                try:
                    coords = [(float(pt[0]), float(pt[1])) for pt in permohonan.polygon]
                    if coords[0] != coords[-1]:
                        coords.append(coords[0])
                    existing_model.geom = from_shape(ShapelyPolygon(coords), srid=4326)
                except Exception:
                    pass
        else:
            # Jika merupakan data baru, lakukan pendaftaran awal (INSERT)
            new_model = self._to_model(permohonan)
            self.db.add(new_model)

        if commit:
            self.db.commit()
        else:
            self.db.flush()
        return permohonan

    def find_all(self) -> List[Permohonan]:
        """Mendapatkan seluruh daftar permohonan."""
        models = self.db.query(PermohonanModel).all()
        return [self._to_domain(m) for m in models]

    def find_kompensasi_by_permohonan_id(self, id_permohonan: str) -> List[Any]:
        """Mengambil data kompensasi yang dikaitkan dengan ID permohonan."""
        from src.infrastructure.database.models import LahanKompensasiModel
        from src.domain.entities.kompensasi import LahanKompensasi, CompensationType, FulfillmentStatus
        
        models = self.db.query(LahanKompensasiModel).filter(
            LahanKompensasiModel.id_permohonan == id_permohonan
        ).all()
        
        results = []
        for m in models:
            polygon_coords = None
            if m.geom:
                from geoalchemy2.shape import to_shape
                try:
                    shapely_poly = to_shape(m.geom)
                    exterior = getattr(shapely_poly, "exterior", None)
                    if exterior is not None:
                        polygon_coords = list(exterior.coords)
                except Exception:
                    pass
            
            results.append(
                LahanKompensasi(
                    id_kompensasi=str(m.id_kompensasi),
                    id_permohonan=str(m.id_permohonan),
                    tipe_kompensasi=CompensationType(str(m.tipe_kompensasi)),
                    luas_kompensasi_m2=float(m.luas_kompensasi_m2),
                    polygon_coords=polygon_coords,
                    status_pemenuhan=FulfillmentStatus(str(m.status_pemenuhan)),
                    nilai_nominal=float(m.nilai_nominal),
                    bukti_legalitas_url=str(m.bukti_legalitas_url) if m.bukti_legalitas_url else None
                )
            )
        return results

    def save_kompensasi(self, kompensasi: Any) -> None:
        """Menyimpan atau memperbarui data kompensasi ke database."""
        from src.infrastructure.database.models import LahanKompensasiModel
        from shapely.geometry import Polygon as ShapelyPolygon
        from geoalchemy2.shape import from_shape

        existing_model = self.db.query(LahanKompensasiModel).filter(
            LahanKompensasiModel.id_kompensasi == kompensasi.id_kompensasi
        ).first()

        geom = None
        if kompensasi.polygon_coords:
            try:
                coords = [(float(pt[0]), float(pt[1])) for pt in kompensasi.polygon_coords]
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                geom = from_shape(ShapelyPolygon(coords), srid=4326)
            except Exception:
                pass

        if existing_model:
            existing_model.status_pemenuhan = kompensasi.status_pemenuhan.value
            existing_model.luas_kompensasi_m2 = kompensasi.luas_kompensasi_m2
            existing_model.nilai_nominal = kompensasi.nilai_nominal
            existing_model.bukti_legalitas_url = kompensasi.bukti_legalitas_url
            existing_model.geom = geom
        else:
            new_model = LahanKompensasiModel(
                id_kompensasi=kompensasi.id_kompensasi,
                id_permohonan=kompensasi.id_permohonan,
                tipe_kompensasi=kompensasi.tipe_kompensasi.value,
                luas_kompensasi_m2=kompensasi.luas_kompensasi_m2,
                geom=geom,
                status_pemenuhan=kompensasi.status_pemenuhan.value,
                nilai_nominal=kompensasi.nilai_nominal,
                bukti_legalitas_url=kompensasi.bukti_legalitas_url
            )
            self.db.add(new_model)
        self.db.commit()

    def save_files(self, id_permohonan: str, files: List[dict]) -> None:
        from src.infrastructure.database.models import PermohonanFileModel
        # 1. Hapus berkas lama
        self.db.query(PermohonanFileModel).filter(PermohonanFileModel.id_permohonan == id_permohonan).delete()
        # 2. Tambahkan berkas baru
        for f in files:
            new_file = PermohonanFileModel(
                id_permohonan=id_permohonan,
                file_type=f["file_type"],
                file_key=f["file_key"],
                file_name=f["file_name"],
                file_path=f["file_path"],
                file_url=f["file_url"]
            )
            self.db.add(new_file)
        self.db.commit()

    def commit(self) -> None:
        """Commit transaksi database yang sedang aktif secara eksplisit."""
        self.db.commit()

    def rollback(self) -> None:
        """Rollback transaksi database yang sedang aktif secara atomik."""
        self.db.rollback()