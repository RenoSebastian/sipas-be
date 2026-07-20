"""
============================================================================
SIPAS HTTP SCHEMAS — Submissions [submissions.py] (REVISED v5.4 - TYPE SAFE)
============================================================================
Peran: Skema validasi data request HTTP menggunakan Pydantic untuk fungsionalitas
       core permohonan. Menjamin tipe data yang masuk sesuai dengan standar
       dinas, mendukung validasi pengajuan draf parsial (is_draft), silsilah
       permohonan revisi, pengaitan induk permohonan, serta input verifikasi
       teknis berbasis dimensi fisik absolut (m² / meter).
       
Pembaruan v5.4: Penambahan DTO khusus untuk Ground Inspection (titik darat)
               dan Aerial Inspection (drone video) secara terpisah.
============================================================================
"""

from pydantic import BaseModel, Field, model_validator, SecretStr
from datetime import date, datetime
from typing import Tuple, Optional, List, Any


class ApplicantDto(BaseModel):
    # Pelonggaran pola regex agar menerima nilai kosong ("" atau None) untuk mendukung penyimpanan draf parsial
    type: Optional[str] = Field(default="PERORANGAN", pattern="^(PERORANGAN|BADAN_USAHA|)$", examples=["BADAN_USAHA"])
    name: Optional[str] = Field(default=None, examples=["PT Geocitra Raya"])
    nik: Optional[str] = Field(default=None, examples=["3201020304050607"])
    nib: Optional[str] = Field(default=None, examples=["9120301938192"])
    npwp: Optional[str] = Field(default=None, examples=["01.234.567.8-901.000"])
    directorName: Optional[str] = Field(default=None, examples=["Ahmad Fauzi"])
    phone: Optional[str] = Field(default=None, examples=["081234567890"])
    email: Optional[str] = Field(default=None, examples=["ahmad.fauzi@geocitra.co.id"])
    address: Optional[str] = Field(default=None, examples=["Gedung Sentosa Lt. 4, Jakarta Pusat"])


class SubmissionDetailsDto(BaseModel):
    submissionType: Optional[str] = Field(default="BARU", pattern="^(BARU|REVISI|PERPANJANGAN|)$", examples=["BARU"])
    activityName: Optional[str] = Field(default=None, examples=["Grand Bogor Residence"])
    category: Optional[str] = Field(default="PERUMAHAN", pattern="^(PERUMAHAN|NON_PERUMAHAN|FASUM|INDUSTRI|)$", examples=["PERUMAHAN"])


class LocationDetailsDto(BaseModel):
    locationName: Optional[str] = Field(default=None, examples=["Lahan Baranangsiang"])
    village: Optional[str] = Field(default=None, examples=["Baranangsiang"])
    district: Optional[str] = Field(default=None, examples=["Bogor Timur"])
    city: Optional[str] = Field(default="Kabupaten Bogor", examples=["Kabupaten Bogor"])
    province: Optional[str] = Field(default="Jawa Barat", examples=["Jawa Barat"])
    fullAddress: Optional[str] = Field(default=None, examples=["Jl. Raya Pajajaran No.21, Kec. Bogor Timur"])
    landArea: Optional[float] = Field(default=None, examples=[25000.0])
    ownershipStatus: Optional[str] = Field(default="SHM", pattern="^(SHM|HGB|HAK_PAKAI|LAINNYA|)$", examples=["SHM"])
    certificateNumber: Optional[str] = Field(default=None, examples=["SHM No. 10293/Baranangsiang"])
    certificateOwner: Optional[str] = Field(default=None, examples=["PT Geocitra Raya"])


class CoordinateDto(BaseModel):
    polygon: Optional[list] = Field(default=None)
    coordinatesText: Optional[str] = Field(default=None)
    cadFileName: Optional[str] = Field(default=None, examples=["blueprint.dxf"])
    cadParamA: Optional[float] = Field(default=None)
    cadParamB: Optional[float] = Field(default=None)
    cadParamTx: Optional[float] = Field(default=None)
    cadParamTy: Optional[float] = Field(default=None)
    cadScale: Optional[float] = Field(default=None)
    cadRotation: Optional[float] = Field(default=None)


class SpatialDetailsDto(BaseModel):
    kkprNumber: Optional[str] = Field(default=None, examples=["503/KKPR/PUPR/2026/089"])
    landUse: Optional[str] = Field(default=None, examples=["Zona Perumahan Kepadatan Sedang"])
    greenArea: Optional[float] = Field(default=0.0, examples=[3850.0])


