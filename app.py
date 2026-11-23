

# 1. IMPORT LIBRARY
import os
import sqlite3
import csv
import io
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from uuid import uuid4

# 2. KONFIGURASI APLIKASI
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# Lokasi database
DATABASE = Path(__file__).parent / "evote_mahasiswa.db"

# Lokasi penyimpanan foto kandidat
UPLOAD_FOLDER = Path(__file__).parent / "static" / "img"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

# Format foto yang diperbolehkan
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

# 3. FUNCTION KONEKSI DATABASE
def koneksi_database():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn



# 4. FUNCTION MEMBUAT DATABASE
def buat_database():
    conn = koneksi_database()
    cursor = conn.cursor()

    # Tabel Pemilih
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pemilih (
            nim TEXT PRIMARY KEY,
            nama TEXT NOT NULL,
            program_studi TEXT NOT NULL,
            angkatan INTEGER NOT NULL,
            sudah_memilih INTEGER DEFAULT 0,
            tanggal_vote TEXT
        )
    """)

    # Tabel Kandidat
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kandidat (
            id_kandidat INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_calon TEXT NOT NULL,
            program_studi TEXT NOT NULL,
            angkatan INTEGER NOT NULL,
            visi TEXT NOT NULL,
            misi TEXT NOT NULL,
            total_suara INTEGER DEFAULT 0
        )
    """)

    # Menambahkan kolom foto jika belum tersedia
    cursor.execute("PRAGMA table_info(kandidat)")
    kolom = [item["name"] for item in cursor.fetchall()]

    if "foto" not in kolom:
     cursor.execute(
        "ALTER TABLE kandidat ADD COLUMN foto TEXT"
     )

        
    # Tabel Admin
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

        # Membuat akun admin pertama kali
    cursor.execute("SELECT COUNT(*) FROM admin")
    jumlah_admin = cursor.fetchone()[0]

    if jumlah_admin == 0:
        password_awal = os.environ.get("ADMIN_INITIAL_PASSWORD")

        if not password_awal:
            raise RuntimeError(
                "ADMIN_INITIAL_PASSWORD belum diatur!"
            )

        password_hash = generate_password_hash(password_awal)

        cursor.execute("""
            INSERT INTO admin (username, password)
            VALUES (?, ?)
        """, ("OPERATOR_HMTI", password_hash))

        print("Akun admin berhasil dibuat!")

    else:
        print("Akun admin sudah tersedia!")
    # Tabel Pengaturan Pemilu
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pengaturan_pemilu (
            id INTEGER PRIMARY KEY,
            status_pemilu TEXT NOT NULL
        )
    """)

    # Status awal pemilu
    cursor.execute("""
        INSERT OR IGNORE INTO pengaturan_pemilu
        (id, status_pemilu)
        VALUES (1, 'AKTIF')
    """)

    # DATA PEMILIH DITAMBAHKAN MELALUI DASHBOARD ADMIN
    # Data mahasiswa tidak ditanam langsung di dalam source code.

    # Simpan perubahan
    conn.commit()

    # Mengecek jumlah data mahasiswa
    cursor.execute("SELECT COUNT(*) FROM pemilih")
    jumlah = cursor.fetchone()[0]

    print("JUMLAH MAHASISWA:", jumlah)

    # Menampilkan beberapa data mahasiswa
    cursor.execute("SELECT nim, nama FROM pemilih LIMIT 5")
    data = cursor.fetchall()

    for mahasiswa in data:
        print(mahasiswa["nim"], mahasiswa["nama"])

    # Tutup koneksi setelah semua proses selesai
    conn.close()



# 5. ROUTE HALAMAN UTAMA
@app.route("/")
def home():
    return render_template("index.html")


# 6. LOGIN MAHASISWA (MENGGUNAKAN NIM SAJA)
@app.route("/login/mahasiswa", methods=["GET", "POST"])
def login_mahasiswa():

    if request.method == "POST":

        nim = request.form.get("nim", "").strip()

        conn = koneksi_database()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM pemilih WHERE nim = ?",
            (nim,)
        )

        mahasiswa = cursor.fetchone()
        conn.close()

        if mahasiswa:
            session.clear()
            session["nim"] = mahasiswa["nim"]
            session["nama"] = mahasiswa["nama"]
            session["role"] = "mahasiswa"

            flash("Login berhasil!", "success")

            return redirect(url_for("dashboard_mahasiswa"))

        else:
            flash("NIM tidak terdaftar!", "error")

    return render_template("login_mahasiswa.html")

# 7. LOGIN ADMIN
@app.route("/login/admin", methods=["GET", "POST"])
def login_admin():

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        conn = koneksi_database()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM admin WHERE username = ?",
            (username,)
        )

        admin = cursor.fetchone()
        conn.close()

        if admin and check_password_hash(admin["password"], password):

            session.clear()
            session["admin_id"] = admin["id"]
            session["username"] = admin["username"]
            session["role"] = "admin"

            flash("Login admin berhasil!", "success")

            return redirect(url_for("dashboard_admin"))

        else:
            flash("Username atau password salah!", "error")

    return render_template("login_admin.html")



# 8. DASHBOARD MAHASISWA
@app.route("/dashboard/mahasiswa")
def dashboard_mahasiswa():

    if session.get("role") != "mahasiswa":
        flash("Silakan login terlebih dahulu!", "error")
        return redirect(url_for("login_mahasiswa"))

    conn = koneksi_database()
    cursor = conn.cursor()

    # Mengambil data mahasiswa
    cursor.execute(
        "SELECT * FROM pemilih WHERE nim = ?",
        (session["nim"],)
    )
    mahasiswa = cursor.fetchone()

    # Mengambil daftar kandidat
    cursor.execute(
        "SELECT * FROM kandidat ORDER BY id_kandidat"
    )
    daftar_kandidat = cursor.fetchall()

    # Mengambil status pemilu
    cursor.execute(
        "SELECT status_pemilu FROM pengaturan_pemilu WHERE id = 1"
    )
    pengaturan = cursor.fetchone()

    status_pemilu = (
        pengaturan["status_pemilu"]
        if pengaturan else "BELUM DIATUR"
    )

    conn.close()

    return render_template(
        "dashboard_mahasiswa.html",
        mahasiswa=mahasiswa,
        daftar_kandidat=daftar_kandidat,
        status_pemilu=status_pemilu
    )



# 9. DASHBOARD ADMIN
@app.route("/dashboard/admin")
def dashboard_admin():

    if session.get("role") != "admin":
        flash("Silakan login sebagai admin!", "error")
        return redirect(url_for("login_admin"))

    conn = koneksi_database()
    cursor = conn.cursor()

    # Menghitung jumlah mahasiswa
    cursor.execute("SELECT COUNT(*) FROM pemilih")
    jumlah_mahasiswa = cursor.fetchone()[0]

    # Menghitung jumlah kandidat
    cursor.execute("SELECT COUNT(*) FROM kandidat")
    jumlah_kandidat = cursor.fetchone()[0]

    # Menghitung total suara
    cursor.execute("SELECT SUM(total_suara) FROM kandidat")
    total_suara = cursor.fetchone()[0] or 0

    # Mengambil status pemilu
    cursor.execute(
        "SELECT status_pemilu FROM pengaturan_pemilu WHERE id = 1"
    )
    pengaturan = cursor.fetchone()
    status_pemilu = pengaturan["status_pemilu"] if pengaturan else "BELUM DIATUR"

    conn.close()

    return render_template(
        "dashboard_admin.html",
        username=session["username"],
        jumlah_mahasiswa=jumlah_mahasiswa,
        jumlah_kandidat=jumlah_kandidat,
        total_suara=total_suara,
        status_pemilu=status_pemilu
    )


# 10. MENAMPILKAN DAFTAR KANDIDAT
@app.route("/admin/kandidat")
def kelola_kandidat():

    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    conn = koneksi_database()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM kandidat ORDER BY id_kandidat")
    daftar_kandidat = cursor.fetchall()

    conn.close()

    return render_template(
        "kandidat.html",
        daftar_kandidat=daftar_kandidat
    )



# 11. MENAMBAHKAN KANDIDAT

@app.route("/admin/kandidat/tambah", methods=["POST"])
def tambah_kandidat():

    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    nama_calon = request.form.get("nama_calon", "").strip()
    program_studi = request.form.get("program_studi", "").strip()
    angkatan = request.form.get("angkatan", "").strip()
    visi = request.form.get("visi", "").strip()
    misi = request.form.get("misi", "").strip()

    if not all([nama_calon, program_studi, angkatan, visi, misi]):
        flash("Semua data kandidat wajib diisi!", "error")
        return redirect(url_for("kelola_kandidat"))

    try:
        angkatan = int(angkatan)
        if angkatan < 1900 or angkatan > 2100:
            raise ValueError
    except ValueError:
        flash("Angkatan tidak valid!", "error")
        return redirect(url_for("kelola_kandidat"))

    # PROSES UPLOAD FOTO
    file_foto = request.files.get("foto")
    nama_foto = None

    if file_foto and file_foto.filename:
        nama_file_aman = secure_filename(file_foto.filename)
        ekstensi = Path(nama_file_aman).suffix.lower()

        if ekstensi not in [".jpg", ".jpeg", ".png", ".webp"]:
            flash("Format foto harus JPG, JPEG, PNG, atau WEBP!", "error")
            return redirect(url_for("kelola_kandidat"))

        nama_foto = f"{uuid4().hex}{ekstensi}"

        file_foto.save(UPLOAD_FOLDER / nama_foto)

    # SIMPAN DATA KE DATABASE
    conn = koneksi_database()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO kandidat
        (nama_calon, program_studi, angkatan, visi, misi, foto)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        nama_calon,
        program_studi,
        angkatan,
        visi,
        misi,
        nama_foto
    ))

    conn.commit()
    conn.close()

    flash("Kandidat dan foto berhasil ditambahkan!", "success")
    return redirect(url_for("kelola_kandidat"))

    # Mengambil foto dari formulir
    file_foto = request.files.get("foto")
    nama_foto = None

    if file_foto and file_foto.filename:
        nama_file_aman = secure_filename(file_foto.filename)
        ekstensi = Path(nama_file_aman).suffix.lower().replace(".", "")

        if ekstensi not in ALLOWED_EXTENSIONS:
            flash("Format foto harus JPG, JPEG, PNG, atau WEBP!", "error")
            return redirect(url_for("kelola_kandidat"))

        nama_foto = f"{uuid4().hex}.{ekstensi}"
        file_foto.save(UPLOAD_FOLDER / nama_foto)

    conn = koneksi_database()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO kandidat
        (nama_calon, program_studi, angkatan, visi, misi, foto)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        nama_calon,
        program_studi,
        angkatan,
        visi,
        misi,
        nama_foto
    ))

    conn.commit()
    conn.close()

    flash("Kandidat berhasil ditambahkan!", "success")
    return redirect(url_for("kelola_kandidat"))




# 12. MENGEDIT KANDIDAT
@app.route("/admin/kandidat/edit/<int:id_kandidat>", methods=["GET", "POST"])
def edit_kandidat(id_kandidat):

    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    conn = koneksi_database()
    cursor = conn.cursor()

    if request.method == "POST":
        nama_calon = request.form.get("nama_calon", "").strip()
        program_studi = request.form.get("program_studi", "").strip()
        angkatan = request.form.get("angkatan", "").strip()
        visi = request.form.get("visi", "").strip()
        misi = request.form.get("misi", "").strip()

        if not all([nama_calon, program_studi, angkatan, visi, misi]):
            flash("Semua data kandidat wajib diisi!", "error")
            conn.close()
            return redirect(url_for("edit_kandidat", id_kandidat=id_kandidat))

        try:
            angkatan = int(angkatan)
            if angkatan < 1900 or angkatan > 2100:
                raise ValueError
        except ValueError:
            flash("Angkatan harus berupa tahun yang valid!", "error")
            conn.close()
            return redirect(url_for("edit_kandidat", id_kandidat=id_kandidat))

        # Mengambil data foto lama
        cursor.execute(
            "SELECT foto FROM kandidat WHERE id_kandidat = ?",
            (id_kandidat,)
        )
        kandidat_lama = cursor.fetchone()

        if kandidat_lama is None:
            conn.close()
            flash("Kandidat tidak ditemukan!", "error")
            return redirect(url_for("kelola_kandidat"))

        nama_foto = kandidat_lama["foto"]

        # Memproses foto baru jika admin mengunggahnya
        file_foto = request.files.get("foto")

        if file_foto and file_foto.filename:
            nama_file_aman = secure_filename(file_foto.filename)
            ekstensi = Path(nama_file_aman).suffix.lower()

            if ekstensi not in [".jpg", ".jpeg", ".png", ".webp"]:
                flash("Format foto harus JPG, JPEG, PNG, atau WEBP!", "error")
                conn.close()
                return redirect(url_for("edit_kandidat", id_kandidat=id_kandidat))

            nama_foto = f"{uuid4().hex}{ekstensi}"
            file_foto.save(UPLOAD_FOLDER / nama_foto)

        # Memperbarui data kandidat
        cursor.execute("""
            UPDATE kandidat
            SET nama_calon = ?,
                program_studi = ?,
                angkatan = ?,
                visi = ?,
                misi = ?,
                foto = ?
            WHERE id_kandidat = ?
        """, (
            nama_calon,
            program_studi,
            angkatan,
            visi,
            misi,
            nama_foto,
            id_kandidat
        ))

        conn.commit()
        conn.close()

        flash("Data kandidat dan foto berhasil diperbarui!", "success")
        return redirect(url_for("kelola_kandidat"))

    cursor.execute(
        "SELECT * FROM kandidat WHERE id_kandidat = ?",
        (id_kandidat,)
    )
    kandidat = cursor.fetchone()
    conn.close()

    if kandidat is None:
        flash("Kandidat tidak ditemukan!", "error")
        return redirect(url_for("kelola_kandidat"))

    return render_template("kandidat.html", kandidat_edit=kandidat)



# 13. MENGHAPUS KANDIDAT
@app.route("/admin/kandidat/hapus/<int:id_kandidat>", methods=["POST"])
def hapus_kandidat(id_kandidat):

    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    conn = koneksi_database()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM kandidat WHERE id_kandidat = ?",
        (id_kandidat,)
    )

    conn.commit()
    conn.close()

    flash("Kandidat berhasil dihapus!", "success")
    return redirect(url_for("kelola_kandidat"))

# 14. PROSES VOTING MAHASISWA
@app.route("/vote/<int:id_kandidat>", methods=["POST"])
def proses_vote(id_kandidat):

    # Cek login mahasiswa
    if session.get("role") != "mahasiswa":
        flash("Silakan login sebagai mahasiswa terlebih dahulu!", "error")
        return redirect(url_for("login_mahasiswa"))

    conn = koneksi_database()
    cursor = conn.cursor()

    try:
        # Mengunci transaksi agar dua permintaan tidak bisa
        # memproses suara mahasiswa yang sama secara bersamaan.
        cursor.execute("BEGIN IMMEDIATE")

        # Cek data mahasiswa
        cursor.execute(
            "SELECT * FROM pemilih WHERE nim = ?",
            (session["nim"],)
        )
        mahasiswa = cursor.fetchone()

        if mahasiswa is None:
            conn.rollback()
            flash("Data mahasiswa tidak ditemukan!", "error")
            return redirect(url_for("dashboard_mahasiswa"))

        # Cek apakah mahasiswa sudah memilih
        if mahasiswa["sudah_memilih"] == 1:
            conn.rollback()
            flash("Anda sudah menggunakan hak suara!", "error")
            return redirect(url_for("dashboard_mahasiswa"))

        # Cek status pemilu
        cursor.execute(
            "SELECT status_pemilu FROM pengaturan_pemilu WHERE id = 1"
        )
        pengaturan = cursor.fetchone()

        if not pengaturan or pengaturan["status_pemilu"] != "AKTIF":
            conn.rollback()
            flash("Pemilu sedang tidak aktif!", "error")
            return redirect(url_for("dashboard_mahasiswa"))

        # Pastikan kandidat yang dipilih tersedia
        cursor.execute(
            "SELECT id_kandidat FROM kandidat WHERE id_kandidat = ?",
            (id_kandidat,)
        )
        kandidat = cursor.fetchone()

        if kandidat is None:
            conn.rollback()
            flash("Kandidat tidak ditemukan!", "error")
            return redirect(url_for("dashboard_mahasiswa"))

        # Tandai mahasiswa sudah memilih
        waktu_vote = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            UPDATE pemilih
            SET sudah_memilih = 1,
                tanggal_vote = ?
            WHERE nim = ? AND sudah_memilih = 0
        """, (waktu_vote, session["nim"]))

        if cursor.rowcount != 1:
            conn.rollback()
            flash("Hak suara Anda sudah digunakan!", "error")
            return redirect(url_for("dashboard_mahasiswa"))

        # Tambahkan satu suara ke kandidat
        cursor.execute("""
            UPDATE kandidat
            SET total_suara = total_suara + 1
            WHERE id_kandidat = ?
        """, (id_kandidat,))

        # Simpan semuanya
        conn.commit()

        flash("Voting berhasil! Terima kasih sudah menggunakan hak suara.", "success")

    except Exception:
        conn.rollback()
        flash("Terjadi kesalahan saat menyimpan suara. Silakan coba lagi.", "error")

    finally:
        conn.close()

    return redirect(url_for("dashboard_mahasiswa"))

