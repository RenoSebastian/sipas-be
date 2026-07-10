"""
============================================================================
SIPAS INFRASTRUCTURE TEMPLATES — Backup Inline HTML [backup_templates.py]
============================================================================
Peran: Menyimpan string HTML Jinja2 inline default sebagai cadangan (fallback)
       jika file template fisik tidak ditemukan pada sistem file server.
       Memisahkan urusan visual/dokumen dari logika kompilasi PDF Engine.
============================================================================
"""

# ─── TEMPLATE 1: TELAAH STAF DEFAULT TEMPLATE ─────────────────────────────────
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
        
        .status-badge {
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
            text-align: center;
            display: inline-block;
        }
        
        .status-SESUAI, .status-Sesuai, .status-DAPAT_DISETUJUI { 
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

# ─── TEMPLATE 2: SURAT KEPUTUSAN (SK) DEFAULT TEMPLATE ─────────────────────────
DEFAULT_SK_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Surat Keputusan - {{ document_metadata.sk_number }}</title>
    <style>
        @page {
            size: A4;
            margin: 20mm 15mm 20mm 20mm;
            @bottom-right {
                content: "Salinan SK Pengesahan - Halaman " counter(page);
                font-family: Arial, sans-serif;
                font-size: 8pt;
                color: #555;
            }
        }
        body {
            font-family: "Times New Roman", Times, serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #000;
            position: relative;
        }
        
        /* ─── WATERMARK DRAFT SECURITY (KONDISIONAL) ─── */
        {% if document_metadata.is_draft %}
        .watermark {
            position: fixed;
            top: 30%;
            left: 5%;
            width: 90%;
            text-align: center;
            font-size: 72pt;
            font-weight: bold;
            color: rgba(220, 53, 69, 0.12);
            transform: rotate(-35deg);
            z-index: -1000;
            text-transform: uppercase;
            pointer-events: none;
            border: 10px dashed rgba(220, 53, 69, 0.15);
            padding: 20px;
        }
        {% endif %}

        /* Kop Surat Standardisasi Permendagri */
        .kop-surat {
            text-align: center;
            border-bottom: 4px double #000;
            padding-bottom: 12px;
            margin-bottom: 20px;
        }
        .kop-surat h2 { margin: 0; font-size: 14pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }
        .kop-surat h1 { margin: 3px 0 0 0; font-size: 16pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }
        .kop-surat p { margin: 4px 0 0 0; font-size: 9pt; font-style: italic; color: #333; }

        .title-block {
            text-align: center;
            margin-bottom: 22px;
        }
        .title-block h3 { margin: 0; font-size: 12pt; font-weight: bold; text-transform: uppercase; }
        .title-block .nomor { margin-top: 4px; font-weight: bold; font-size: 11pt; }
        .title-block .tentang { margin-top: 12px; font-weight: bold; text-transform: uppercase; font-size: 12pt; }

        /* Struktur Diktum Penimbangan */
        .recital-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .recital-table td { vertical-align: top; padding: 4px 0; }
        .recital-table td.clause { width: 15%; font-weight: bold; text-transform: uppercase; }
        .recital-table td.num { width: 4%; text-align: center; }
        .recital-table td.text { text-align: justify; }

        /* Pembatas Bab Keputusan */
        .verdict-header {
            text-align: center;
            font-weight: bold;
            text-transform: uppercase;
            margin-top: 20px;
            margin-bottom: 15px;
            font-size: 12pt;
            letter-spacing: 1px;
        }

        .dictum-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .dictum-table td { vertical-align: top; padding: 6px 0; }
        .dictum-table td.dictum-name { width: 15%; font-weight: bold; text-transform: uppercase; }
        .dictum-table td.separator { width: 3%; text-align: center; }
        .dictum-table td.content { text-align: justify; }

        /* Tabel Rincian Data Teknis Diktum KEDUA */
        .inner-spec-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 8px;
            margin-bottom: 8px;
        }
        .inner-spec-table th, .inner-spec-table td {
            border: 1px solid #000;
            padding: 5px 7px;
            font-size: 9.5pt;
        }
        .inner-spec-table th { background-color: #f5f5f2; font-weight: bold; text-transform: uppercase; }

        tr, td, th {
            page-break-inside: avoid !important;
            break-inside: avoid-page !important;
        }

        /* Blok TTE / Tanda Tangan */
        .signer-block {
            margin-top: 35px;
            width: 100%;
            page-break-inside: avoid !important;
            break-inside: avoid-page !important;
        }
        .signer-table {
            width: 100%;
            border-collapse: collapse;
        }
        .signer-table td.spacer { width: 50%; }
        .signer-table td.content { width: 50%; text-align: center; }

        .tte-box {
            border: 1px solid #ddd;
            background-color: #fafafa;
            padding: 8px;
            margin: 8px auto;
            width: 200px;
            text-align: center;
            font-size: 8pt;
            color: #444;
        }
    </style>
</head>
<body>
    {% if document_metadata.is_draft %}
    <div class="watermark">DRAFT — BUKAN ASLI</div>
    {% endif %}

    <div class="kop-surat">
        <h2>Pemerintah Kabupaten Bogor</h2>
        <h1>Dinas Penanaman Modal Dan Pelayanan Terpadu Satu Pintu</h1>
        <p>Jl. Tegar Beriman No. 25, Cibinong 16914 | Telp: (021) 8751090, Fax: (021) 8751091 | email: dpmptsp@bogorkab.go.id</p>
    </div>

    <div class="title-block">
        <h3>Keputusan Kepala Dinas Penanaman Modal Dan Pelayanan Terpadu Satu Pintu</h3>
        <h3>Kabupaten Bogor</h3>
        <div class="nomor">NOMOR: {{ document_metadata.sk_number }}</div>
        <div class="tentang">TENTANG<br>Persetujuan Rencana Tapak (Site Plan) Perumahan<br>"{{ project_snapshot.activity_name }}"</div>
    </div>

    <!-- KONSIDERANS -->
    <table class="recital-table">
        <!-- Menimbang -->
        {% for item in considerations.menimbang %}
        <tr>
            <td class="clause">{% if loop.first %}Menimbang{% endif %}</td>
            <td class="num">:</td>
            <td class="text">{{ item }}</td>
        </tr>
        {% endfor %}
        <!-- Mengingat -->
        {% for item in considerations.mengingat %}
        <tr>
            <td class="clause">{% if loop.first %}Mengingat{% endif %}</td>
            <td class="num">:</td>
            <td class="text">{{ item }}</td>
        </tr>
        {% endfor %}
        <!-- Memperhatikan -->
        {% for item in considerations.memperhatikan %}
        <tr>
            <td class="clause">{% if loop.first %}Memperhatikan{% endif %}</td>
            <td class="num">:</td>
            <td class="text">{{ item }}</td>
        </tr>
        {% endfor %}
    </table>

    <div class="verdict-header">MEMUTUSKAN:</div>

    <!-- DIKTUM KEPUTUSAN -->
    <table class="dictum-table">
        <tr>
            <td class="dictum-name">Kesatu</td>
            <td class="separator">:</td>
            <td class="content">
                Memberikan Persetujuan Rencana Tapak (Site Plan) kepada Kuasa/Pemohon <strong>{{ applicant_snapshot.name }}</strong> yang bertindak untuk dan atas nama pemilik <strong>"{{ applicant_snapshot.company_name }}"</strong> atas lahan yang terletak di Desa/Kelurahan {{ project_snapshot.village }}, Kecamatan {{ project_snapshot.district }}, Kabupaten Bogor dengan luas total lahan bersih <strong>{{ project_snapshot.land_area }} m²</strong>.
            </td>
        </tr>
        <tr>
            <td class="dictum-name">Kedua</td>
            <td class="separator">:</td>
            <td class="content">
                Pemberian Persetujuan Rencana Tapak pada Diktum KESATU ditetapkan dengan spesifikasi teknis dan rincian pembagian ruang sebagai berikut:
                
                <!-- 1. Rincian Hunian -->
                <div style="margin-top: 8px; font-weight: bold;">1. Jumlah Kaveling Hunian Efektif:</div>
                <table class="inner-spec-table">
                    <thead>
                        <tr>
                            <th>Klasifikasi Kaveling / Tipe</th>
                            <th>Jumlah Unit</th>
                            <th>Estimasi Luas Total Hunian</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in diktum_hunian %}
                        <tr>
                            <td>{{ item.tipe_rumah }}</td>
                            <td style="text-align: center;">{{ item.jumlah_unit }} Unit</td>
                            <td style="text-align: right;">{{ item.luas_m2 }} m²</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>

                <!-- 2. Rincian PSU -->
                <div style="margin-top: 8px; font-weight: bold;">2. Prasarana, Sarana, dan Utilitas Umum (PSU):</div>
                <ul style="margin: 4px 0; padding-left: 20px; font-size: 10pt;">
                    <li><strong>Luas Alokasi Hijau/Taman (RTH)</strong>: {{ diktum_psu.total_psu_area_m2 }} m² (Memenuhi syarat minimal).</li>
                    <li><strong>Komponen Alokasi Utilitas</strong>: {{ diktum_psu.allocation_details }}.</li>
                    <li><strong>Skema Lahan Pemakaman (TPU 2%)</strong>: {{ diktum_psu.cemetery_scheme }}.</li>
                    <li><strong>Lebar Jalan (Rumija)</strong>: Berkisar antara {{ diktum_psu.road_row_min }} meter s/d {{ diktum_psu.road_row_max }} meter dengan konstruksi lapis keras perkerasan jalan paving block dilengkapi {{ diktum_psu.drainage_type }}.</li>
                </ul>

                <!-- 3. Rincian Koefisien Intensitas Ruang -->
                <div style="margin-top: 8px; font-weight: bold;">3. Intensitas Penggunaan Ruang Maksimal:</div>
                <table class="inner-spec-table" style="width: 70%; margin-left: 0;">
                    <thead>
                        <tr>
                            <th>Parameter</th>
                            <th>Batas Baku Pengesahan (Verified)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Koefisien Dasar Bangunan (KDB) Maksimal</td>
                            <td style="text-align: center; font-weight: bold;">{{ diktum_intensity.kdb_max }}%</td>
                        </tr>
                        <tr>
                            <td>Koefisien Lantai Bangunan (KLB) Maksimal</td>
                            <td style="text-align: center; font-weight: bold;">{{ diktum_intensity.klb_max }}x</td>
                        </tr>
                        <tr>
                            <td>Koefisien Dasar Hijau (KDH) Minimal</td>
                            <td style="text-align: center; font-weight: bold;">{{ diktum_intensity.kdh_min }}%</td>
                        </tr>
                    </tbody>
                </table>
            </td>
        </tr>
        <tr>
            <td class="dictum-name">Ketiga</td>
            <td class="separator">:</td>
            <td class="content">
                Apabila keterangan dan rincian spesifikasi teknis pada Diktum KEDUA tidak dipenuhi, tidak ditaati, atau disalahgunakan di luar peruntukan yang disahkan, maka Surat Keputusan Persetujuan Rencana Tapak (Site Plan) ini dinyatakan <strong>BATAL DEMI HUKUM</strong>.
            </td>
        </tr>
        <tr>
            <td class="dictum-name">Keempat</td>
            <td class="separator">:</td>
            <td class="content">
                Keputusan ini mulai berlaku pada tanggal ditetapkan dengan ketentuan bahwa segala sesuatunya akan ditinjau kembali dan diperbaiki sebagaimana mestinya apabila di kemudian hari terdapat kekeliruan.
            </td>
        </tr>
    </table>

    <!-- SIGNATURE BLOCK -->
    <div class="signer-block">
        <table class="signer-table">
            <tr>
                <td class="spacer"></td>
                <td class="content">
                    <p>Ditetapkan di: Cibinong<br>Pada Tanggal: {{ document_metadata.created_at }}</p>
                    <p><strong>KEPALA DINAS PENANAMAN MODAL DAN PTSP<br>KABUPATEN BOGOR</strong></p>
                    
                    {% if signer.signature_base64 %}
                        <!-- Visualisasi TTD Coret Kadis -->
                        <div style="height: 70px; margin: 10px auto;">
                            <img src="{{ signer.signature_base64 }}" style="max-height: 70px; max-width: 180px; display: block; margin: 0 auto;" />
                        </div>
                    {% else %}
                        <br><br><br>
                    {% endif %}
                    
                    <p><strong>{{ signer.name }}</strong><br>NIP. {{ signer.nip }}</p>
                    
                    <!-- Simbol Keamanan TTE BSrE Mock -->
                    <div class="tte-box">
                        Dokumen ini ditandatangani secara elektronik secara sah berdasarkan UU ITE Pasal 11.
                    </div>
                </td>
            </tr>
        </table>
    </div>
</body>
</html>
"""


# ─── TEMPLATE 3: EXECUTIVE REPORT DEFAULT TEMPLATE ────────────────────────────
DEFAULT_REPORT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Laporan Eksekutif GEOSIPAS - {{ month_name }} {{ year }}</title>
    <style>
        @page {
            size: A4;
            margin: 20mm 18mm 20mm 25mm;
            @bottom-center {
                content: "Halaman " counter(page) " dari " counter(pages);
                font-family: "Times New Roman", Times, serif;
                font-size: 8pt;
                color: #555;
            }
        }
        body {
            font-family: "Times New Roman", Times, serif;
            font-size: 11pt;
            line-height: 1.5;
            color: #111;
        }
        .header {
            text-align: center;
            margin-bottom: 16px;
            border-bottom: 2px solid #000;
            padding-bottom: 10px;
        }
        .header h1 {
            margin: 0;
            font-size: 13pt;
            text-transform: uppercase;
            font-weight: bold;
            font-family: Arial, Helvetica, sans-serif;
            letter-spacing: 0.5px;
        }
        .header h2 {
            margin: 3px 0 0 0;
            font-size: 11pt;
            text-transform: uppercase;
            font-weight: bold;
            font-family: Arial, Helvetica, sans-serif;
            color: #222;
        }
        .header p {
            margin: 5px 0 0 0;
            font-size: 9pt;
            color: #444;
            font-family: Arial, Helvetica, sans-serif;
        }

        .title-block {
            text-align: center;
            margin-bottom: 18px;
            margin-top: 6px;
        }
        .title-block h3 {
            margin: 0;
            font-size: 12pt;
            text-transform: uppercase;
            font-weight: bold;
            font-family: Arial, Helvetica, sans-serif;
            color: #111D13;
            letter-spacing: 0.3px;
        }
        .title-block p {
            margin: 4px 0 0 0;
            font-size: 10pt;
            color: #444;
            font-family: "Times New Roman", Times, serif;
        }

        .section-title {
            font-size: 10pt;
            font-weight: bold;
            text-transform: uppercase;
            font-family: Arial, Helvetica, sans-serif;
            background-color: #f1f5f4;
            padding: 5px 10px;
            margin-top: 18px;
            margin-bottom: 8px;
            border-left: 4px solid #415D43;
            color: #1e293b;
            letter-spacing: 0.2px;
        }

        .kpi-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 14px;
        }
        .kpi-table td {
            width: 25%;
            padding: 10px;
            border: 1px solid #bfcbbf;
            vertical-align: top;
        }
        .kpi-label {
            font-size: 8pt;
            font-weight: bold;
            font-family: Arial, Helvetica, sans-serif;
            color: #555;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        .kpi-value {
            font-size: 14pt;
            font-weight: bold;
            font-family: Arial, Helvetica, sans-serif;
            color: #111D13;
            margin-top: 5px;
        }
        .kpi-sub {
            font-size: 8.5pt;
            font-family: "Times New Roman", Times, serif;
            color: #555;
            margin-top: 3px;
        }

        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 14px;
            font-size: 9.5pt;
            font-family: "Times New Roman", Times, serif;
        }
        .data-table th {
            background-color: #f1f5f4;
            border: 1px solid #bfcbbf;
            padding: 6px 8px;
            font-weight: bold;
            font-family: Arial, Helvetica, sans-serif;
            font-size: 9pt;
            text-align: left;
            color: #1e293b;
        }
        .data-table td {
            border: 1px solid #d1d9d1;
            padding: 6px 8px;
            vertical-align: middle;
        }
        .text-center { text-align: center; }
        .text-right  { text-align: right; }
        .font-bold   { font-weight: bold; }

        .badge {
            display: inline-block;
            padding: 2px 6px;
            font-size: 8pt;
            font-weight: bold;
            font-family: Arial, Helvetica, sans-serif;
            color: #fff;
            border-radius: 2px;
        }
        .badge-emerald { background-color: #2d6a4f; }
        .badge-amber   { background-color: #b45309; }
        .badge-rose    { background-color: #be123c; }

        .footer-note {
            font-size: 8.5pt;
            font-family: "Times New Roman", Times, serif;
            color: #555;
            margin-top: 30px;
            border-top: 1px solid #ccc;
            padding-top: 6px;
            font-style: italic;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Pemerintah Kabupaten Bogor</h1>
        <h2>Dinas Penanaman Modal dan Pelayanan Terpadu Satu Pintu</h2>
        <p>Gedung Kesenian Kabupaten Bogor, Cibinong. Telp: (021) 8790-xxxx | Email: dpmptsp@bogorkab.go.id</p>
    </div>

    <div class="title-block">
        <h3>Laporan Eksekutif Realisasi Rencana Tapak (Site Plan)</h3>
        <p>Periode Laporan: {{ month_name }} {{ year }} &nbsp;|&nbsp; Tanggal Cetak: {{ print_date }}</p>
    </div>

    <div class="section-title">Ringkasan KPI Utama (YTD)</div>
    <table class="kpi-table">
        <tr>
            <td>
                <div class="kpi-label">Total Lahan YTD</div>
                <div class="kpi-value">{{ land_area_formatted }} m²</div>
                <div class="kpi-sub">Setara dengan ~{{ land_area_ha }} Ha</div>
            </td>
            <td>
                <div class="kpi-label">Pengajuan YTD</div>
                <div class="kpi-value">{{ total_pengajuan_ytd }} Berkas</div>
                <div class="kpi-sub">Bulan ini: {{ pengajuan_bulan_ini }} baru</div>
            </td>
            <td>
                <div class="kpi-label">Penyelesaian YTD</div>
                <div class="kpi-value">{{ total_disetujui_ytd }} SK</div>
                <div class="kpi-sub">Bulan ini: {{ penyelesaian_bulan_ini }} disahkan</div>
            </td>
            <td>
                <div class="kpi-label">Rasio Penerimaan</div>
                <div class="kpi-value">{{ success_rate }}%</div>
                <div class="kpi-sub">Lolos: {{ approved_decisions }} | Ditolak: {{ tidak_sesuai_ytd }}</div>
            </td>
        </tr>
    </table>

    <div class="section-title">Distribusi Keputusan Tata Ruang (YTD)</div>
    <table class="data-table">
        <thead>
          <tr>
            <th>Parameter Verifikasi</th>
            <th class="text-center">Jumlah Berkas</th>
            <th class="text-center">Persentase</th>
            <th>Rekomendasi Tindak Lanjut</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Sesuai (Lolos)</strong></td>
            <td class="text-center">{{ sesuai_ytd }}</td>
            <td class="text-center">{{ sesuai_pct }}%</td>
            <td>Rekomendasi persetujuan site plan langsung diterbitkan tanpa syarat.</td>
          </tr>
          <tr>
            <td><strong>Sesuai Bersyarat (Lolos Bersyarat)</strong></td>
            <td class="text-center">{{ sesuai_bersyarat_ytd }}</td>
            <td class="text-center">{{ sesuai_bersyarat_pct }}%</td>
            <td>Rekomendasi diterbitkan dengan kewajiban pemenuhan kompensasi PSU/KDH.</td>
          </tr>
          <tr>
            <td><strong>Tidak Sesuai / Ditolak</strong></td>
            <td class="text-center">{{ tidak_sesuai_ytd }}</td>
            <td class="text-center">{{ tidak_sesuai_pct }}%</td>
            <td>Berkas dikembalikan ke pemohon untuk melakukan revisi gambar rencana tapak.</td>
          </tr>
        </tbody>
    </table>

    <div class="section-title">Snapshot Pipeline Tahapan (Berkas Aktif Saat Ini)</div>
    <table class="data-table">
        <thead>
          <tr>
            <th class="text-center">1. Pemohon</th>
            <th class="text-center">2. Admin</th>
            <th class="text-center">3. Tim Teknis</th>
            <th class="text-center">4. Kabid</th>
            <th class="text-center">5. Kadis (TTE)</th>
            <th class="text-center">6. Selesai</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="text-center font-bold" style="font-size: 12pt; font-family: Arial, sans-serif;">{{ pipeline.pemohon }}</td>
            <td class="text-center font-bold" style="font-size: 12pt; font-family: Arial, sans-serif;">{{ pipeline.admin }}</td>
            <td class="text-center font-bold" style="font-size: 12pt; font-family: Arial, sans-serif;">{{ pipeline.teknis }}</td>
            <td class="text-center font-bold" style="font-size: 12pt; font-family: Arial, sans-serif;">{{ pipeline.kabid }}</td>
            <td class="text-center font-bold" style="font-size: 12pt; font-family: Arial, sans-serif;">{{ pipeline.kadis }}</td>
            <td class="text-center font-bold" style="font-size: 12pt; font-family: Arial, sans-serif; color: #2d6a4f;">{{ pipeline.selesai }}</td>
          </tr>
        </tbody>
    </table>

    <div class="section-title">Daftar Surat Keputusan (SK) Terbit - Periode {{ month_name }} {{ year }}</div>
    <table class="data-table">
        <thead>
          <tr>
            <th style="width: 25%;">No. Pengajuan</th>
            <th style="width: 45%;">Nama Perumahan / Kegiatan</th>
            <th style="width: 30%;" class="text-right">Nomor Surat Keputusan (SK)</th>
          </tr>
        </thead>
        <tbody>
          {% if sk_recap|length == 0 %}
          <tr>
            <td colspan="3" class="text-center" style="padding: 15px; color: #555; font-style: italic;">
              Tidak ada Surat Keputusan (SK) yang terbit pada periode ini.
            </td>
          </tr>
          {% else %}
            {% for sk in sk_recap %}
            <tr>
              <td>{{ sk.submission_no }}</td>
              <td><strong>{{ sk.housing_name }}</strong></td>
              <td class="text-right font-bold" style="color: #415D43;">{{ sk.sk_number }}</td>
            </tr>
            {% endfor %}
          {% endif %}
        </tbody>
    </table>

    <p class="footer-note">
        * Dokumen ini dibuat dan divalidasi secara otomatis melalui sistem GEOSIPAS Kabupaten Bogor berbasis data real-time spasial.
    </p>
</body>
</html>
"""

