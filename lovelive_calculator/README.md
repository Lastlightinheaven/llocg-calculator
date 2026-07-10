# 🎤 LLOCG Live Probability Calculator

เครื่องมือคำนวณโอกาสเล่น Live สำเร็จ สำหรับเกม **Love Live! Official Card Game (LLOCG)**
พัฒนาด้วย Python + Streamlit

---

## ✨ ฟีเจอร์

| ฟีเจอร์ | รายละเอียด |
|---|---|
| 📊 Exact Probability | คำนวณด้วย Multivariate Hypergeometric Distribution |
| 🎲 Monte Carlo Simulation | จำลองการจั่วจริงเพื่อสอบทาน (รองรับ Mid-Yell Reshuffle) |
| 🎵 รองรับหลาย Live | เล่น 1–3 Live พร้อมกันในเทิร์นเดียว |
| 🎨 ทุกสีหัวใจ | Red / Blue / Green / Yellow / Purple / Pink / Gray / All Trigger |
| 🎮 Game Board | เลือก Member/Live ลงบอร์ดผ่าน card picker พร้อมรูปการ์ด |
| ✏️ ปรับ Stat ก่อนคำนวณ | แก้ Blade / Basic Hearts ของ Member และ Required Hearts ของ Live ได้ก่อนยืนยันบอร์ด (เผื่อ effect เปลี่ยน stat) |
| 📊 Board Comparison | เก็บสแนปช็อตหลายบอร์ดแล้วเทียบโอกาสสำเร็จบน Situation เดียวกัน + กราฟเส้นตาม Non-Trigger |
| 🃏 Deck Import | ดึง Deck จาก Decklog code หรือ Paste รายการเอง |
| ✏️ Deck Editor | สร้าง/แก้ไข Deck พร้อม filter, preview รูป, trigger monitor, export PNG และสร้าง Deck บน Decklog |
| ⭐ Score+ | นับ/คำนวณโอกาสจั่วโดน Score+ Live card |
| 🔍 Card DB | โหลดฐานข้อมูลการ์ดจาก Assets (ออฟไลน์) พร้อม fallback snapshot / เว็บ |

---

## 🚀 วิธีติดตั้งและรัน

```bash
pip install -r requirements.txt
streamlit run Calculator.py
```

เปิด browser ที่ `http://localhost:8501`

> ข้อมูลการ์ดโหลดจากโฟลเดอร์ `Assets/` โดยตรง (ออฟไลน์) — ไม่ต้องต่อเน็ตก็ใช้งานได้

---

## 📖 วิธีใช้งาน

### 1. นำเข้า Deck (sidebar)

ใช้ expander **📥 Import Deck จาก Decklog** — มี 2 วิธี:

