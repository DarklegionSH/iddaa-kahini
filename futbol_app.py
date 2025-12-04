import streamlit as st
import pandas as pd
import numpy as np
import requests
from io import StringIO
import warnings
import plotly.graph_objects as go # YENİ: Grafik Kütüphanesi

# Sayfa Ayarları
st.set_page_config(page_title="Master Bet AI Pro", page_icon="🧠", layout="wide")

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
                    puan = temiz_sayilar[-1] # Puanı da alalım
                    
                    temiz_ad = ''.join([i for i in takim_adi if not i.isdigit()]).replace('.', '').replace('A.Ş.', '').strip()
                    evrensel_ad = turkce_karakter_duzelt(temiz_ad)
                    
                    # Veri setine Puan'ı da ekledik
                    takimlar[evrensel_ad] = {'O': mac_sayisi, 'A': atilan, 'Y': yenilen, 'P': puan}
                    toplam_mac += mac_sayisi
                    toplam_gol += atilan
            except: continue

        if toplam_mac == 0: return None, None
        lig_ort = toplam_gol / (toplam_mac / 2)
        
        guc_tablosu = {}
        for takim, veri in takimlar.items():
            guc_tablosu[takim] = {
                'Hucum': (veri['A'] / veri['O']) / lig_ort,
                'Defans': (veri['Y'] / veri['O']) / lig_ort,
                'PuanOrt': veri['P'] / veri['O'], # Maç başı puan
                'GolOrt': veri['A'] / veri['O']
            }
        return guc_tablosu, lig_ort

    except Exception as e:
        st.error(f"Veri hatası: {e}")
        return None, None

# --- RADAR GRAFİĞİ FONKSİYONU ---
def radar_ciz(ev_ad, dep_ad, ev_stats, dep_stats):
    categories = ['Hücum Gücü', 'Defans Direnci', 'Puan Ort.', 'Gol Ort.']
    
    # Verileri 0-100 arasına normalize edelim (Görsel güzel olsun diye)
    # Bu katsayılar tamamen görsel ölçekleme içindir
    ev_values = [
        ev_stats['Hucum'] * 50, 
        (2 - ev_stats['Defans']) * 50, # Defans ne kadar azsa o kadar iyi, ters çeviriyoruz
        ev_stats['PuanOrt'] * 30,
        ev_stats['GolOrt'] * 30
    ]
    
    dep_values = [
        dep_stats['Hucum'] * 50, 
        (2 - dep_stats['Defans']) * 50,
        dep_stats['PuanOrt'] * 30,
        dep_stats['GolOrt'] * 30
    ]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=ev_values,
        theta=categories,
        fill='toself',
        name=ev_ad,
        line_color='red'
    ))
    
    fig.add_trace(go.Scatterpolar(
        r=dep_values,
        theta=categories,
        fill='toself',
        name=dep_ad,
        line_color='blue'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100])
        ),
        showlegend=True,
        height=300,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    return fig

# --- YORUMCU ROBOT ---
def yapay_zeka_yorumu(ev, dep, ev_s, dep_s, ev_xg, dep_xg):
    yorumlar = []
    
    # Hücum Analizi
    if ev_s['Hucum'] > dep_s['Hucum'] * 1.2:
        yorumlar.append(f"🔥 **{ev}** hücum hattı rakibine göre çok daha üretken. Gol yollarında sorun yaşamazlar.")
    elif dep_s['Hucum'] > ev_s['Hucum'] * 1.2:
        yorumlar.append(f"⚠️ **{dep}** kontra ataklarda çok tehlikeli olabilir, hücum güçleri lig ortalamasının çok üstünde.")
        
    # Defans Analizi
    if ev_s['Defans'] > 1.2: # 1.0 ortalama, üstü kötü
        yorumlar.append(f"🛡️ **{ev}** savunması alarm veriyor (Lig ortalamasından fazla gol yiyorlar).")
        
    # xG Yorumu
    if ev_xg > dep_xg + 1.0:
        yorumlar.append(f"🎯 İstatistikler **{ev}** tarafını net favori gösteriyor. Farklı bir galibiyet şaşırtmaz.")
    elif abs(ev_xg - dep_xg) < 0.3:
        yorumlar.append(f"⚖️ **Kıran kırana bir maç!** İki takımın güçleri birbirine çok denk, beraberlik kokuyor.")
    else:
        yorumlar.append(f"👀 Maçın kaderini **{ev}** takımının saha avantajı belirleyecek gibi.")

    return yorumlar