# 14. RESET SEMUA VOTING
@app.route("/admin/reset-voting", methods=["POST"])
def reset_voting():

    # Pastikan hanya admin yang bisa melakukan reset
    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    conn = koneksi_database()
    cursor = conn.cursor()

    try:
        # Reset seluruh suara kandidat
        cursor.execute("""
            UPDATE kandidat
            SET total_suara = 0
        """)

        # Reset status seluruh mahasiswa
        cursor.execute("""
            UPDATE pemilih
            SET sudah_memilih = 0,
                tanggal_vote = NULL
        """)

        conn.commit()

        flash(
            "Berhasil! Seluruh hasil voting sudah direset menjadi 0.",
            "success"
        )

    except Exception:
        conn.rollback()
        flash("Gagal melakukan reset voting!", "error")

    finally:
        conn.close()

    return redirect(url_for("dashboard_admin"))


# 15. MENGUBAH STATUS PEMILU
@app.route("/admin/status-pemilu", methods=["POST"])
def ubah_status_pemilu():

    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    status_baru = request.form.get("status_pemilu")

    if status_baru not in ["AKTIF", "NONAKTIF"]:
        flash("Status pemilu tidak valid!", "error")
        return redirect(url_for("dashboard_admin"))

    conn = koneksi_database()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE pengaturan_pemilu
        SET status_pemilu = ?
        WHERE id = 1
    """, (status_baru,))

    conn.commit()
    conn.close()

    flash(
        f"Status pemilu berhasil diubah menjadi {status_baru}!",
        "success"
    )

    return redirect(url_for("dashboard_admin"))


# 16. HALAMAN PENGUMUMAN PEMENANG
@app.route("/pengumuman-pemenang")
def pengumuman_pemenang():

    conn = koneksi_database()
    cursor = conn.cursor()

    # Mengambil status pemilu
    cursor.execute("""
        SELECT status_pemilu
        FROM pengaturan_pemilu
        WHERE id = 1
    """)
    pengaturan = cursor.fetchone()

    status_pemilu = (
        pengaturan["status_pemilu"]
        if pengaturan else "BELUM DIATUR"
    )

    # Menghitung total seluruh suara
    cursor.execute("""
        SELECT COALESCE(SUM(total_suara), 0)
        FROM kandidat
    """)
    total_suara = cursor.fetchone()[0]

    pemenang = None
    kandidat_seri = []
    suara_tertinggi = 0
    persentase_pemenang = 0

    # Pemenang hanya diumumkan setelah pemilu ditutup
    if status_pemilu == "NONAKTIF":

        cursor.execute("""
            SELECT *
            FROM kandidat
            ORDER BY total_suara DESC
        """)
        daftar_kandidat = cursor.fetchall()

        if daftar_kandidat:
            suara_tertinggi = daftar_kandidat[0]["total_suara"]

            if suara_tertinggi > 0:

                kandidat_teratas = [
                    kandidat
                    for kandidat in daftar_kandidat
                    if kandidat["total_suara"] == suara_tertinggi
                ]

                if len(kandidat_teratas) == 1:
                    pemenang = kandidat_teratas[0]

                    # Menghitung persentase suara pemenang
                    if total_suara > 0:
                        persentase_pemenang = round(
                            pemenang["total_suara"] / total_suara * 100,
                            1
                        )

                else:
                    kandidat_seri = kandidat_teratas

    conn.close()

    return render_template(
        "pengumuman_pemenang.html",
        status_pemilu=status_pemilu,
        pemenang=pemenang,
        kandidat_seri=kandidat_seri,
        suara_tertinggi=suara_tertinggi,
        total_suara=total_suara,
        persentase_pemenang=persentase_pemenang
    )

# HALAMAN HASIL VOTING
@app.route("/admin/hasil-voting")
def hasil_voting():

    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    conn = koneksi_database()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM kandidat
        ORDER BY total_suara DESC
    """)

    daftar_kandidat = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(SUM(total_suara), 0)
        FROM kandidat
    """)

    total_suara = cursor.fetchone()[0]

    conn.close()

    return render_template(
        "hasil_voting.html",
        daftar_kandidat=daftar_kandidat,
        total_suara=total_suara
    )

# FITUR BONUS: EXPORT HASIL VOTING KE CSV
@app.route("/admin/export-csv")
def export_hasil_csv():

    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    conn = koneksi_database()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            nama_calon,
            program_studi,
            angkatan,
            total_suara
        FROM kandidat
        ORDER BY total_suara DESC
    """)

    daftar_kandidat = cursor.fetchall()

    cursor.execute("""
        SELECT COALESCE(SUM(total_suara), 0)
        FROM kandidat
    """)

    total_suara = cursor.fetchone()[0]

    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Nama Kandidat",
        "Program Studi",
        "Angkatan",
        "Jumlah Suara",
        "Persentase Suara"
    ])

    for kandidat in daftar_kandidat:

        if total_suara > 0:
            persentase = round(
                kandidat["total_suara"] / total_suara * 100, 1
            )
        else:
            persentase = 0

        writer.writerow([
            kandidat["nama_calon"],
            kandidat["program_studi"],
            kandidat["angkatan"],
            kandidat["total_suara"],
            f"{persentase}%"
        ])

    response = make_response("\\ufeff" + output.getvalue())
    response.headers["Content-Disposition"] = (
        "attachment; filename=hasil_voting_hmti.csv"
    )
    response.headers["Content-Type"] = "text/csv; charset=utf-8"

    return response

