import io
import html
import re
import textwrap
import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
import tema
import login

st.set_page_config(
    page_title="Business Intelligence | Universitas Timor",
    page_icon=":material/analytics:",
    layout="wide",
    initial_sidebar_state="collapsed",
)
ss = st.session_state
UNK = "Tidak diketahui"
CAN = dict(tid="Transaction_ID", date="Transaction_Date", cid="Customer_ID", pid="Product_ID", pname="Product_Name",
           cat="Category", qty="Quantity", price="Unit_Price", disc="Discount_Rate", total="Line_Total", region="Region",
           country="Country", cname="Customer_Name", ctype="Customer_Type", pay="Payment_Method", age="Age")
KEYS = [("tid", ["transactionid", "transaksiid", "idtransaksi", "notransaksi", "invoice", "nota", "orderid"]),
        ("cid", ["customerid", "pelangganid", "idpelanggan", "custid", "idcustomer", "memberid"]),
        ("pid", ["productid", "produkid", "idproduk", "sku", "kodeproduk"]),
        ("cname", ["customername", "namapelanggan", "namacustomer"]),
        ("ctype", ["customertype", "tipepelanggan", "jenispelanggan"]),
        ("pname", ["productname", "namaproduk", "namabarang", "produk", "product", "item"]),
        ("cat", ["category", "kategori"]),
        ("disc", ["discount", "diskon"]),
        ("qty", ["quantity", "qty", "kuantitas", "jumlah"]),
        ("price", ["unitprice", "hargasatuan", "harga", "price"]),
        ("total", ["linetotal", "netsales", "revenue", "pendapatan", "totalpenjualan", "subtotal", "amount", "sales", "total"]),
        ("date", ["transactiondate", "orderdate", "tanggal", "datetime", "date", "tgl", "waktu"]),
        ("country", ["country", "negara"]),
        ("region", ["region", "wilayah", "kota", "area", "provinsi"]),
        ("pay", ["payment", "pembayaran", "metodebayar"]),
        ("age", ["age", "umur", "usia"])]
DEFAULTS = dict(auth=False, raw=None, map=None, sheet=None, load_err=None, audit=None, clean=None,
                log=None, psum=None, prep_err=None, rfm=None, rfm_err=None, kmeans=None, apriori=None,
                reco=None, xlsx=None, ver=0, p_sup=0.01, p_conf=0.20, p_lift=1.2, p_len=3, km_k=None,
                elbow=None, km_err=None)
for _k, _v in DEFAULTS.items():
    ss.setdefault(_k, _v)


def rp(x, dec=0):
    """Format angka ke Rupiah lengkap: Rp 1.234.567"""
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "Rp -"
    if not isinstance(x, (int, float, np.integer, np.floating)):
        try:
            x = float(x)
        except Exception:
            return "Rp -"
    neg = x < 0
    x = abs(x)
    if dec:
        s = f"{x:,.{dec}f}"
        intpart, frac = s.rsplit(".", 1)
        s = intpart.replace(",", ".") + "," + frac
    else:
        s = f"{x:,.0f}".replace(",", ".")
    return ("-Rp " if neg else "Rp ") + s


def wk(fn, key, default, *a, **kw):
    if key not in ss:
        ss[key] = ss.get("_k_" + key, default)
    v = fn(*a, key=key, **kw)
    ss["_k_" + key] = v
    return v


def reset_data():
    for k in ["raw", "map", "sheet", "load_err", "audit", "clean", "log", "psum", "prep_err",
              "rfm", "rfm_err", "kmeans", "apriori", "reco", "xlsx", "km_k", "elbow", "km_err"]:
        ss[k] = None
    for k in list(ss.keys()):
        if k.startswith("f_") or k.startswith("_k_f_"):
            del ss[k]
    ss["ver"] += 1


def detect(cols):
    m, used = {}, set()
    norm = {c: re.sub(r"[^a-z0-9]", "", str(c).lower()) for c in cols}
    for role, keys in KEYS:
        for key in keys:
            hit = [c for c in cols if c not in used and (norm[c] == key or key in norm[c])]
            if hit:
                m[role] = hit[0]
                used.add(hit[0])
                break
    return m


def read_workbook(f):
    sheets = pd.read_excel(io.BytesIO(f.getvalue()), sheet_name=None, engine="openpyxl")
    best = None
    for name, df in sheets.items():
        df = df.dropna(how="all").dropna(axis=1, how="all")
        if df.empty:
            continue
        m = detect(list(df.columns))
        if not ({"tid", "date"} <= set(m) and ("pid" in m or "pname" in m)):
            continue
        score = sum(k in m for k in ["tid", "date", "pid", "pname", "qty", "price", "total"]) * 10**6 + len(df)
        if best is None or score > best[0]:
            best = (score, name, df, m)
    if best is None:
        raise ValueError("Tidak ditemukan sheet data transaksi. Sheet harus memuat minimal kolom ID transaksi, tanggal, dan produk (ID atau nama).")
    return best[1], best[2].reset_index(drop=True), best[3]


def qp_masks(q, p, item):
    pm = p.where(p > 0).groupby(item).transform("median")
    pos = q[q > 0]
    cap = max(10.0, pos.quantile(.75) + 3 * (pos.quantile(.75) - pos.quantile(.25))) if len(pos) else 10.0
    return (q.isna() | (q <= 0) | (q > cap)), (p.isna() | (p <= 0) | (p > 5 * pm)), pm, cap


def audit(raw, m):
    a = {}
    miss = pd.DataFrame({"Kolom": raw.columns, "Tipe data": [str(t) for t in raw.dtypes], "Kosong": raw.isna().sum().values})
    miss["Persen kosong (%)"] = (miss["Kosong"] / max(len(raw), 1) * 100).round(2)
    num = [c for c in raw.columns if pd.api.types.is_numeric_dtype(raw[c])]
    dte = [c for c in raw.columns if pd.api.types.is_datetime64_any_dtype(raw[c])] or ([m["date"]] if "date" in m else [])
    a["miss"], a["num"], a["dte"] = miss, num, dte
    a["cat"] = [c for c in raw.columns if c not in num and c not in dte]
    a["dims"], a["empty"], a["dup"] = raw.shape, int(raw.isna().sum().sum()), int(raw.duplicated().sum())
    ck = []
    for k, lab in [("tid", "Transaction_ID kosong"), ("cid", "Customer_ID kosong"), ("pid", "Product_ID kosong")]:
        if k in m:
            ck.append((lab, int(raw[m[k]].isna().sum()), "Baris tanpa ID; ID pelanggan kosong tetap dihitung sebagai penjualan tetapi dikeluarkan dari RFM/K-Means"))
    if "date" in m:
        dt = pd.to_datetime(raw[m["date"]], errors="coerce")
        ck.append(("Tanggal tidak valid/kosong", int(dt.isna().sum()), "Baris dengan tanggal tidak bisa dibaca"))
    item = raw[m.get("pname", m.get("pid"))].astype("string").str.strip()
    if "qty" in m and "price" in m:
        q, p = pd.to_numeric(raw[m["qty"]], errors="coerce"), pd.to_numeric(raw[m["price"]], errors="coerce")
        qb, pb, pm, cap = qp_masks(q, p, item)
        ck.append(("Quantity <= 0 (potensi retur/tidak valid)", int((q <= 0).sum()), "Nilai nol atau negatif"))
        ck.append((f"Quantity di atas batas wajar ({cap:g})", int((q > cap).sum()), "Outlier ekstrem (batas = maks(10, Q3 + 3 x IQR))"))
        ck.append(("Quantity kosong", int(q.isna().sum()), "Dipulihkan dari Line_Total bila memungkinkan"))
        ck.append(("Unit_Price <= 0", int((p <= 0).sum()), "Harga nol atau negatif"))
        ck.append(("Unit_Price > 5x median produk", int((p > 5 * pm).sum()), "Outlier ekstrem harga"))
        ck.append(("Unit_Price kosong", int(p.isna().sum()), "Dipulihkan dari Line_Total atau median produk"))
        if "total" in m:
            t = pd.to_numeric(raw[m["total"]], errors="coerce")
            calc = q * p * (1 - (pd.to_numeric(raw[m["disc"]], errors="coerce").fillna(0) if "disc" in m else 0))
            ck.append(("Line_Total tidak konsisten dengan Qty x Harga x (1 - Diskon)", int((t.notna() & calc.notna() & ((t - calc).abs() > np.maximum(1, .01 * calc))).sum()), "Termasuk akibat Quantity/Harga bermasalah"))
    ck.append(("Baris duplikat penuh", a["dup"], "Seluruh kolom identik"))
    ck.append(("Potensi duplikasi (Transaction_ID + produk sama)", int(raw.assign(_i=item).duplicated([m["tid"], "_i"]).sum()), "Termasuk duplikat penuh; Transaction_ID berulang saja bukan duplikat"))
    var = 0
    for c in a["cat"]:
        s = raw[c].dropna().astype(str)
        var += int((s.groupby(s.str.strip().str.casefold()).nunique() > 1).sum())
    ck.append(("Kelompok teks dengan variasi ejaan/kapital/spasi", var, "Nilai berbeda hanya karena kapital atau spasi"))
    a["checks"] = pd.DataFrame(ck, columns=["Pemeriksaan", "Jumlah", "Keterangan"])
    return a


def prep(raw, m):
    d, log, n0 = raw.copy(), [], len(raw)
    L = lambda a, b, c, t: log.append(dict(Masalah=a, Aturan=b, Jumlah=int(c), Tindakan=t))
    txt = [m[k] for k in ("tid", "cid", "pid", "pname", "cat", "region", "country", "cname", "ctype", "pay") if k in m]
    before = {c: raw[c].copy() for c in txt}
    for c in txt:
        s = d[c].astype("string").str.strip().str.replace(r"\s+", " ", regex=True)
        d[c] = s.astype(object).where(s.fillna("") != "", np.nan)
    for c in [m[k] for k in ("cat", "region", "ctype", "pay", "pname", "country") if k in m]:
        s = d[c]
        kk = s.str.casefold()
        canon = s.groupby(kk).agg(lambda x: x.value_counts().index[0])
        d[c] = kk.map(canon).where(s.notna(), np.nan)
    ch = sum(int((before[c].notna() & (before[c].astype(str) != d[c].astype(str))).sum()) for c in txt)
    L("Inkonsistensi teks (spasi, kapital, ejaan)", "Trim, rapikan spasi, samakan variasi kapital ke bentuk paling sering", ch, "Diperbaiki")
    dup = d.duplicated()
    L("Baris duplikat penuh", f"Seluruh kolom identik ({int(raw.duplicated().sum())} pada data asli, sisanya muncul setelah teks dirapikan). Transaction_ID berulang tidak dianggap duplikat", dup.sum(), "Dihapus (baris pertama dipertahankan)")
    d = d[~dup].copy()
    dt = pd.to_datetime(d[m["date"]], errors="coerce")
    L("Tanggal tidak valid", "Tidak dapat dikonversi ke tanggal", dt.isna().sum(), "Dihapus")
    d = d[dt.notna()].copy()
    d[m["date"]] = dt[dt.notna()]
    bad = d[m["tid"]].isna()
    L("Transaction_ID kosong", "Baris tidak dapat dikelompokkan ke transaksi", bad.sum(), "Dihapus")
    d = d[~bad].copy()
    pid, pn = m.get("pid"), m.get("pname")
    if pid and pn:
        n2i = d.dropna(subset=[pid, pn]).groupby(pn)[pid].agg(lambda x: x.value_counts().index[0])
        i2n = d.dropna(subset=[pid, pn]).groupby(pid)[pn].agg(lambda x: x.value_counts().index[0])
        mp = d[pid].isna() & d[pn].notna()
        d.loc[mp, pid] = d.loc[mp, pn].map(n2i)
        mn = d[pn].isna() & d[pid].notna()
        d.loc[mn, pn] = d.loc[mn, pid].map(i2n)
        L("Product_ID/Product_Name kosong", "Dilengkapi dari pasangan ID-nama yang paling sering pada data", mp.sum() + mn.sum(), "Diimputasi")
    it = pn or pid
    bad = d[it].isna()
    L("Produk tidak teridentifikasi", "ID dan nama produk sama-sama kosong", bad.sum(), "Dihapus")
    d = d[~bad].copy()
    num = lambda k: pd.to_numeric(d[m[k]], errors="coerce") if k in m else None
    q, p, t, dsc = num("qty"), num("price"), num("total"), num("disc")
    if dsc is None:
        dsc = pd.Series(0.0, index=d.index)
    else:
        L("Discount_Rate kosong", "Dianggap tanpa diskon (0)", dsc.isna().sum(), "Diimputasi 0")
        dsc = dsc.fillna(0)
    flag = pd.Series("", index=d.index)
    info = ""
    if q is not None and p is not None:
        qb, pb, pm, cap = qp_masks(q, p, d[it])
        L("Quantity <= 0 (potensi retur/tidak valid)", "Tidak ada kolom status retur; nilai nol/negatif dianggap tidak valid", (q <= 0).sum(), "Dipulihkan dari Line_Total jika bulat dan wajar, selain itu dihapus")
        dm = 1 - dsc
        nfp = nip = nfq = 0
        if t is not None:
            rp_ = t / (q.where(~qb) * dm)
            ok = pb & ~qb & t.notna() & rp_.between(.5 * pm, 2 * pm)
            p = p.where(~ok, rp_.round())
            flag = flag.mask(ok, "harga dipulihkan dari Line_Total")
            nfp = int(ok.sum())
            pb = pb & ~ok
        ok2 = pb & pm.notna()
        p = p.where(~ok2, pm)
        flag = flag.mask(ok2, "harga diimputasi median produk")
        nip = int(ok2.sum())
        L("Unit_Price kosong/<=0/ekstrem", f"Kosong, <= 0, atau > 5x median produk (total {int(((raw[m['price']].isna()) | (pd.to_numeric(raw[m['price']], errors='coerce') <= 0)).sum())} kosong/<=0 pada data asli)", nfp + nip, f"Diperbaiki: {nfp} dari Line_Total, {nip} dari median produk")
        if t is not None:
            rq = t / (p * dm)
            okq = qb & p.gt(0) & t.notna() & ((rq - rq.round()).abs() < .05) & rq.round().between(1, cap)
            q = q.where(~okq, rq.round())
            flag = flag.mask(okq, "quantity dipulihkan dari Line_Total")
            nfq = int(okq.sum())
        L("Quantity kosong/ekstrem", f"Kosong, <= 0, atau di atas batas wajar {cap:g}", nfq, "Dipulihkan dari Line_Total")
        drop = (q.isna() | (q <= 0) | (q > cap)) | (p.isna() | (p <= 0))
        L("Quantity/Harga tidak dapat dipulihkan", "Tidak ada dasar perbaikan yang wajar", drop.sum(), "Dihapus")
        d, q, p, t, dsc, flag = [x[~drop] if x is not None else None for x in (d, q, p, t, dsc, flag)]
        calc = q * p * (1 - dsc)
        if t is not None:
            cons = t.notna() & ((t - calc).abs() <= np.maximum(1, .01 * calc))
            net = t.where(cons, calc)
            L("Line_Total kosong", "Dihitung Quantity x Unit_Price x (1 - Diskon)", t.isna().sum(), "Dihitung ulang")
            L("Line_Total tidak konsisten", "Selisih > 1% dari hasil hitung", (t.notna() & ~cons).sum(), "Dihitung ulang dan ditandai")
            flag = flag.mask(~cons & (flag == ""), "line_total dihitung ulang")
            info = f"Line_Total konsisten dengan Qty x Harga x (1 - Diskon) pada {cons.mean() * 100:.1f}% baris bersih, sehingga bernilai per baris item dan tidak diulang pada setiap item dalam transaksi (tidak ada penghitungan ganda)."
        else:
            net = calc
            info = "Pendapatan dihitung dari Quantity x Unit_Price x (1 - Diskon) karena kolom total tidak tersedia."
    elif t is not None:
        drop = t.isna()
        L("Pendapatan kosong", "Tidak ada Quantity/Harga untuk menghitung ulang", drop.sum(), "Dihapus")
        d, t, dsc, flag = d[~drop], t[~drop], dsc[~drop], flag[~drop]
        net = t
        info = "Pendapatan memakai kolom total apa adanya."
    else:
        net = None
        info = "Kolom pendapatan, Quantity, dan Unit_Price tidak tersedia sehingga metrik pendapatan tidak dapat dihitung."
    d = d.rename(columns={m[k]: CAN[k] for k in m}).copy()
    if q is not None and p is not None:
        d["Quantity"], d["Unit_Price"] = q, p
    if "disc" in m:
        d["Discount_Rate"] = dsc
    if "total" in m:
        d["Line_Total"] = t
    if net is not None:
        d["Net_Sales"] = net
    d["Item"] = d["Product_Name"] if pn else d["Product_ID"]
    if "Category" in d:
        mc = d.dropna(subset=["Category"]).groupby("Item")["Category"].agg(lambda x: x.value_counts().index[0])
        n = d["Category"].isna().sum()
        d["Category"] = d["Category"].fillna(d["Item"].map(mc)).fillna(UNK)
        if n:
            L("Category kosong", "Diisi kategori paling sering untuk produk yang sama", n, "Diimputasi")
    if "Customer_ID" in d:
        L("Customer_ID kosong", "Pelanggan tidak dapat dilacak", d["Customer_ID"].isna().sum(), "Dipertahankan untuk penjualan/Apriori; dikeluarkan dari RFM dan K-Means")
        for c in ("Region", "Customer_Type"):
            if c in d:
                mc = d.dropna(subset=["Customer_ID", c]).groupby("Customer_ID")[c].agg(lambda x: x.value_counts().index[0])
                n = d[c].isna().sum()
                d[c] = d[c].fillna(d["Customer_ID"].map(mc))
                L(f"{c} kosong", "Diisi nilai paling sering pelanggan yang sama", n - d[c].isna().sum(), "Diimputasi")
    for c in ("Region", "Customer_Type", "Payment_Method", "Country", "Customer_Name"):
        if c in d:
            n = d[c].isna().sum()
            d[c] = d[c].fillna(UNK)
            if n:
                L(f"{c} masih kosong", "Tidak ada dasar imputasi", n, f"Diberi label '{UNK}'")
    d["Month"] = d["Transaction_Date"].dt.to_period("M").astype(str)
    d["Basket_Size"] = d.groupby("Transaction_ID")["Item"].transform("nunique")
    d["Catatan_Perbaikan"] = flag.reindex(d.index).fillna("")
    d = d.reset_index(drop=True)
    cust = lambda x: int(x["Customer_ID"].nunique()) if "Customer_ID" in x else None
    ps = dict(rows0=n0, rows1=len(d), tid0=int(raw[m["tid"]].astype("string").str.strip().nunique()), tid1=int(d["Transaction_ID"].nunique()),
              cust0=int(raw[m["cid"]].nunique()) if "cid" in m else None, cust1=cust(d), empty0=int(raw.isna().sum().sum()), empty1=int(d.isna().sum().sum()),
              info=info, fixed=int((d["Catatan_Perbaikan"] != "").sum()))
    return d, pd.DataFrame(log), ps