**วิธีที่ 1 — Deck code**
1. เปิด deck บน [decklog-en.bushiroad.com](https://decklog-en.bushiroad.com/)
2. คัดลอก code จาก URL (เช่น `4FRKD`)
3. วางใน field **Deck code** แล้วกด **🔽 ดึงจาก Decklog**

**วิธีที่ 2 — Paste รายการ**
1. คัดลอกรายการการ์ดรูปแบบ `card_no × จำนวน`
2. วางใน tab **📋 Paste** แล้วกด **✅ Parse & Apply**

เมื่อ import แล้ว sidebar จะสรุปองค์ประกอบ Deck (Trigger แต่ละสี, All Trigger, Non-Trigger, Score+ Live) และเปิดดู **Gallery รูปการ์ด** ได้

---

### 2. แก้ไข Deck ด้วย Deck Editor (หน้า ✏️ Deck Editor)

- **ค้นหา/กรอง** ด้วยชื่อการ์ด, ประเภท (Member / Live), กลุ่ม (Series), Unit, Cost — เรียงตาม Cost
- คลิก **🔍** เพื่อดูรายละเอียด (รูปใหญ่ + ข้อความการ์ด), กด **＋ / －** ปรับจำนวน
- **Trigger ใน Deck** อัปเดต real-time + Summary bar เตือนเมื่อไม่ครบกฎ (Member 48 / Live 12 / รวม 60)
- **🖼️ Export PNG** — บันทึกภาพ Deck
- **สร้าง Deck บน Decklog** — publish ขึ้น Decklog ได้ลิงก์กลับมาทันที
- **📥 โหลดจาก Deck ที่ Import** / **✅ Apply กลับ Calculator**

---

### 3. จัดบอร์ดด้วย Game Board (หน้าหลัก)

- **🎵 Live** และ **🎭 Stage (Member)** — กดปุ่มเลือกช่อง แล้วเลือกการ์ดจาก picker (มีรูป) ระบบดึง Blade / Basic Hearts / Required Hearts ให้อัตโนมัติ
- **✏️ ปรับ Stat การ์ด (ก่อนยืนยัน)** — dropdown สำหรับปรับค่าราย Member (Blade + Basic Hearts) และราย Live (Required Hearts) พร้อมแสดงข้อความการ์ด (Text) ประกอบ — ใช้เมื่อมี effect เปลี่ยน stat
- กด **✅ ยืนยัน Game Board** เพื่อสรุปค่าลง Stage / Live / Waiting Room

---

### 4. Waiting Room (การ์ดที่ออกจาก Deck แล้ว)

ระบุจาก 3 แหล่ง ระบบรวมให้อัตโนมัติ:

| แหล่ง | ความหมาย |
|---|---|
| Stage & Live บน Board | นับจากการ์ดที่วางบนบอร์ด (อัตโนมัติ) |
| การ์ดในมือ | จำนวนการ์ดในมือ (สุ่มสีจาก deck ที่เหลือได้) |
| การ์ดใน WR จาก Turn ก่อน | การ์ดที่ออกไปแล้ว (สุ่ม/ระบุสีได้) |
| Live สำเร็จแล้ว | Live ที่เล่นสำเร็จไปก่อนหน้า (มีผลกับ Score+) |

---

### 5. อ่านผลลัพธ์

- **🎯 Exact Hypergeometric** — โอกาสสำเร็จแบบแม่นยำ
- **🎲 Monte Carlo** — สอบทานด้วยการจำลอง (รองรับ Mid-Yell Reshuffle)
- **⭐ Score+** — โอกาสจั่วโดน Score+ Live card ระหว่าง Yell
- **📉 Non-Trigger Sensitivity** — กราฟผลกระทบของจำนวน Non-Trigger คงเหลือใน Deck

---

### 6. เปรียบเทียบบอร์ด (📊 Compare boards)

- กด **➕ เพิ่มบอร์ดปัจจุบันเข้าตาราง** เพื่อเก็บสแนปช็อต (Live + Members + stat ที่ปรับ) — เพิ่มได้ไม่จำกัด
- ปรับ **Blade / Hearts / Required** ราย scenario ได้ใน dropdown (ยุบไว้เพื่อประหยัดพื้นที่)
- กด **🔄 คำนวณตารางเทียบ** → ตารางเทียบ **Exact % · Monte Carlo % · Δ · ผลรวม Board (Blade+Hearts) · Cost** พร้อมไฮไลต์บอร์ดดีสุด 🏆
- **hover ชื่อการ์ด** เพื่อดูรูป · **กราฟเส้น** เทียบอัตราผ่านตาม Non-Trigger คงเหลือใน Deck (สลับ Exact/MC ได้)
- ทุกบอร์ดคำนวณบน **Situation เดียวกัน** (Deck + Waiting Room ปัจจุบัน) — เปลี่ยนแค่ Stage/Live

---

## 📐 หลักการคำนวณ

Live สำเร็จเมื่อ:
1. หัวใจแต่ละสี (ที่ไม่ใช่ Gray) ≥ Required Hearts ของสีนั้น
2. หัวใจรวมทั้งหมด (รวม Gray/All) ≥ Required Hearts รวม

หัวใจมาจาก:
- **Basic Hearts** จาก Member บนเวที
- **Trigger Hearts** จากการ์ดที่พลิกขึ้นใน Yell (จำนวน = Blade รวมของ Live ที่เล่น)
- **All Trigger** (wildcard) — ใช้เติมสีไหนก็ได้ที่ขาด
- **Mid-Yell Reshuffle** — รองรับกรณี Blade เกิน Deck ที่เหลือ (นับ Waiting Room ที่ shuffle กลับ)

---

## 📁 โครงสร้างโปรเจกต์

```
lovelive_calculator/
├── Calculator.py           # หน้าหลัก (Game Board, คำนวณ, เปรียบเทียบบอร์ด)
├── pages/
│   └── 1_Deck_Editor.py    # หน้า Deck Editor
├── models.py               # Data classes (Color, DeckComposition, GameState ฯลฯ)
├── probability.py          # Hypergeometric math + Non-Trigger sensitivity
├── simulator.py            # Monte Carlo simulation
├── card_db.py              # Card database loader (Assets → snapshot → web)
├── deck_import.py          # Decklog import / deck composition
├── deck_export.py          # Export Deck เป็นรูป PNG
├── decklog_publish.py      # สร้าง Deck บน Decklog
├── build_card_snapshot.py  # สร้าง snapshot การ์ดจากเว็บ (offline fallback)
├── Assets/                 # ฐานข้อมูลการ์ด (JSON) + รูป (Card List CSV)
├── requirements.txt
├── README.md
└── Game_Rule.md            # สรุปกฎเกมอ้างอิง
```

---

## 🌐 Deploy

รันเป็น Streamlit app ได้บน:
- **Streamlit Community Cloud** — https://streamlit.io/cloud
- **Hugging Face Spaces** — https://huggingface.co/spaces
- **Render / Railway / Fly.io**

> ตั้ง entry point เป็น `Calculator.py`
