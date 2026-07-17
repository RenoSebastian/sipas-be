"""
============================================================================
SIPAS INFRASTRUCTURE TEMPLATES — Backup Inline HTML [backup_templates.py] (REVISED v10.2)
============================================================================
Peran: Menyimpan string HTML Jinja2 inline default sebagai cadangan (fallback)
       jika file template fisik tidak ditemukan pada sistem file server.
       Mendukung penomoran diktum hukum dinamis pada draf Surat Keputusan (SK)
       serta menyajikan visualisasi perbandingan luas fisik (m²) & galat selisih
       secara detil pada lembar Telaah Staf.
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
                font-family: Arial, Helvetica, sans-serif;
                font-size: 9pt;
            }
        }
        body {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 10pt;
            line-height: 1.5;
            color: #000;
        }
        .header {
            text-align: center;
            margin-bottom: 25px;
            border-bottom: 3px double #000;
            padding-bottom: 10px;
        }
        /* KOP SURAT — tabel logo + nama instansi */
        .kop-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 0;
        }
        .kop-table td { padding: 0; vertical-align: middle; }
        .kop-logo-cell { width: 72px; text-align: center; padding-right: 12px; }
        .kop-logo-cell img { width: 64px; height: 64px; object-fit: contain; display: block; margin: 0 auto; }
        .kop-logo-placeholder {
            width: 64px; height: 64px;
            background: #e8e8e8;
            border: 1px solid #ccc;
            display: flex; align-items: center; justify-content: center;
            font-size: 7pt; color: #888; text-align: center;
            font-family: Arial, sans-serif;
        }
        .kop-text-cell { text-align: center; }
        .kop-instansi { margin: 0; font-size: 11pt; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
        .kop-dinas   { margin: 2px 0 0 0; font-size: 13pt; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
        .kop-alamat  { margin: 3px 0 0 0; font-size: 8.5pt; color: #333; font-style: italic; }
        .kop-judul-dokumen {
            margin-top: 10px;
            text-align: center;
            font-size: 10.5pt;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        .header h1 { margin: 0; font-size: 13pt; text-transform: uppercase; font-weight: bold; }
        
        .meta-table, .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .meta-table td { padding: 4px 0; vertical-align: top; }
        .meta-table td.label { width: 25%; }
        .meta-table td.separator { width: 3%; text-align: center; }
        
        .data-table th, .data-table td {
            border: 1px solid #000;
            padding: 6px 8px;
            text-align: left;
            font-size: 9.5pt;
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

        /* PERBAIKAN: Menambahkan aturan anti-terpisah dari konten di bawahnya */
        .section-title {
            font-size: 10.5pt;
            font-weight: bold;
            text-transform: uppercase;
            margin-top: 15px;
            margin-bottom: 6px;
            text-decoration: underline;
            page-break-after: avoid !important;
            break-after: avoid !important;
        }
        
        /* PERBAIKAN: Menambahkan aturan anti-terpisah dari tabel di bawahnya */
        .table-subtitle {
            font-size: 9.5pt;
            font-weight: bold;
            text-transform: uppercase;
            margin-top: 10px;
            margin-bottom: 4px;
            color: #111;
            page-break-after: avoid !important;
            break-after: avoid !important;
        }
        
        .status-badge {
            font-weight: normal;
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
        .system-log-block {
            margin-top: 24px;
            padding: 10px 12px;
            border: 1px solid #cbd5e1;
            background: #f8fafc;
            font-size: 8.5pt;
            color: #334155;
            line-height: 1.4;
            page-break-inside: avoid !important;
            break-inside: avoid-page !important;
        }
        .system-log-title {
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-bottom: 4px;
            color: #0f172a;
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
            font-size: 9.5pt;
            margin-top: 4px;
            margin-bottom: 6px;
            line-height: 1.4;
        }
    </style>
</head>
<body>
    <!-- KOP SURAT INSTANSI -->
    <table class="kop-table" style="border-bottom: 3px double #000; padding-bottom: 10px; margin-bottom: 18px;">
        <tr>
            <td class="kop-logo-cell" style="width: 80px;">
                {% if logo_base64 %}
                    <img src="{{ logo_base64 }}" style="width: 64px; height: 64px; object-fit: contain; display: block; margin: 0 auto;" />
                {% else %}
                    <div style="width: 64px; height: 64px; background: #e8e8e8; border: 1px solid #ccc; display: block; margin: 0 auto; line-height: 64px; text-align: center; font-size: 7pt; color: #888; font-family: Arial, sans-serif;">{{ app_name }}</div>
                {% endif %}
            </td>
            <td class="kop-text-cell">
                <p class="kop-instansi">Pemerintah Kabupaten Bogor</p>
                <p class="kop-dinas">Dinas Penanaman Modal dan Pelayanan Terpadu Satu Pintu</p>
                <p class="kop-alamat">Jl. Tegar Beriman No. 25, Cibinong 16914 | Telp: (021) 8751090 | Email: dpmptsp@bogorkab.go.id</p>
            </td>
            <td style="width: 80px;"></td>
        </tr>
    </table>
    <p class="kop-judul-dokumen">Dokumen / Lembar Telaah Staf Permohonan Pengesahan E-Siteplan</p>
    <div style="margin-bottom: 18px;"></div>

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
            <td class="label">Keputusan Hasil Telaah</td>
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
                <th style="width: 5%; text-align: center;">No</th>
                <th style="width: 40%;">Uraian Persyaratan Dokumen</th>
                <th style="width: 20%; text-align: center;">Status</th>
                <th style="width: 35%;">Keterangan</th>
            </tr>
        </thead>
        <tbody>
            {% for item in administrative_checklist %}
            <tr>
                <td style="text-align: center;">{{ loop.index }}</td>
                <td>{{ item.doc_label }}</td>
                <td style="text-align: center;"><span class="status-badge status-{{ item.status }}">{{ item.status }}</span></td>
                <td>{{ item.notes or "-" }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <div class="section-title">II. Matriks Komparasi Parameter Teknis Spasial</div>
    <p class="narrative-p">
        Berdasarkan hasil pemetaan batas koordinat bidang tanah menggunakan kalibrasi parameter Helmert 2D terhitung, Tim Teknis Dinas PUPR melakukan analisis spasial tumpang tindih (overlay) terhadap dokumen rencana tapak (site plan) CAD yang disandingkan dengan Rencana Detail Tata Ruang (RDTR) Kabupaten Bogor dengan rincian evaluasi sebagai berikut:
    </p>

    <!-- REVISED v10.2: MERENDER PERBANDINGAN DIMENSI FISIK RIIL (m²) & PERSENTASE DALAM 5 KOLOM TERPADU -->
    <div class="table-subtitle">Tabel II-A. Sandingan Metrik Tapak Terpadu (m² &amp; Persentase)</div>
    <table class="data-table">
        <thead>
            <tr>
                <th style="width: 24%;">Parameter</th>
                <th style="width: 21%; text-align: center;">Proposed (Usulan)</th>
                <th style="width: 16%; text-align: center;">Bylaws (Aturan)</th>
                <th style="width: 21%; text-align: center;">Verified (Dinas)</th>
                <th style="width: 18%; text-align: center;">Selisih (Galat)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td><strong>Luas Lahan Terdaftar</strong></td>
                <td style="text-align: center;">{{ sandingan_3sisi.land.proposed_m2 }} m²</td>
                <td style="text-align: center;">-</td>
                <td style="text-align: center; font-weight: bold;">{{ sandingan_3sisi.land.verified_m2 }} m²</td>
                <td style="text-align: center; color: #842029; font-weight: bold;">
                    {{ sandingan_3sisi.land.error_sqm }} m²
                    <br><span style="font-size: 8pt; font-weight: normal;">({{ sandingan_3sisi.land.error_pct }})</span>
                </td>
            </tr>
            <tr>
                <td><strong>KDB (Koefisien Dasar Bangunan)</strong></td>
                <td style="text-align: center;">
                    {{ sandingan_3sisi.kdb.proposed_m2 }} m²
                    <br><span style="font-size: 8pt; color: #555;">({{ sandingan_3sisi.kdb.proposed_pct }}%)</span>
                </td>
                <td style="text-align: center;">Maks {{ sandingan_3sisi.kdb.bylaw }}%</td>
                <td style="text-align: center; font-weight: bold;">
                    {{ sandingan_3sisi.kdb.verified_m2 }} m²
                    <br><span style="font-size: 8pt; color: #111;">({{ sandingan_3sisi.kdb.verified_pct }})</span>
                </td>
                <td style="text-align: center; color: #842029; font-weight: bold;">
                    {{ sandingan_3sisi.kdb.error_sqm }} m²
                    <br><span style="font-size: 8pt; font-weight: normal;">({{ sandingan_3sisi.kdb.error_pct }})</span>
                </td>
            </tr>
            <tr>
                <td><strong>KLB (Koefisien Lantai Bangunan)</strong></td>
                <td style="text-align: center;">
                    {{ sandingan_3sisi.klb.proposed_m2 }} m²
                    <br><span style="font-size: 8pt; color: #555;">({{ sandingan_3sisi.klb.proposed_ratio }}x)</span>
                </td>
                <td style="text-align: center;">Maks {{ sandingan_3sisi.klb.bylaw }}</td>
                <td style="text-align: center; font-weight: bold;">
                    {{ sandingan_3sisi.klb.verified_m2 }} m²
                    <br><span style="font-size: 8pt; color: #111;">({{ sandingan_3sisi.klb.verified_ratio }}x)</span>
                </td>
                <td style="text-align: center; color: #842029; font-weight: bold;">
                    {{ sandingan_3sisi.klb.error_sqm }} m²
                    <br><span style="font-size: 8pt; font-weight: normal;">({{ sandingan_3sisi.klb.error_pct }})</span>
                </td>
            </tr>
            <tr>
                <td><strong>KDH (Koefisien Dasar Hijau)</strong></td>
                <td style="text-align: center;">
                    {{ sandingan_3sisi.kdh.proposed_m2 }} m²
                    <br><span style="font-size: 8pt; color: #555;">({{ sandingan_3sisi.kdh.proposed_pct }}%)</span>
                </td>
                <td style="text-align: center;">Min {{ sandingan_3sisi.kdh.bylaw }}%</td>
                <td style="text-align: center; font-weight: bold;">
                    {{ sandingan_3sisi.kdh.verified_m2 }} m²
                    <br><span style="font-size: 8pt; color: #111;">({{ sandingan_3sisi.kdh.verified_pct }})</span>
                </td>
                <td style="text-align: center; color: #14532d; font-weight: bold;">
                    {{ sandingan_3sisi.kdh.error_sqm }} m²
                    <br><span style="font-size: 8pt; font-weight: normal;">({{ sandingan_3sisi.kdh.error_pct }})</span>
                </td>
            </tr>
            <tr>
                <td><strong>GSB (Garis Sempadan Bangunan)</strong></td>
                <td style="text-align: center;">{{ sandingan_3sisi.gsb.proposed }}</td>
                <td style="text-align: center;">Min {{ sandingan_3sisi.gsb.bylaw }} m</td>
                <td style="text-align: center; font-weight: bold;">{{ sandingan_3sisi.gsb.verified }}</td>
                <td style="text-align: center;">-</td>
            </tr>
            <tr>
                <td><strong>RTH (Ruang Terbuka Hijau)</strong></td>
                <td style="text-align: center;">{{ sandingan_3sisi.rth.proposed }}</td>
                <td style="text-align: center;">Min {{ sandingan_3sisi.rth.bylaw }}</td>
                <td style="text-align: center; font-weight: bold;">{{ sandingan_3sisi.rth.verified }}</td>
                <td style="text-align: center;">-</td>
            </tr>
        </tbody>
    </table>

    <div class="table-subtitle" style="margin-top: 25px;">Tabel II-B. Evaluasi Kelayakan Aspek Teknis Spasial</div>
    <table class="data-table">
        <thead>
            <tr>
                <th style="width: 45%;">Parameter Teknis</th>
                <th style="width: 15%; text-align: center;">Status</th>
                <th style="width: 40%;">Analisis Lapangan</th>
            </tr>
        </thead>
        <tbody>
            {% for metric in technical_comparison.matrix %}
            <tr>
                <td>{{ metric.label }}</td>
                <td style="text-align: center;"><span class="status-badge status-{{ metric.status }}">{{ metric.status }}</span></td>
                <td>{{ metric.notes or "-" }}</td>
            </tr>
            {% endfor %}
        </tbody>
    </table>

    <!-- PERBAIKAN: Menambahkan gaya inline forced page break agar Seksi III pindah ke Halaman 3 dan menyatu dengan Tanda Tangan -->
    <div class="section-title" style="page-break-before: always; break-before: page;">III. Kesimpulan Dan Narasi Rekomendasi</div>
    <p style="text-align: justify; text-indent: 10mm; font-size: 9.5pt; margin-top: 10px;">
        {{ recommendation_summary.verdict_narrative }}
    </p>
    {% if recommendation_summary.verifikator_conclusion_notes and recommendation_summary.verifikator_conclusion_notes != "-" %}
    <p style="font-style: italic; font-size: 9pt; color: #444; border-left: 3px solid #000; padding-left: 10px; margin-top: 12px; page-break-inside: avoid;">
        Catatan Peninjauan Khusus: {{ recommendation_summary.verifikator_conclusion_notes }}
    </p>
    {% endif %}

    <div class="signature-block">
        <table class="signature-table">
            <tr>
                <td style="width: 50%;"></td>
                <td style="width: 50%; text-align: center;">
                    <p>Disusun Oleh,<br><strong>Verifikator Teknis</strong></p>
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

    <div class="system-log-block" style="margin-top: 28px;">
        <div class="system-log-title">Log Sistem Pembuatan Dokumen</div>
        <div>Pengguna: {{ system_log.generated_by or 'Sistem' }}</div>
        <div>Tanggal: {{ system_log.generated_date or '-' }}</div>
        <div>Waktu: {{ system_log.generated_time or '-' }}</div>
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
                font-family: "Times New Roman", Times, serif;
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
        .kop-surat h2 { margin: 0; font-size: 13pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }
        .kop-surat h1 { margin: 3px 0 0 0; font-size: 15pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }
        .kop-surat p { margin: 4px 0 0 0; font-size: 8.5pt; font-style: italic; color: #333; }

        .title-block {
            text-align: center;
            margin-bottom: 22px;
        }
        .title-block h3 { margin: 0; font-size: 11pt; font-weight: bold; text-transform: uppercase; }
        .title-block .nomor { margin-top: 4px; font-weight: bold; font-size: 10pt; }
        .title-block .tentang { margin-top: 12px; font-weight: bold; text-transform: uppercase; font-size: 11pt; }

        /* Struktur Diktum Penimbangan */
        .recital-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .recital-table td { vertical-align: top; padding: 4px 0; font-size: 9.5pt; }
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
            font-size: 11pt;
            letter-spacing: 1px;
        }

        .dictum-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .dictum-table td { vertical-align: top; padding: 6px 0; font-size: 9.5pt; }
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
            font-size: 9pt;
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
        .system-log-block {
            margin-top: 24px;
            padding: 10px 12px;
            border: 1px solid #d1d5db;
            background: #f9fafb;
            font-size: 8.5pt;
            color: #374151;
            line-height: 1.4;
            page-break-inside: avoid !important;
            break-inside: avoid-page !important;
        }
        .system-log-title {
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-bottom: 4px;
            color: #111827;
        }
    </style>
</head>
<body>
    {% if document_metadata.is_draft %}
    <div class="watermark">DRAFT — BUKAN ASLI</div>
    {% endif %}

    <table style="width: 100%; border-collapse: collapse; border-bottom: 4px double #000; padding-bottom: 12px; margin-bottom: 20px;">
        <tr>
            <td style="width: 80px; vertical-align: middle; text-align: center; padding-right: 12px;">
                {% if logo_base64 %}
                    <img src="{{ logo_base64 }}" style="width: 68px; height: 68px; object-fit: contain; display: block; margin: 0 auto;" />
                {% else %}
                    <div style="width: 68px; height: 68px; background: #e8e8e8; border: 1px solid #ccc; display: block; margin: 0 auto; line-height: 68px; text-align: center; font-size: 7pt; color: #888; font-family: Arial, sans-serif;">{{ app_name }}</div>
                {% endif %}
            </td>
            <td style="text-align: center; vertical-align: middle;">
                <h2 style="margin: 0; font-size: 13pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Pemerintah Kabupaten Bogor</h2>
                <h1 style="margin: 3px 0 0 0; font-size: 15pt; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">Dinas Penanaman Modal Dan Pelayanan Terpadu Satu Pintu</h1>
                <p style="margin: 4px 0 0 0; font-size: 8.5pt; font-style: italic; color: #333;">Jl. Tegar Beriman No. 25, Cibinong 16914 | Telp: (021) 8751090, Fax: (021) 8751091 | email: dpmptsp@bogorkab.go.id</p>
            </td>
            <td style="width: 80px;"></td>
        </tr>
    </table>

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
                            <th style="text-align: left;">Klasifikasi Kaveling / Tipe</th>
                            <th style="text-align: center;">Jumlah Unit</th>
                            <th style="text-align: center;">Estimasi Luas Total Hunian</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for item in diktum_hunian %}
                        <tr>
                            <td>{{ item.tipe_rumah }}</td>
                            <td style="text-align: center;">{{ item.jumlah_unit }} Unit</td>
                            <td style="text-align: center;">{{ item.luas_m2 }} m²</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>

                <!-- 2. Rincian PSU -->
                <div style="margin-top: 8px; font-weight: bold;">2. Prasarana, Sarana, dan Utilitas Umum (PSU):</div>
                <ul style="margin: 4px 0; padding-left: 20px; font-size: 9.5pt;">
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
                            <th style="text-align: left;">Parameter</th>
                            <th style="text-align: center;">Batas Baku Pengesahan (Verified)</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Koefisien Dasar Bangunan (KDB) Maksimal</td>
                            <td style="text-align: center;">{{ diktum_intensity.kdb_max }}%</td>
                        </tr>
                        <tr>
                            <td>Koefisien Lantai Bangunan (KLB) Maksimal</td>
                            <td style="text-align: center;">{{ diktum_intensity.klb_max }}x</td>
                        </tr>
                        <tr>
                            <td>Koefisien Dasar Hijau (KDH) Minimal</td>
                            <td style="text-align: center;">{{ diktum_intensity.kdh_min }}%</td>
                        </tr>
                    </tbody>
                </table>
            </td>
        </tr>
        
        <!-- ─── UPDATE FASE 5 (REVISI): SILSILAH PENOMORAN DIKTUM HUKUM DINAMIS ─── -->
        {% if considerations.replaced_sk_number %}
        <tr>
            <td class="dictum-name">Ketiga</td>
            <td class="separator">:</td>
            <td class="content">
                Mencabut dan menyatakan tidak berlaku lagi Surat Keputusan Kepala Dinas Penanaman Modal dan Pelayanan Terpadu Satu Pintu Kabupaten Bogor 
                Nomor: <strong>{{ considerations.replaced_sk_number }}</strong> tanggal <strong>{{ considerations.replaced_sk_date }}</strong> 
                terhitung sejak ditetapkannya Keputusan ini.
            </td>
        </tr>
        <tr>
            <td class="dictum-name">Keempat</td>
            <td class="separator">:</td>
            <td class="content">
                Apabila keterangan dan rincian specifications teknis pada Diktum KEDUA tidak dipenuhi, tidak ditaati, atau disalahgunakan di luar peruntukan yang disahkan, maka Surat Keputusan Persetujuan Rencana Tapak (Site Plan) ini dinyatakan <strong>BATAL DEMI HUKUM</strong>.
            </td>
        </tr>
        <tr>
            <td class="dictum-name">Kelima</td>
            <td class="separator">:</td>
            <td class="content">
                Keputusan ini mulai berlaku pada tanggal ditetapkan dengan ketentuan bahwa segala sesuatunya akan ditinjau kembali dan diperbaiki sebagaimana mestinya apabila di kemudian hari terdapat kekeliruan.
            </td>
        </tr>
        {% else %}
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
        {% endif %}
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

    <div class="system-log-block">
        <div class="system-log-title">Log Sistem Pembuatan Dokumen</div>
        <div>Pengguna: {{ system_log.generated_by or 'Sistem' }}</div>
        <div>Tanggal: {{ system_log.generated_date or '-' }}</div>
        <div>Waktu: {{ system_log.generated_time or '-' }}</div>
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
            margin: 20mm 15mm 20mm 20mm;
            @bottom-center {
                content: "Halaman " counter(page) " dari " counter(pages);
                font-family: Arial, Helvetica, sans-serif;
                font-size: 8pt;
                color: #555;
            }
        }
        body {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 8.5pt;
            line-height: 1.4;
            color: #111d13;
        }
        
        /* Kop Surat */
        .kop-surat {
            text-align: center;
            border-bottom: 3px double #111d13;
            padding-bottom: 10px;
            margin-bottom: 18px;
        }
        .kop-surat h2 { 
            margin: 0; 
            font-size: 12pt; 
            font-weight: bold; 
            text-transform: uppercase; 
            letter-spacing: 0.5px;
            color: #111d13;
        }
        .kop-surat h1 { 
            margin: 3px 0 0 0; 
            font-size: 14pt; 
            font-weight: bold; 
            text-transform: uppercase; 
            letter-spacing: 0.5px;
            color: #111d13;
        }
        .kop-surat p { 
            margin: 4px 0 0 0; 
            font-size: 8.5pt; 
            font-style: italic; 
            color: #415D43; 
        }

        /* Judul Utama */
        .title-block {
            text-align: center;
            margin-top: 10px;
            margin-bottom: 20px;
        }
        .title-block h3 {
            margin: 0;
            font-size: 13.5pt;
            text-transform: uppercase;
            font-weight: bold;
            color: #111d13;
            letter-spacing: 0.3px;
        }
        .title-block p {
            margin: 4px 0 0 0;
            font-size: 9pt;
            color: #555;
            font-weight: normal;
        }

        /* Sub Judul Bagian (Section Title) */
        .section-title {
            font-size: 11pt;
            font-weight: bold;
            text-transform: uppercase;
            background-color: #f4f7f4;
            padding: 5px 10px;
            margin-top: 20px;
            margin-bottom: 8px;
            border-left: 4px solid #415D43;
            color: #111d13;
            letter-spacing: 0.3px;
        }

        /* Blok Kartu KPI */
        .kpi-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .kpi-table td {
            width: 25%;
            padding: 8px 10px;
            border: 1px solid #dae4db;
            vertical-align: top;
            background-color: #fafdfa;
        }
        .kpi-label {
            font-size: 7.5pt;
            font-weight: bold;
            color: #555;
            text-transform: uppercase;
            letter-spacing: 0.3px;
        }
        .kpi-value {
            font-size: 10pt; 
            font-weight: bold;
            color: #111d13;
            margin-top: 4px;
        }
        .kpi-sub {
            font-size: 7.5pt;
            color: #666;
            margin-top: 2px;
        }

        /* Data Tabel */
        .data-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 15px;
        }
        .data-table th {
            background-color: #f4f7f4;
            border: 1px solid #dae4db;
            padding: 6px 8px;
            font-weight: bold;
            font-size: 8.5pt;
            color: #111d13;
            letter-spacing: 0.2px;
        }
        .data-table td {
            border: 1px solid #dae4db;
            padding: 6px 8px;
            vertical-align: middle;
            font-size: 8pt;
            color: #2c3e35;
        }

        /* Helper Utility */
        .text-center { text-align: center !important; }
        .text-left   { text-align: left !important; }
        .text-right  { text-align: right !important; }
        .font-bold   { font-weight: bold; }

        .footer-note {
            font-size: 7.5pt;
            color: #666;
            margin-top: 25px;
            border-top: 1px dashed #dae4db;
            padding-top: 8px;
            font-style: italic;
        }
        .system-log-block {
            margin-top: 18px;
            padding: 10px 12px;
            border: 1px solid #dae4db;
            background: #f7faf7;
            font-size: 7.5pt;
            color: #334155;
            line-height: 1.4;
            text-align: center;
            page-break-inside: avoid !important;
            break-inside: avoid-page !important;
        }
        .system-log-title {
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-bottom: 4px;
            color: #111d13;
        }
    </style>
</head>
<body>
    <div class="kop-surat">
        <h2>Pemerintah Kabupaten Bogor</h2>
        <h1>Dinas Penanaman Modal dan Pelayanan Terpadu Satu Pintu</h1>
        <p>Jl. Tegar Beriman No. 25, Cibinong 16914 | Telp: (021) 8751090 | Email: dpmptsp@bogorkab.go.id</p>
    </div>

    <div class="title-block">
        <h3>Laporan Eksekutif Realisasi Rencana Tapak (Site Plan)</h3>
        <p>Periode Laporan: {{ month_name }} {{ year }} &nbsp;|&nbsp; Tanggal Cetak: {{ print_date }}</p>
    </div>

    <!-- SEKSI 1: RINGKASAN KPI UTAMA -->
    <div class="section-title">Ringkasan KPI Utama (YTD)</div>
    <table class="kpi-table">
        <tr>
            <td>
                <div class="kpi-label">Total Lahan YTD</div>
                <div class="kpi-value text-left">{{ land_area_formatted }} m²</div>
                <div class="kpi-sub">Setara dengan ~{{ land_area_ha }} Ha</div>
            </td>
            <td>
                <div class="kpi-label">Pengajuan YTD</div>
                <div class="kpi-value text-left">{{ total_pengajuan_ytd }} Berkas</div>
                <div class="kpi-sub">Bulan ini: {{ pengajuan_bulan_ini }} baru</div>
            </td>
            <td>
                <div class="kpi-label">Penyelesaian YTD</div>
                <div class="kpi-value text-left">{{ total_disetujui_ytd }} SK</div>
                <div class="kpi-sub">Bulan ini: {{ penyelesaian_bulan_ini }} disahkan</div>
            </td>
            <td>
                <div class="kpi-label">Rasio Penerimaan</div>
                <div class="kpi-value text-left">{{ success_rate }}%</div>
                <div class="kpi-sub">Lolos: {{ approved_decisions }} | Ditolak: {{ tidak_sesuai_ytd }}</div>
            </td>
        </tr>
    </table>

    <!-- SEKSI 2: DISTRIBUSI KEPUTUSAN -->
    <div class="section-title">Distribusi Keputusan Tata Ruang (YTD)</div>
    <table class="data-table">
        <thead>
          <tr>
            <th style="width: 30%; text-align: left;">Parameter Verifikasi</th>
            <th style="width: 15%; text-align: center;">Jumlah Berkas</th>
            <th style="width: 15%; text-align: center;">Persentase</th>
            <th style="width: 40%; text-align: left;">Rekomendasi Tindak Lanjut</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="text-left font-bold">Sesuai (Lolos)</td>
            <td class="text-center font-bold">{{ sesuai_ytd }}</td>
            <td class="text-center font-bold">{{ sesuai_pct }}%</td>
            <td class="text-left">Rekomendasi persetujuan site plan langsung diterbitkan tanpa syarat.</td>
          </tr>
          <tr>
            <td class="text-left">Sesuai Bersyarat (Lolos Bersyarat)</td>
            <td class="text-center">{{ sesuai_bersyarat_ytd }}</td>
            <td class="text-center">{{ sesuai_bersyarat_pct }}%</td>
            <td class="text-left">Rekomendasi diterbitkan dengan kewajiban pemenuhan kompensasi PSU/KDH.</td>
          </tr>
          <tr>
            <td class="text-left">Tidak Sesuai / Ditolak</td>
            <td class="text-center">{{ tidak_sesuai_ytd }}</td>
            <td class="text-center">{{ tidak_sesuai_pct }}%</td>
            <td class="text-left">Berkas dikembalikan ke pemohon untuk melakukan revisi gambar rencana tapak.</td>
          </tr>
        </tbody>
    </table>

    <!-- SEKSI 3: SNAPSHOT PIPELINE -->
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
            <td class="text-center font-bold">{{ pipeline.pemohon }}</td>
            <td class="text-center font-bold">{{ pipeline.admin }}</td>
            <td class="text-center font-bold">{{ pipeline.teknis }}</td>
            <td class="text-center font-bold">{{ pipeline.kabid }}</td>
            <td class="text-center font-bold">{{ pipeline.kadis }}</td>
            <td class="text-center font-bold" style="color: #415D43;">{{ pipeline.selesai }}</td>
          </tr>
        </tbody>
    </table>

    <!-- SEKSI 4: DAFTAR SK TERBIT -->
    <div class="section-title">Daftar Surat Keputusan (SK) Terbit - Periode {{ month_name }} {{ year }}</div>
    <table class="data-table">
        <thead>
          <tr>
            <th style="width: 25%; text-align: center;">No. Pengajuan</th>
            <th style="width: 45%; text-align: left;">Nama Perumahan / Kegiatan</th>
            <th style="width: 30%; text-align: center;">Nomor Surat Keputusan (SK)</th>
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
              <td class="text-center font-bold">{{ sk.submission_no }}</td>
              <td class="text-left font-bold" style="color: #111d13;">{{ sk.housing_name }}</td>
              <td class="text-center font-bold" style="color: #415D43;">{{ sk.sk_number }}</td>
            </tr>
            {% endfor %}
          {% endif %}
        </tbody>
    </table>

    <p class="footer-note">
        * Dokumen ini dibuat dan divalidasi secara otomatis melalui sistem GEOSIPAS Kabupaten Bogor berbasis data real-time spasial.
    </p>

    <div class="system-log-block">
        <div class="system-log-title">Log Sistem Pembuatan Dokumen</div>
        <div>Pengguna: {{ system_log.generated_by or 'Sistem' }}</div>
        <div>Tanggal: {{ system_log.generated_date or '-' }}</div>
        <div>Waktu: {{ system_log.generated_time or '-' }}</div>
    </div>
</body>
</html>
"""