def make_rfm(c):
    need = {"Customer_ID", "Transaction_Date", "Net_Sales"}
    if not need <= set(c.columns):
        return None, "Kolom wajib RFM tidak tersedia: " + ", ".join(sorted(need - set(c.columns))) + ". Segmen tidak dibuat."
    x = c.dropna(subset=["Customer_ID"])
    if x["Customer_ID"].nunique() < 10:
        return None, "Jumlah pelanggan dengan ID kurang dari 10, segmentasi RFM tidak dapat dipertanggungjawabkan."
    ref = c["Transaction_Date"].max().normalize()
    g = x.groupby("Customer_ID")
    r = pd.DataFrame({"Recency": (ref - g["Transaction_Date"].max()).dt.days, "Frequency": g["Transaction_ID"].nunique(), "Monetary": g["Net_Sales"].sum()})
    for col, lab in (("Recency", [5, 4, 3, 2, 1]), ("Frequency", [1, 2, 3, 4, 5]), ("Monetary", [1, 2, 3, 4, 5])):
        r["Skor_" + col[0]] = pd.qcut(r[col].rank(method="first"), 5, labels=lab).astype(int)
    R, F = r["Skor_R"], r["Skor_F"]
    r["Segmen"] = np.select([(R >= 4) & (F >= 4), F >= 4, (R >= 4) & (F <= 2), (R <= 2) & (F >= 3), (R <= 2) & (F <= 2)],
                            ["Champions", "Pelanggan Setia", "Pelanggan Baru", "Berisiko Tidak Kembali", "Hampir Hilang"], "Potensial")
    r["Skor_RFM"] = r["Skor_R"].astype(str) + r["Skor_F"].astype(str) + r["Skor_M"].astype(str)
    r.attrs["ref"] = ref
    return r.reset_index(), None


def run_apriori(c, sup, conf, lift, ml):
    from mlxtend.frequent_patterns import apriori, association_rules
    basket = c.groupby(["Transaction_ID", "Item"]).size().unstack(fill_value=0).gt(0)
    freq = apriori(basket, min_support=sup, use_colnames=True, max_len=ml)
    res = dict(n_tx=len(basket), n_items=basket.shape[1], params=dict(sup=sup, conf=conf, lift=lift, ml=ml), freq=freq, rules=pd.DataFrame(), msg=None)
    if freq.empty:
        res["msg"] = "Tidak ada itemset yang memenuhi minimum support. Turunkan minimum support."
        return res
    freq["Itemset"] = freq["itemsets"].map(lambda s: ", ".join(sorted(s)))
    freq["Ukuran"] = freq["itemsets"].map(len)
    try:
        r = association_rules(freq[["support", "itemsets"]], num_itemsets=len(basket), metric="confidence", min_threshold=conf)
    except TypeError:
        r = association_rules(freq[["support", "itemsets"]], metric="confidence", min_threshold=conf)
    except ValueError:
        r = pd.DataFrame()
    if len(r):
        r = r[r["lift"] >= lift].copy()
    if r.empty:
        res["msg"] = "Itemset ditemukan, tetapi tidak ada aturan yang memenuhi minimum confidence dan minimum lift. Longgarkan ambang."
        return res
    r["Antecedent"] = r["antecedents"].map(lambda s: ", ".join(sorted(s)))
    r["Consequent"] = r["consequents"].map(lambda s: ", ".join(sorted(s)))
    r["Aturan"] = r["Antecedent"] + " -> " + r["Consequent"]
    r = r.sort_values(["lift", "confidence", "support"], ascending=False).reset_index(drop=True)
    res["rules"] = r
    return res


RFM_COLS = ["Recency", "Frequency", "Monetary"]
KMAX = 8
K_MIN_BISNIS = 3
MIN_SHARE = 5.0
CLUSTER_COL = list(tema.WARNA) + ["#C9A8D9", "#9B85C7"]
SEGMEN_WARNA = {
    "Loyal": tema.LAVENDER,
    "New": "#F0C9A8",
    "Churn Risk": tema.TEKS_GELAP,
    "Developing": tema.ABU_LEMBUT,
}


def rfm_matrix(rfm):
    raw = rfm[RFM_COLS].apply(pd.to_numeric, errors="coerce")
    raw = raw.replace([np.inf, -np.inf], np.nan)
    raw = raw.fillna(raw.median()).clip(lower=0)
    logged = np.log1p(raw)
    z = StandardScaler().fit_transform(logged)
    return raw, logged, z


