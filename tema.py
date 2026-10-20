import html

import numpy as np
import pandas as pd
import streamlit as st

# ===== Palet BI Pastel =====
LAVENDER = "#B8A9D9"
DUSTY_PINK = "#E8B4C8"
BABY_BLUE = "#A8C8E8"
MINT = "#A8D8C8"
CREAM = "#F5EFE6"
PUTIH = "#FFFFFF"
TEKS_GELAP = "#2E2A3A"
TEKS_MUTED = "#6B6578"
ABU_LEMBUT = "#D8D3E0"
BORDER_LEMBUT = "#E5E0EC"
PEACH = "#F0C9A8"

WARNA = [LAVENDER, DUSTY_PINK, BABY_BLUE, MINT, TEKS_GELAP, "#C9A8D9"]
FONT = "'Inter', 'Segoe UI', Arial, sans-serif"
HEAD = "'Poppins', 'Segoe UI', Arial, sans-serif"

CSS = """
:root {
    --bp-lavender: #B8A9D9;
    --bp-pink: #E8B4C8;
    --bp-blue: #A8C8E8;
    --bp-mint: #A8D8C8;
    --bp-cream: #F5EFE6;
    --bp-white: #FFFFFF;
    --bp-ink: #2E2A3A;
    --bp-muted: #6B6578;
    --bp-border: #E5E0EC;
    --bp-soft: #D8D3E0;
    --bp-peach: #F0C9A8;
    --bp-font: __BP_FONT__;
    --bp-head: __BP_HEAD__;
}

html { scroll-behavior: smooth; }

.stApp {
    color: var(--bp-ink);
    background-color: #FAF7F2;
    background-image:
        radial-gradient(circle at 10% 5%, rgba(184,169,217,.10) 0, transparent 40%),
        radial-gradient(circle at 90% 15%, rgba(232,180,200,.10) 0, transparent 40%),
        radial-gradient(circle at 50% 90%, rgba(168,200,232,.10) 0, transparent 45%);
    background-attachment: fixed;
    font-family: var(--bp-font);
}
header[data-testid="stHeader"] { background: transparent; }
#MainMenu, footer, [data-testid="stDeployButton"], [data-testid="stStatusWidget"] {
    visibility: hidden;
    height: 0;
}
.block-container {
    width: 100%;
    max-width: 1380px;
    padding: 1.4rem 2rem 3rem;
}
h1, h2, h3, h4 {
    color: var(--bp-ink);
    font-family: var(--bp-head);
    font-weight: 700;
    letter-spacing: .01em;
}
p, li, label, span, div { font-family: var(--bp-font); }

/* ===== Header ===== */
.hdr {
    margin: .35rem 0 1.2rem;
    padding: 1.15rem 1.35rem;
    background: var(--bp-white);
    border: 1px solid var(--bp-border);
    border-left: 6px solid var(--bp-lavender);
    border-radius: 14px;
    box-shadow: 0 4px 14px rgba(46,42,58,.06);
}
.hdr h2 { margin: 0; font-size: clamp(1.5rem, 2.4vw, 1.9rem); line-height: 1.2; }
.hdr p { margin: .35rem 0 .55rem; color: var(--bp-muted); font-size: .98rem; }
.badges { display: flex; flex-wrap: wrap; gap: .4rem; }
.bdg {
    padding: .22rem .7rem;
    color: var(--bp-ink);
    background: var(--bp-cream);
    border: 1px solid var(--bp-border);
    border-radius: 999px;
    font-size: .82rem;
    line-height: 1.4;
}
.bdg.y { background: #FFF3D9; border-color: #E9D6A8; }
.bdg.g { color: var(--bp-white); background: var(--bp-ink); border-color: var(--bp-ink); }

/* ===== KPI ===== */
.kgrid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: .85rem;
    margin: .45rem 0 1.1rem;
}
.kpi {
    min-width: 0;
    padding: .9rem 1.05rem;
    background: var(--bp-white);
    border: 1px solid var(--bp-border);
    border-top: 3px solid var(--bp-lavender);
    border-radius: 12px;
    box-shadow: 0 3px 12px rgba(46,42,58,.05);
}
.kpi:nth-child(4n+2) { border-top-color: var(--bp-pink); }
.kpi:nth-child(4n+3) { border-top-color: var(--bp-blue); }
.kpi:nth-child(4n+4) { border-top-color: var(--bp-mint); }
.kpi span {
    display: block;
    color: var(--bp-muted);
    font-size: .78rem;
    font-weight: 600;
    letter-spacing: .03em;
    text-transform: uppercase;
}
.kpi b {
    display: block;
    margin-top: .2rem;
    color: var(--bp-ink);
    font-family: var(--bp-head);
    font-size: clamp(1.25rem, 2.1vw, 1.7rem);
    font-weight: 700;
    line-height: 1.2;
    overflow-wrap: anywhere;
}

/* ===== Note / Card ===== */
.note {
    margin: .55rem 0 1.1rem;
    padding: .8rem 1rem;
    color: var(--bp-ink);
    background: #F3EDFB;
    border: 1px solid #DFD3F0;
    border-left: 4px solid var(--bp-lavender);
    border-radius: 10px;
    line-height: 1.55;
    overflow-wrap: anywhere;
}
.card {
    margin: .45rem 0 1.1rem;
    padding: 1rem 1.15rem;
    color: var(--bp-ink);
    background: var(--bp-white);
    border: 1px solid var(--bp-border);
    border-radius: 12px;
    box-shadow: 0 3px 12px rgba(46,42,58,.05);
    line-height: 1.6;
}

/* ===== Table ===== */
.tw {
    max-width: 100%;
    max-height: 460px;
    overflow: auto;
    margin: .35rem 0 .9rem;
    background: var(--bp-white);
    border: 1px solid var(--bp-border);
    border-radius: 10px;
}
table.bi { width: max-content; min-width: 100%; border-collapse: collapse; font-size: .9rem; }
table.bi th {
    position: sticky;
    top: 0;
    z-index: 1;
    padding: .6rem .8rem;
    color: var(--bp-white);
    background: #7C6BA8;
    border-bottom: 2px solid var(--bp-lavender);
    text-align: left;
    white-space: nowrap;
    font-weight: 600;
}
table.bi td {
    padding: .5rem .8rem;
    color: var(--bp-ink);
    border-top: 1px solid var(--bp-border);
    vertical-align: top;
}
table.bi tr:nth-child(even) td { background: #FBF8FE; }
.tw + p { color: var(--bp-muted); font-size: .85rem; }

/* ===== Buttons ===== */
.stButton > button, .stDownloadButton > button {
    min-height: 2.6rem;
    border-radius: 10px;
    font-family: var(--bp-font);
    font-size: .95rem;
    font-weight: 600;
    transition: background-color .18s ease, border-color .18s ease, transform .18s ease;
}
.stButton > button[kind="primary"] {
    color: var(--bp-white);
    background: #9B85C7;
    border: 1px solid #9B85C7;
}
.stButton > button[kind="primary"]:hover {
    color: var(--bp-white);
    background: #7C6BA8;
    border-color: #7C6BA8;
    transform: translateY(-1px);
}
.stDownloadButton > button {
    color: var(--bp-white);
    background: var(--bp-ink);
    border: 1px solid var(--bp-ink);
}
[data-testid="stFileUploader"] section {
    background: var(--bp-white);
    border: 1.5px dashed var(--bp-lavender);
    border-radius: 12px;
}
[data-testid="stFileUploader"] section:hover { border-color: #9B85C7; }

/* ===== Expander ===== */
[data-testid="stExpander"] {
    background: var(--bp-white);
    border: 1px solid var(--bp-border);
    border-radius: 12px;
    box-shadow: 0 2px 8px rgba(46,42,58,.04);
}
[data-testid="stExpander"] summary {
    color: var(--bp-ink);
    font-weight: 600;
}

/* ===== Topbar ===== */
.st-key-topbar {
    margin-bottom: 1rem;
    padding: 1rem 1.2rem;
    color: var(--bp-white);
    background: linear-gradient(120deg, #7C6BA8, #9B85C7 60%, #B8A9D9);
    border-radius: 14px;
    box-shadow: 0 6px 20px rgba(124,107,168,.22);
}
.st-key-topbar [data-testid="stHorizontalBlock"] { align-items: center; }
.dp-topbrand { display: flex; min-width: 0; align-items: center; gap: .9rem; }
.dp-topbrand .dp-uni-logo { width: 46px; height: 46px; flex-basis: 46px; }
.dp-topbrand-title { color: var(--bp-white); font-family: var(--bp-head); font-size: 1.3rem; font-weight: 700; line-height: 1.15; }
.dp-topbrand-sub { color: #EDE6F5; font-size: .85rem; line-height: 1.4; }
.dp-badges { display: flex; flex-wrap: wrap; justify-content: flex-start; gap: .35rem; margin-top: .35rem; }
.dp-badge-top {
    padding: .22rem .6rem;
    color: var(--bp-ink);
    background: var(--bp-white);
    border: 1px solid rgba(255,255,255,.4);
    border-radius: 999px;
    font-size: .76rem;
    line-height: 1.4;
}
.dp-badge-top.y { background: #F0C9A8; border-color: #F0C9A8; }
.st-key-topbar .stButton > button {
    color: var(--bp-white);
    background: transparent;
    border: 1.5px solid rgba(255,255,255,.6);
    border-radius: 10px;
}
.st-key-topbar .stButton > button:hover { background: rgba(255,255,255,.15); }

/* ===== Login shell ===== */
.stApp:has(.st-key-login-shell) {
    background-color: #F5EFFA;
    background-image:
        radial-gradient(circle at 15% 10%, rgba(184,169,217,.25) 0, transparent 45%),
        radial-gradient(circle at 85% 20%, rgba(232,180,200,.20) 0, transparent 45%),
        radial-gradient(circle at 50% 100%, rgba(168,216,200,.18) 0, transparent 45%);
}
.stApp:has(.st-key-login-shell) .block-container {
    display: flex;
    max-width: 1240px;
    min-height: 100vh;
    min-height: 100svh;
    flex-direction: column;
    justify-content: center;
    padding: 2rem;
}
.st-key-login-shell {
    width: 100%;
    max-width: 1140px;
    margin: auto;
    overflow: hidden;
    background: var(--bp-white);
    border: 1px solid var(--bp-border);
    border-radius: 20px;
    box-shadow: 0 20px 50px rgba(124,107,168,.18), 0 4px 12px rgba(46,42,58,.06);
}
.st-key-login-shell [data-testid="stHorizontalBlock"] { align-items: stretch; gap: 0 !important; }
.st-key-login-shell [data-testid="stColumn"] { box-sizing: border-box; min-width: 0; padding: 2.5rem; }
.st-key-login-shell [data-testid="stColumn"]:has(.dp-identity-panel) {
    color: var(--bp-white);
    background: linear-gradient(160deg, #7C6BA8 0%, #9B85C7 55%, #B8A9D9 100%);
}
.dp-identity-panel { color: var(--bp-white); }
.dp-uni-header { display: flex; align-items: center; gap: .9rem; margin-bottom: 1.4rem; }
.dp-uni-logo {
    display: flex;
    width: 64px;
    height: 64px;
    flex: 0 0 64px;
    align-items: center;
    justify-content: center;
    overflow: hidden;
    background: var(--bp-white);
    border: 2px solid rgba(255,255,255,.7);
    border-radius: 14px;
    box-shadow: 0 4px 12px rgba(0,0,0,.10);
}
.dp-uni-logo img { width: 100%; height: 100%; padding: 4px; object-fit: contain; }
.dp-eyebrow { color: #EDE6F5; font-size: .72rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.dp-uni-name { color: var(--bp-white); font-size: 1.05rem; font-weight: 700; line-height: 1.25; }
.dp-title-wrap { margin: 1rem 0 .6rem; padding-bottom: .8rem; border-bottom: 1.5px solid rgba(255,255,255,.25); }
.dp-title-kicker { margin-bottom: .35rem; color: #F0C9A8; font-size: .68rem; font-weight: 700; letter-spacing: .16em; }
.dp-title { margin: 0; color: var(--bp-white); font-family: var(--bp-head); font-size: clamp(1.9rem, 3.2vw, 2.6rem); line-height: 1.05; font-weight: 700; }
.dp-title span { color: #FFE9C4; }
.dp-title-stripe { width: 72px; height: 5px; margin-top: .8rem; background: #FFE9C4; border-radius: 4px; }
.dp-sub { margin: .5rem 0 1.3rem; color: #EDE6F5; font-size: .95rem; line-height: 1.55; }
.dp-idblock { display: flex; align-items: flex-start; gap: 1rem; padding: 1rem; background: rgba(255,255,255,.08); border: 1px solid rgba(255,255,255,.2); border-radius: 14px; }
.dp-foto {
    width: 112px;
    height: 148px;
    flex: 0 0 112px;
    overflow: hidden;
    background: rgba(255,255,255,.12);
    border: 2px solid rgba(255,255,255,.5);
    border-radius: 12px;
    box-shadow: 0 4px 12px rgba(0,0,0,.10);
}
.dp-foto img { width: 100%; height: 100%; object-fit: cover; object-position: center 24%; }
.dp-foto .dp-missing { padding: .5rem; color: #FFE9C4; font-size: .78rem; }
.dp-info { min-width: 0; flex: 1; }
.dp-info-title { color: var(--bp-white); font-size: .78rem; font-weight: 700; letter-spacing: .08em; }
.dp-info-desc { margin: .15rem 0 .6rem; color: #EDE6F5; font-size: .78rem; }
.dp-kv { display: grid; grid-template-columns: minmax(88px, .7fr) minmax(0, 1.3fr); gap: .4rem .55rem; font-size: .84rem; line-height: 1.4; }
.dp-kv .k { color: #EDE6F5; }
.dp-kv .v { color: var(--bp-white); font-weight: 600; overflow-wrap: anywhere; }

.st-key-login-shell [data-testid="stColumn"]:has(.dp-login-form-head) {
    color: var(--bp-ink);
    background: var(--bp-white);
    display: flex;
    flex-direction: column;
    justify-content: center;
}
.dp-login-form-head { margin: 0 0 1rem; }
.dp-eyebrow-secure { color: #9B85C7; font-size: .74rem; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.dp-access-tag {
    display: inline-flex; align-items: center; gap: .4rem;
    padding: .3rem .7rem; color: var(--bp-ink);
    background: #F0C9A8; border-radius: 8px;
    font-size: .7rem; font-weight: 700; letter-spacing: .08em;
}
.dp-access-indicator { display: inline-block; width: 8px; height: 8px; background: #7C6BA8; border-radius: 50%; }
.dp-login-kicker { margin-top: 1.2rem; color: #9B85C7; font-size: .7rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; }
.dp-welcome { margin: .3rem 0 .4rem; color: var(--bp-ink); font-family: var(--bp-head); font-size: clamp(1.8rem, 3vw, 2.3rem); font-weight: 700; line-height: 1.15; }
.dp-welcome-sub { margin: 0 0 1.2rem; color: var(--bp-muted); font-size: .92rem; line-height: 1.6; }
.dp-login-divider { display: flex; align-items: center; gap: .7rem; margin: 1.2rem 0 .5rem; color: var(--bp-muted); font-size: .7rem; font-weight: 700; letter-spacing: .1em; }
.dp-login-divider::after { content: ""; height: 1.5px; flex: 1; background: var(--bp-border); }
.dp-login-divider span { color: #9B85C7; }
.st-key-login-shell [data-testid="stTextInput"] label { color: var(--bp-ink); font-size: .8rem; font-weight: 700; }
.st-key-login-shell [data-testid="stTextInput"] input {
    min-height: 3rem;
    color: var(--bp-ink);
    background: #FAF7F2;
    border: 1.5px solid var(--bp-border);
    border-radius: 10px;
    font-size: .95rem;
}
.st-key-login-shell [data-testid="stTextInput"] input:focus {
    border-color: #9B85C7;
    box-shadow: 0 0 0 3px rgba(155,133,199,.18);
}
.st-key-login-shell .stButton > button,
.st-key-login-shell .stFormSubmitButton > button {
    min-height: 2.9rem;
    border-radius: 10px;
    font-weight: 700;
    letter-spacing: .02em;
}
.st-key-login-shell .stButton > button[kind="primary"] {
    color: var(--bp-white);
    background: #7C6BA8;
    border: 1px solid #7C6BA8;
    box-shadow: 0 4px 12px rgba(124,107,168,.25);
}
.st-key-login-shell .stButton > button[kind="primary"]:hover { background: #6B5A93; }
.st-key-login-shell .stButton > button[kind="secondary"] {
    color: var(--bp-muted);
    background: transparent;
    border: 1px solid var(--bp-border);
}
.dp-left-footer { display: flex; justify-content: space-between; gap: .5rem; margin-top: 1.4rem; padding-top: .7rem; color: #EDE6F5; border-top: 1px solid rgba(255,255,255,.2); font-size: .68rem; font-weight: 600; letter-spacing: .08em; }

/* ===== Section nav & banner (one-page) ===== */
.sec-nav {
    position: sticky;
    top: 0;
    z-index: 10;
    display: flex;
    flex-wrap: wrap;
    gap: .45rem;
    margin: .2rem 0 1.2rem;
    padding: .65rem .7rem;
    background: rgba(255,255,255,.92);
    border: 1px solid var(--bp-border);
    border-radius: 12px;
    box-shadow: 0 4px 14px rgba(46,42,58,.06);
    backdrop-filter: blur(8px);
}
.sec-nav a {
    display: inline-flex; align-items: center; gap: .4rem;
    padding: .35rem .8rem;
    color: var(--bp-ink) !important;
    background: var(--bp-cream);
    border: 1px solid var(--bp-border);
    border-radius: 8px;
    font-size: .84rem; font-weight: 600;
    text-decoration: none !important;
    transition: background-color .15s ease, border-color .15s ease;
}
.sec-nav a b {
    display: inline-grid; width: 1.3rem; height: 1.3rem; place-items: center;
    color: var(--bp-white); background: #9B85C7; border-radius: 50%;
    font-size: .72rem;
}
.sec-nav a:hover { background: #F0C9A8; border-color: #F0C9A8; }
.sec-banner {
    display: flex; align-items: center; gap: .9rem;
    margin: 2rem 0 1rem;
    padding: .85rem 1.15rem;
    scroll-margin-top: 5rem;
    color: var(--bp-ink);
    background: linear-gradient(120deg, #F0EAFB, #FBEEF4 60%, #E8F3FA);
    border: 1px solid var(--bp-border);
    border-left: 6px solid #9B85C7;
    border-radius: 14px;
    box-shadow: 0 4px 14px rgba(46,42,58,.05);
}
.sec-banner .sec-no {
    display: grid; flex: 0 0 2.5rem; width: 2.5rem; height: 2.5rem; place-items: center;
    color: var(--bp-white); background: #9B85C7; border-radius: 50%;
    font-family: var(--bp-head); font-size: 1.2rem; font-weight: 700;
}
.sec-banner b { display: block; color: var(--bp-ink); font-family: var(--bp-head); font-size: clamp(1.2rem, 2.2vw, 1.5rem); font-weight: 700; line-height: 1.15; }
.sec-banner small { display: block; color: var(--bp-muted); font-size: .84rem; margin-top: .15rem; }

/* ===== Legacy rack styles (kept harmless; not used after Smart Shelf removal) ===== */
.rack { margin: .6rem 0 1.1rem; padding: .9rem; background: var(--bp-white); border: 1px solid var(--bp-border); border-radius: 12px; }
.tier { margin-bottom: 1rem; }
.tlabel { display: inline-block; margin-bottom: .45rem; padding: .2rem .7rem; color: var(--bp-white); background: #7C6BA8; border-radius: 6px; font-weight: 600; font-size: .84rem; }
.slots { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .55rem; }
.slot { min-height: 100px; padding: .45rem; background: #FBF8FE; border: 1px dashed var(--bp-soft); border-radius: 8px; }
.prod { min-height: 90px; padding: .55rem; background: var(--bp-white); border: 1px solid var(--bp-border); border-radius: 8px; overflow-wrap: anywhere; }
.prod b { display: block; font-size: .92rem; color: var(--bp-ink); }
.prod i { display: block; margin: .2rem 0; color: var(--bp-muted); font-size: .8rem; font-style: normal; }
.src { display: inline-block; margin: .2rem .15rem 0 0; padding: .05rem .4rem; background: #FFE9C4; border: 1px solid #E9D6A8; border-radius: 6px; font-size: .72rem; font-weight: 600; }
.src.k { color: var(--bp-white); background: var(--bp-ink); border-color: var(--bp-ink); }
.src.a { color: var(--bp-white); background: #9B85C7; border-color: #9B85C7; }
.board { height: 6px; margin-top: .45rem; background: var(--bp-soft); border-radius: 99px; }

.brand { display: flex; align-items: center; gap: .75rem; margin-bottom: .65rem; }
.brand b { display: block; color: var(--bp-ink); font-family: var(--bp-head); font-size: 1.5rem; font-weight: 700; }
.brand small { display: block; color: var(--bp-muted); font-size: .84rem; }
.dp-topbar-logo { display: grid; width: 46px; height: 46px; flex: 0 0 46px; place-items: center; color: var(--bp-white); background: #9B85C7; border-radius: 12px; font-family: var(--bp-head); font-size: 1.2rem; font-weight: 700; }
.dp-topbar-logo-img { width: 100%; height: 100%; padding: 3px; object-fit: contain; }
.dp-missing { display: flex; width: 100%; height: 100%; min-height: 55px; flex-direction: column; align-items: center; justify-content: center; padding: .5rem; color: var(--bp-muted); overflow-wrap: anywhere; font-size: .72rem; text-align: center; }
.dp-missing-label { margin-bottom: .3rem; color: #9B85C7; font-size: .62rem; font-weight: 700; letter-spacing: .08em; }

:focus-visible { outline: 3px solid #B8A9D9; outline-offset: 2px; }

@media (max-width: 900px) {
    .block-container { padding-right: 1.25rem; padding-left: 1.25rem; }
    .st-key-login-shell [data-testid="stColumn"] { padding: 1.75rem; }
    .dp-idblock { flex-wrap: wrap; }
}
@media (max-width: 680px) {
    .block-container { padding: 1rem .8rem 2rem; }
    .slots { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .stApp:has(.st-key-login-shell) .block-container { justify-content: flex-start; padding: 1rem .65rem; }
    .st-key-login-shell { border-radius: 14px; }
    .st-key-login-shell [data-testid="stHorizontalBlock"] { flex-direction: column !important; }
    .st-key-login-shell [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        width: 100% !important; flex: 1 1 auto !important;
    }
    .st-key-login-shell [data-testid="stColumn"] { padding: 1.35rem; }
    .dp-uni-header { margin-bottom: 1rem; }
    .dp-idblock { flex-wrap: nowrap; }
    .dp-foto { width: 96px; height: 128px; flex-basis: 96px; }
    .dp-badges { justify-content: flex-start; }
    .sec-nav { position: static; }
}
@media (max-width: 390px) {
    .dp-idblock { flex-direction: column; align-items: flex-start; }
    .dp-foto { width: 90px; height: 120px; }
    .dp-kv { grid-template-columns: 1fr; gap: .08rem; }
    .dp-kv .v { margin-bottom: .3rem; }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; }
}
""".replace("__BP_FONT__", FONT).replace("__BP_HEAD__", HEAD)