class TechnicalDetailsDto(BaseModel):
    lotCount: Optional[int] = Field(default=None, examples=[120])
    housingType: Optional[str] = Field(default=None, examples=["NON_SUBSIDI"])
    cemeteryArea: Optional[float] = Field(default=None, examples=[500.0])
    roadRowMain: Optional[str] = Field(default=None, examples=["12 Meter"])
    roadRowLocal: Optional[str] = Field(default=None, examples=["8 Meter"])
    waterSystem: Optional[str] = Field(default=None, examples=["PDAM"])
    waterSource: Optional[str] = Field(default=None, examples=["PDAM Tirta Kahuripan"])
    buildingBlocks: Optional[int] = Field(default=None, examples=[3])
    kdb: Optional[float] = Field(default=None, examples=[55.2])
    klb: Optional[float] = Field(default=None, examples=[2.1])
    kdh: Optional[float] = Field(default=None, examples=[15.4])
    parkingCapacity: Optional[int] = Field(default=None, examples=[150])
    maxFloors: Optional[int] = Field(default=None, examples=[5])
    totalFloorArea: Optional[float] = Field(default=None, examples=[24000.0])
    facilityType: Optional[str] = Field(default=None)
    capacity: Optional[int] = Field(default=None)
    disabledAccess: Optional[str] = Field(default=None)
    specialParking: Optional[str] = Field(default=None)
    fireProtection: Optional[str] = Field(default=None)
    warehouseCount: Optional[int] = Field(default=None)
    roadLoadMst: Optional[str] = Field(default=None)
    electricityPower: Optional[str] = Field(default=None)
    ipalCapacity: Optional[str] = Field(default=None)
    greenBufferArea: Optional[float] = Field(default=None)
    tpsB3Provision: Optional[str] = Field(default=None)

    # Metrik Proposed Pengembang
    applicantBuildingArea: Optional[float] = Field(default=None, examples=[13750.0])
    applicantGsb: Optional[float] = Field(default=None, examples=[5.0])
    applicantRthArea: Optional[float] = Field(default=None, examples=[2500.0])


class ConsultantDto(BaseModel):
    consultantName: Optional[str] = Field(default=None, examples=["Ir. Hermawan Pratama"])
    companyName: Optional[str] = Field(default=None, examples=["CV Rencana Semesta"])
    picName: Optional[str] = Field(default=None, examples=["Hermawan Pratama"])


class StatementDto(BaseModel):
    agreed: bool = Field(default=True)


class DocumentDto(BaseModel):
    legalDoc: Optional[str] = Field(default=None)
    technicalDoc: Optional[str] = Field(default=None)
    supportDoc: Optional[str] = Field(default=None)
    supportDoc2: Optional[str] = Field(default=None)
    skaDoc: Optional[str] = Field(default=None)
    cadDoc: Optional[str] = Field(default=None)
    ktpDoc: Optional[str] = Field(default=None)
    nibDoc: Optional[str] = Field(default=None)


class PhotoDto(BaseModel):
    photoNorth: Optional[str] = Field(default=None)
    photoSouth: Optional[str] = Field(default=None)
    photoEast: Optional[str] = Field(default=None)
    photoWest: Optional[str] = Field(default=None)
    photoAccess: Optional[str] = Field(default=None)


class TPUDetailsDto(BaseModel):
    method: str = Field(..., pattern="^(MANDIRI|EKSISTING|KERJASAMA|KOMPENSASI_UANG|INTEGRASI_WARGA)$")
    area: Optional[float] = None
    namaTpu: Optional[str] = None
    pengurusTpu: Optional[str] = None
    noPks: Optional[str] = None
    nominalKompensasi: Optional[float] = None
    alamat: Optional[str] = None
    koordinat: Optional[str] = None
    buktiDokumenUrl: Optional[str] = None


class SelfDeclaredCompensationDto(BaseModel):
    type: str = Field(..., pattern="^(LAHAN_SAWAH|LAHAN_MAKAM_FISIK|LAHAN_MAKAM_UANG|PSU_FISIK_TAMBAHAN)$")
    requiredAreaM2: float
    fulfillmentMethod: str = Field(..., pattern="^(PENYEDIAAN_FISIK_OFFSITE|KOMPENSASI_UANG|KERJASAMA_PIHAK_KETIGA)$")
    locationAddress: Optional[str] = None
    nominalAmount: Optional[float] = None
    documentUrl: Optional[str] = None


class LegacyMetadataDto(BaseModel):
    replaced_sk_number: str = Field(..., examples=["600/120/415.19/2020"])
    replaced_sk_date: date = Field(..., examples=["2020-08-15"])
    replaced_sk_doc_url: str = Field(..., examples=["/uploads/permohonan/sk_lama.pdf"])


