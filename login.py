import base64
import os
import textwrap

import streamlit as st
import tema


# =========================================================
# KONFIGURASI IDENTITAS
# =========================================================

NPM_VALID = "51230152"

ID = {
    "nama": "Marsyanda Juliana Tara Nurak",
    "npm": NPM_VALID,
    "prodi": "Teknologi Informasi",
    "fak": "Fakultas Pertanian, Sains dan Kesehatan",
    "univ": "Universitas Timor",
    "mk": "Business Intelligence",
    "kelas": "VII/B",
    "label": "UTS Business Intelligence",
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LOGO_FILE = os.path.join(BASE_DIR, "universitas.jpg")
FOTO_FILE = os.path.join(BASE_DIR, "profile.jpeg")

_EXT_ALT = (".png", ".jpg", ".jpeg", ".webp", ".svg")


# =========================================================
# UTILITAS GAMBAR
# =========================================================

def _find_file(base_name):
    """Cari gambar menggunakan nama dan ekstensi alternatif."""
    if os.path.isfile(base_name):
        return base_name
    root, _ = os.path.splitext(base_name)
    for ext in _EXT_ALT:
        candidate = root + ext
        if os.path.isfile(candidate):
            return candidate
    return None


def _img_data_uri(path):
    """Konversi gambar lokal menjadi data URI."""
    if not path or not os.path.isfile(path):
        return None
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    mime_types = {
        "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
        "webp": "image/webp", "svg": "image/svg+xml",
    }
    mime = mime_types.get(ext)
    if not mime:
        return None
    try:
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("ascii")
    except OSError:
        return None
    return f"data:{mime};base64,{encoded}"


LOGO_URI = _img_data_uri(_find_file(LOGO_FILE))
FOTO_URI = _img_data_uri(_find_file(FOTO_FILE))


def _img_html(uri, alt, css_class=""):
    safe_alt = tema.esc(alt)
    safe_class = tema.esc(css_class)
    if uri:
        return f'<img src="{uri}" alt="{safe_alt}" class="{safe_class}">'
    return (
        '<div class="dp-missing">'
        '<span class="dp-missing-label">IMAGE NOT FOUND</span>'
        f'<div>{safe_alt}</div>'
        '</div>'
    )


def _render_html(markup, target=st):
    target.html(textwrap.dedent(markup).strip())


def _clear_login_input():
    st.session_state["npm_input"] = ""
    st.session_state.pop("login_err", None)


# =========================================================
# HALAMAN LOGIN
# =========================================================

def halaman_login():
    tema.inject(login=True)

    if st.session_state.get("auth", False):
        return

    with st.container(key="login-shell"):
        kiri, kanan = st.columns([1.08, 1], gap=None)

        with kiri:
            logo_html = _img_html(LOGO_URI, "Logo Universitas Timor", "dp-logo-img")
            foto_html = _img_html(FOTO_URI, "Foto mahasiswa", "dp-profile-img")
            _render_html(
                f"""
                <section class="dp-identity-panel">
                    <div class="dp-uni-header">
                        <div class="dp-uni-logo">{logo_html}</div>
                        <div class="dp-uni-text">
                            <div class="dp-eyebrow">UNIVERSITAS</div>
                            <div class="dp-uni-name">Universitas Timor</div>
                        </div>
                    </div>
                    <div class="dp-title-wrap">
                        <div class="dp-title-kicker">SISTEM ANALISIS BISNIS</div>
                        <h1 class="dp-title">UTS BUSINESS<br><span>INTELLIGENCE</span></h1>
                        <div class="dp-title-stripe"></div>
                    </div>
                    <p class="dp-sub">Analisis bisnis dan penjualan · Universitas Timor</p>
                    <div class="dp-idblock">
                        <div class="dp-foto">{foto_html}</div>
                        <div class="dp-info">
                            <div class="dp-info-title">IDENTITAS MAHASISWA</div>
                            <div class="dp-info-desc">Identitas peserta dan mata kuliah</div>
                            <div class="dp-kv">
                                <div class="k">Nama</div><div class="v">{tema.esc(ID["nama"])}</div>
                                <div class="k">NPM</div><div class="v">{tema.esc(ID["npm"])}</div>
                                <div class="k">Program Studi</div><div class="v">{tema.esc(ID["prodi"])}</div>
                                <div class="k">Fakultas</div><div class="v">{tema.esc(ID["fak"])}</div>
                                <div class="k">Universitas</div><div class="v">{tema.esc(ID["univ"])}</div>
                                <div class="k">Mata Kuliah</div><div class="v">{tema.esc(ID["mk"])}</div>
                                <div class="k">Kelas</div><div class="v">{tema.esc(ID["kelas"])}</div>
                            </div>
                        </div>
                    </div>
                    <div class="dp-left-footer">
                        <span>BUSINESS INTELLIGENCE</span>
                        <span>UTS · 2026</span>
                    </div>
                </section>
                """,
            )

        with kanan:
            _render_html(
                """
                <section class="dp-login-form-head">
                    <div class="dp-access-tag">
                        <span class="dp-access-indicator"></span>
                        SECURE ACCESS
                    </div>
                    <div class="dp-login-kicker">PORTAL MAHASISWA</div>
                    <h2 class="dp-welcome">Welcome Back</h2>
                    <p class="dp-welcome-sub">
                        Masuk ke Business Intelligence System
                        menggunakan NPM mahasiswa terdaftar.
                    </p>
                    <div class="dp-login-divider"><span>NPM / USERNAME</span></div>
                </section>
                """,
            )

            npm = st.text_input(
                "NPM / Username",
                key="npm_input",
                max_chars=12,
                placeholder="Masukkan NPM Anda",
                help="Masukkan NPM yang terdaftar untuk mata kuliah ini.",
                label_visibility="visible",
            )

            btn_masuk = st.button(
                "Masuk", key="btn_masuk", type="primary", width="stretch",
            )
            st.button(
                "Bersihkan input", key="btn_keluar_login",
                width="stretch", on_click=_clear_login_input,
            )

            if btn_masuk:
                npm_input = npm.strip()
                if not npm_input:
                    st.session_state["login_err"] = "empty"
                elif npm_input == NPM_VALID:
                    st.session_state["auth"] = True
                    st.session_state.pop("login_err", None)
                    st.rerun()
                else:
                    st.session_state["login_err"] = "invalid"

            login_error = st.session_state.get("login_err")
            if login_error == "empty":
                st.warning("Masukkan NPM terlebih dahulu sebelum melanjutkan.")
            elif login_error == "invalid":
                st.error("NPM tidak terdaftar. Periksa kembali nomor yang Anda masukkan.")


# =========================================================
# TOPBAR DASHBOARD
# =========================================================

def topbar(status_badges):
    tema.inject()
    with st.container(key="topbar"):
        identitas, keluar = st.columns([7, 1], vertical_alignment="center")
        logo_html = _img_html(LOGO_URI, "Logo Universitas Timor", "dp-topbar-logo-img")
        badge_items = [
            (ID["nama"], ""),
            (f"NPM {ID['npm']}", ""),
            (ID["label"], "y"),
            *status_badges,
        ]
        badges = "".join(
            f"<span class='dp-badge-top {'y' if category == 'y' else ''}'>"
            f"{tema.esc(label)}</span>"
            for label, category in badge_items
        )
        _render_html(
            f"""
            <div class="dp-topbrand">
                <div class="dp-uni-logo">{logo_html}</div>
                <div class="dp-topbrand-content">
                    <div class="dp-topbrand-title">BUSINESS INTELLIGENCE</div>
                    <div class="dp-topbrand-sub">
                        {tema.esc(ID["mk"])} · Kelas {tema.esc(ID["kelas"])} · {tema.esc(ID["univ"])}
                    </div>
                    <div class="dp-badges">{badges}</div>
                </div>
            </div>
            """,
            target=identitas,
        )
        if keluar.button("Keluar", key="btn_keluar", width="stretch"):
            logout()
            st.rerun()


# =========================================================
# LOGOUT
# =========================================================

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]