def inject(login=False):
    """Pasang tema visual BI Pastel pada halaman Streamlit.

    Argumen login dipertahankan untuk kompatibilitas dengan pemanggilan lama.
    Styling login diaktifkan melalui class st-key-login-shell yang digunakan
    oleh login.py.
    """
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)


def esc(x):
    return html.escape(str(x))


def header(title, sub, ctx=()):
    badges = "".join(
        f"<span class='bdg {category}'>{esc(label)}</span>"
        for label, category in ctx
    )
    st.markdown(
        f"<div class='hdr'><h2>{esc(title)}</h2><p>{esc(sub)}</p>"
        f"<div class='badges'>{badges}</div></div>",
        unsafe_allow_html=True,
    )


def kpis(items):
    cards = "".join(
        f"<div class='kpi'><span>{esc(label)}</span><b>{esc(value)}</b></div>"
        for label, value in items
    )
    st.markdown(f"<div class='kgrid'>{cards}</div>", unsafe_allow_html=True)


def note(text):
    st.markdown(f"<div class='note'>{text}</div>", unsafe_allow_html=True)


def card(text):
    st.markdown(f"<div class='card'>{text}</div>", unsafe_allow_html=True)


def _fmt(value):
    if isinstance(value, (float, np.floating)):
        if np.isnan(value):
            return ""
        return f"{value:,.0f}" if abs(value) >= 1000 else f"{value:,.3f}".rstrip("0").rstrip(".")
    if isinstance(value, (int, np.integer)):
        return f"{value:,}"
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d %H:%M")
    return "" if value is None or (isinstance(value, float) and np.isnan(value)) else esc(value)