# --- ARAYÜZ ---
col_logo, col_baslik = st.columns([1, 6])
with col_logo:
    st.image("https://cdn-icons-png.flaticon.com/512/2643/2643509.png", width=70)
with col_baslik:
    st.title("Master Bet AI - Pro Analiz")

with st.spinner('Lig Verileri Yükleniyor...'):
    guc_tablosu, lig_ort = verileri_hazirla()

if guc_tablosu:
    takim_listesi = sorted(list(guc_tablosu.keys()))

    # SOL PANEL
    st.sidebar.header("⚙️ Ayarlar")
    ev_sahibi = st.sidebar.selectbox("🏠 Ev Sahibi", takim_listesi, index=0)
    deplasman = st.sidebar.selectbox("✈️ Deplasman", takim_listesi, index=1)
    
    # Oranlar
    st.sidebar.markdown("💰 **Bahis Oranları**")
    oran_1 = st.sidebar.number_input("MS 1", 1.01, 2.10, step=0.05)
    oran_0 = st.sidebar.number_input("MS 0", 1.01, 3.20, step=0.05)
    oran_2 = st.sidebar.number_input("MS 2", 1.01, 2.80, step=0.05)
    
    kasa = st.sidebar.number_input("💼 Kasa (TL)", 100, 1000)

    if st.button("🚀 ANALİZ ET", type="primary", use_container_width=True):
        if ev_sahibi == deplasman:
            st.error("Aynı takımları seçme!")
        else:
            # HESAPLAMALAR
            ev_stats = guc_tablosu[ev_sahibi]
            dep_stats = guc_tablosu[deplasman]
            
            ev_xg = ev_stats['Hucum'] * dep_stats['Defans'] * lig_ort * 1.15 
            dep_xg = dep_stats['Hucum'] * ev_stats['Defans'] * lig_ort
            
            # Simülasyon
            sim_sayisi = 5000
            ms_list = []
            for _ in range(sim_sayisi):
                e = np.random.poisson(ev_xg)
                d = np.random.poisson(dep_xg)
                if e > d: ms_list.append('1')
                elif d > e: ms_list.append('2')
                else: ms_list.append('0')
            
            p1 = ms_list.count('1') / sim_sayisi
            p0 = ms_list.count('0') / sim_sayisi
            p2 = ms_list.count('2') / sim_sayisi

            # --- SONUÇ EKRANI (3 KOLON) ---
            # 1. KOLON: SKOR VE LOGOLAR
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                st.image(logo_getir(ev_sahibi), width=100)
                st.metric(ev_sahibi, f"xG: {ev_xg:.2f}")
            with c2:
                # RADAR GRAFİĞİ BURAYA GELİYOR
                fig = radar_ciz(ev_sahibi, deplasman, ev_stats, dep_stats)
                st.plotly_chart(fig, use_container_width=True)
            with c3:
                st.image(logo_getir(deplasman), width=100)
                st.metric(deplasman, f"xG: {dep_xg:.2f}")

            st.divider()

            # 2. KOLON: YZ YORUMCUSU
            st.subheader("🤖 Yapay Zeka Yorumcusu")
            yorumlar = yapay_zeka_yorumu(ev_sahibi, deplasman, ev_stats, dep_stats, ev_xg, dep_xg)
            for yorum in yorumlar:
                st.info(yorum)

            st.divider()

            # 3. KOLON: VALUE BET
            st.subheader("💰 Value Bet Fırsatları")
            cols = st.columns(3)
            
            # Fonksiyon
            def value_kontrol(col, ad, prob, oran):
                fair = 1/prob if prob > 0 else 99
                col.metric(f"{ad} Olasılığı", f"%{prob*100:.1f}")
                col.caption(f"Adil Oran: {fair:.2f} | Site: {oran:.2f}")
                if oran > fair:
                    kar = ((oran * prob) - 1) * 100
                    col.success(f"🔥 VALUE (%{kar:.1f})")
                    kelly = (((oran * prob) - 1) / (oran - 1)) * 0.5
                    if kelly > 0: col.write(f"💵 Bas: **{int(kasa*kelly)} TL**")
                else:
                    col.error("Değersiz")

            value_kontrol(cols[0], "MS 1", p1, oran_1)
            value_kontrol(cols[1], "MS 0", p0, oran_0)
            value_kontrol(cols[2], "MS 2", p2, oran_2)

else:
    st.error("Veriler Yüklenemedi.")