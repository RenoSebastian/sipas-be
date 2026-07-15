"""
============================================================================
SIPAS HTTP SCHEMAS — Submissions [submissions.py] (REVISED v5.1 - TYPE SAFE)
============================================================================
Peran: Skema validasi data request HTTP menggunakan Pydantic untuk fungsionalitas
       core permohonan. Menjamin tipe data yang masuk sesuai dengan standar
       dinas, serta mendukung validasi pengajuan draf parsial (is_draft) dan
       silsilah permohonan revisi secara deklaratif.
============================================================================
"""

from pydantic import BaseModel, Field, model_validator, SecretStr
from datetime import date
from typing import Tuple, Optional, List, Any


class ApplicantDto(BaseModel):
    type: Optional[str] = Field(default="PERORANGAN", pattern="^(PERORANGAN|BADAN_USAHA)$", examples=["BADAN_USAHA"])
    name: Optional[str] = Field(default=None, examples=["PT Geocitra Raya"])
    nik: Optional[str] = Field(default=None, examples=["3201020304050607"])
    nib: Optional[str] = Field(default=None, examples=["9120301938192"])
    npwp: Optional[str] = Field(default=None, examples=["01.234.567.8-901.000"])
    directorName: Optional[str] = Field(default=None, examples=["Ahmad Fauzi"])
    phone: Optional[str] = Field(default=None, examples=["081234567890"])
    email: Optional[str] = Field(default=None, examples=["ahmad.fauzi@geocitra.co.id"])
    address: Optional[str] = Field(default=None, examples=["Gedung Sentosa Lt. 4, Jakarta Pusat"])


class SubmissionDetailsDto(BaseModel):
    submissionType: Optional[str] = Field(default="BARU", pattern="^(BARU|REVISI|PERPANJANGAN)$", examples=["BARU"])
    activityName: Optional[str] = Field(default=None, examples=["Grand Bogor Residence"])
    category: Optional[str] = Field(default="PERUMAHAN", pattern="^(PERUMAHAN|NON_PERUMAHAN|FASUM|INDUSTRI)$", examples=["PERUMAHAN"])


class LocationDetailsDto(BaseModel):
    locationName: Optional[str] = Field(default=None, examples=["Lahan Baranangsiang"])
    village: Optional[str] = Field(default=None, examples=["Baranangsiang"])
    district: Optional[str] = Field(default=None, examples=["Bogor Timur"])
    city: Optional[str] = Field(default="Kabupaten Bogor", examples=["Kabupaten Bogor"])
    province: Optional[str] = Field(default="Jawa Barat", examples=["Jawa Barat"])
    fullAddress: Optional[str] = Field(default=None, examples=["Jl. Raya Pajajaran No.21, Kec. Bogor Timur"])
    landArea: Optional[float] = Field(default=None, examples=[25000.0])
    ownershipStatus: Optional[str] = Field(default="SHM", pattern="^(SHM|HGB|HAK_PAKAI|LAINNYA)$", examples=["SHM"])
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


# ─── UPDATE FASE 5 (REVISI): SKEMA DETIL METADATA FISIK/LEGACY SK LAMA ───────
class LegacyMetadataDto(BaseModel):
    replaced_sk_number: str = Field(..., examples=["600/120/415.19/2020"])
    replaced_sk_date: date = Field(..., examples=["2020-08-15"])
    replaced_sk_doc_url: str = Field(..., examples=["/uploads/permohonan/sk_lama.pdf"])


class SubmitRequest(BaseModel):
    id_permohonan: Optional[str] = Field(default=None, examples=["sub-123456"])
    is_draft: bool = Field(default=False)
    
    # ─── UPDATE FASE 5 (REVISI): SILSILAH PERMOHONAN SELF-REFERENTIAL ────────
    baseline_source: Optional[str] = Field(default=None, pattern="^(DIGITAL|LEGACY)$")
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
    action_type: str = Field(pattern="^(APPROVE|REJECT|REVERT_TO_TECHNICAL|REVERT_TO_ADMINISTRATIVE|OVERRIDE_VERDICT|SAVE_TECHNICAL_MATRIX)$")
    notes: str = Field(...)
    is_spatially_compliant: bool = Field(default=True)
    signature_base64: Optional[str] = Field(default=None, description="Visual signature coretan tangan")

    # Parameter Penilaian Spasial & Komparasi Tiga Sisi
    kkpr_verdict: Optional[str] = Field(default=None, pattern="^(Sesuai|Sesuai Bersyarat|Perlu Perbaikan / Revisi|Tidak Sesuai / Ditolak|SESUAI|SESUAI_BERSYARAT|PERLU_PERBAIKAN|TIDAK_SESUAI)$")
    verified_kdb: Optional[float] = None
    verified_klb: Optional[float] = None
    verified_kdh: Optional[float] = None
    verified_gsb: Optional[float] = None
    verified_rth_area: Optional[float] = None
    checklist_items: Optional[List[EvaluasiChecklistItemDto]] = None