# 🎤 LLOCG Live Probability Calculator

เครื่องมือคำนวณโอกาสเล่น Live สำเร็จ สำหรับเกม **Love Live! Official Card Game (LLOCG)**
พัฒนาด้วย Python + Streamlit

## ✨ ฟีเจอร์

- 📊 **Exact Probability** — ใช้ Multivariate Hypergeometric Distribution
- 🎲 **Monte Carlo Simulation** — จำลองการจั่วจริงเพื่อสอบทาน
- 🎵 **รองรับหลาย Live** — เล่น 1-3 Live พร้อมกันในเทิร์นเดียว
- 🎨 **รองรับทุกสีหัวใจ** — Red, Blue, Green, Yellow, Purple, Pink, Gray (wildcard), All Trigger
- 🧮 **คำนึงถึงทุกปัจจัย** — Deck, Waiting Room, Basic Hearts บนเวที, Blade count

## 📐 หลักการคำนวณ

Live สำเร็จเมื่อ:
1. หัวใจแต่ละสีที่ไม่ใช่สี Gray ครบตาม Required Hearts
2. หัวใจรวมทั้งหมด (รวม Gray) ≥ Required Hearts รวม

โดยหัวใจได้มาจาก:
- **Basic Hearts** จาก Member บนเวที
- **Trigger Hearts** จากการ์ดที่เปิดขึ้นใน Yell (จำนวน = Blade รวม)
- **All Trigger** (wildcard) ใช้เติมสีไหนก็ได้

## 🚀 วิธีติดตั้งและใช้งาน

### ติดตั้ง
```bash
pip install -r requirements.txt
```

### รันโปรแกรม
```bash
streamlit run app.py
```

เปิด browser ไปที่ `http://localhost:8501`

### Deploy เพื่อแชร์ให้คนอื่นใช้
สามารถ deploy ฟรีได้ที่:
- **Streamlit Community Cloud** — https://streamlit.io/cloud (แชร์ง่ายที่สุด)
- **Hugging Face Spaces** — https://huggingface.co/spaces
- **Render / Railway / Fly.io**

## 📁 โครงสร้างโปรเจกต์

```
lovelive_calculator/
├── app.py              # Streamlit UI
├── models.py           # Data classes (Color, Deck, Live, etc.)
├── probability.py      # Hypergeometric math
├── simulator.py        # Monte Carlo simulation
├── test_math.py        # Verification against Google Sheet (90.85%)
├── requirements.txt
└── README.md
```

## 🧩 Extend เพิ่มเติม

สถาปัตยกรรมออกแบบให้ extend ได้ง่าย เช่น:
- เพิ่ม Member database (เชื่อม LLOCG Thai DB)
- เพิ่ม Optimizer หา combination Member ที่ให้ probability สูงสุด
- เพิ่ม export/import deck list
- เพิ่ม deck analyzer เพื่อวิเคราะห์ความสมดุลของ deck