class SubmitRequest(BaseModel):
    id_permohonan: Optional[str] = Field(default=None, examples=["sub-123456"])
    is_draft: bool = Field(default=False)
    
    baseline_source: Optional[str] = Field(default=None, pattern="^(DIGITAL|LEGACY|)$")
    parent_id_permohonan: Optional[str] = Field(default=None, examples=["sub-old-12345"])
    legacy_metadata: Optional[LegacyMetadataDto] = Field(default=None)

    applicant: ApplicantDto
    submission: SubmissionDetailsDto
    location: LocationDetailsDto
    coordinate: CoordinateDto
    spatial: SpatialDetailsDto
    technical: TechnicalDetailsDto
    consultant: ConsultantDto
    statement: StatementDto
    document: Optional[DocumentDto] = Field(default=None)
    photo: Optional[PhotoDto] = Field(default=None)
    tpu: Optional[TPUDetailsDto] = Field(default=None)
    compensations: Optional[List[SelfDeclaredCompensationDto]] = Field(default=None)

    @model_validator(mode='before')
    @classmethod
    def allow_empty_fields_for_draft(cls, data: Any) -> Any:
        if isinstance(data, dict):
            is_draft = data.get("is_draft", False)
            if is_draft:
                for field in ["applicant", "submission", "location", "coordinate", "spatial", "technical", "consultant", "statement", "document", "photo"]:
                    if field not in data or data[field] is None:
                        data[field] = {}
        return data


class CalibrateRequest(BaseModel):
    cad_file_path: str = Field(examples=["C:/temp/blueprint.dxf"])
    anchor_cad_1: Tuple[float, float] = Field(examples=[(10.0, 15.0)])
    anchor_cad_2: Tuple[float, float] = Field(examples=[(120.0, 95.0)])
    anchor_map_1: Tuple[float, float] = Field(examples=[(106.8272, -6.5971)])
    anchor_map_2: Tuple[float, float] = Field(examples=[(106.8295, -6.5990)])


class EvaluasiChecklistItemDto(BaseModel):
    aspek_code: str = Field(..., examples=["M3_KDB", "legalDoc"])
    aspek_label: str = Field(..., examples=["Koefisien Dasar Bangunan (KDB)", "Sertifikat Tanah BPN"])
    status_kelayakan: str = Field(..., pattern="^(Sesuai|Sesuai Bersyarat|Tidak Sesuai|Pending|SESUAI|SESUAI_BERSYARAT|TIDAK_SESUAI|PENDING)$", examples=["Sesuai"])
    catatan_verifikator: Optional[str] = Field(default=None, examples=["Memenuhi batas aman"])
    attachment_url: Optional[str] = Field(default=None, examples=["/uploads/evaluasi/revisi_kdb.pdf"])


class VerifyRequest(BaseModel):
    nip: Optional[str] = Field(default=None, examples=["197503112000031001"])
    passphrase: Optional[SecretStr] = Field(default=None, min_length=6, json_schema_extra={"writeOnly": True}, examples=["P@ssw0rdPejabat!"])
    action_type: str = Field(pattern="^(APPROVE|REJECT|REVERT_TO_TECHNICAL|REVERT_TO_ADMINISTRATIVE|OVERRIDE_VERDICT|SAVE_TECHNICAL_MATRIX|REVERT_TO_PEMOHON)$")
    notes: str = Field(...)
    is_spatially_compliant: bool = Field(default=True)
    signature_base64: Optional[str] = Field(default=None, description="Visual signature coretan tangan")

    kkpr_verdict: Optional[str] = Field(default=None, pattern="^(Sesuai|Sesuai Bersyarat|Perlu Perbaikan / Revisi|Tidak Sesuai / Ditolak|SESUAI|SESUAI_BERSYARAT|PERLU_PERBAIKAN|TIDAK_SESUAI)$")
    
    # ─── REVISED: RAW PHYSICAL DIMENSIONS UNTUK AUTOMATED CALCULATION ENGINE ───
    verified_land_area: Optional[float] = Field(default=None, description="Luas lahan terverifikasi fisik riil (m²)", examples=[9500.0])
    verified_building_area: Optional[float] = Field(default=None, description="Luas dasar tapak bangunan terverifikasi riil (m²)", examples=[5700.0])
    verified_total_floor_area: Optional[float] = Field(default=None, description="Luas akumulasi seluruh lantai terverifikasi riil (m²)", examples=[17100.0])
    verified_rth_area: Optional[float] = Field(default=None, description="Luas wilayah Ruang Terbuka Hijau terverifikasi riil (m²)", examples=[1425.0])
    verified_gsb: Optional[float] = Field(default=None, description="Garis Sempadan Bangunan terverifikasi riil (meter)", examples=[5.0])
    
    checklist_items: Optional[List[EvaluasiChecklistItemDto]] = None