# HALAMAN STATISTIK PEMILU
@app.route("/admin/statistik")
def statistik_pemilu():

    # Pastikan hanya admin yang bisa mengakses
    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    conn = koneksi_database()
    cursor = conn.cursor()

    # Menghitung jumlah seluruh mahasiswa
    cursor.execute("SELECT COUNT(*) FROM pemilih")
    jumlah_mahasiswa = cursor.fetchone()[0]

    # Menghitung mahasiswa yang sudah memilih
    cursor.execute("""
        SELECT COUNT(*)
        FROM pemilih
        WHERE sudah_memilih = 1
    """)
    jumlah_pemilih = cursor.fetchone()[0]

    # Menghitung mahasiswa yang belum memilih
    belum_memilih = jumlah_mahasiswa - jumlah_pemilih

    conn.close()

    # Menghitung persentase partisipasi
    if jumlah_mahasiswa > 0:
        persentase_pemilih = round(
            jumlah_pemilih / jumlah_mahasiswa * 100, 1
        )

        persentase_belum_memilih = round(
            belum_memilih / jumlah_mahasiswa * 100, 1
        )
    else:
        persentase_pemilih = 0
        persentase_belum_memilih = 0

    return render_template(
        "statistic.html",
        jumlah_mahasiswa=jumlah_mahasiswa,
        jumlah_pemilih=jumlah_pemilih,
        belum_memilih=belum_memilih,
        persentase_pemilih=persentase_pemilih,
        persentase_belum_memilih=persentase_belum_memilih
    )



