# 🎤 LLOCG Live Probability Calculator

เครื่องมือคำนวณโอกาสเล่น Live สำเร็จ สำหรับเกม **Love Live! Official Card Game (LLOCG)**
พัฒนาด้วย Python + Streamlit

---

## ✨ ฟีเจอร์

| ฟีเจอร์ | รายละเอียด |
|---|---|
| 📊 Exact Probability | คำนวณด้วย Multivariate Hypergeometric Distribution |
| 🎲 Monte Carlo Simulation | จำลองการจั่วจริงเพื่อสอบทาน |
| 🎵 รองรับหลาย Live | เล่น 1–3 Live พร้อมกันในเทิร์นเดียว |
| 🎨 ทุกสีหัวใจ | Red / Blue / Green / Yellow / Purple / Pink / Gray / All Trigger |
| 🃏 Deck Import | ดึง Deck จาก Decklog URL code หรือ Paste รายการเอง |
| ✏️ Deck Editor | สร้าง/แก้ไข Deck พร้อม filter, preview รูปการ์ด, และ trigger monitor |
| 🔍 Card DB | โหลดฐานข้อมูลการ์ดจากเซิร์ฟเวอร์หรือ snapshot ออฟไลน์ |

---

## 🚀 วิธีติดตั้งและรัน

```bash
pip install -r requirements.txt
streamlit run app.py
```

เปิด browser ที่ `http://localhost:8501`

---

## 📖 วิธีใช้งาน

### 1. โหลดฐานข้อมูลการ์ด

กด **🔄 Refresh from DB** ใน sidebar เพื่อดึงข้อมูลการ์ดล่าสุดจากเซิร์ฟเวอร์
- ถ้าไม่มีอินเทอร์เน็ต โปรแกรมจะใช้ snapshot ที่บันทึกไว้แทนอัตโนมัติ

---

### 2. นำเข้า Deck

ใช้ expander **📥 Import Deck จาก Decklog** ใน sidebar มี 2 วิธี:

**วิธีที่ 1 — Deck code**
1. เปิด [decklog-en.bushiroad.com](https://decklog-en.bushiroad.com/) แล้วเปิด deck ที่ต้องการ
2. คัดลอก code จาก URL (เช่น `ABC12`)
3. วางใน field **Deck code** แล้วกด **🔽 ดึงจาก Decklog**

**วิธีที่ 2 — Paste รายการ**
1. คัดลอกรายการการ์ดในรูปแบบ `card_no×จำนวน` (เช่น `PL!SP-bp1-001×4`)
2. วางใน tab **📋 Paste** แล้วกด **📋 Parse & Import**

---

### 3. แก้ไข Deck ด้วย Deck Editor

กดเมนู **✏️ Deck Editor** ในแถบซ้ายเพื่อเปิดหน้า editor

**แถบซ้าย — ค้นหาการ์ด**
- ค้นหาด้วย **ชื่อการ์ด**, **ประเภท** (Member / Live), **กลุ่ม (Series)**, **Unit**, และ **Cost**
- กด **＋** บนการ์ดเพื่อเพิ่มเข้า Deck

**แถบขวา — จัดการ Deck**
- กด **＋ / －** เพื่อปรับจำนวนแต่ละใบ
- Hover เมาส์บนชื่อการ์ดเพื่อดู **Preview รูป**
- **Trigger ใน Deck** แสดงจำนวน trigger แต่ละสีแบบ real-time
- Summary bar แสดงจำนวนรวม พร้อมเตือนถ้าไม่ครบกฎ (Member 48 / Live 12 / รวม 60 ใบ)
- กด **📥 โหลดจาก Deck ที่ Import แล้ว** เพื่อนำ Deck จากหน้าหลักมาแก้ต่อ
- กด **✅ Apply — ส่งกลับ Calculator** เพื่อส่ง Deck กลับไปใช้งาน (ปุ่มจะ disable ถ้า Deck ไม่ถูกกฎ)

---

### 4. ตั้งค่า Game State (หน้าหลัก)

#### Member บนเวที
เลือกการ์ด Member 1–5 ใบที่อยู่บน Stage ระบบจะดึง Basic Hearts อัตโนมัติ

#### Live ที่จะเล่น
เลือก Live card 1–3 ใบ ระบบจะดึง Required Hearts และ Blade count อัตโนมัติ

#### Waiting Room (WR)
กรอกจำนวนการ์ดที่ออกจาก Deck ไปแล้วก่อนเทิร์นนี้:

| Field | ความหมาย |
|---|---|
| การ์ดที่ใช้ไปแล้ว (สีต่างๆ) | การ์ดสีนั้นที่อยู่ใน WR แล้ว |
| จำนวนการ์ดในมือ | การ์ดที่ถือในมือ (ไม่รู้สี) |
| การ์ดใน WR จาก Turn ก่อน | การ์ดใน WR ที่ไม่รู้สี (มาจาก turn ก่อน) |
| Score+ Live ที่ออกไปทางอื่น | Score+ Live ที่อยู่ในมือหรือ WR แล้ว |

---

### 5. อ่านผลลัพธ์

- **โอกาสสำเร็จ** — เปอร์เซ็นต์รวมที่ Live จะสำเร็จ
- **Exact vs Monte Carlo** — ตัวเลขสองชุดเพื่อสอบทาน ควรใกล้เคียงกัน
- **Score+ Probability** — โอกาสที่จะจั่วโดน Score+ Live card ระหว่าง Yell
- **Non-Trigger Sensitivity** — กราฟแสดงว่าถ้าลด/เพิ่ม Non-Trigger ใน Deck จะกระทบ probability แค่ไหน

---

## 📐 หลักการคำนวณ

Live สำเร็จเมื่อ:
1. หัวใจแต่ละสี (ที่ไม่ใช่ Gray) ≥ Required Hearts ของสีนั้น
2. หัวใจรวมทั้งหมด (รวม Gray/All) ≥ Required Hearts รวม

หัวใจมาจาก:
- **Basic Hearts** จาก Member บนเวที
- **Trigger Hearts** จากการ์ดที่พลิกขึ้นใน Yell (จำนวน = Blade รวมของ Live ที่เล่น)
- **All Trigger** (wildcard) — ใช้เติมสีไหนก็ได้ที่ขาด
- **Mid-Yell Reshuffle** — รองรับกรณี Blade เกิน Deck ที่เหลือ (รวม WR เข้า)

---

## 📁 โครงสร้างโปรเจกต์

```
lovelive_calculator/
├── app.py                  # หน้าหลัก Calculator
├── pages/
│   └── 1_Deck_Editor.py   # หน้า Deck Editor
├── models.py               # Data classes (Color, Deck, Live, GameState ฯลฯ)
├── probability.py          # Hypergeometric math
├── simulator.py            # Monte Carlo simulation
├── card_db.py              # Card database loader / cache
├── deck_import.py          # Decklog import / deck composition
├── requirements.txt
├── README.md
└── Game_Rule.md            # สรุปกฎเกมอ้างอิง
```

---

## 🌐 Deploy

สามารถ deploy ฟรีได้ที่:
- **Streamlit Community Cloud** — https://streamlit.io/cloud
- **Hugging Face Spaces** — https://huggingface.co/spaces
- **Render / Railway / Fly.io**
