"""
============================================================================
SIPAS USE CASE — Calibrate CAD [calibrate_cad.py] (REVISED v7)
============================================================================
Peran: Mengorkestrasikan pembacaan berkas gambar kerja CAD, kalkulasi
       transformasi koordinat Helmert 2D [Jakarta 5], konversi poligon rencana,
       dan mendaftarkan log audit perubahan status administratif [Bogor 7].
       Telah diisolasi penuh dari format presentasi spasial visual frontend.
============================================================================
"""

import os
from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, cast
from dataclasses import dataclass
from shapely.geometry import Polygon as ShapelyPolygon

from src.use_cases.submit_permohonan import PermohonanRepositoryPort, AuditTrailRepositoryPort
from src.domain.entities.permohonan import SubmissionStatus
from src.domain.value_objects.spatial_params import HelmertParameters, solveHelmert2D, Coordinate


# ─── SECTION: PORT ABSTRAKSI LAYANAN EKSTERNAL (PORTS) ───────────────────

class CadParserPort(ABC):
    @abstractmethod
    def parse_and_extract_layers(self, file_path: str) -> Dict[str, List[List[Tuple[float, float]]]]:
        """
        Membaca file CAD asli (.dwg/.dxf) dan mengembalikan koordinat lokal (x, y) 
        per layer standardisasi (KDB, KDH, Jalan, dll) [Jakarta 5].
        """
        pass


class GeoServerPort(ABC):
    @abstractmethod
    def publish_submission_layers(self, id_permohonan: str) -> None:
        """
        Picu penayangan / penyegaran layer peta visual interaktif di GeoServer [Bogor 3].
        Port ini diimplementasikan di layer infrastruktur dan dieksekusi di akhir background task.
        """
        pass


# ─── SECTION: INPUT DATA TRANSFER OBJECT (DTO) ────────────────────────────

@dataclass(frozen=True)
class CalibrateCadInputDto:
    id_permohonan: str
    cad_file_path: str
    anchor_cad_1: Tuple[float, float]  # [x, y] kontrol 1 pada CAD
    anchor_cad_2: Tuple[float, float]  # [x, y] kontrol 2 pada CAD
    anchor_map_1: Tuple[float, float]  # [lng, lat] geospasial 1 pada peta
    anchor_map_2: Tuple[float, float]  # [lng, lat] geospasial 2 pada peta
    actor_name: str
    role: str


# ─── SECTION: USE CASE INTERACTOR ─────────────────────────────────────────

class CalibrateCadUseCase:
    def __init__(
        self,
        permohonan_repo: PermohonanRepositoryPort,
        cad_parser: CadParserPort,
        audit_trail_repo: AuditTrailRepositoryPort
    ):
        """
        Inisialisasi Use Case dengan Dependency Injection.
        Ketergantungan terhadap GeoServerPort dilepas dari konstruktor ini untuk 
        mencegah bug race condition dan menjaga prinsip Low Coupling.
        """
        self.permohonan_repo = permohonan_repo
        self.cad_parser = cad_parser
        self.audit_trail_repo = audit_trail_repo

    def execute(self, input_dto: CalibrateCadInputDto) -> None:
        """Mengorkestrasikan penyelarasan koordinat & ekstraksi gambar CAD [Jakarta 5]."""
        
        # 1. Cari data permohonan di repositori
        permohonan = self.permohonan_repo.find_by_id(input_dto.id_permohonan)
        if not permohonan:
            raise ValueError(f"Ilegal: Permohonan ID '{input_dto.id_permohonan}' tidak ditemukan.")

        # 2. Hitung parameter transformasi Helmert 2D secara matematis murni [Jakarta 5]
        helmert_res = solveHelmert2D(
            p1=input_dto.anchor_cad_1,
            p2=input_dto.anchor_cad_2,
            P1=input_dto.anchor_map_1,
            P2=input_dto.anchor_map_2
        )

        # Bungkus hasil kalkulasi ke dalam Value Object HelmertParameters yang imutabel
        transform_params = HelmertParameters(
            A=helmert_res["A"],
            B=helmert_res["B"],
            Tx=helmert_res["Tx"],
            Ty=helmert_res["Ty"],
            scale=helmert_res["scale"],
            rotation_rad=helmert_res["rotation"]
        )

        # 3. Ekstrak nama file CAD dinamis dari jalur absolut fisiknya
        cad_filename = os.path.basename(input_dto.cad_file_path)

        # 4. Assign computed Helmert parameters to permohonan to avoid state loss
        permohonan.cad_file_name = cad_filename
        permohonan.cad_param_a = transform_params.A
        permohonan.cad_param_b = transform_params.B
        permohonan.cad_param_tx = transform_params.Tx
        permohonan.cad_param_ty = transform_params.Ty
        permohonan.cad_scale = transform_params.scale
        permohonan.cad_rotation = transform_params.rotation_rad

        # 5. Mutasikan status permohonan ke tahap evaluasi spasial dinas (Verifikasi Teknis)
        permohonan.transition_status(SubmissionStatus.VERIFIKASI_TEKNIS)

        # 6. Simpan status administratif (commit=True)
        self.permohonan_repo.save(permohonan)

        # 7. Catat mutasi berkas dan parameter kalibrasi ke dalam sistem log audit [Bogor 7]
        self.audit_trail_repo.log_action(
            submission_id=permohonan.id_permohonan,
            actor_name=input_dto.actor_name,
            role=input_dto.role,
            action="VERIFY_TECHNICAL_APPROVED",
            status_before=SubmissionStatus.VERIFIKASI_ADMINISTRASI.value,
            status_after=SubmissionStatus.VERIFIKASI_TEKNIS.value,
            notes=(
                f"Kalibrasi spasial berhasil diselesaikan. File CAD '{cad_filename}' "
                f"tertransformasi ke koordinat nyata (Skala: {transform_params.scale:.4f}, "
                f"Rotasi: {(transform_params.rotation_rad * (180 / 3.14159)):.2f}°)."
            )
        )