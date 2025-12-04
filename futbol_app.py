import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import StringIO
import warnings
import os
from datetime import datetime

# Sayfa Ayarları
st.set_page_config(page_title="Pro Futbol Analiz", page_icon="⚽", layout="centered")

# Uyarıları kapat
warnings.filterwarnings("ignore")

# --- LOGO ADRESLERİ (İnternetten çekiyoruz) ---
LOGOLAR = {
    "GALATASARAY": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/Galatasaray_Sports_Club_Logo.png/600px-Galatasaray_Sports_Club_Logo.png",
    "FENERBAHCE": "https://upload.wikimedia.org/wikipedia/tr/8/86/Fenerbah%C3%A7e_SK.png",
    "BESIKTAS": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/Logo_of_Be%C5%9Fikta%C5%9F_JK.svg/800px-Logo_of_Be%C5%9Fikta%C5%9F_JK.svg.png",
    "TRABZONSPOR": "https://upload.wikimedia.org/wikipedia/tr/a/ab/Trabzonspor_Amblemi.png",
    "SAMSUNSPOR": "https://upload.wikimedia.org/wikipedia/tr/e/ef/Samsunspor_logo_2.png",
    "GENEL": "https://upload.wikimedia.org/wikipedia/tr/archive/f/f1/20220606135805%21TFF_1._Lig_logo.png" # Diğer takımlar için
}

def logo_getir(takim_adi):
    # Takım isminin içinde anahtar kelime geçiyor mu diye bakar
    for key in LOGOLAR:
        if key in takim_adi:
            return LOGOLAR[key]
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
# Banner Resmi
st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Football_iu_1996.jpg/1200px-Football_iu_1996.jpg", use_container_width=True)

st.title("⚽ Pro Futbol İddaa Analisti")
st.markdown("---")

with st.spinner('TFF verileri ve logolar yükleniyor...'):
    guc_tablosu, lig_ort = verileri_hazirla()

if guc_tablosu:
    takim_listesi = sorted(list(guc_tablosu.keys()))

    # --- SOL PANEL ---
    st.sidebar.header("⚙️ Maç Ayarları")
    ev_sahibi = st.sidebar.selectbox("🏠 Ev Sahibi", takim_listesi, index=0)
    deplasman = st.sidebar.selectbox("✈️ Deplasman", takim_listesi, index=1)
    
    st.sidebar.divider()
    st.sidebar.write("📊 **Form Durumu (Son 5 Maç)**")
    ev_form = st.sidebar.slider(f"{ev_sahibi}", 0, 5, 3)
    dep_form = st.sidebar.slider(f"{deplasman}", 0, 5, 3)
    
    st.sidebar.write("🚑 **Eksik Oyuncu**")
    ev_eksik = st.sidebar.checkbox(f"{ev_sahibi} eksik var", value=False)
    dep_eksik = st.sidebar.checkbox(f"{deplasman} eksik var", value=False)

    if st.button("🔥 MAÇI ANALİZ ET", type="primary", use_container_width=True):
        if ev_sahibi == deplasman:
            st.error("Aynı takımı seçemezsin!")
        else:
            # --- MOTOR ---
            ev_stats = guc_tablosu[ev_sahibi]
            dep_stats = guc_tablosu[deplasman]
            
            # Katsayılar
            ev_guc = 1 + ((ev_form - 2.5) * 0.05)
            dep_guc = 1 + ((dep_form - 2.5) * 0.05)
            if ev_eksik: ev_guc *= 0.85
            if dep_eksik: dep_guc *= 0.85
            
            ev_xg = ev_stats['Hucum'] * dep_stats['Defans'] * lig_ort * 1.15 * ev_guc
            dep_xg = dep_stats['Hucum'] * ev_stats['Defans'] * lig_ort * dep_guc
            
            # SİMÜLASYON
            ms_sayac = {'1':0, '0':0, '2':0}
            iy_ms_sayac = {}
            alt_ust_sayac = {'ALT':0, 'UST':0}
            skor_sayac = {}
            
            for _ in range(5000):
                e_gol_top = np.random.poisson(ev_xg)
                d_gol_top = np.random.poisson(dep_xg)
                e_gol_iy = np.random.binomial(e_gol_top, 0.45)
                d_gol_iy = np.random.binomial(d_gol_top, 0.45)
                
                # Sonuçlar
                if e_gol_iy > d_gol_iy: iy = '1'
                elif d_gol_iy > e_gol_iy: iy = '2'
                else: iy = '0'
                
                if e_gol_top > d_gol_top: ms = '1'
                elif d_gol_top > e_gol_top: ms = '2'
                else: ms = '0'
                
                ms_sayac[ms] += 1
                iy_ms_key = f"{iy}/{ms}"
                iy_ms_sayac[iy_ms_key] = iy_ms_sayac.get(iy_ms_key, 0) + 1
                
                if (e_gol_top + d_gol_top) > 2.5: alt_ust_sayac['UST'] += 1
                else: alt_ust_sayac['ALT'] += 1
                
                skor_key = f"{e_gol_top}-{d_gol_top}"
                skor_sayac[skor_key] = skor_sayac.get(skor_key, 0) + 1

            # --- GÖRSEL SONUÇ EKRANI ---
            col_ev, col_orta, col_dep = st.columns([1, 0.5, 1])
            
            with col_ev:
                st.image(logo_getir(ev_sahibi), width=100)
                st.subheader(ev_sahibi)
                st.metric("Gol Beklentisi", f"{ev_xg:.2f}")

            with col_orta:
                st.write("# VS")

            with col_dep:
                st.image(logo_getir(deplasman), width=100)
                st.subheader(deplasman)
                st.metric("Gol Beklentisi", f"{dep_xg:.2f}")

            st.divider()
            
            # SEKMELER
            tab1, tab2, tab3 = st.tabs(["🏆 Maç Sonucu", "🔄 İY / MS", "🥅 Alt / Üst & Skor"])
            
            with tab1:
                p1 = (ms_sayac['1']/5000)
                p0 = (ms_sayac['0']/5000)
                p2 = (ms_sayac['2']/5000)
                
                c1, c2, c3 = st.columns(3)
                c1.success(f"EV: %{p1*100:.1f}")
                c2.warning(f"BER: %{p0*100:.1f}")
                c3.error(f"DEP: %{p2*100:.1f}")
                
                st.progress(p1, text="Ev Sahibi")
                st.progress(p0, text="Berabere")
                st.progress(p2, text="Deplasman")

            with tab2:
                sirali_iyms = sorted(iy_ms_sayac.items(), key=lambda x: x[1], reverse=True)[:5]
                df_iyms = pd.DataFrame(sirali_iyms, columns=['Tahmin', 'Sayı'])
                df_iyms['Olasılık %'] = (df_iyms['Sayı'] / 5000) * 100
                st.dataframe(df_iyms[['Tahmin', 'Olasılık %']], hide_index=True, use_container_width=True)

            with tab3:
                c1, c2 = st.columns(2)
                c1.metric("2.5 ÜST", f"%{(alt_ust_sayac['UST']/5000)*100:.1f}")
                c2.metric("2.5 ALT", f"%{(alt_ust_sayac['ALT']/5000)*100:.1f}")
                
                st.write("🎯 **En Olası Skorlar:**")
                sirali_skor = sorted(skor_sayac.items(), key=lambda x: x[1], reverse=True)[:3]
                for s in sirali_skor:
                    st.info(f"{s[0]} (Olasılık: %{(s[1]/5000)*100:.1f})")

else:
    st.error("Veriler yüklenemedi.")