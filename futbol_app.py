import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import StringIO
import warnings
import os
from datetime import datetime

# Sayfa Ayarları
st.set_page_config(page_title="Master Bet AI", page_icon="🧠", layout="wide") # Geniş ekran modu

# Uyarıları kapat
warnings.filterwarnings("ignore")

# --- LOGOLAR ---
LOGOLAR = {
    "GALATASARAY": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/Galatasaray_Sports_Club_Logo.png/600px-Galatasaray_Sports_Club_Logo.png",
    "FENERBAHCE": "https://upload.wikimedia.org/wikipedia/tr/8/86/Fenerbah%C3%A7e_SK.png",
    "BESIKTAS": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Logo_of_Be%C5%9Fikta%C5%9F_JK.svg/800px-Logo_of_Be%C5%9Fikta%C5%9F_JK.svg.png",
    "TRABZONSPOR": "https://upload.wikimedia.org/wikipedia/tr/a/ab/Trabzonspor_Amblemi.png",
    "SAMSUNSPOR": "https://upload.wikimedia.org/wikipedia/tr/e/ef/Samsunspor_logo_2.png",
    "GENEL": "https://upload.wikimedia.org/wikipedia/tr/archive/f/f1/20220606135805%21TFF_1._Lig_logo.png"
}

def logo_getir(takim_adi):
    for key in LOGOLAR:
        if key in takim_adi: return LOGOLAR[key]
    return LOGOLAR["GENEL"]

def turkce_karakter_duzelt(metin):
    duzeltme = str.maketrans("ŞşĞğÜüİıÖöÇç", "SsGgUuIiOoCc")
    return str(metin).translate(duzeltme).upper()

# --- VERİ ÇEKME ---
@st.cache_data
def verileri_hazirla():
    url = "https://www.tff.org/default.aspx?pageID=198"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers)
        response.encoding = 'iso-8859-9'
        try:
            html_icerik = StringIO(response.text)
            tablolar = pd.read_html(html_icerik)
        except:
            tablolar = pd.read_html(response.text)
        
        puan_durumu = None
        for tablo in tablolar:
            if len(tablo) > 15 and "G" in str(tablo) and "B" in str(tablo):
                puan_durumu = tablo
                break
        
        if puan_durumu is None: return None, None

        if isinstance(puan_durumu.columns, pd.MultiIndex):
            puan_durumu.columns = puan_durumu.columns.get_level_values(-1)
            
        takimlar = {}
        toplam_gol = 0
        toplam_mac = 0
        
        for index, satir in puan_durumu.iterrows():
            try:
                satir_veri = [str(x) for x in satir.values]
                takim_adi = ""
                for veri in satir_veri:
                    if len(veri) > 3 and not veri.isdigit() and "nan" not in veri.lower() and "Takım" not in veri:
                        takim_adi = veri
                
                temiz_sayilar = [int(x) for x in satir_veri if x.isdigit()]
                
                if len(temiz_sayilar) >= 4 and takim_adi:
                    atilan = temiz_sayilar[-4]
                    yenilen = temiz_sayilar[-3]
                    mac_sayisi = temiz_sayilar[1]
                    temiz_ad = ''.join([i for i in takim_adi if not i.isdigit()]).replace('.', '').replace('A.Ş.', '').strip()
                    evrensel_ad = turkce_karakter_duzelt(temiz_ad)
                    takimlar[evrensel_ad] = {'O': mac_sayisi, 'A': atilan, 'Y': yenilen}
                    toplam_mac += mac_sayisi
                    toplam_gol += atilan
            except: continue

        if toplam_mac == 0: return None, None
        lig_ort = toplam_gol / (toplam_mac / 2)
        
        guc_tablosu = {}
        for takim, veri in takimlar.items():
            guc_tablosu[takim] = {
                'Hucum': (veri['A'] / veri['O']) / lig_ort,
                'Defans': (veri['Y'] / veri['O']) / lig_ort
            }
        return guc_tablosu, lig_ort

    except Exception as e:
        st.error(f"Veri hatası: {e}")
        return None, None

# --- ARAYÜZ ---
c1, c2 = st.columns([1, 5])
with c1:
    st.image("https://cdn-icons-png.flaticon.com/512/2643/2643509.png", width=80)
with c2:
    st.title("Master Bet AI - Bahis Mühendisi")
    st.markdown("Yapay Zeka Tahminleri + **Value Bet Analizi** + **Kelly Kriteri**")

with st.spinner('Veriler Güncelleniyor...'):
    guc_tablosu, lig_ort = verileri_hazirla()