def run_elbow(rfm, kmax=KMAX):
    raw, logged, z = rfm_matrix(rfm)
    n = len(z)
    distinct = len(np.unique(np.round(z, 8), axis=0))
    kmax = int(min(kmax, n // 10, distinct - 1))
    if n < 30 or kmax < K_MIN_BISNIS:
        return dict(ok=False, msg=(
            f"Jumlah pelanggan ({n}) atau variasi pola RFM ({distinct} pola unik) belum cukup "
            f"untuk menguji K sampai {K_MIN_BISNIS}. Elbow Method tidak dijalankan."
        ))
    rows = []
    for k in range(1, kmax + 1):
        model = KMeans(n_clusters=k, n_init=10, random_state=42).fit(z)
        sizes = np.bincount(model.labels_, minlength=k)
        sil = np.nan
        if k >= 2:
            sil = float(silhouette_score(z, model.labels_, sample_size=min(5000, n), random_state=42))
        rows.append(dict(K=k, Inertia=float(model.inertia_), Silhouette=sil,
                         Iterasi=int(model.n_iter_), Terkecil=float(sizes.min() / n * 100)))
    table = pd.DataFrame(rows)
    table["Penurunan"] = -table["Inertia"].diff()
    table["Penurunan_pct"] = table["Penurunan"] / table["Inertia"].shift(1) * 100
    ks = table["K"].to_numpy(float)
    inertia = table["Inertia"].to_numpy()
    x = (ks - ks.min()) / (ks.max() - ks.min())
    span = inertia.max() - inertia.min()
    y = (inertia - inertia.min()) / span if span > 0 else np.zeros_like(inertia)
    table["Jarak_siku"] = (1 - x) - y
    multi = table[table["K"] >= 2]
    elbow_k = int(multi.loc[multi["Jarak_siku"].idxmax(), "K"])
    sil_k_all = int(multi.loc[multi["Silhouette"].idxmax(), "K"])
    cand = table[table["K"] >= K_MIN_BISNIS]
    viable = cand[cand["Terkecil"] >= MIN_SHARE]
    pool = viable if not viable.empty else cand
    sil_span = pool["Silhouette"].max() - pool["Silhouette"].min()
    norm_sil = ((pool["Silhouette"] - pool["Silhouette"].min()) / sil_span if sil_span > 0 else pd.Series(0.0, index=pool.index))
    dmax = pool["Jarak_siku"].max()
    norm_elbow = (pool["Jarak_siku"].clip(lower=0) / dmax if dmax > 0 else pd.Series(0.0, index=pool.index))
    score = (0.5 * norm_sil + 0.5 * norm_elbow).rename("Skor")
    table["Skor"] = score.reindex(table.index)
    ranked = pool.assign(Skor=score).sort_values(["Skor", "K"], ascending=[False, True])
    rec_k = int(ranked.iloc[0]["K"])
    sil_k_pool = int(pool.loc[pool["Silhouette"].idxmax(), "K"])
    return dict(ok=True, table=table, kmax=kmax, n=n, rec_k=rec_k, elbow_k=elbow_k,
                sil_k_all=sil_k_all, sil_k_pool=sil_k_pool, viable_all=bool(not viable.empty))


def label_clusters(cent):
    thr = 0.3
    labels = {}
    value = {}
    for cl, z in cent.iterrows():
        r, f, m = float(z["Recency"]), float(z["Frequency"]), float(z["Monetary"])
        value[cl] = (f + m) / 2 - r
        if r >= thr:
            labels[cl] = ("Lama tidak aktif, riwayat belanja tinggi" if (f > thr or m > thr) else "Lama tidak aktif, belanja rendah")
        elif (f + m) / 2 >= thr:
            labels[cl] = ("Aktif, sering, dan bernilai tinggi" if r <= -thr else "Cukup aktif, sering, dan bernilai tinggi")
        elif r <= -thr and f < 0 and m < 0:
            labels[cl] = "Aktif terbaru, riwayat pembelian terbatas"
        elif (f + m) / 2 <= -thr:
            labels[cl] = "Aktivitas dan nilai belanja rendah"
        else:
            labels[cl] = "Aktivitas menengah"
    by_label = {}
    for cl, lab in labels.items():
        by_label.setdefault(lab, []).append(cl)
    for lab, members in by_label.items():
        if len(members) < 2:
            continue
        members = sorted(members, key=lambda cl: value[cl], reverse=True)
        for pos, cl in enumerate(members):
            tag = ("nilai tertinggi" if pos == 0 else "nilai terendah" if pos == len(members) - 1 else "nilai menengah")
            labels[cl] = f"{lab} ({tag})"
    return labels


def run_kmeans(rfm, k):
    n = len(rfm)
    if k < 2 or n < max(10, k * 3):
        return dict(ok=False, msg=f"Jumlah pelanggan ({n}) belum memadai untuk {k} klaster.")
    raw, logged, z = rfm_matrix(rfm)
    model = KMeans(n_clusters=k, n_init=10, random_state=42).fit(z)
    sil = float(silhouette_score(z, model.labels_, sample_size=min(5000, n), random_state=42))
    centers = pd.DataFrame(model.cluster_centers_, columns=RFM_COLS)
    order = (((centers["Frequency"] + centers["Monetary"]) / 2 - centers["Recency"]).sort_values(ascending=False).index.tolist())
    new_id = {old: pos + 1 for pos, old in enumerate(order)}
    lab = pd.Series(model.labels_).map(new_id).to_numpy()
    cent = centers.loc[order].copy()
    cent.index = range(1, k + 1)
    cent.index.name = "Klaster"
    names = label_clusters(cent)
    a = rfm.copy()
    a["Klaster"] = lab
    a["Label_Klaster"] = a["Klaster"].map(names)
    a["Z_Recency"], a["Z_Frequency"], a["Z_Monetary"] = z[:, 0], z[:, 1], z[:, 2]
    prof = a.groupby("Klaster").agg(
        Pelanggan=("Customer_ID", "count"),
        Recency_rata=("Recency", "mean"), Frequency_rata=("Frequency", "mean"),
        Monetary_rata=("Monetary", "mean"), Recency_median=("Recency", "median"),
        Frequency_median=("Frequency", "median"), Monetary_median=("Monetary", "median"),
        Monetary_total=("Monetary", "sum"),
    ).reset_index()
    prof.insert(1, "Label", prof["Klaster"].map(names))
    prof["Pelanggan_pct"] = prof["Pelanggan"] / prof["Pelanggan"].sum() * 100
    total = prof["Monetary_total"].sum()
    prof["Revenue_pct"] = prof["Monetary_total"] / total * 100 if total else np.nan
    skew = pd.DataFrame({
        "Fitur": RFM_COLS,
        "Skewness mentah": [float(raw[c].skew()) for c in RFM_COLS],
        "Skewness setelah log1p": [float(logged[c].skew()) for c in RFM_COLS],
        "Rata-rata mentah": [float(raw[c].mean()) for c in RFM_COLS],
        "Std mentah": [float(raw[c].std()) for c in RFM_COLS],
        "Rata-rata log1p": [float(logged[c].mean()) for c in RFM_COLS],
        "Std log1p": [float(logged[c].std()) for c in RFM_COLS],
    })
    return dict(ok=True, k=int(k), inertia=float(model.inertia_), n_iter=int(model.n_iter_),
                sil=sil, assign=a, prof=prof, cent=cent, names=names, skew=skew)


def make_reco(c, rules, km):
    cat = c.groupby("Item")["Category"].agg(lambda x: x.value_counts().index[0]).to_dict() if "Category" in c else {}
    fmt = lambda r: f"{r['Antecedent']} -> {r['Consequent']} (support {r['support']:.4f}, confidence {r['confidence']:.3f}, lift {r['lift']:.2f})"
    cons, ante = {}, {}
    for _, r in rules.head(10).iterrows():
        for i in r["consequents"]:
            cons.setdefault(i, fmt(r))
        for i in r["antecedents"]:
            ante.setdefault(i, fmt(r))
    kmc = {}
    if km and km.get("ok") and "Customer_ID" in c:
        a, prof = km["assign"], km["prof"]
        best = int(prof.sort_values("Monetary_total", ascending=False).iloc[0]["Klaster"])
        mem = set(a.loc[a["Klaster"] == best, "Customer_ID"])
        x = c.dropna(subset=["Customer_ID"])
        pc_ = x[x["Customer_ID"].isin(mem)].groupby("Item")["Customer_ID"].nunique() / max(len(mem), 1)
        pa = x.groupby("Item")["Customer_ID"].nunique() / x["Customer_ID"].nunique()
        idx = (pc_ / pa).dropna().sort_values(ascending=False)
        row = prof[prof["Klaster"] == best].iloc[0]
        for i, v in idx[idx > 1].head(8).items():
            kmc[i] = (f"Klaster {best} ({row['Label']}, {int(row['Pelanggan'])} pelanggan, rata-rata Recency {row['Recency_rata']:.1f} hari, Frequency {row['Frequency_rata']:.2f}, "
                      f"Monetary {rp(row['Monetary_rata'])}); klaster dengan total pembelian terbesar. {pc_[i] * 100:.1f}% anggota klaster membeli produk ini vs {pa[i] * 100:.1f}% seluruh pelanggan (indeks {v:.2f})")
    placed, tiers = set(), []
    t1 = list(cons)[:4]
    placed.update(t1)
    t2 = [i for i in kmc if i not in placed][:4]
    placed.update(t2)
    t3 = [i for i in ante if i not in placed][:4]
    rows = []
    for lab, items in (("Rak Atas", t1), ("Rak Tengah", t2), ("Rak Bawah", t3)):
        slots = []
        for i in items:
            ra = ("Consequent aturan: " + cons[i]) if i in cons else ("Antecedent (produk pemicu) aturan: " + ante[i]) if i in ante else ""
            bd = (["Apriori"] if ra else []) + (["K-Means"] if i in kmc else [])
            slots.append(dict(nama=i, kategori=cat.get(i), badge=bd))
            rows.append({"Rak": lab, "Produk": i, "Kategori": cat.get(i, ""), "Sumber": " + ".join(bd), "Alasan Apriori": ra, "Alasan K-Means": kmc.get(i, "")})
        slots += [None] * (4 - len(slots))
        tiers.append((lab, slots))
    return dict(tiers=tiers, table=pd.DataFrame(rows))


def run_pipeline(c, sup, conf, lift, ml):
    ap = run_apriori(c, sup, conf, lift, ml)
    ss["apriori"], ss["reco"] = ap, None
    if len(ap["rules"]):
        ss["reco"] = make_reco(c, ap["rules"], ss["kmeans"])
    ss["xlsx"] = None
    ss["ver"] += 1


def ensure_clean():
    if ss["raw"] is None or ss["clean"] is not None or ss["prep_err"]:
        return
    try:
        with st.spinner("Pra-pemrosesan otomatis berjalan satu kali..."):
            ss["audit"] = audit(ss["raw"], ss["map"])
            ss["clean"], ss["log"], ss["psum"] = prep(ss["raw"], ss["map"])
            ss["rfm"], ss["rfm_err"] = make_rfm(ss["clean"])
    except Exception as e:
        ss["prep_err"] = f"Pra-pemrosesan gagal: {e}"


def ensure_models():
    if ss["clean"] is None or ss["rfm"] is None or ss["km_err"]:
        return
    try:
        if ss["elbow"] is None:
            with st.spinner("Menghitung Elbow Method dan K-Means..."):
                ss["elbow"] = run_elbow(ss["rfm"])
        if ss["kmeans"] is None and ss["elbow"].get("ok"):
            k = ss.get("km_k") or ss["elbow"]["rec_k"]
            ss["kmeans"] = run_kmeans(ss["rfm"], k)
    except Exception as e:
        ss["km_err"] = f"Elbow/K-Means gagal dijalankan: {e}"


def kpi_df(c):
    rev = c["Net_Sales"].sum() if "Net_Sales" in c else None
    return pd.DataFrame([
        ("Baris item (bersih)", len(c)),
        ("Transaksi unik", c["Transaction_ID"].nunique()),
        ("Pelanggan unik", c["Customer_ID"].nunique() if "Customer_ID" in c else "tidak tersedia"),
        ("Produk unik", c["Item"].nunique()),
        ("Total pendapatan bersih", rp(rev) if rev is not None else "tidak tersedia"),
        ("Rata-rata basket size", round(c.groupby("Transaction_ID")["Item"].nunique().mean(), 3)),
    ], columns=["KPI", "Nilai"])


def export_tables():
    c, ap = ss["clean"], ss["apriori"]
    t = {"Data_Bersih": c, "Kualitas_Kolom": ss["audit"]["miss"], "Kualitas_Pemeriksaan": ss["audit"]["checks"],
         "Log_Pembersihan": ss["log"], "KPI": kpi_df(c)}
    if ss["rfm"] is not None:
        t["RFM"] = ss["rfm"]
    if ap and ap.get("ok", True) and len(ap["freq"]):
        t["Frequent_Itemsets"] = ap["freq"][["Itemset", "Ukuran", "support"]]
    if ap and len(ap["rules"]):
        t["Aturan_Apriori"] = ap["rules"][["Aturan", "Antecedent", "Consequent", "support", "confidence", "lift"]]
    if ss["kmeans"] and ss["kmeans"].get("ok"):
        t["Hasil_Klaster"] = ss["kmeans"]["assign"]
        t["Profil_Klaster"] = ss["kmeans"]["prof"]
        t["Centroid_Z"] = ss["kmeans"]["cent"].reset_index()
        if ss["elbow"] and ss["elbow"].get("ok"):
            t["Elbow_Method"] = ss["elbow"]["table"]
    if ss["reco"] is not None:
        t["Rekomendasi"] = ss["reco"]["table"]
    return t


def xlsx_bytes(tables):
    if ss["xlsx"] is None or ss["xlsx"][0] != ss["ver"]:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            for n, d in tables.items():
                d.to_excel(w, sheet_name=n[:31], index=False)
        ss["xlsx"] = (ss["ver"], buf.getvalue())
    return ss["xlsx"][1]


def ctx():
    c = ss["clean"]
    if c is None:
        return [("Workbook belum dimuat", "y")]
    out = [(f"Sheet: {ss['sheet']}", "g"), (f"{len(c):,} baris bersih", ""), (f"{c['Transaction_ID'].nunique():,} transaksi", "")]
    if ss["kmeans"] and ss["kmeans"].get("ok"):
        out.append((f"K-Means: K = {ss['kmeans']['k']}", ""))
    out.append(("Apriori: sudah dijalankan" if ss["apriori"] else "Apriori: belum dijalankan", "y" if not ss["apriori"] else ""))
    return out


def need(title, sub, header=True):
    if header:
        tema.header(title, sub, ctx())
    if ss["raw"] is None:
        tema.note("Unggah workbook Excel pada panel <b>Unggah berkas</b> di atas untuk memulai.")
        return None
    if ss["prep_err"]:
        st.error(ss["prep_err"])
        return None
    return ss["clean"]


def upload_panel():
    with st.expander("Unggah berkas", expanded=ss["raw"] is None):
        f = st.file_uploader("Unggah berkas", type=["xlsx", "xlsm"], key="uploader", label_visibility="collapsed")
        if f is None and ss.get("sig") is not None:
            ss["sig"] = None
            reset_data()
        if f is not None:
            sig = (f.name, f.size, getattr(f, "file_id", None))
            if sig != ss.get("sig"):
                reset_data()
                ss["sig"] = sig
                try:
                    ss["sheet"], ss["raw"], ss["map"] = read_workbook(f)
                except Exception as e:
                    ss["load_err"] = f"Workbook tidak dapat dibaca atau tidak valid: {e}"
        if ss["load_err"]:
            st.error(ss["load_err"])
        elif ss["raw"] is not None:
            r, m = ss["raw"], ss["map"]
            tid = r[m["tid"]].astype("string").str.strip().nunique()
            tema.kpis([("Baris", f"{len(r):,}"), ("Kolom", f"{r.shape[1]}"), ("Transaction_ID unik", f"{tid:,}"),
                       ("Sel kosong", f"{int(r.isna().sum().sum()):,}"), ("Baris duplikat penuh", f"{int(r.duplicated().sum()):,}")])
            st.caption(f"Sheet data utama terdeteksi otomatis: {ss['sheet']}. Analisis berat belum dijalankan.")
            tema.tabel(pd.DataFrame([(k, v, CAN[k]) for k, v in m.items()], columns=["Peran", "Kolom di workbook", "Nama standar"]))
        else:
            st.info("Belum ada berkas. Pilih workbook Excel (.xlsx) yang memuat sheet data transaksi.")


# ===== Sections (one-page scroll) =====

def section_banner(anchor, number, title, sub):
    st.markdown(
        f"<div class='sec-banner' id='{anchor}'><span class='sec-no'>{number}</span>"
        f"<div><b>{tema.esc(title)}</b><small>{tema.esc(sub)}</small></div></div>",
        unsafe_allow_html=True,
    )


SECTION_LIST = [
    ("sec-kualitas", "1", "Kualitas Data", "Laporan kualitas sumber sebelum pembersihan"),
    ("sec-eda", "2", "EDA", "Eksplorasi data bersih: statistik, distribusi, tren"),
    ("sec-rfm", "3", "RFM", "Recency, Frequency, Monetary dan transformasinya"),
    ("sec-segmentasi", "4", "Segmentasi Pelanggan", "Elbow Method, K-Means, dan Loyal/New/Churn Risk"),
    ("sec-apriori", "5", "Apriori (Market Basket Analysis)", "Pola produk yang dibeli bersama"),
    ("sec-reko", "6", "Rekomendasi & Ekspor", "Penempatan rak dan unduhan hasil"),
    ("sec-dashboard", "7", "Dashboard BI", "Ringkasan kinerja penjualan dan hasil analisis"),
]


def nav_anchors():
    links = "".join(
        f"<a href='#{anchor}'><b>{num}</b> {tema.esc(title)}</a>"
        for anchor, num, title, _ in SECTION_LIST
    )
    st.markdown(f"<nav class='sec-nav'>{links}</nav>", unsafe_allow_html=True)


# ===== Kualitas Data =====

def tab_kualitas():
    c = need("Kualitas Data", "Laporan kualitas seluruh sheet sumber sebelum pembersihan")
    if c is None:
        return
    a, ps = ss["audit"], ss["psum"]
    tema.kpis([("Baris x Kolom", f"{a['dims'][0]:,} x {a['dims'][1]}"), ("Sel kosong", f"{a['empty']:,}"),
               ("Duplikat penuh", f"{a['dup']:,}"), ("Kolom numerik", len(a["num"])),
               ("Kolom kategorikal", len(a["cat"])), ("Kolom tanggal", len(a["dte"]))])
    st.subheader("Nilai kosong per kolom dan tipe data")
    tema.tabel(a["miss"])
    mm = a["miss"][a["miss"]["Kosong"] > 0]
    if len(mm):
        tema.plot(px.bar(mm, x="Kolom", y="Persen kosong (%)", title="Persentase nilai kosong per kolom"), 320)
    st.subheader("Pemeriksaan masalah data")
    tema.tabel(a["checks"])
    ck = a["checks"][a["checks"]["Jumlah"] > 0]
    if len(ck):
        tema.plot(px.bar(ck, x="Jumlah", y="Pemeriksaan", orientation="h", title="Jumlah baris/kelompok bermasalah"), 420)
    st.subheader("Aturan pembersihan dan hasilnya")
    tema.kpis([("Baris sebelum", f"{ps['rows0']:,}"), ("Baris sesudah", f"{ps['rows1']:,}"),
               ("Baris dikeluarkan", f"{ps['rows0'] - ps['rows1']:,}"),
               ("Transaksi unik sebelum/sesudah", f"{ps['tid0']:,} / {ps['tid1']:,}"),
               ("Sel kosong sebelum/sesudah", f"{ps['empty0']:,} / {ps['empty1']:,}"),
               ("Baris diperbaiki nilainya", f"{ps['fixed']:,}")])
    tema.tabel(ss["log"])
    tema.note("Data asli tidak diubah; seluruh proses memakai salinan. Setiap baris yang dihapus tercatat pada tabel di atas. " + ps["info"])


# ===== EDA =====

def tab_eda():
    c = need("EDA", "Eksplorasi data bersih: statistik, distribusi, dan tren")
    if c is None:
        return
    tema.kpis([("Baris item", f"{len(c):,}"), ("Transaksi unik", f"{c['Transaction_ID'].nunique():,}"),
               ("Pelanggan unik", f"{c['Customer_ID'].nunique():,}" if "Customer_ID" in c else "n/a"),
               ("Produk unik", f"{c['Item'].nunique():,}"),
               ("Sel kosong tersisa", f"{int(c.drop(columns=['Catatan_Perbaikan']).isna().sum().sum()):,}"),
               ("Rentang tanggal", f"{c['Transaction_Date'].min():%d %b %Y} - {c['Transaction_Date'].max():%d %b %Y}")])
    ncols = [x for x in ["Quantity", "Unit_Price", "Discount_Rate", "Net_Sales", "Basket_Size"] if x in c]
    if ncols:
        st.subheader("Statistik numerik")
        tema.tabel(c[ncols].describe().T.reset_index().rename(columns={"index": "Variabel"}))
    col1, col2 = st.columns(2)
    with col1:
        if "Category" in c:
            g = c.groupby("Category").agg(Baris=("Item", "size"), Pendapatan=("Net_Sales", "sum") if "Net_Sales" in c else ("Item", "size")).reset_index()
            tema.plot(px.bar(g.sort_values("Baris"), x="Baris", y="Category", orientation="h", title="Distribusi baris per kategori"), 340)
        if "Quantity" in c:
            tema.plot(px.bar(c["Quantity"].value_counts().sort_index().reset_index(), x="Quantity", y="count", title="Distribusi kuantitas"), 320)
    with col2:
        if "Unit_Price" in c:
            tema.plot(px.histogram(c, x="Unit_Price", nbins=40, title="Distribusi harga satuan"), 340)
        if "Net_Sales" in c:
            tema.plot(px.histogram(c, x="Net_Sales", nbins=40, title="Distribusi pendapatan bersih per baris"), 320)
    if "Net_Sales" in c:
        mo = c.groupby("Month").agg(Pendapatan=("Net_Sales", "sum"), Transaksi=("Transaction_ID", "nunique")).reset_index()
        fig = px.line(mo, x="Month", y="Pendapatan", markers=True, title="Tren pendapatan bulanan",
                      labels={"Pendapatan": "Pendapatan (Rp)"})
        fig.update_traces(hovertemplate="%{x}<br>%{y:,.0f}<extra></extra>")
        tema.plot(fig, 330)
        ins = [f"Bulan dengan pendapatan tertinggi: <b>{mo.loc[mo['Pendapatan'].idxmax(), 'Month']}</b> ({rp(mo['Pendapatan'].max())})."]
        if "Category" in c:
            cr = c.groupby("Category")["Net_Sales"].sum().sort_values(ascending=False)
            ins.append(f"Kategori dengan pendapatan terbesar: <b>{cr.index[0]}</b> ({cr.iloc[0] / cr.sum() * 100:.1f}% dari total).")
        bs = c.drop_duplicates("Transaction_ID")["Basket_Size"]
        ins.append(f"<b>{(bs >= 2).mean() * 100:.1f}%</b> transaksi memuat minimal 2 produk unik (rata-rata {bs.mean():.2f}), sehingga analisis keranjang layak dilakukan.")
        tema.card("<b>Insight awal dari data bersih</b><br>" + "<br>".join("- " + i for i in ins))
    if "Payment_Method" in c:
        tema.plot(px.pie(c.drop_duplicates("Transaction_ID"), names="Payment_Method", title="Metode pembayaran (transaksi unik)", hole=.4), 330)


# ===== RFM =====

SEG_TXT = {
    "Champions": "Terbaru, sering, dan bernilai tinggi: pertahankan dengan program eksklusif.",
    "Pelanggan Setia": "Sering membeli tetapi tidak sebaru Champions: dorong pembelian ulang.",
    "Pelanggan Baru": "Baru bertransaksi dan belum sering: dorong pembelian kedua.",
    "Berisiko Tidak Kembali": "Dulu cukup sering, kini lama tidak membeli: kampanye reaktivasi.",
    "Hampir Hilang": "Lama tidak membeli dan jarang: reaktivasi biaya rendah atau diprioritaskan rendah.",
    "Potensial": "Aktivitas menengah: tawarkan bundling untuk menaikkan frekuensi.",
}


def _fmt_id(value, dec=2):
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "-"
    s = f"{value:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def tab_rfm():
    c = need("RFM", "Recency, Frequency, Monetary per pelanggan dan transformasinya")
    if c is None:
        return
    rfm = ss["rfm"]
    if rfm is None:
        st.warning(ss["rfm_err"])
        return
    raw, logged, _ = rfm_matrix(rfm)
    ref = pd.to_datetime(c["Transaction_Date"]).max().normalize()
    tema.kpis([("Pelanggan dianalisis", f"{len(rfm):,}"), ("Tanggal acuan Recency", f"{ref:%d %b %Y}"),
               ("Baris tanpa Customer_ID", f"{int(c['Customer_ID'].isna().sum()):,}"),
               ("Transaksi unik", f"{c['Transaction_ID'].nunique():,}")])
    tema.card(
        "<b>Definisi fitur RFM</b><br>"
        "- <b>Recency</b>: jumlah hari antara transaksi terakhir pelanggan dan tanggal acuan "
        "(transaksi terakhir pada seluruh data). Makin kecil berarti makin baru.<br>"
        "- <b>Frequency</b>: jumlah <i>Transaction_ID</i> unik per pelanggan (bukan jumlah baris produk).<br>"
        "- <b>Monetary</b>: total <i>Net_Sales</i> pelanggan setelah diskon.<br>"
        "Pelanggan tanpa Customer_ID tidak dapat dilacak sehingga dikeluarkan dari RFM, "
        "tetapi tetap dihitung pada penjualan di Dashboard BI."
    )
    st.subheader("Statistik RFM dan transformasi")
    rows = []
    for col in RFM_COLS:
        rows.append({
            "Fitur": col,
            "Rata-rata": _fmt_id(raw[col].mean()),
            "Median": _fmt_id(raw[col].median()),
            "Std": _fmt_id(raw[col].std()),
            "Min": _fmt_id(raw[col].min()),
            "Maks": _fmt_id(raw[col].max()),
            "Skewness mentah": _fmt_id(raw[col].skew()),
            "Skewness log1p": _fmt_id(logged[col].skew()),
        })
    tema.tabel(pd.DataFrame(rows))
    worst = max(RFM_COLS, key=lambda col: abs(raw[col].skew()))
    tema.note(
        "<b>Mengapa ditransformasi?</b> Recency (hari), Frequency (jumlah transaksi), dan Monetary (rupiah) "
        "memiliki satuan dan skala yang sangat berbeda, serta cenderung miring ke kanan. "
        "K-Means memakai jarak Euclidean, sehingga fitur berskala besar akan mendominasi jarak. "
        "Langkah yang dipakai: <b>(1)</b> <code>log1p(x) = ln(1 + x)</code> untuk meredam kemiringan dan pencilan "
        "(aman untuk nilai 0), lalu <b>(2)</b> <b>StandardScaler</b> <code>z = (x − rata-rata) / std</code> agar ketiga fitur "
        f"bermean 0 dan std 1. Pada data ini, kemiringan terbesar ada pada <b>{tema.esc(worst)}</b>: "
        f"{_fmt_id(raw[worst].skew())} (mentah) menjadi {_fmt_id(logged[worst].skew())} (setelah log1p)."
    )
    st.subheader("Distribusi sebelum dan sesudah log1p")
    cols = st.columns(3)
    for column, name in zip(cols, RFM_COLS):
        with column:
            tema.plot(px.histogram(raw, x=name, nbins=40, title=f"{name} (mentah)"), 290)
    cols = st.columns(3)
    for column, name in zip(cols, RFM_COLS):
        with column:
            tema.plot(px.histogram(logged, x=name, nbins=40, title=f"{name} (log1p)", labels={name: f"log1p({name})"}), 290)
    corr = logged.corr()
    fig = px.imshow(
        corr, text_auto=".2f", zmin=-1, zmax=1, aspect="auto",
        color_continuous_scale=[[0, tema.TEKS_GELAP], [.5, tema.PUTIH], [1, tema.LAVENDER]],
        title="Korelasi antar fitur (log1p)",
    )
    tema.plot(fig, 340)
    pairs = [(a, b, corr.loc[a, b]) for i, a in enumerate(RFM_COLS) for b in RFM_COLS[i + 1:]]
    top = max(pairs, key=lambda item: abs(item[2]))
    tema.card(
        f"<b>Catatan korelasi:</b> pasangan fitur dengan korelasi terkuat adalah {tema.esc(top[0])} dan "
        f"{tema.esc(top[1])} (r = {_fmt_id(top[2])}). Korelasi tinggi berarti dua fitur membawa informasi yang "
        "mirip, sehingga pengaruhnya pada jarak K-Means bertambah."
    )


# ===== Elbow & K-Means =====

def _elbow_text(el):
    t = el["table"].set_index("K")
    k = el["rec_k"]
    stat, biz = [], []
    stat.append(
        f"Silhouette pada K = {k} adalah <b>{_fmt_id(t.loc[k, 'Silhouette'], 3)}</b>; "
        f"Silhouette tertinggi pada K ≥ {K_MIN_BISNIS} ada di K = {el['sil_k_pool']}, "
        f"dan pada seluruh K ≥ 2 ada di K = {el['sil_k_all']}."
    )
    stat.append(
        f"Titik siku (jarak terjauh kurva Inertia dari garis lurus K = 1 ke K = {el['kmax']}) berada pada "
        f"K = {el['elbow_k']}."
    )
    stat.append(
        f"Inertia turun <b>{_fmt_id(t.loc[k, 'Penurunan_pct'], 1)}%</b> saat K naik dari {k - 1} ke {k}"
        + (f", sedangkan dari {k} ke {k + 1} hanya turun {_fmt_id(t.loc[k + 1, 'Penurunan_pct'], 1)}%."
           if (k + 1) in t.index else ".")
    )
    stat.append(
        "Skor gabungan = 50% Silhouette (dinormalisasi) + 50% jarak siku (dinormalisasi) di antara kandidat "
        f"K ≥ {K_MIN_BISNIS} yang klaster terkecilnya ≥ {MIN_SHARE:g}% pelanggan; K dengan skor tertinggi dipilih "
        "(jika seri, K yang lebih kecil)."
    )
    small = t.loc[k, "Terkecil"]
    avg = el["n"] / k
    biz.append(
        f"Strategi bisnis yang diminta memisahkan pelanggan Loyal, New, dan Churn Risk, sehingga K minimum "
        f"{K_MIN_BISNIS} dipakai sebagai batas bisnis. Dengan K = {k}, rata-rata klaster berisi "
        f"{_fmt_id(avg, 0)} pelanggan dan klaster terkecil {_fmt_id(small, 1)}% dari pelanggan."
    )
    if small < MIN_SHARE:
        biz.append(
            "Klaster terkecil berada di bawah ambang 5%, sehingga perlu kehati-hatian: kelompok sekecil itu "
            "bisa jadi pencilan, bukan segmen yang layak dibuatkan kampanye sendiri."
        )
    if el["sil_k_all"] == 2 and k != 2:
        biz.append(
            f"Silhouette tertinggi sebenarnya pada K = 2 ({_fmt_id(t.loc[2, 'Silhouette'], 3)}), artinya data cenderung "
            "terbelah menjadi dua kutub besar. K = 2 tetap tidak dipilih karena hanya menghasilkan dua tindakan "
            f"dan tidak dapat membedakan tiga strategi; K = {k} mengorbankan "
            f"{_fmt_id(t.loc[2, 'Silhouette'] - t.loc[k, 'Silhouette'], 3)} poin Silhouette untuk pemisahan yang lebih terarah."
        )
    if k >= 6:
        biz.append(
            "K yang besar menambah beban operasional karena tiap klaster butuh strategi sendiri; "
            "klaster yang berdekatan dapat digabung saat eksekusi kampanye."
        )
    return stat, biz


def tab_elbow(embedded=False):
    c = need("Elbow Method", "Menentukan jumlah cluster dari Inertia (WCSS) dan Silhouette Score", header=not embedded)
    if c is None:
        return
    if ss["rfm"] is None:
        st.warning(ss["rfm_err"])
        return
    if ss.get("km_err"):
        st.error(ss["km_err"])
        return
    el = ss["elbow"]
    if not el or not el["ok"]:
        st.warning(el["msg"] if el else "Elbow Method belum tersedia.")
        return
    t = el["table"]
    k = el["rec_k"]
    km = ss.get("kmeans")
    tema.kpis([
        ("K rekomendasi", f"{k}"),
        ("K titik siku (Inertia)", f"{el['elbow_k']}"),
        ("K Silhouette tertinggi (K ≥ 2)", f"{el['sil_k_all']}"),
        ("Silhouette pada K rekomendasi", f"{t.loc[t['K'] == k, 'Silhouette'].iloc[0]:.3f}"),
        ("Rentang K diuji", f"1 – {el['kmax']}"),
        ("K dipakai di K-Means", f"{km['k']}" if km and km.get("ok") else "-"),
    ])
    tema.note(
        "<b>Data uji:</b> RFM seluruh pelanggan yang sudah ditransformasi (log1p lalu StandardScaler). "
        "Inertia (WCSS) = jumlah kuadrat jarak titik ke centroid klasternya; makin kecil makin padat, tetapi "
        "selalu turun saat K bertambah, sehingga dicari titik siku. Silhouette (−1 sampai 1) mengukur seberapa "
        "terpisah klaster satu sama lain."
    )
    left, right = st.columns(2)
    with left:
        fig = px.line(t, x="K", y="Inertia", markers=True, title="Elbow Method · Inertia (WCSS)")
        fig.add_vline(x=k, line_dash="dash", line_color=tema.LAVENDER, annotation_text=f"K rekomendasi = {k}", annotation_position="top right")
        fig.update_xaxes(dtick=1)
        fig.update_yaxes(title="Inertia")
        tema.plot(fig, 380)
    with right:
        sil = t[t["K"] >= 2]
        fig = px.line(sil, x="K", y="Silhouette", markers=True, title="Silhouette Score per K")
        fig.add_vline(x=k, line_dash="dash", line_color=tema.LAVENDER, annotation_text=f"K rekomendasi = {k}", annotation_position="top right")
        fig.update_xaxes(dtick=1)
        tema.plot(fig, 380)
    st.subheader("Tabel perbandingan K")
    view = pd.DataFrame({
        "K": t["K"],
        "Inertia": t["Inertia"].map(lambda v: _fmt_id(v, 1)),
        "Penurunan Inertia": t["Penurunan"].map(lambda v: "-" if pd.isna(v) else _fmt_id(v, 1)),
        "Penurunan (%)": t["Penurunan_pct"].map(lambda v: "-" if pd.isna(v) else f"{_fmt_id(v, 1)}%"),
        "Silhouette": t["Silhouette"].map(lambda v: "-" if pd.isna(v) else _fmt_id(v, 3)),
        "Iterasi": t["Iterasi"],
        "Klaster terkecil": t["Terkecil"].map(lambda v: f"{_fmt_id(v, 1)}%"),
        "Catatan": [" · ".join(filter(None, [
            "REKOMENDASI" if kk == k else "",
            "titik siku" if kk == el["elbow_k"] else "",
            "Silhouette tertinggi" if kk == el["sil_k_all"] else "",
        ])) for kk in t["K"]],
    })
    tema.tabel(view, len(view))
    stat, biz = _elbow_text(el)
    tema.card(
        f"<b>Rekomendasi: K = {k}</b><br><br><b>Alasan statistik</b><br>"
        + "<br>".join("- " + s for s in stat)
        + "<br><br><b>Alasan bisnis</b><br>" + "<br>".join("- " + s for s in biz)
    )
    tema.note(
        "Rekomendasi dihitung dari data aktual dan dapat berubah untuk workbook lain; angkanya tidak ditetapkan "
        "di depan. Pengguna dapat menimpa K pada bagian <b>K-Means</b> di bawah."
    )


def apply_k(c, k):
    updated = run_kmeans(ss["rfm"], k)
    if not updated["ok"]:
        st.error(updated["msg"])
        return False
    ss["km_k"], ss["kmeans"], ss["xlsx"] = int(k), updated, None
    ap = ss.get("apriori")
    if ap is not None and len(ap["rules"]):
        ss["reco"] = make_reco(c, ap["rules"], updated)
    return True


def tab_kmeans(embedded=False):
    c = need("K-Means", "Segmentasi pelanggan berdasarkan RFM tertransformasi", header=not embedded)
    if c is None:
        return
    if ss["rfm"] is None:
        st.warning(ss["rfm_err"])
        return
    if ss.get("km_err"):
        st.error(ss["km_err"])
        return
    el, km = ss["elbow"], ss["kmeans"]
    if not km or not km.get("ok"):
        st.warning(km["msg"] if km else (el["msg"] if el and not el.get("ok") else "K-Means belum tersedia."))
        return
    rec = el["rec_k"] if el and el.get("ok") else None
    kmax = el["kmax"] if el and el.get("ok") else KMAX
    options = list(range(2, kmax + 1))
    key = f"km_k_choice_{ss['ver']}"
    if key not in ss or ss[key] not in options:
        ss[key] = km["k"] if km["k"] in options else options[0]
    chosen = st.selectbox(
        "Jumlah klaster (K)", options, key=key,
        format_func=lambda v: f"K = {v}" + (" · rekomendasi Elbow" if v == rec else ""),
        help="Default mengikuti rekomendasi bagian Elbow Method. Model dilatih ulang otomatis bila K diubah.",
    )
    if chosen != km["k"]:
        with st.spinner(f"Menghitung ulang K-Means untuk K = {chosen}..."):
            if apply_k(c, chosen):
                km = ss["kmeans"]
    tema.kpis([
        ("Jumlah cluster", f"{km['k']}"),
        ("Inertia", _fmt_id(km["inertia"], 1)),
        ("Iterasi", f"{km['n_iter']}"),
        ("Silhouette Score", f"{km['sil']:.3f}"),
        ("Pelanggan", f"{len(km['assign']):,}"),
    ])
    if rec is not None and km["k"] != rec:
        tema.note(f"K = {km['k']} dipilih manual. Rekomendasi Elbow Method untuk data ini adalah K = {rec}.")
    tema.note(
        "<b>Transformasi dan standardisasi:</b> Recency, Frequency, dan Monetary diubah dengan "
        "<code>log1p(x)</code> agar distribusi miring dan pencilan terredam, lalu distandardisasi "
        "<code>z = (x − rata-rata) / std</code> sehingga satuan hari, jumlah transaksi, dan rupiah setara. "
        "K-Means (n_init = 10, random_state = 42) dijalankan pada nilai z. Nomor cluster hanya penanda urutan "
        "(1 = nilai pelanggan tertinggi); <b>nama cluster ditentukan dari posisi centroid</b>, bukan dari nomornya."
    )
    with st.expander("Detail transformasi per fitur", expanded=False):
        sk = km["skew"].copy()
        for col in sk.columns[1:]:
            sk[col] = sk[col].map(lambda v: _fmt_id(v, 2))
        tema.tabel(sk)
    a, prof, cent, names = km["assign"], km["prof"], km["cent"], km["names"]
    a = a.copy()
    a["Kelompok"] = a["Klaster"].map(lambda kk: f"K{kk} · {names[kk]}")
    order = [f"K{kk} · {names[kk]}" for kk in prof["Klaster"]]
    cmap = {name: CLUSTER_COL[i % len(CLUSTER_COL)] for i, name in enumerate(order)}
    st.subheader("Profil cluster")
    view = pd.DataFrame({
        "Klaster": prof["Klaster"],
        "Karakteristik": prof["Label"],
        "Pelanggan": prof["Pelanggan"],
        "Pelanggan (%)": prof["Pelanggan_pct"].map(lambda v: f"{_fmt_id(v, 1)}%"),
        "Recency rata-rata (hari)": prof["Recency_rata"].map(lambda v: _fmt_id(v, 1)),
        "Recency median": prof["Recency_median"].map(lambda v: _fmt_id(v, 0)),
        "Frequency rata-rata": prof["Frequency_rata"].map(lambda v: _fmt_id(v, 2)),
        "Frequency median": prof["Frequency_median"].map(lambda v: _fmt_id(v, 0)),
        "Monetary rata-rata": prof["Monetary_rata"].map(rp),
        "Monetary median": prof["Monetary_median"].map(rp),
        "Total Monetary": prof["Monetary_total"].map(rp),
        "Kontribusi revenue (%)": prof["Revenue_pct"].map(lambda v: f"{_fmt_id(v, 1)}%"),
    })
    tema.tabel(view, len(view))
    st.subheader("Visualisasi cluster")
    fig = px.scatter_3d(
        a, x="Z_Recency", y="Z_Frequency", z="Z_Monetary", color="Kelompok",
        category_orders={"Kelompok": order}, color_discrete_map=cmap,
        hover_data={"Customer_ID": True, "Recency": ":,.0f", "Frequency": ":,.0f", "Monetary": ":,.0f",
                    "Z_Recency": False, "Z_Frequency": False, "Z_Monetary": False, "Kelompok": False},
        labels={"Z_Recency": "Recency (z)", "Z_Frequency": "Frequency (z)", "Z_Monetary": "Monetary (z)"},
        title=f"Cluster pelanggan 3D (ruang z log1p) · K = {km['k']}",
    )
    fig.update_traces(marker=dict(size=3.5, opacity=.78))
    fig.update_layout(legend=dict(orientation="h", x=0.5, xanchor="center", y=-0.05, yanchor="top"),
                      scene=dict(aspectmode="cube", camera=dict(eye=dict(x=1.6, y=1.6, z=1.1))))
    tema.plot(fig, 520, config={"displayModeBar": True, "displaylogo": False, "responsive": True,
                                "scrollZoom": True, "modeBarButtonsToAdd": ["resetCameraDefault"]})
    left, right = st.columns(2)
    with left:
        fig = px.scatter(
            a, x="Recency", y="Monetary", color="Kelompok", category_orders={"Kelompok": order},
            color_discrete_map=cmap, opacity=.7, hover_name="Customer_ID",
            hover_data={"Frequency": ":,.0f", "Kelompok": False},
            title="Recency vs Monetary",
            labels={"Recency": "Recency (hari sejak transaksi terakhir)", "Monetary": "Monetary (Rp, skala log)"},
        )
        fig.update_yaxes(type="log")
        centers = prof.assign(Kelompok=prof["Klaster"].map(lambda kk: f"K{kk} · {names[kk]}"))
        fig.add_trace(go.Scatter(
            x=centers["Recency_median"], y=centers["Monetary_median"], mode="markers+text",
            text=[f"K{kk}" for kk in centers["Klaster"]], textposition="top center",
            marker=dict(symbol="x", size=13, color=tema.TEKS_GELAP, line=dict(width=2, color=tema.LAVENDER)),
            name="Median cluster", hovertemplate="Median %{text}<br>Recency %{x:,.0f}<br>Rp %{y:,.0f}<extra></extra>",
        ))
        tema.plot(fig, 440)
    with right:
        sizes = prof.assign(Kelompok=prof["Klaster"].map(lambda kk: f"K{kk}"))
        fig = px.bar(sizes, x="Kelompok", y="Pelanggan", text="Pelanggan", color="Kelompok",
                     color_discrete_sequence=CLUSTER_COL, title="Ukuran cluster",
                     labels={"Kelompok": "Cluster"})
        fig.update_layout(showlegend=False)
        tema.plot(fig, 440)
    st.subheader("Centroid terstandardisasi")
    zmax = max(1.0, float(np.abs(cent.to_numpy()).max()))
    heat = cent.copy()
    heat.index = [f"K{kk} · {names[kk]}" for kk in heat.index]
    fig = px.imshow(
        heat.T, text_auto=".2f", aspect="auto", zmin=-zmax, zmax=zmax,
        color_continuous_scale=[[0, tema.TEKS_GELAP], [.5, tema.PUTIH], [1, tema.LAVENDER]],
        title="Centroid (z-score log1p): ungu tua = di atas rata-rata, gelap = di bawah rata-rata",
        labels={"color": "z"},
    )
    tema.plot(fig, 330)
    cent_view = cent.reset_index().rename(columns={"Recency": "Recency (z)", "Frequency": "Frequency (z)", "Monetary": "Monetary (z)"})
    cent_view.insert(1, "Karakteristik", cent_view["Klaster"].map(names))
    for col in ("Recency (z)", "Frequency (z)", "Monetary (z)"):
        cent_view[col] = cent_view[col].map(lambda v: _fmt_id(v, 2))
    tema.tabel(cent_view, len(cent_view))
    st.caption("Untuk Recency, z negatif berarti lebih baru dari rata-rata pelanggan (lebih baik); "
               "untuk Frequency dan Monetary, z positif berarti lebih tinggi dari rata-rata.")
    st.subheader("Karakteristik tiap cluster")
    lines = []
    for row, z in zip(prof.itertuples(), cent.itertuples()):
        rec_desc = ("lebih baru dari rata-rata pelanggan" if z.Recency < -0.3 else
                    "lebih lama dari rata-rata pelanggan" if z.Recency > 0.3 else "sekitar rata-rata pelanggan")
        f_desc = ("di atas rata-rata pelanggan" if z.Frequency > 0.3 else
                  "di bawah rata-rata pelanggan" if z.Frequency < -0.3 else "sekitar rata-rata pelanggan")
        m_desc = ("di atas rata-rata pelanggan" if z.Monetary > 0.3 else
                  "di bawah rata-rata pelanggan" if z.Monetary < -0.3 else "sekitar rata-rata pelanggan")
        lines.append(
            f"<b>K{row.Klaster} · {tema.esc(row.Label)}</b> — {row.Pelanggan:,} pelanggan "
            f"({_fmt_id(row.Pelanggan_pct, 1)}%), kontribusi revenue {_fmt_id(row.Revenue_pct, 1)}%.<br>"
            f"Recency rata-rata {_fmt_id(row.Recency_rata, 1)} hari ({rec_desc}, z = {_fmt_id(z.Recency, 2)}); "
            f"Frequency {_fmt_id(row.Frequency_rata, 2)} transaksi ({f_desc}, z = {_fmt_id(z.Frequency, 2)}); "
            f"Monetary rata-rata {rp(row.Monetary_rata)} ({m_desc}, z = {_fmt_id(z.Monetary, 2)})."
        )
    tema.card("<br><br>".join(lines))
    tema.note(
        f"Silhouette {km['sil']:.3f} menunjukkan "
        + ("pemisahan klaster yang kuat." if km["sil"] >= .5 else
           "struktur klaster yang cukup jelas." if km["sil"] >= .35 else
           "struktur klaster yang lemah hingga sedang; batas antar klaster cenderung tumpang tindih, "
           "sehingga hasil dipakai sebagai pendukung keputusan, bukan kebenaran mutlak.")
    )


# ===== Segmentasi Pelanggan =====

def _dashboard_customer_segments(frame):
    empty = pd.DataFrame()
    required = {"Transaction_ID", "Customer_ID", "Transaction_Date", "Net_Sales"}
    if not required.issubset(frame.columns):
        return empty, empty, "Segmentasi memerlukan Transaction_ID, Customer_ID, Transaction_Date, dan Net_Sales."
    transactions = frame.loc[
        _valid_dashboard_id(frame["Transaction_ID"]) & _valid_dashboard_id(frame["Customer_ID"]),
        ["Transaction_ID", "Customer_ID", "Transaction_Date", "Net_Sales"],
    ].copy()
    transactions["Transaction_Date"] = pd.to_datetime(transactions["Transaction_Date"], errors="coerce")
    transactions["Net_Sales"] = pd.to_numeric(transactions["Net_Sales"], errors="coerce")
    transactions = transactions.dropna(subset=["Transaction_Date", "Net_Sales"])
    if transactions.empty:
        return empty, empty, "Tidak ada transaksi valid untuk menghitung RFM."
    last_date = transactions["Transaction_Date"].max()
    first_date = transactions["Transaction_Date"].min()
    customers = (
        transactions.groupby("Customer_ID", as_index=False)
        .agg(First_Transaction=("Transaction_Date", "min"), Last_Transaction=("Transaction_Date", "max"),
             Frequency=("Transaction_ID", "nunique"), Monetary=("Net_Sales", "sum"))
    )
    customers["Recency"] = (last_date.normalize() - customers["Last_Transaction"].dt.normalize()).dt.days
    if len(customers) < 10:
        return empty, empty, (f"RFM terhitung untuk {len(customers)} pelanggan, tetapi minimal 10 pelanggan "
                              "diperlukan agar ambang kuartil relatif cukup bermakna.")
    recency_q25, recency_q50, recency_q75 = customers["Recency"].quantile([.25, .50, .75])
    frequency_q50, frequency_q75 = customers["Frequency"].quantile([.50, .75])
    monetary_q50 = customers["Monetary"].quantile(.50)
    observation_span = (last_date.normalize() - first_date.normalize()).days
    recent_first_purchase_cutoff = last_date.normalize() - pd.Timedelta(days=observation_span * .25)
    labels = pd.Series("Developing", index=customers.index, dtype="string")
    churn_mask = customers["Recency"].ge(recency_q75) & (recency_q75 > recency_q50)
    new_mask = (customers["Frequency"].le(frequency_q50)
                & customers["First_Transaction"].ge(recent_first_purchase_cutoff)
                & (observation_span > 0))
    loyal_mask = (customers["Recency"].le(recency_q50)
                  & customers["Frequency"].ge(frequency_q75)
                  & customers["Monetary"].ge(monetary_q50))
    labels.loc[new_mask] = "New"
    labels.loc[churn_mask & ~new_mask] = "Churn Risk"
    labels.loc[loyal_mask & ~new_mask & ~churn_mask] = "Loyal"
    customers["Segmen"] = labels
    segment_order = ["Loyal", "New", "Churn Risk", "Developing"]
    count_by_segment = customers["Segmen"].value_counts()
    rows = []
    actions = {
        "Loyal": "Uji reward/membership, retensi, dan upselling berdasarkan produk yang relevan.",
        "New": "Lakukan onboarding dan dorong pembelian kedua; label ini hanya berdasarkan transaksi pertama yang teramati.",
        "Churn Risk": "Uji reaktivasi atau win-back untuk pelanggan dengan jeda transaksi relatif panjang.",
        "Developing": "Pantau perubahan RFM dan sesuaikan komunikasi setelah pola pembelian lebih jelas.",
    }
    for segment in segment_order:
        members = customers[customers["Segmen"].eq(segment)]
        rows.append({
            "Segmen": segment, "Pelanggan": int(count_by_segment.get(segment, 0)),
            "Pelanggan (%)": len(members) / len(customers) * 100,
            "Transaksi": int(members["Frequency"].sum()),
            "Frequency": members["Frequency"].mean(), "Revenue": members["Monetary"].sum(),
            "Recency rata-rata (hari)": members["Recency"].mean(),
            "Frequency rata-rata": members["Frequency"].mean(),
            "Monetary rata-rata": members["Monetary"].mean(),
            "Rekomendasi": actions[segment],
        })
    summary = pd.DataFrame(rows)
    revenue_total = summary["Revenue"].sum()
    summary["Kontribusi revenue (%)"] = summary["Revenue"] / revenue_total * 100 if revenue_total else np.nan
    notes = (
        "Label diturunkan dari RFM aktual seluruh workbook: Loyal = aktif (Recency di bawah atau sama dengan median), "
        "Frequency pada kuartil tertinggi, dan Monetary di atas atau sama dengan median; "
        "New = transaksi pertama berada pada 25% periode pengamatan terbaru dan Frequency tidak melebihi median; "
        "Churn Risk = Recency pada kuartil tertinggi jika distribusi Recency memang bervariasi. "
        "Sisanya ditampilkan sebagai Developing, bukan dipaksakan ke tiga label."
    )
    if observation_span == 0:
        notes += " Periode data hanya satu tanggal, sehingga pelanggan New tidak dapat dibedakan secara temporal."
    return customers, summary, notes


def _valid_dashboard_id(values):
    return values.notna() & values.astype("string").str.strip().ne("").fillna(False)


def tab_segmentasi(embedded=False):
    c = need("Segmentasi Pelanggan", "Loyal, New, dan Churn Risk dari RFM aktual", header=not embedded)
    if c is None:
        return
    customers, summary, method_note = _dashboard_customer_segments(c)
    if customers.empty or summary.empty:
        st.warning(method_note)
        return
    customers = customers.copy()
    if "Customer_Name" in c:
        names = (c.dropna(subset=["Customer_ID", "Customer_Name"])
                 .groupby("Customer_ID")["Customer_Name"]
                 .agg(lambda values: values.mode().iat[0] if not values.mode().empty else ""))
        customers["Nama Pelanggan"] = customers["Customer_ID"].map(names)
    else:
        customers["Nama Pelanggan"] = "Tidak tersedia"
    customers["Transaksi pertama"] = customers["First_Transaction"].dt.strftime("%Y-%m-%d")
    customers["Transaksi terakhir"] = customers["Last_Transaction"].dt.strftime("%Y-%m-%d")
    customers["Monetary"] = pd.to_numeric(customers["Monetary"], errors="coerce")
    row_of = lambda seg: summary.loc[summary["Segmen"].eq(seg)].iloc[0]
    st.subheader("Ringkasan segmen")
    styles = {
        "Loyal": ("★", tema.LAVENDER, "Aktif, Frequency dan Monetary relatif tinggi."),
        "New": ("✦", "#F0C9A8", "Pembelian pertama baru-baru ini dengan riwayat terbatas."),
        "Churn Risk": ("↻", tema.TEKS_GELAP, "Relatif lama tidak bertransaksi."),
    }
    for column, segment in zip(st.columns(3), ("Loyal", "New", "Churn Risk")):
        r = row_of(segment)
        icon, color, desc = styles[segment]
        with column:
            tema.card(
                f"<div style='border-left:6px solid {color};padding:.5rem .7rem'>"
                f"<div style='font-size:1.6rem;color:{color}'>{icon}</div><b>{tema.esc(segment)}</b>"
                f"<div style='font-size:1.7rem;font-weight:800'>{int(r['Pelanggan']):,}</div>"
                f"<div>{_fmt_id(r['Pelanggan (%)'], 1)}% pelanggan · {_fmt_id(r['Kontribusi revenue (%)'], 1)}% revenue</div>"
                f"<div style='margin-top:.3rem'>{tema.esc(desc)}</div></div>"
            )
    tema.note(method_note)
    developing = row_of("Developing")
    if developing["Pelanggan"]:
        st.caption(
            f"{int(developing['Pelanggan']):,} pelanggan ({_fmt_id(developing['Pelanggan (%)'], 1)}%) tidak memenuhi "
            "kriteria Loyal, New, maupun Churn Risk dan ditampilkan sebagai Developing agar label tetap "
            "didukung data."
        )
    st.subheader("Profil RFM dan kontribusi revenue")
    table = pd.DataFrame({
        "Segmen": summary["Segmen"], "Pelanggan": summary["Pelanggan"],
        "Pelanggan (%)": summary["Pelanggan (%)"].map(lambda v: f"{_fmt_id(v, 1)}%"),
        "Recency rata-rata (hari)": summary["Recency rata-rata (hari)"].map(lambda v: _fmt_id(v, 1)),
        "Frequency rata-rata": summary["Frequency rata-rata"].map(lambda v: _fmt_id(v, 2)),
        "Monetary rata-rata": summary["Monetary rata-rata"].map(lambda v: rp(v) if pd.notna(v) else "-"),
        "Total revenue": summary["Revenue"].map(rp),
        "Kontribusi revenue (%)": summary["Kontribusi revenue (%)"].map(lambda v: f"{_fmt_id(v, 1)}%"),
    })
    tema.tabel(table, len(table))
    shown = summary[summary["Pelanggan"].gt(0)]
    left, right = st.columns(2)
    with left:
        long = pd.concat([
            pd.DataFrame({"Segmen": shown["Segmen"], "Persen": shown["Pelanggan (%)"], "Ukuran": "% pelanggan"}),
            pd.DataFrame({"Segmen": shown["Segmen"], "Persen": shown["Kontribusi revenue (%)"], "Ukuran": "% revenue"}),
        ])
        fig = px.bar(long, x="Segmen", y="Persen", color="Ukuran", barmode="group", text="Persen",
                     color_discrete_map={"% pelanggan": tema.LAVENDER, "% revenue": tema.DUSTY_PINK},
                     title="Komposisi pelanggan vs kontribusi revenue", labels={"Persen": "Persen (%)"})
        fig.update_traces(texttemplate="%{text:.1f}%")
        tema.plot(fig, 380)
    with right:
        overall = customers[RFM_COLS].mean()
        idx = shown.assign(**{
            "Recency": shown["Recency rata-rata (hari)"] / overall["Recency"] * 100,
            "Frequency": shown["Frequency rata-rata"] / overall["Frequency"] * 100,
            "Monetary": shown["Monetary rata-rata"] / overall["Monetary"] * 100,
        }).melt(id_vars="Segmen", value_vars=RFM_COLS, var_name="Fitur", value_name="Indeks")
        fig = px.bar(idx, x="Fitur", y="Indeks", color="Segmen", barmode="group",
                     color_discrete_map=SEGMEN_WARNA,
                     title="Indeks RFM per segmen (rata-rata semua pelanggan = 100)")
        fig.add_hline(y=100, line_dash="dash", line_color=tema.ABU_LEMBUT)
        tema.plot(fig, 380)
    fig = px.scatter(
        customers, x="Recency", y="Monetary", color="Segmen", color_discrete_map=SEGMEN_WARNA,
        opacity=.7, hover_name="Customer_ID", hover_data=["Frequency"],
        title="Recency vs Monetary per segmen",
        labels={"Recency": "Hari sejak transaksi terakhir", "Monetary": "Total belanja (Rp, skala log)"},
    )
    fig.update_yaxes(type="log")
    tema.plot(fig, 380)
    top_items = {}
    if "Item" in c:
        seg_map = customers.set_index("Customer_ID")["Segmen"]
        tmp = c.dropna(subset=["Customer_ID"]).copy()
        tmp["Segmen"] = tmp["Customer_ID"].map(seg_map)
        for seg, grp in tmp.dropna(subset=["Segmen"]).groupby("Segmen"):
            top_items[str(seg)] = (grp.groupby("Item")["Transaction_ID"].nunique()
                                   .sort_values(ascending=False).head(3).index.tolist())
    st.subheader("Rekomendasi strategi")
    strategy = {
        "Loyal": "Program reward dan membership bertingkat, retensi (akses awal, layanan prioritas), serta upselling "
                 "ke produk bernilai lebih tinggi atau bundling yang relevan dengan riwayat belanja.",
        "New": "Onboarding yang jelas (sapaan, panduan, rekomendasi produk awal) dan dorongan pembelian kedua "
               "dengan insentif berbatas waktu; ukur konversi dari pembelian pertama ke kedua.",
        "Churn Risk": "Kampanye reaktivasi dan win-back dengan penawaran personal berdasarkan produk yang pernah dibeli; "
                      "uji pada sebagian pelanggan terlebih dahulu dan bandingkan dengan kelompok pembanding.",
        "Developing": "Pantau perubahan RFM dan gunakan komunikasi ringan untuk membangun kebiasaan belanja.",
    }
    for seg in ("Loyal", "New", "Churn Risk", "Developing"):
        r = row_of(seg)
        if not r["Pelanggan"]:
            if seg != "Developing":
                tema.card(f"<b>{seg}</b> · tidak ada pelanggan yang memenuhi kriteria pada data ini, "
                          "sehingga tidak ada strategi yang dapat diarahkan ke segmen tersebut.")
            continue
        items = top_items.get(seg)
        item_text = (f"<br>Produk yang paling sering dibeli segmen ini: {tema.esc(', '.join(items))}." if items else "")
        tema.card(
            f"<b>{tema.esc(seg)} · {int(r['Pelanggan']):,} pelanggan ({_fmt_id(r['Pelanggan (%)'], 1)}%) · "
            f"{_fmt_id(r['Kontribusi revenue (%)'], 1)}% revenue</b><br>"
            f"Recency rata-rata {_fmt_id(r['Recency rata-rata (hari)'], 1)} hari; Frequency {_fmt_id(r['Frequency rata-rata'], 2)}; "
            f"Monetary rata-rata {rp(r['Monetary rata-rata'])}.{item_text}<br>"
            f"<b>Tindakan:</b> {tema.esc(strategy[seg])}"
        )
    km = ss.get("kmeans")
    if km and km.get("ok"):
        st.subheader("Keterkaitan dengan cluster K-Means")
        merged = customers[["Customer_ID", "Segmen"]].merge(
            km["assign"][["Customer_ID", "Klaster"]], on="Customer_ID", how="inner")
        if not merged.empty:
            cross = pd.crosstab(merged["Klaster"], merged["Segmen"])
            cross.index = [f"K{kk} · {km['names'][kk]}" for kk in cross.index]
            cross.index.name = "Cluster"
            cross.columns.name = None
            tema.tabel(cross.reset_index(), len(cross))
            st.caption("Tabel silang jumlah pelanggan: label segmen berasal dari aturan RFM relatif, sedangkan "
                       "cluster berasal dari K-Means. Keduanya dihitung terpisah sehingga dapat saling memvalidasi.")
    st.subheader("Tabel pelanggan per segmen")
    selected = st.selectbox("Filter segmen", ["Semua segmen", "Loyal", "New", "Churn Risk", "Developing"],
                            key=f"seg_filter_{ss['ver']}")
    query = st.text_input("Cari ID atau nama pelanggan", key=f"seg_search_{ss['ver']}",
                          placeholder="Ketik ID atau nama pelanggan").strip().casefold()
    view = customers.copy()
    if selected != "Semua segmen":
        view = view[view["Segmen"].eq(selected)]
    if query:
        match = (view["Customer_ID"].astype("string").str.casefold().str.contains(query, na=False)
                 | view["Nama Pelanggan"].astype("string").str.casefold().str.contains(query, na=False))
        view = view.loc[match]
    sort_col = st.selectbox(
        "Urutkan pelanggan berdasarkan",
        ["Monetary", "Frequency", "Recency", "First_Transaction", "Last_Transaction"],
        format_func=lambda v: {"Monetary": "Monetary tertinggi", "Frequency": "Frekuensi tertinggi",
                               "Recency": "Recency tertinggi", "First_Transaction": "Transaksi pertama terbaru",
                               "Last_Transaction": "Transaksi terakhir terbaru"}[v],
        key=f"seg_sort_{ss['ver']}")
    asc = st.checkbox("Urutan naik", value=False, key=f"seg_asc_{ss['ver']}")
    view = view.sort_values(sort_col, ascending=asc, kind="stable")
    cols = ["Customer_ID", "Nama Pelanggan", "Segmen", "Frequency", "Monetary",
            "Transaksi pertama", "Transaksi terakhir", "Recency"]
    shown_df = view[cols].rename(columns={"Customer_ID": "ID Pelanggan", "Frequency": "Jumlah transaksi",
                                          "Monetary": "Total belanja", "Recency": "Recency (hari)"})
    shown_df["Total belanja"] = shown_df["Total belanja"].map(rp)
    st.dataframe(shown_df, width="stretch", hide_index=True, height=min(520, 42 + len(shown_df) * 36))
    st.download_button("Unduh CSV pelanggan terfilter", view[cols].to_csv(index=False).encode("utf-8-sig"),
                       "detail_segmentasi_pelanggan.csv", "text/csv", key=f"seg_csv_{ss['ver']}")


# ===== Apriori =====

def tab_apriori():
    c = need("Apriori", "Analisis keranjang belanja: pola produk yang dibeli bersama")
    if c is None:
        return
    st.markdown("**Parameter analisis**")
    p1, p2, p3, p4 = st.columns(4)
    with p1:
        sup = wk(st.slider, "w_sup", ss["p_sup"], "Minimum support", 0.002, 0.10, step=0.002, format="%.3f")
    with p2:
        conf = wk(st.slider, "w_conf", ss["p_conf"], "Minimum confidence", 0.05, 0.80, step=0.05)
    with p3:
        lift = wk(st.slider, "w_lift", ss["p_lift"], "Minimum lift", 1.0, 3.0, step=0.1)
    with p4:
        ml = wk(st.radio, "w_len", ss["p_len"], "Maksimum itemset", [2, 3, 4], horizontal=True)
    ss["p_sup"], ss["p_conf"], ss["p_lift"], ss["p_len"] = sup, conf, lift, ml
    ntx = c["Transaction_ID"].nunique()
    st.caption(f"Keranjang = Transaction_ID ({ntx:,} transaksi); item = {('Product_Name' if 'Product_Name' in c else 'Product_ID')} unik per transaksi. Support minimum {sup:.3f} setara kira-kira {int(np.ceil(sup * ntx))} transaksi.")
    if st.button("Jalankan Analisis Apriori", key="btn_apriori"):
        try:
            with st.spinner("Menjalankan Apriori dan rekomendasi..."):
                run_pipeline(c, sup, conf, lift, ml)
        except ImportError:
            st.error("Pustaka mlxtend belum terpasang. Jalankan: python -m pip install mlxtend")
        except Exception as e:
            st.error(f"Apriori gagal dijalankan: {e}")
    ap = ss["apriori"]
    if ap is None:
        tema.note("Belum ada hasil. Atur parameter lalu tekan <b>Jalankan Analisis Apriori</b>. Rekomendasi di bagian berikut akan diperbarui otomatis setelahnya.")
        return
    pr = ap["params"]
    if (pr["sup"], pr["conf"], pr["lift"], pr["ml"]) != (sup, conf, lift, ml):
        tema.note("Parameter di atas berbeda dari parameter hasil terakhir. Hasil di bawah memakai support "
                  f"{pr['sup']:.3f}, confidence {pr['conf']:.2f}, lift {pr['lift']:.1f}, maks itemset {pr['ml']}.")
    tema.kpis([("Transaksi (keranjang)", f"{ap['n_tx']:,}"), ("Produk unik", f"{ap['n_items']}"),
               ("Frequent itemsets", f"{len(ap['freq']):,}"), ("Aturan lolos ambang", f"{len(ap['rules']):,}")])
    if ap["msg"]:
        st.warning(ap["msg"])
    if len(ap["freq"]):
        st.subheader("Frequent itemsets")
        tema.tabel(ap["freq"].sort_values("support", ascending=False)[["Itemset", "Ukuran", "support"]], 100)
    r = ap["rules"]
    if len(r):
        st.subheader("10 aturan terbaik")
        st.caption("Peringkat: lift terbesar, lalu confidence, lalu support. Lift > 1 berarti produk dibeli bersama lebih sering daripada kebetulan.")
        top = r.head(10)
        tema.tabel(top[["Antecedent", "Consequent", "support", "confidence", "lift"]])
        tema.plot(px.bar(top.iloc[::-1], x="lift", y="Aturan", orientation="h", title="Lift 10 aturan terbaik"), 420)
        hm = r.head(40).pivot_table(index="Antecedent", columns="Consequent", values="lift", aggfunc="max")
        if hm.shape[0] > 1 and hm.shape[1] > 1:
            tema.plot(px.imshow(hm, color_continuous_scale=["#F7F3EA", "#9B85C7"], aspect="auto",
                                title="Heatmap lift (40 aturan teratas)"), 420)
        tema.card("<b>Interpretasi bisnis</b><br>" + "<br>".join(
            f"- Pelanggan yang membeli <b>{tema.esc(x.Antecedent)}</b> memiliki peluang {x.confidence * 100:.1f}% juga membeli <b>{tema.esc(x.Consequent)}</b> ({x.lift:.2f}x lebih sering dari acak; muncul di {x.support * 100:.2f}% transaksi). Kandidat bundling atau penempatan berdekatan."
            for x in top.head(3).itertuples()) + "<br><i>Ini pola asosiasi, bukan bukti sebab-akibat; efek penjualan perlu diuji.</i>")


# ===== Rekomendasi & Ekspor =====

def tab_reko():
    c = need("Rekomendasi & Ekspor", "Penempatan rak berbasis hasil analisis dan unduhan hasil")
    if c is None:
        return
    rk = ss["reco"]
    if rk is None:
        tema.rack([("Rak Atas", [None] * 4), ("Rak Tengah", [None] * 4), ("Rak Bawah", [None] * 4)],
                  "Rak menunggu analisis — jalankan Apriori untuk mengisi rak.")
    else:
        tema.rack(rk["tiers"])
        st.subheader("Alasan penempatan (dapat ditelusuri)")
        tema.tabel(rk["table"])
        tema.note("Rak Atas: consequent dari aturan Apriori terkuat. Rak Tengah: produk yang lebih banyak dibeli klaster K-Means unggulan (total pembelian terbesar) daripada rata-rata pelanggan. Rak Bawah: produk pemicu (antecedent) aturan Apriori. Slot kosong berarti tidak ada bukti analisis tambahan.")
        r = ss["apriori"]["rules"].iloc[0]
        st.subheader("Rekomendasi prioritas")
        seg = ss["rfm"]
        rec = [("1. Penempatan/bundling produk", f"Aturan terkuat: {r['Antecedent']} -> {r['Consequent']} (support {r['support']:.4f}, confidence {r['confidence']:.3f}, lift {r['lift']:.2f}).",
                "Tempatkan produk berdekatan atau buat paket.", "Rata-rata basket size dan frekuensi pembelian bersama pasangan produk ini.")]
        if seg is not None:
            rk_ = seg[seg["Segmen"].isin(["Berisiko Tidak Kembali", "Hampir Hilang"])]
            rec.append(("2. Retensi pelanggan", f"{len(rk_)} dari {len(seg)} pelanggan ({len(rk_) / len(seg) * 100:.1f}%) berada di segmen Berisiko/Hampir Hilang dan menyumbang {rk_['Monetary'].sum() / seg['Monetary'].sum() * 100:.1f}% total pembelian ({rp(rk_['Monetary'].sum())}).",
                        "Kampanye reaktivasi untuk segmen tersebut.", "Tingkat pembelian ulang segmen dalam periode kampanye dibanding kelompok pembanding."))
        if ss["kmeans"] and ss["kmeans"].get("ok"):
            top = ss["kmeans"]["prof"].sort_values("Monetary_total", ascending=False).iloc[0]
            rec.append(("3. Tindakan pemasaran", f"Klaster {int(top['Klaster'])} ({top['Label']}) berisi {int(top['Pelanggan'])} pelanggan dengan total pembelian terbesar ({rp(top['Monetary_total'])}).",
                        "Sasar penawaran produk Rak Tengah ke klaster ini.", "Konversi penawaran dan rata-rata Monetary klaster."))
        tema.card("<br><br>".join(f"<b>{a}</b><br>Bukti data (temuan faktual): {b}<br>Tindakan: {t}<br>KPI keberhasilan: {k}<br>Asumsi: pola historis berlanjut; biaya dan manfaat belum diestimasi karena data biaya tidak tersedia.<br>Evaluasi: uji A/B atau bandingkan sebelum-sesudah. <i>Dampak aktual belum diuji.</i>" for a, b, t, k in rec))
    st.subheader("Unduhan")
    tabs = export_tables()
    st.download_button("Unduh semua hasil (Excel)", xlsx_bytes(tabs), "hasil_analisis_business_intelligence.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_all")
    cols = st.columns(3)
    for i, (n, d) in enumerate(tabs.items()):
        cols[i % 3].download_button(f"CSV {n}", d.to_csv(index=False).encode("utf-8-sig"),
                                     f"{n}.csv", "text/csv", key=f"dl_{n}")


# ===== Dashboard BI =====

def _dashboard_sales_metrics(frame):
    transaction_count = (frame.loc[_valid_dashboard_id(frame["Transaction_ID"]), "Transaction_ID"].nunique()
                         if "Transaction_ID" in frame else 0)
    customer_count = (frame.loc[_valid_dashboard_id(frame["Customer_ID"]), "Customer_ID"].nunique()
                      if "Customer_ID" in frame else None)
    net_sales = (pd.to_numeric(frame["Net_Sales"], errors="coerce").sum(min_count=1)
                 if "Net_Sales" in frame else None)
    quantity = (pd.to_numeric(frame["Quantity"], errors="coerce").sum(min_count=1)
                if "Quantity" in frame else None)
    valid_sales_mask = (_valid_dashboard_id(frame["Transaction_ID"]) if "Transaction_ID" in frame
                        else pd.Series(False, index=frame.index))
    gross_sales = None
    if {"Quantity", "Unit_Price"}.issubset(frame.columns):
        quantities = pd.to_numeric(frame["Quantity"], errors="coerce")
        prices = pd.to_numeric(frame["Unit_Price"], errors="coerce")
        valid_sales_mask &= quantities.gt(0) & prices.gt(0)
        gross_sales = (quantities * prices).where(valid_sales_mask).sum(min_count=1)
    elif "Net_Sales" in frame:
        valid_sales_mask &= pd.to_numeric(frame["Net_Sales"], errors="coerce").notna()
    if frame.empty:
        if "Net_Sales" in frame:
            net_sales = 0
        if "Quantity" in frame:
            quantity = 0
        if {"Quantity", "Unit_Price"}.issubset(frame.columns):
            gross_sales = 0
    average_transaction = (net_sales / transaction_count
                           if net_sales is not None and pd.notna(net_sales) and transaction_count else None)
    return {"gross_sales": gross_sales, "net_sales": net_sales,
            "valid_sales_count": int(valid_sales_mask.sum()),
            "transaction_count": transaction_count, "customer_count": customer_count,
            "average_transaction": average_transaction, "quantity": quantity}


def _dashboard_monthly_sales(frame):
    columns = ["Bulan", "Penjualan sebelum diskon", "Penjualan setelah diskon", "Transaksi unik"]
    if frame.empty or "Transaction_Date" not in frame:
        return pd.DataFrame(columns=columns), False
    data = frame.copy()
    data["Transaction_Date"] = pd.to_datetime(data["Transaction_Date"], errors="coerce")
    data = data.dropna(subset=["Transaction_Date"])
    if data.empty:
        return pd.DataFrame(columns=columns), False
    data["Bulan"] = data["Transaction_Date"].dt.to_period("M")
    has_gross = {"Quantity", "Unit_Price"}.issubset(data.columns)
    if has_gross:
        quantity = pd.to_numeric(data["Quantity"], errors="coerce")
        price = pd.to_numeric(data["Unit_Price"], errors="coerce")
        data["Penjualan sebelum diskon"] = (quantity * price).where(quantity.gt(0) & price.gt(0))
    if "Net_Sales" in data:
        data["Penjualan setelah diskon"] = pd.to_numeric(data["Net_Sales"], errors="coerce")
    monthly = pd.DataFrame(index=pd.period_range(data["Bulan"].min(), data["Bulan"].max(), freq="M"))
    monthly.index.name = "Bulan"
    sales_columns = [c for c in ("Penjualan sebelum diskon", "Penjualan setelah diskon") if c in data]
    if sales_columns:
        revenue = data.groupby("Bulan")[sales_columns].sum(min_count=1)
        monthly = monthly.join(revenue)
    if "Transaction_ID" in data:
        transactions = data.loc[_valid_dashboard_id(data["Transaction_ID"])].drop_duplicates("Transaction_ID")
        monthly_transactions = (transactions.groupby("Bulan")["Transaction_ID"].nunique().rename("Transaksi unik"))
        monthly = monthly.join(monthly_transactions)
    monthly = monthly.fillna(0)
    monthly.index = monthly.index.astype(str)
    monthly = monthly.rename_axis("Bulan").reset_index()
    for column in columns:
        if column not in monthly:
            monthly[column] = np.nan if column.startswith("Penjualan") else 0
    return monthly[columns], has_gross


def _dashboard_options(frame, column):
    if column not in frame:
        return []
    values = frame[column].dropna().astype("string").str.strip()
    return sorted(value for value in values.unique() if value)


def _dashboard_payment_counts(frame):
    required = {"Transaction_ID", "Payment_Method"}
    if not required.issubset(frame.columns):
        return pd.DataFrame(columns=["Payment_Method", "Transaksi"])
    payments = frame.loc[_valid_dashboard_id(frame["Transaction_ID"]),
                         ["Transaction_ID", "Payment_Method"]].copy()
    payments["Payment_Method"] = payments["Payment_Method"].astype("string").str.strip()
    payments = payments[payments["Payment_Method"].notna() & payments["Payment_Method"].ne("")
                        & payments["Payment_Method"].ne(UNK)]
    per_transaction = payments.groupby("Transaction_ID")["Payment_Method"].agg(
        lambda values: values.dropna().nunique())
    consistent_ids = per_transaction[per_transaction.eq(1)].index
    payments = payments[payments["Transaction_ID"].isin(consistent_ids)].drop_duplicates(
        ["Transaction_ID", "Payment_Method"])
    return (payments.groupby("Payment_Method")["Transaction_ID"].nunique()
            .sort_values(ascending=False).rename("Transaksi").reset_index())


def _dashboard_insights(monthly, categories, products, rules, segments):
    insights = []
    if (not monthly.empty and "Revenue" in monthly
            and pd.to_numeric(monthly["Revenue"], errors="coerce").notna().any()):
        peak = monthly.loc[monthly["Revenue"].idxmax()]
        revenue_total = monthly["Revenue"].sum()
        share = peak["Revenue"] / revenue_total * 100 if revenue_total else None
        share_text = f" ({share:.1f}% dari revenue terpilih)" if share is not None else ""
        insights.append(("Tren revenue",
                         f"Bulan {peak['Bulan']} mencatat revenue tertinggi, {rp(peak['Revenue'])}{share_text}.",
                         "Tinjau faktor operasional pada bulan tersebut sebelum menetapkan rencana stok atau promosi."))
    if not categories.empty and "Revenue" in categories:
        leader = categories.iloc[0]
        total = categories["Revenue"].sum()
        share = leader["Revenue"] / total * 100 if total else None
        share_text = f" ({share:.1f}% dari revenue berkategori)" if share is not None else ""
        insights.append(("Kategori dengan revenue tertinggi",
                         f"{leader['Category']} menghasilkan {rp(leader['Revenue'])}{share_text}.",
                         "Evaluasi ketersediaan produk pada kategori ini dan bandingkan kontribusinya pada periode berikutnya."))
    if not products.empty and "Revenue" in products:
        leader = products.iloc[0]
        insights.append(("Produk dengan revenue tertinggi",
                         f"{leader['Item']} mencatat {rp(leader['Revenue'])} pada data terpilih.",
                         "Gunakan produk ini sebagai kandidat evaluasi promosi; ukur hasilnya dengan pembanding."))
    if rules is not None and not rules.empty:
        best = rules.sort_values(["lift", "confidence", "support"], ascending=False, kind="stable").iloc[0]
        insights.append(("Asosiasi produk",
                         f"{best['Antecedent']} -> {best['Consequent']} memiliki lift {best['lift']:.2f}, "
                         f"confidence {best['confidence']:.1%}, dan support {best['support']:.1%}.",
                         "Pertimbangkan uji bundling untuk pasangan ini; asosiasi tidak membuktikan hubungan sebab-akibat."))
    if segments is not None and not segments.empty:
        leading = segments.sort_values(["Monetary", "Frequency"], ascending=False, kind="stable").iloc[0]
        insights.append(("Segmen pelanggan bernilai tertinggi",
                         f"Segmen {leading['Segmen']} memiliki Monetary total tertinggi "
                         f"({rp(leading['Monetary'])}) pada hasil RFM yang tersedia.",
                         SEG_TXT.get(str(leading["Segmen"]), "Tinjau strategi yang sesuai dengan pola aktual segmen.")))
    if segments is not None and not segments.empty and "Kontribusi revenue (%)" in segments:
        churn = segments.loc[segments["Segmen"].eq("Churn Risk")]
        if not churn.empty and churn.iloc[0]["Pelanggan"] > 0:
            row = churn.iloc[0]
            insights.append(("Revenue yang berisiko hilang",
                             f"Churn Risk mencakup {row['Pelanggan (%)']:.1f}% pelanggan dan menyumbang "
                             f"{row['Kontribusi revenue (%)']:.1f}% revenue ({rp(row['Monetary'])}).",
                             "Prioritaskan win-back dan ukur hasilnya terhadap kelompok pembanding."))
    return insights[:6]


def tab_dashboard():
    c = need("Dashboard BI", "Ringkasan kinerja penjualan dan hasil analisis yang telah dijalankan")
    if c is None:
        return
    tema.note(
        "KPI dan visualisasi transaksi mengikuti filter yang diterapkan. "
        "Hasil Apriori, RFM, dan K-Means menggunakan seluruh data yang dipakai "
        "saat model dijalankan; membuka dashboard tidak menjalankan ulang model."
    )
    dated = c
    if "Transaction_Date" in c:
        dates = pd.to_datetime(c["Transaction_Date"], errors="coerce").dropna()
        if dates.empty:
            st.warning("Kolom Transaction_Date tidak memiliki tanggal valid untuk filter.")
            return
        min_date, max_date = dates.min().date(), dates.max().date()
    else:
        min_date = max_date = None
        st.info("Filter tanggal tidak tersedia karena Transaction_Date tidak ditemukan.")
    category_options = _dashboard_options(c, "Category")
    item_column = "Item" if "Item" in c else (
        "Product_Name" if "Product_Name" in c else
        "Product_ID" if "Product_ID" in c else None)
    item_options = _dashboard_options(c, item_column) if item_column else []
    payment_counts = _dashboard_payment_counts(c)
    payment_options = payment_counts["Payment_Method"].astype(str).tolist()
    kmeans = ss.get("kmeans")
    cluster_assignments = None
    cluster_options = []
    if kmeans and kmeans.get("ok") and "assign" in kmeans:
        assignment = kmeans["assign"]
        if {"Customer_ID", "Klaster"}.issubset(assignment.columns):
            cluster_assignments = assignment[["Customer_ID", "Klaster"]].dropna(subset=["Customer_ID"]).copy()
            cluster_assignments["_dashboard_customer_key"] = (
                cluster_assignments["Customer_ID"].astype("string").str.strip())
            cluster_assignments = cluster_assignments.drop_duplicates("_dashboard_customer_key")
            cluster_options = sorted(cluster_assignments["Klaster"].unique().tolist())
    st.subheader("Filter dashboard")
    filter_version = ss.get("ver", 0)
    with st.form(f"dashboard_filter_form_{filter_version}"):
        if min_date is not None:
            selected_dates = st.date_input("Rentang tanggal", value=(min_date, max_date),
                                            min_value=min_date, max_value=max_date,
                                            key=f"dashboard_dates_{filter_version}")
        else:
            selected_dates = None
        filter_columns = st.columns(2)
        with filter_columns[0]:
            selected_categories = (st.multiselect("Kategori", category_options,
                                                   key=f"dashboard_categories_{filter_version}",
                                                   help="Kosongkan pilihan untuk memasukkan semua kategori.")
                                   if category_options else [])
            selected_items = (st.multiselect("Produk", item_options,
                                              key=f"dashboard_products_{filter_version}",
                                              help="Kosongkan pilihan untuk memasukkan semua produk.")
                              if item_options else [])
        with filter_columns[1]:
            selected_payments = (st.multiselect("Metode pembayaran", payment_options,
                                                 key=f"dashboard_payments_{filter_version}",
                                                 help="Kosongkan pilihan untuk memasukkan semua metode pembayaran.")
                                 if payment_options else [])
            selected_cluster = (st.selectbox("Klaster pelanggan", options=[None, *cluster_options],
                                              format_func=lambda value: "Semua klaster" if value is None else f"Klaster {value}",
                                              key=f"dashboard_cluster_{filter_version}")
                                if cluster_options else None)
            if not payment_options:
                st.caption("Filter metode pembayaran tidak tersedia pada data ini.")
            if not cluster_options:
                st.caption("Filter klaster tersedia setelah hasil K-Means berhasil.")
        apply_filters = st.form_submit_button("Terapkan filter", type="primary")
    if apply_filters:
        ss["dashboard_filters"] = {"version": filter_version, "dates": selected_dates,
                                    "categories": selected_categories, "items": selected_items,
                                    "payments": selected_payments, "cluster": selected_cluster}
    filters = ss.get("dashboard_filters", {})
    if filters.get("version") != filter_version:
        filters = {"version": filter_version,
                   "dates": (min_date, max_date) if min_date is not None else None,
                   "categories": [], "items": [], "payments": [], "cluster": None}
    f = c.copy()
    if "Transaction_ID" in f:
        f = f.loc[_valid_dashboard_id(f["Transaction_ID"])].copy()
    if "Transaction_Date" in f and isinstance(filters.get("dates"), (tuple, list)):
        selected_range = filters["dates"]
        if len(selected_range) == 2:
            date_series = pd.to_datetime(f["Transaction_Date"], errors="coerce")
            f = f.loc[date_series.dt.date.between(selected_range[0], selected_range[1])].copy()
    if filters.get("categories") and "Category" in f:
        f = f[f["Category"].astype("string").isin(filters["categories"])]
    if filters.get("items") and item_column:
        f = f[f[item_column].astype("string").isin(filters["items"])]
    if filters.get("payments") and "Payment_Method" in f:
        f = f[f["Payment_Method"].astype("string").isin(filters["payments"])]
    if filters.get("cluster") is not None and cluster_assignments is not None:
        cluster_by_customer = cluster_assignments.set_index("_dashboard_customer_key")["Klaster"]
        customer_keys = f["Customer_ID"].astype("string").str.strip()
        f = f.loc[customer_keys.map(cluster_by_customer).eq(filters["cluster"])].copy()
    filtered = f
    if filtered.empty:
        st.info("Tidak ada baris yang sesuai dengan filter. Ubah pilihan filter untuk melihat hasil.")
    sales_metrics = _dashboard_sales_metrics(filtered)
    na = "Tidak tersedia"
    tema.kpis([
        ("Total Customers", f"{sales_metrics['customer_count']:,}" if sales_metrics["customer_count"] is not None else na),
        ("Total Transactions", f"{sales_metrics['transaction_count']:,}"),
        ("Total Revenue", rp(sales_metrics["net_sales"]) if sales_metrics["net_sales"] is not None and pd.notna(sales_metrics["net_sales"]) else na),
        ("Average Transaction Value", rp(sales_metrics["average_transaction"]) if sales_metrics["average_transaction"] is not None else na),
        ("Total Quantity Sold", f"{sales_metrics['quantity']:,.0f}" if sales_metrics["quantity"] is not None and pd.notna(sales_metrics["quantity"]) else na),
        ("Penjualan sebelum diskon", rp(sales_metrics["gross_sales"]) if sales_metrics["gross_sales"] is not None and pd.notna(sales_metrics["gross_sales"]) else na),
        ("Penjualan valid (baris)", f"{sales_metrics['valid_sales_count']:,}"),
    ])
    st.caption(
        "Total Revenue adalah Net_Sales setelah diskon; transaksi dihitung dari "
        "Transaction_ID unik (bukan baris produk), sehingga Average Transaction "
        "Value = Total Revenue ÷ Total Transactions. Penjualan sebelum diskon "
        "dihitung dari Quantity × Unit_Price; penjualan setelah diskon memakai "
        "Net_Sales tervalidasi."
    )
    st.subheader("Kinerja penjualan")
    if filtered.empty:
        st.info("Visualisasi penjualan belum dapat dibuat karena hasil filter kosong.")
    elif "Transaction_Date" not in filtered:
        st.info("Visualisasi tren bulanan tidak tersedia karena Transaction_Date tidak ditemukan.")
    else:
        chart_data = filtered.copy()
        chart_data["Transaction_Date"] = pd.to_datetime(chart_data["Transaction_Date"], errors="coerce")
        chart_data = chart_data.dropna(subset=["Transaction_Date"])
        monthly, has_gross_monthly = _dashboard_monthly_sales(chart_data)
        monthly["Revenue"] = monthly["Penjualan setelah diskon"]
        monthly_lines = [c for c in ("Penjualan sebelum diskon", "Penjualan setelah diskon")
                         if monthly[c].notna().any()]
        if monthly_lines:
            fig = px.line(monthly, x="Bulan", y=monthly_lines, markers=True,
                          title="Penjualan bulanan sebelum dan setelah diskon",
                          labels={"value": "Penjualan (Rp)", "variable": "Metrik"})
            fig.update_traces(hovertemplate="%{x}<br>%{fullData.name}: Rp %{y:,.0f}<extra></extra>")
            tema.plot(fig, 380)
        else:
            st.info("Grafik penjualan bulanan memerlukan nilai pendapatan yang valid.")
        if not has_gross_monthly:
            st.info("Penjualan sebelum diskon tidak dapat dihitung karena Quantity atau Unit_Price tidak tersedia pada workbook.")
        if monthly["Transaksi unik"].gt(0).any():
            fig = px.bar(monthly, x="Bulan", y="Transaksi unik", title="Jumlah transaksi bulanan",
                         labels={"Transaksi unik": "Transaction_ID unik"})
            tema.plot(fig, 330)
        monthly_display = monthly.drop(columns="Revenue").copy()
        for column in ("Penjualan sebelum diskon", "Penjualan setelah diskon"):
            monthly_display[column] = monthly_display[column].map(
                lambda value: rp(value) if pd.notna(value) else "Tidak tersedia")
        st.markdown("**Seluruh bulan pada rentang data terpilih**")
        tema.tabel(monthly_display, max(12, len(monthly_display)))
        category_summary = pd.DataFrame()
        if "Category" in chart_data and "Net_Sales" in chart_data:
            category_summary = (chart_data.groupby("Category", dropna=True)["Net_Sales"]
                                .sum(min_count=1).rename("Revenue")
                                .sort_values(ascending=False).rename_axis("Category").reset_index())
            if not category_summary.empty:
                category_total = category_summary["Revenue"].sum()
                category_summary["Kontribusi"] = (category_summary["Revenue"] / category_total * 100
                                                   if category_total else np.nan)
                fig = px.bar(category_summary.sort_values("Revenue"), x="Revenue", y="Category",
                             orientation="h", title="Revenue per kategori",
                             labels={"Revenue": "Revenue (Rp)", "Category": "Kategori"})
                tema.plot(fig, 380)
                category_display = category_summary.copy()
                category_display["Revenue"] = category_display["Revenue"].map(rp)
                category_display["Kontribusi"] = category_display["Kontribusi"].map(
                    lambda value: f"{value:.1f}%" if pd.notna(value) else "Tidak tersedia")
                tema.tabel(category_display)
                if category_summary["Revenue"].gt(0).all() and category_total > 0:
                    fig = px.pie(category_summary, names="Category", values="Revenue", hole=.42,
                                 title="Kontribusi revenue per kategori", custom_data=["Kontribusi"])
                    fig.update_traces(hovertemplate="%{label}<br>Revenue: Rp %{value:,.0f}<br>Kontribusi: %{customdata[0]:.1f}%<extra></extra>")
                    tema.plot(fig, 360)
                else:
                    st.info("Diagram kontribusi berbentuk pie tidak ditampilkan karena pendapatan bersih kategori mencakup nilai nol/negatif; tabel kontribusi tetap menampilkan nilai aktual.")
        else:
            st.info("Revenue per kategori memerlukan Category dan Net_Sales.")
        product_summary = pd.DataFrame()
        if item_column and ("Net_Sales" in chart_data or "Quantity" in chart_data):
            aggregations = {}
            if "Net_Sales" in chart_data:
                aggregations["Revenue"] = ("Net_Sales", "sum")
            if "Quantity" in chart_data:
                aggregations["Kuantitas"] = ("Quantity", "sum")
            product_summary = (chart_data.groupby(item_column, dropna=True)
                               .agg(**aggregations)
                               .sort_values("Revenue" if "Revenue" in aggregations else "Kuantitas", ascending=False)
                               .rename_axis("Item").reset_index())
            if "Revenue" in product_summary:
                top_revenue = product_summary.nlargest(10, "Revenue").sort_values("Revenue")
                fig = px.bar(top_revenue, x="Revenue", y="Item", orientation="h",
                             title="Top 10 produk berdasarkan revenue",
                             labels={"Revenue": "Revenue (Rp)", "Item": "Produk"})
                tema.plot(fig, 400)
            if "Kuantitas" in product_summary:
                top_quantity = product_summary.nlargest(10, "Kuantitas").sort_values("Kuantitas")
                fig = px.bar(top_quantity, x="Kuantitas", y="Item", orientation="h",
                             title="Top 10 produk berdasarkan kuantitas",
                             labels={"Kuantitas": "Kuantitas terjual", "Item": "Produk"})
                tema.plot(fig, 400)
        else:
            st.info("Top produk memerlukan kolom produk serta Revenue atau Quantity.")
        selected_payment_counts = _dashboard_payment_counts(chart_data)
        if not selected_payment_counts.empty:
            fig = px.pie(selected_payment_counts, names="Payment_Method", values="Transaksi", hole=.42,
                         title="Transaksi per metode pembayaran")
            tema.plot(fig, 350)
            st.caption("Hanya transaksi yang memiliki tepat satu metode pembayaran nonkosong yang dihitung pada grafik ini.")
        elif "Payment_Method" in chart_data:
            st.info("Belum ada metode pembayaran konsisten yang dapat dihitung per transaksi.")
        else:
            st.info("Visualisasi metode pembayaran tidak tersedia karena kolom Payment_Method tidak ditemukan.")
        st.subheader("Ringkasan Apriori")
        apriori = ss.get("apriori")
        if apriori is None:
            st.info("Apriori belum dijalankan. Jalankan analisis pada bagian Apriori untuk menampilkan aturan dan bundling.")
            rule_data = pd.DataFrame()
        else:
            rule_data = apriori.get("rules", pd.DataFrame())
            tema.kpis([("Aturan asosiasi", f"{len(rule_data):,}"),
                       ("Minimum support", f"{apriori['params']['sup']:.3f}"),
                       ("Minimum confidence", f"{apriori['params']['conf']:.2f}"),
                       ("Minimum lift", f"{apriori['params']['lift']:.2f}")])
            if rule_data.empty:
                st.info(apriori.get("msg") or "Belum ada aturan asosiasi yang memenuhi parameter analisis.")
            else:
                top_rules = rule_data.sort_values(["lift", "confidence", "support"],
                                                   ascending=False, kind="stable").head(10)
                rule_table = top_rules[["Antecedent", "Consequent", "support", "confidence", "lift"]].copy()
                rule_table["support"] = rule_table["support"].map(lambda value: f"{value:.2%}")
                rule_table["confidence"] = rule_table["confidence"].map(lambda value: f"{value:.2%}")
                rule_table["lift"] = rule_table["lift"].map(lambda value: f"{value:.2f}")
                tema.tabel(rule_table)
                best_rule = top_rules.iloc[0]
                tema.card(
                    "<b>Rekomendasi bundling berdasarkan aturan teratas</b><br>"
                    f"Uji bundling <b>{tema.esc(best_rule['Antecedent'])}</b> dengan "
                    f"<b>{tema.esc(best_rule['Consequent'])}</b>. "
                    f"Support {best_rule['support']:.2%}, confidence "
                    f"{best_rule['confidence']:.2%}, lift {best_rule['lift']:.2f}. "
                    "Temuan ini menunjukkan asosiasi, bukan sebab-akibat; evaluasi "
                    "dampak melalui uji penjualan."
                )
        st.subheader("Profil RFM dan K-Means")
        rfm = ss.get("rfm")
        kmeans = ss.get("kmeans")
        _, segment_summary, segment_notes = _dashboard_customer_segments(c)
        if segment_summary.empty:
            st.info(segment_notes)
        else:
            st.markdown("**Loyal, New, dan Churn Risk berdasarkan RFM aktual (seluruh workbook)**")
            tema.note(segment_notes)
            st.caption(
                "Segmentasi dihitung dari data workbook penuh dan tidak berubah oleh "
                "filter dashboard. Transaksi per segmen adalah jumlah Transaction_ID "
                "unik yang dibeli anggota segmen."
            )
            segment_summary = segment_summary.rename(columns={"Revenue": "Monetary"})
            segment_chart = segment_summary[segment_summary["Pelanggan"].gt(0)]
            fig = px.pie(segment_chart, names="Segmen", values="Pelanggan", hole=.42,
                         title="Distribusi pelanggan menurut segmen RFM", custom_data=["Pelanggan (%)"])
            fig.update_traces(hovertemplate="%{label}<br>Pelanggan: %{value:,}<br>Persentase: %{customdata[0]:.1f}%<extra></extra>")
            tema.plot(fig, 350)
            fig = px.bar(segment_chart, x="Segmen", y="Monetary", color="Segmen",
                         color_discrete_map=SEGMEN_WARNA, text="Kontribusi revenue (%)",
                         title="Revenue per segmen", labels={"Monetary": "Revenue (Rp)"},
                         custom_data=["Pelanggan"])
            fig.update_traces(texttemplate="%{text:.1f}%",
                              hovertemplate="%{x}<br>Revenue: Rp %{y:,.0f}<br>Pelanggan: %{customdata[0]:,}<extra></extra>")
            fig.update_layout(showlegend=False)
            tema.plot(fig, 350)
            segment_table = segment_summary.copy()
            segment_table["Pelanggan (%)"] = segment_table["Pelanggan (%)"].map(lambda value: f"{value:.1f}%")
            segment_table["Kontribusi revenue (%)"] = segment_table["Kontribusi revenue (%)"].map(
                lambda value: f"{value:.1f}%" if pd.notna(value) else "—")
            for column in ("Recency rata-rata (hari)",):
                segment_table[column] = segment_table[column].map(
                    lambda value: f"{value:.1f}" if pd.notna(value) else "—")
            for column in ("Frequency rata-rata",):
                segment_table[column] = segment_table[column].map(
                    lambda value: f"{value:.2f}" if pd.notna(value) else "—")
            for column in ("Monetary", "Monetary rata-rata"):
                segment_table[column] = segment_table[column].map(
                    lambda value: rp(value) if pd.notna(value) else "Tidak tersedia")
            tema.tabel(segment_table)
        cluster_summary = pd.DataFrame()
        if not kmeans or not kmeans.get("ok"):
            st.info(kmeans.get("msg") if kmeans and kmeans.get("msg")
                    else "K-Means belum berhasil dijalankan. Jalankan alur Apriori/K-Means pada bagian terkait.")
        else:
            profile = kmeans.get("prof", pd.DataFrame()).copy()
            assigned = kmeans.get("assign", pd.DataFrame())
            if profile.empty or "Klaster" not in profile or "Klaster" not in assigned:
                st.info("Profil pelanggan K-Means belum tersedia dalam format yang dapat ditampilkan.")
            else:
                assigned_count = assigned["Klaster"].notna().sum()
                profile["Pelanggan (%)"] = profile["Pelanggan"] / max(assigned_count, 1) * 100
                cluster_summary = profile
                display_profile = profile.copy()
                for column in ("Pelanggan (%)",):
                    display_profile[column] = display_profile[column].map(lambda value: f"{value:.1f}%")
                for column in ("Recency_rata", "Recency_median"):
                    if column in display_profile:
                        display_profile[column] = display_profile[column].map(lambda value: f"{value:.1f} hari")
                for column in ("Frequency_rata", "Frequency_median"):
                    if column in display_profile:
                        display_profile[column] = display_profile[column].map(lambda value: f"{value:.2f}")
                for column in ("Monetary_rata", "Monetary_median", "Monetary_total"):
                    if column in display_profile:
                        display_profile[column] = display_profile[column].map(rp)
                st.markdown(f"**Distribusi dan profil K-Means ({int(kmeans.get('k', profile['Klaster'].nunique()))} klaster; {assigned_count:,} pelanggan terklasifikasi)**")
                tema.tabel(display_profile)
                st.caption("Persentase cluster dihitung dari seluruh pelanggan yang mendapat label model. Filter dashboard tidak melatih ulang model.")
        st.subheader("Business insights")
        insight_monthly = monthly.copy() if "monthly" in locals() else pd.DataFrame()
        insight_categories = category_summary.sort_values("Revenue", ascending=False) if not category_summary.empty and "Revenue" in category_summary else pd.DataFrame()
        insight_products = product_summary.sort_values("Revenue", ascending=False) if not product_summary.empty and "Revenue" in product_summary else pd.DataFrame()
        insights = _dashboard_insights(insight_monthly, insight_categories, insight_products, rule_data, segment_summary)
        if not insights:
            st.info("Insight belum tersedia; diperlukan data transaksi atau hasil model yang valid.")
        else:
            for index, (title, finding, action) in enumerate(insights, start=1):
                tema.card(f"<b>{index}. {tema.esc(title)}</b><br>"
                          f"<b>Temuan:</b> {tema.esc(finding)}<br>"
                          f"<b>Interpretasi / tindakan:</b> {tema.esc(action)}")


# ===== Combined Section: Segmentasi Pelanggan =====

def section_analisis_pelanggan():
    c = need("Segmentasi Pelanggan",
             "Elbow Method, K-Means, dan segmentasi Loyal, New, Churn Risk dalam satu alur")
    if c is None:
        return
    if ss["rfm"] is None:
        st.warning(ss["rfm_err"])
        return
    sync_k_choice(c)
    st.markdown(
        "<div class='sec-nav'>"
        "<a href='#sub-elbow'><b>A</b> Elbow Method</a>"
        "<a href='#sub-kmeans'><b>B</b> K-Means</a>"
        "<a href='#sub-segmen'><b>C</b> Segmentasi</a>"
        "</div>",
        unsafe_allow_html=True,
    )
    section_banner("sub-elbow", "A", "Elbow Method", "Menentukan jumlah cluster dari Inertia dan Silhouette")
    tab_elbow(embedded=True)
    section_banner("sub-kmeans", "B", "K-Means", "Profil, visualisasi, dan karakteristik cluster")
    tab_kmeans(embedded=True)
    section_banner("sub-segmen", "C", "Segmentasi Pelanggan", "Loyal, New, dan Churn Risk beserta strategi")
    tab_segmentasi(embedded=True)


def sync_k_choice(c):
    km = ss.get("kmeans")
    key = f"km_k_choice_{ss['ver']}"
    chosen = ss.get(key)
    if km and km.get("ok") and chosen and chosen != km["k"]:
        with st.spinner(f"Menghitung ulang K-Means untuk K = {chosen}..."):
            apply_k(c, chosen)


# ===== Main =====

def main():
    if not ss["auth"]:
        login.halaman_login()
        return
    workbook_ready = (ss["clean"] is not None and ss["prep_err"] is None and ss["load_err"] is None)
    st_ = [("Workbook: siap" if workbook_ready else "Workbook: belum siap", "g" if workbook_ready else "y"),
           ("Apriori: selesai" if ss["apriori"] else "Apriori: menunggu", "")]
    login.topbar(st_)
    upload_panel()
    ensure_clean()
    ensure_models()
    if ss["prep_err"]:
        st.error(ss["prep_err"])
        return
    if ss["raw"] is None or ss["clean"] is None or ss["load_err"]:
        return
    nav_anchors()
    section_banner("sec-kualitas", "1", "Kualitas Data", "Laporan kualitas sumber sebelum pembersihan")
    tab_kualitas()
    section_banner("sec-eda", "2", "EDA", "Eksplorasi data bersih: statistik, distribusi, tren")
    tab_eda()
    section_banner("sec-rfm", "3", "RFM", "Recency, Frequency, Monetary dan transformasinya")
    tab_rfm()
    section_banner("sec-segmentasi", "4", "Segmentasi Pelanggan",
                   "Elbow Method, K-Means, dan Loyal/New/Churn Risk")
    section_analisis_pelanggan()
    section_banner("sec-apriori", "5", "Apriori (Market Basket Analysis)",
                   "Pola produk yang dibeli bersama")
    tab_apriori()
    section_banner("sec-reko", "6", "Rekomendasi & Ekspor", "Penempatan rak dan unduhan hasil")
    tab_reko()
    section_banner("sec-dashboard", "7", "Dashboard BI",
                   "Ringkasan kinerja penjualan dan hasil analisis")
    tab_dashboard()


main()