# HALAMAN DAFTAR PEMILIH
@app.route("/admin/daftar-pemilih")
def daftar_pemilih():

    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    # Mengambil kata kunci pencarian
    kata_kunci = request.args.get("q", "").strip()

    conn = koneksi_database()
    cursor = conn.cursor()

    if kata_kunci:
        cursor.execute("""
            SELECT
                nim,
                nama,
                program_studi,
                angkatan,
                sudah_memilih,
                tanggal_vote
            FROM pemilih
            WHERE nim LIKE ? OR nama LIKE ?
            ORDER BY nim ASC
        """, (f"%{kata_kunci}%", f"%{kata_kunci}%"))

    else:
        cursor.execute("""
            SELECT
                nim,
                nama,
                program_studi,
                angkatan,
                sudah_memilih,
                tanggal_vote
            FROM pemilih
            ORDER BY nim ASC
        """)

    daftar_mahasiswa = cursor.fetchall()

    conn.close()

    return render_template(
        "daftar_pemilih.html",
        daftar_mahasiswa=daftar_mahasiswa,
        kata_kunci=kata_kunci
    )


# MENAMBAHKAN DATA PEMILIH
@app.route("/admin/pemilih/tambah", methods=["POST"])
def tambah_pemilih():

    # Pastikan hanya admin yang bisa menambahkan pemilih
    if session.get("role") != "admin":
        flash("Akses hanya untuk admin!", "error")
        return redirect(url_for("login_admin"))

    # Mengambil data dari formulir
    nim = request.form.get("nim", "").strip()
    nama = request.form.get("nama", "").strip()
    program_studi = request.form.get("program_studi", "").strip()
    angkatan = request.form.get("angkatan", "").strip()

    # Validasi semua kolom
    if not all([nim, nama, program_studi, angkatan]):
        flash("Semua data pemilih wajib diisi!", "error")
        return redirect(url_for("daftar_pemilih"))

    # Validasi angkatan
    try:
        angkatan = int(angkatan)

        if angkatan < 1900 or angkatan > 2100:
            raise ValueError

    except ValueError:
        flash("Angkatan tidak valid!", "error")
        return redirect(url_for("daftar_pemilih"))

    conn = koneksi_database()
    cursor = conn.cursor()

    try:
        # Memasukkan mahasiswa baru ke database
        cursor.execute("""
            INSERT INTO pemilih
            (nim, nama, program_studi, angkatan)
            VALUES (?, ?, ?, ?)
        """, (nim, nama, program_studi, angkatan))

        conn.commit()

        flash("Data pemilih berhasil ditambahkan!", "success")

    except sqlite3.IntegrityError:
        conn.rollback()
        flash("NIM sudah terdaftar! Gunakan NIM lain.", "error")

    except Exception:
        conn.rollback()
        flash("Terjadi kesalahan saat menambahkan pemilih!", "error")

    finally:
        conn.close()

    return redirect(url_for("daftar_pemilih"))


# 10. LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    flash("Anda berhasil logout!", "success")
    return redirect(url_for("home"))


# 11. MENJALANKAN PROGRAM
if __name__ == "__main__":
    buat_database()
    print("Database berhasil dibuat!")
    app.run(debug=True)