class LinkParentRequest(BaseModel):
    """
    Skema validasi permintaan pengaitan manual silsilah permohonan (parent-child) oleh Admin.
    Menjamin kelengkapan dokumen pendukung yang dikirim berdasarkan skenario baseline yang dipilih.
    """
    baseline_source: str = Field(
        ..., 
        pattern="^(DIGITAL|LEGACY)$", 
        description="Sumber rujukan SK Lama yang dipilih", 
        examples=["DIGITAL"]
    )
    parent_id_permohonan: Optional[str] = Field(
        default=None, 
        description="ID permohonan rujukan yang terdaftar aktif dalam database (untuk tipe DIGITAL)", 
        examples=["sub-12345"]
    )
    replaced_sk_number: Optional[str] = Field(
        default=None, 
        description="Nomor Surat Keputusan rujukan fisik / lama (untuk tipe LEGACY)", 
        examples=["600/120/415.19/2020"]
    )
    replaced_sk_date: Optional[date] = Field(
        default=None, 
        description="Tanggal terbit Surat Keputusan rujukan fisik / lama (untuk tipe LEGACY)", 
        examples=["2020-08-15"]
    )
    replaced_sk_doc_url: Optional[str] = Field(
        default=None, 
        description="URL berkas pindaian dokumen rujukan fisik / lama (untuk tipe LEGACY)", 
        examples=["/uploads/permohonan/sk_lama.pdf"]
    )
    notes: str = Field(
        ..., 
        min_length=5, 
        description="Justifikasi atau catatan tertulis dari Admin terkait pengaitan silsilah", 
        examples=["Menghubungkan permohonan revisi dengan SK Utama yang tumpang tindih spasial."]
    )

    @model_validator(mode='after')
    def validate_linkage_requirements(self) -> 'LinkParentRequest':
        if self.baseline_source == "DIGITAL" and not self.parent_id_permohonan:
            raise ValueError("Pengaitan bertipe 'DIGITAL' wajib melampirkan parameter 'parent_id_permohonan'.")
        
        if self.baseline_source == "LEGACY":
            if not self.replaced_sk_number:
                raise ValueError("Pengaitan bertipe 'LEGACY' wajib mengisi parameter 'replaced_sk_number'.")
            if not self.replaced_sk_date:
                raise ValueError("Pengaitan bertipe 'LEGACY' wajib mengisi parameter 'replaced_sk_date'.")
            if not self.replaced_sk_doc_url:
                raise ValueError("Pengaitan bertipe 'LEGACY' wajib mengunggah dokumen rujukan pada 'replaced_sk_doc_url'.")
                
        return self


# ─── PEMBARUAN v5.4: DTO BARU UNTUK SINKRONISASI INSPEKSI DARAT & UDARA ──────

class GroundInspectionResponseDto(BaseModel):
    """Skema DTO untuk representasi data log sidak titik fisik darat (Ground Inspection)."""
    id: int = Field(..., examples=[1])
    id_permohonan: str = Field(..., examples=["sub-4"])
    inspector_name: str = Field(..., examples=["Ir. Budi Santoso"])
    timestamp: datetime = Field(...)
    latitude: float = Field(..., examples=[-6.3802])
    longitude: float = Field(..., examples=[106.9602])
    distance_from_boundary_meters: Optional[float] = Field(default=None, examples=[4.5])
    is_verified: bool = Field(default=True)
    photo_url: str = Field(..., examples=["http://localhost:8000/uploads/inspeksi/photo.jpg"])
    notes: Optional[str] = Field(default=None, examples=["Pemeriksaan patok beton sesuai dokumen BPN."])

    class Config:
        from_attributes = True


class AerialInspectionResponseDto(BaseModel):
    """Skema DTO untuk representasi data dokumentasi video udara drone secara makro (Aerial Inspection)."""
    id: int = Field(..., examples=[1])
    id_permohonan: str = Field(..., examples=["sub-4"])
    pilot_name: str = Field(..., examples=["Ir. Budi Santoso"])
    timestamp: datetime = Field(...)
    drone_video_url: str = Field(..., examples=["http://localhost:8000/uploads/inspeksi_video/drone.mp4"])
    flight_metadata: Optional[dict] = Field(default=None, examples=[{
        "drone_model": "DJI Mavic 3 Pro",
        "pilot_license": "Sertifikasi-FASI-10923",
        "flight_altitude_meters": 80.0,
        "weather_condition": "Clear Sky"
    }])
    notes: Optional[str] = Field(default=None, examples=["Flyover makro kawasan perumahan."])

    class Config:
        from_attributes = True