if guc_tablosu:
    takim_listesi = sorted(list(guc_tablosu.keys()))

    # --- SOL PANEL (AYARLAR) ---
    st.sidebar.header("⚙️ Analiz Parametreleri")
    
    st.sidebar.subheader("1. Takım Seçimi")
    ev_sahibi = st.sidebar.selectbox("🏠 Ev Sahibi", takim_listesi, index=0)
    deplasman = st.sidebar.selectbox("✈️ Deplasman", takim_listesi, index=1)
    
    st.sidebar.subheader("2. Detaylar")
    ev_form = st.sidebar.slider(f"{ev_sahibi} Form (0-5)", 0, 5, 3)
    dep_form = st.sidebar.slider(f"{deplasman} Form (0-5)", 0, 5, 3)
    ev_eksik = st.sidebar.checkbox(f"{ev_sahibi} Eksik Var", False)
    dep_eksik = st.sidebar.checkbox(f"{deplasman} Eksik Var", False)
    
    st.sidebar.divider()
    
    # YENİ EKLENEN KISIM: BAHİS ORANLARI
    st.sidebar.subheader("💰 Bahis Oranları (Bültenden Gir)")
    oran_1 = st.sidebar.number_input("Ev Sahibi (1) Oranı", min_value=1.01, value=2.10, step=0.05)
    oran_0 = st.sidebar.number_input("Beraberlik (0) Oranı", min_value=1.01, value=3.20, step=0.05)
    oran_2 = st.sidebar.number_input("Deplasman (2) Oranı", min_value=1.01, value=2.80, step=0.05)
    
    st.sidebar.divider()
    kasa = st.sidebar.number_input("💼 Toplam Kasan (TL)", min_value=100, value=1000, step=100)

    if st.button("🚀 BÜYÜK ANALİZİ BAŞLAT", type="primary", use_container_width=True):
        if ev_sahibi == deplasman:
            st.error("Aynı takımı seçemezsin!")
        else:
            # --- MOTOR ---
            ev_stats = guc_tablosu[ev_sahibi]
            dep_stats = guc_tablosu[deplasman]
            
            ev_guc = 1 + ((ev_form - 2.5) * 0.05)
            dep_guc = 1 + ((dep_form - 2.5) * 0.05)
            if ev_eksik: ev_guc *= 0.85
            if dep_eksik: dep_guc *= 0.85
            
            ev_xg = ev_stats['Hucum'] * dep_stats['Defans'] * lig_ort * 1.15 * ev_guc
            dep_xg = dep_stats['Hucum'] * ev_stats['Defans'] * lig_ort * dep_guc
            
            # SİMÜLASYON
            ms_sayac = {'1':0, '0':0, '2':0}
            iy_ms_sayac = {}
            skor_sayac = {}
            alt_ust = {'UST':0, 'ALT':0}
            
            sim_sayisi = 5000
            for _ in range(sim_sayisi):
                e_gol = np.random.poisson(ev_xg)
                d_gol = np.random.poisson(dep_xg)
                
                # MS
                if e_gol > d_gol: ms='1'
                elif d_gol > e_gol: ms='2'
                else: ms='0'
                ms_sayac[ms] += 1
                
                # İY (Basit model)
                e_iy = np.random.binomial(e_gol, 0.45)
                d_iy = np.random.binomial(d_gol, 0.45)
                if e_iy > d_iy: iy='1'
                elif d_iy > e_iy: iy='2'
                else: iy='0'
                
                iy_ms_key = f"{iy}/{ms}"
                iy_ms_sayac[iy_ms_key] = iy_ms_sayac.get(iy_ms_key, 0) + 1
                
                skor_key = f"{e_gol}-{d_gol}"
                skor_sayac[skor_key] = skor_sayac.get(skor_key, 0) + 1
                
                if (e_gol+d_gol) > 2.5: alt_ust['UST'] += 1
                else: alt_ust['ALT'] += 1

            # --- ANALİZ SONUÇLARI ---
            
            # 1. BAŞLIK VE SKOR
            colA, colB, colC = st.columns([1, 0.8, 1])
            with colA:
                st.image(logo_getir(ev_sahibi), width=100)
                st.markdown(f"### {ev_sahibi}")
                st.info(f"xG: {ev_xg:.2f}")
            with colB:
                st.write("# VS")
            with colC:
                st.image(logo_getir(deplasman), width=100)
                st.markdown(f"### {deplasman}")
                st.info(f"xG: {dep_xg:.2f}")

            st.divider()

            # 2. OLASILIKLAR VE VALUE BET ANALİZİ
            prob_1 = ms_sayac['1'] / sim_sayisi
            prob_0 = ms_sayac['0'] / sim_sayisi
            prob_2 = ms_sayac['2'] / sim_sayisi
            
            # Adil Oranlar (1 / Olasılık)
            fair_1 = 1 / prob_1 if prob_1 > 0 else 99
            fair_0 = 1 / prob_0 if prob_0 > 0 else 99
            fair_2 = 1 / prob_2 if prob_2 > 0 else 99
            
            st.subheader("💰 VALUE BET (Değerli Bahis) ANALİZİ")
            st.caption("Eğer Yapay Zeka Oranı < Bahis Sitesi Oranı ise, bu bir FIRSAT bahsidir.")
            
            cols = st.columns(3)
            
            # EV SAHİBİ ANALİZİ
            with cols[0]:
                st.markdown(f"**{ev_sahibi} Kazanır**")
                st.progress(prob_1)
                st.write(f"YZ Olasılığı: **%{prob_1*100:.1f}**")
                st.write(f"Adil Oran: **{fair_1:.2f}**")
                st.write(f"Site Oranı: **{oran_1:.2f}**")
                
                if oran_1 > fair_1:
                    deger = ((oran_1 * prob_1) - 1) * 100
                    st.success(f"🔥 VALUE VAR! (Değer: %{deger:.1f})")
                    # Kelly Kriteri (Basitleştirilmiş: Kasadan ne kadar basmalı?)
                    # (Oran * Olasılık - 1) / (Oran - 1)
                    kelly = (((oran_1 * prob_1) - 1) / (oran_1 - 1)) * 0.5 # %50 güvenli Kelly
                    if kelly > 0:
                        st.write(f"💵 Önerilen Bahis: **{int(kasa * kelly)} TL**")
                else:
                    st.error("Değersiz Oran (Oynama)")

            # BERABERLİK ANALİZİ
            with cols[1]:
                st.markdown(f"**Beraberlik**")
                st.progress(prob_0)
                st.write(f"YZ Olasılığı: **%{prob_0*100:.1f}**")
                st.write(f"Adil Oran: **{fair_0:.2f}**")
                st.write(f"Site Oranı: **{oran_0:.2f}**")
                
                if oran_0 > fair_0:
                    deger = ((oran_0 * prob_0) - 1) * 100
                    st.success(f"🔥 VALUE! (%{deger:.1f})")
                    kelly = (((oran_0 * prob_0) - 1) / (oran_0 - 1)) * 0.5
                    if kelly > 0:
                        st.write(f"💵 Önerilen: **{int(kasa * kelly)} TL**")
                else:
                    st.error("Değersiz")

            # DEPLASMAN ANALİZİ
            with cols[2]:
                st.markdown(f"**{deplasman} Kazanır**")
                st.progress(prob_2)
                st.write(f"YZ Olasılığı: **%{prob_2*100:.1f}**")
                st.write(f"Adil Oran: **{fair_2:.2f}**")
                st.write(f"Site Oranı: **{oran_2:.2f}**")
                
                if oran_2 > fair_2:
                    deger = ((oran_2 * prob_2) - 1) * 100
                    st.success(f"🔥 VALUE! (%{deger:.1f})")
                    kelly = (((oran_2 * prob_2) - 1) / (oran_2 - 1)) * 0.5
                    if kelly > 0:
                        st.write(f"💵 Önerilen: **{int(kasa * kelly)} TL**")
                else:
                    st.error("Değersiz")

            st.divider()
            
            # DİĞER TAHMİNLER (TABLO HALİNDE)
            t1, t2 = st.tabs(["📊 SKOR & ALT/ÜST", "🔄 İY / MS"])
            
            with t1:
                c_a, c_b = st.columns(2)
                c_a.metric("2.5 ÜST Olasılığı", f"%{(alt_ust['UST']/sim_sayisi)*100:.1f}")
                c_b.metric("2.5 ALT Olasılığı", f"%{(alt_ust['ALT']/sim_sayisi)*100:.1f}")
                
                st.write("**En Olası Skorlar:**")
                sirali_skor = sorted(skor_sayac.items(), key=lambda x: x[1], reverse=True)[:5]
                st.table(pd.DataFrame(sirali_skor, columns=["Skor", "Simülasyon Sayısı"]))
            
            with t2:
                st.write("**İY / MS Tahminleri:**")
                sirali_iy = sorted(iy_ms_sayac.items(), key=lambda x: x[1], reverse=True)[:5]
                st.table(pd.DataFrame(sirali_iy, columns=["İY/MS", "Simülasyon Sayısı"]))

else:
    st.error("TFF Verileri Yüklenemedi. İnternet bağlantını kontrol et.")