def tabel(df, maxrows=300):
    if df is None or len(df) == 0:
        st.markdown("<div class='card'>Tidak ada baris untuk ditampilkan.</div>", unsafe_allow_html=True)
        return
    displayed = df.head(maxrows)
    headings = "".join(f"<th>{esc(column)}</th>" for column in displayed.columns)
    rows = "".join(
        "<tr>" + "".join(f"<td>{_fmt(value)}</td>" for value in row) + "</tr>"
        for row in displayed.itertuples(index=False)
    )
    caption = (
        f"<p>Menampilkan {len(displayed):,} dari {len(df):,} baris.</p>"
        if len(df) > maxrows else ""
    )
    st.markdown(
        f"<div class='tw'><table class='bi'><thead><tr>{headings}</tr></thead>"
        f"<tbody>{rows}</tbody></table></div>{caption}",
        unsafe_allow_html=True,
    )


def plot(fig, h=360, config=None):
    """Terapkan gaya visual BI Pastel ke grafik Plotly 2D maupun 3D.

    Tidak mengubah data, trace, maupun hasil perhitungan grafik.
    """
    if config is None:
        config = {
            "displayModeBar": True,
            "displaylogo": False,
            "responsive": True,
            "scrollZoom": True,
        }
    else:
        config = {"displaylogo": False, "responsive": True, **config}

    fig.update_layout(
        paper_bgcolor=PUTIH,
        plot_bgcolor=PUTIH,
        colorway=WARNA,
        height=h,
        font=dict(family=FONT, color=TEKS_GELAP, size=13),
        margin=dict(l=48, r=24, t=58, b=48),
        title=dict(font=dict(family=HEAD, size=20, color=TEKS_GELAP)),
        legend=dict(
            font=dict(family=FONT, color=TEKS_GELAP, size=12),
            bgcolor="rgba(255,255,255,.92)",
            bordercolor=BORDER_LEMBUT,
            borderwidth=1,
        ),
        hoverlabel=dict(
            bgcolor=TEKS_GELAP,
            bordercolor=LAVENDER,
            font=dict(family=FONT, color=PUTIH, size=12),
        ),
        coloraxis_colorbar=dict(
            outlinecolor=ABU_LEMBUT,
            tickfont=dict(family=FONT, color=TEKS_GELAP),
            title_font=dict(family=FONT, color=TEKS_GELAP),
        ),
    )

    fig.update_xaxes(
        gridcolor=BORDER_LEMBUT,
        linecolor=TEKS_GELAP,
        zerolinecolor=ABU_LEMBUT,
        tickfont=dict(family=FONT, color=TEKS_GELAP),
        title_font=dict(family=FONT, color=TEKS_GELAP),
    )
    fig.update_yaxes(
        gridcolor=BORDER_LEMBUT,
        linecolor=TEKS_GELAP,
        zerolinecolor=ABU_LEMBUT,
        tickfont=dict(family=FONT, color=TEKS_GELAP),
        title_font=dict(family=FONT, color=TEKS_GELAP),
    )

    try:
        fig.update_scenes(
            bgcolor=PUTIH,
            xaxis=dict(
                backgroundcolor="#FBF8FE",
                gridcolor=BORDER_LEMBUT,
                linecolor=TEKS_GELAP,
                zerolinecolor=ABU_LEMBUT,
                showbackground=True,
                showgrid=True,
                tickfont=dict(family=FONT, color=TEKS_GELAP, size=11),
                title_font=dict(family=FONT, color=TEKS_GELAP, size=13),
            ),
            yaxis=dict(
                backgroundcolor="#FBF8FE",
                gridcolor=BORDER_LEMBUT,
                linecolor=TEKS_GELAP,
                zerolinecolor=ABU_LEMBUT,
                showbackground=True,
                showgrid=True,
                tickfont=dict(family=FONT, color=TEKS_GELAP, size=11),
                title_font=dict(family=FONT, color=TEKS_GELAP, size=13),
            ),
            zaxis=dict(
                backgroundcolor="#FBF8FE",
                gridcolor=BORDER_LEMBUT,
                linecolor=TEKS_GELAP,
                zerolinecolor=ABU_LEMBUT,
                showbackground=True,
                showgrid=True,
                tickfont=dict(family=FONT, color=TEKS_GELAP, size=11),
                title_font=dict(family=FONT, color=TEKS_GELAP, size=13),
            ),
        )
    except (AttributeError, ValueError):
        pass

    st.plotly_chart(fig, width="stretch", config=config)


def rack(tiers, empty_msg=None):
    """Tampilan rak sederhana untuk tab Rekomendasi & Ekspor."""
    output = "<div class='rack'>"
    if empty_msg:
        output += f"<div class='note' style='margin-top:0'>{esc(empty_msg)}</div>"
    for label, slots in tiers:
        cells = ""
        for slot in slots:
            if slot is None:
                cells += "<div class='slot'></div>"
            else:
                badges = "".join(
                    f"<span class='src {'k' if badge == 'K-Means' else 'a' if badge == 'Apriori' else ''}'>"
                    f"{esc(badge)}</span> "
                    for badge in slot["badge"]
                )
                cells += (
                    f"<div class='slot'><div class='prod'><b>{esc(slot['nama'])}</b>"
                    f"<i>{esc(slot.get('kategori') or 'Kategori tidak tersedia')}</i>{badges}</div></div>"
                )
        output += (
            f"<div class='tier'><span class='tlabel'>{esc(label)}</span>"
            f"<div class='slots'>{cells}</div><div class='board'></div></div>"
        )
    st.markdown(output + "</div>", unsafe_allow_html=True)