# ─── TEMPLATE 4: TANDA TERIMA PERMOHONAN DEFAULT TEMPLATE ───────────────────
DEFAULT_RECEIPT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Tanda Terima Permohonan - {{ permohonan.submission_no }}</title>
    <style>
        @page {
            size: A4;
            margin: 20mm;
            @bottom-right {
                content: "Halaman 1 dari 1";
                font-family: Arial, Helvetica, sans-serif;
                font-size: 8pt;
            }
        }
        body {
            font-family: Arial, Helvetica, sans-serif;
            font-size: 10pt;
            line-height: 1.6;
            color: #1e293b;
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
            border-bottom: 3px double #0f172a;
            padding-bottom: 12px;
        }
        .kop-table {
            width: 100%;
            border-collapse: collapse;
        }
        .kop-table td { padding: 0; vertical-align: middle; }
        .kop-logo-cell { width: 75px; text-align: center; }
        .kop-logo-cell img { width: 64px; height: 64px; object-fit: contain; }
        .kop-text-cell { text-align: center; }
        .kop-instansi { margin: 0; font-size: 11pt; font-weight: bold; text-transform: uppercase; }
        .kop-dinas { margin: 2px 0 0 0; font-size: 13pt; font-weight: bold; text-transform: uppercase; color: #0f172a; }
        .kop-alamat { margin: 3px 0 0 0; font-size: 8pt; color: #475569; font-style: italic; }
        
        .title {
            text-align: center;
            font-size: 14pt;
            font-weight: bold;
            text-transform: uppercase;
            margin-top: 20px;
            margin-bottom: 25px;
            color: #0f172a;
            letter-spacing: 0.5px;
        }
        
        .info-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 25px;
        }
        .info-table td {
            padding: 8px 12px;
            vertical-align: top;
            border-bottom: 1px solid #e2e8f0;
        }
        .info-table td.label {
            width: 30%;
            font-weight: bold;
            color: #475569;
        }
        .info-table td.value {
            color: #0f172a;
        }
        
        .alert-box {
            background-color: #f0fdf4;
            border-left: 4px solid #16a34a;
            padding: 15px;
            margin-bottom: 25px;
            border-radius: 4px;
        }
        .alert-box p {
            margin: 0;
            font-size: 9.5pt;
            color: #14532d;
        }
        
        .guide-section {
            margin-top: 20px;
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 20px;
            border-radius: 6px;
        }
        .guide-title {
            font-size: 11pt;
            font-weight: bold;
            color: #0f172a;
            margin-top: 0;
            margin-bottom: 12px;
            border-bottom: 1px solid #cbd5e1;
            padding-bottom: 6px;
            text-transform: uppercase;
        }
        .guide-list {
            margin: 0;
            padding-left: 20px;
        }
        .guide-list li {
            margin-bottom: 10px;
            font-size: 9pt;
            color: #334155;
        }
        .guide-list li strong {
            color: #0f172a;
        }
        
        .footer {
            margin-top: 40px;
            text-align: center;
            font-size: 8pt;
            color: #94a3b8;
            border-top: 1px solid #e2e8f0;
            padding-top: 10px;
        }
        .signature-area {
            margin-top: 30px;
            float: right;
            width: 250px;
            text-align: center;
        }
        .signature-name {
            font-size: 9.5pt;
            font-weight: bold;
            color: #0f172a;
            border-bottom: 1px solid #0f172a;
            padding-bottom: 2px;
            display: inline-block;
        }
    </style>
</head>
<body>
    <div class="header">
        <table class="kop-table">
            <tr>
                <td class="kop-logo-cell">
                    {% if logo_base64 %}
                        <img src="{{ logo_base64 }}" />
                    {% else %}
                        <div style="width: 55px; height: 55px; background: #e2e8f0; border: 1px solid #cbd5e1; line-height: 55px; font-size: 8pt; font-weight: bold; color: #64748b; border-radius: 50%;">SIPAS</div>
                    {% endif %}
                </td>
                <td class="kop-text-cell">
                    <div class="kop-instansi">Pemerintah Kabupaten Bogor</div>
                    <div class="kop-dinas">Dinas Penanaman Modal dan Pelayanan Terpadu Satu Pintu</div>
                    <div class="kop-alamat">Jl. Tegar Beriman No. 1, Cibinong, Kabupaten Bogor, Jawa Barat 16914</div>
                </td>
            </tr>
        </table>
    </div>

    <div class="title">Tanda Terima Permohonan</div>

    <div class="alert-box">
        <p>
            <strong>Pemberitahuan:</strong> Berkas permohonan pengesahan site plan Anda telah sukses diunggah dan diterima oleh sistem GEOSIPAS. Dokumen tanda terima ini diterbitkan sebagai bukti registrasi awal.
        </p>
    </div>

    <table class="info-table">
        <tr>
            <td class="label">Nomor Permohonan</td>
            <td class="value" style="font-weight: bold; color: #16a34a;">{{ permohonan.submission_no }}</td>
        </tr>
        <tr>
            <td class="label">Nama Pemohon</td>
            <td class="value">{{ permohonan.applicant_name }}</td>
        </tr>
        <tr>
            <td class="label">Nama Perumahan/Kegiatan</td>
            <td class="value">{{ permohonan.housing_name }}</td>
        </tr>
        <tr>
            <td class="label">Kategori Dokumen</td>
            <td class="value">{{ permohonan.document_category }}</td>
        </tr>
        <tr>
            <td class="label">Luas Lahan</td>
            <td class="value">{{ permohonan.land_area }} m²</td>
        </tr>
        <tr>
            <td class="label">Tanggal Diterima</td>
            <td class="value">{{ system_log.generated_at }}</td>
        </tr>
    </table>

    <div class="guide-section">
        <div class="guide-title">Panduan Pemantauan (Monitoring) Permohonan</div>
        <ol class="guide-list">
            <li>Buka peramban (browser) dan akses halaman aplikasi <strong>GEOSIPAS</strong>.</li>
            <li>Masuk (Login) menggunakan akun Pemohon terdaftar yang Anda gunakan saat mengajukan berkas.</li>
            <li>Arahkan ke menu utama pada sidebar sebelah kiri, pilih menu <strong>Daftar Pengajuan</strong>.</li>
            <li>Cari berkas Anda berdasarkan <strong>Nomor Permohonan</strong> atau <strong>Nama Perumahan</strong>.</li>
            <li>Klik tombol <strong>Detail</strong> pada baris pengajuan untuk memantau status secara real-time:
                <ul style="margin-top: 5px; padding-left: 15px;">
                    <li><strong>Pengajuan Dokumen:</strong> Berkas sedang berada di antrean verifikasi administrasi awal.</li>
                    <li><strong>Verifikasi Administrasi:</strong> Pemeriksaan kelengkapan berkas administratif oleh petugas.</li>
                    <li><strong>Verifikasi Teknis:</strong> Evaluasi batas-batas spasial RDTR dan kesesuaian gambar rencana tapak oleh Tim Teknis.</li>
                    <li><strong>Menunggu Rekomendasi/Persetujuan:</strong> Peninjauan draf Surat Keputusan (SK) oleh Kepala Bidang dan Kepala Dinas.</li>
                    <li><strong>Disetujui:</strong> Dokumen SK resmi telah ditandatangani secara elektronik (TTE) dan siap diunduh.</li>
                </ul>
            </li>
        </ol>
    </div>

    <div class="signature-area" style="font-family: 'Segoe UI', Helvetica, Arial, sans-serif; text-align: center; width: 220px; margin: 20px auto; color: #334155;">
    <!-- Judul Atas -->
    <div class="signature-title" style="font-size: 8pt; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: #64748b; margin-bottom: 12px;">
        Sistem Administrasi GEOSIPAS
    </div>
    
    <!-- Box Verifikasi Sistem -->
    <div class="signature-badge" style="border: 1.5px dashed #cbd5e1; background-color: #f8fafc; border-radius: 6px; padding: 10px 8px; margin-bottom: 15px;">
        <div style="font-size: 7.5pt; font-weight: bold; color: #0284c7; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px;">
            ✓ TERVERIFIKASI SISTEM
        </div>
        <div style="font-size: 6.5pt; color: #64748b; line-height: 1.3;">
            Dokumen ini sah dan ditandatangani secara elektronik oleh sistem
        </div>
    </div>
    
    <!-- Nama Penandatangan -->
    <div class="signature-name" style="font-size: 9pt; font-weight: bold; color: #0f172a; border-top: 1px solid #e2e8f0; padding-top: 8px;">
        GEOSIPAS KAB. BOGOR
    </div>
</div>

    <div style="clear: both;"></div>

    <div class="footer">
        Dokumen ini diterbitkan oleh sistem e-Siteplan GEOSIPAS Kabupaten Bogor secara elektronik pada {{ system_log.generated_date }} {{ system_log.generated_time }}.
    </div>
</body>
</html>
"""