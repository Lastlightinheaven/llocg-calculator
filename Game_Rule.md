# LLOCG Live Probability Calculator

## Project Overview
เครื่องมือคำนวณความน่าจะเป็นในการเล่น Live สำเร็จ สำหรับเกม **Love Live! Official Card Game (LLOCG)**
สร้างด้วย Python + Streamlit · คำนวณแบบ Multivariate Hypergeometric Distribution + Monte Carlo Simulation

## Game Rules (สำคัญต่อการเขียนโค้ด)

### Deck
- Deck หลัก 60 ใบ = Member 48 ใบ + Live 12 ใบ
- Member card มี "Basic Heart" (หัวใจที่ได้แน่ตอนอยู่บน Stage) + "Blade" (penlight, นับเป็นจำนวนที่จะจั่วตอน Yell) + "Trigger" (หัวใจที่ให้เมื่อถูกจั่วออกมาตอน Yell)

### Colors (สีหัวใจ)
- **Red, Blue, Green, Yellow, Purple, Pink** — สีหัวใจ 6 สี
- **Gray** — wildcard *requirement* (ช่องนี้หัวใจสีไหนก็เติมได้)
- **All Trigger** — wildcard *reward* (การ์ดใน deck ที่เปิดเจอแล้วใช้เป็นหัวใจสีไหนก็ได้)

### Live Success Conditions
Live สำเร็จเมื่อ **ครบทั้ง 2 เงื่อนไข**:
1. สำหรับทุกสี non-Gray: `hearts_acquired[color] >= required_hearts[color]`
2. หัวใจรวมทั้งหมด (รวม Gray) ≥ required hearts รวม

Hearts มาจาก: Basic Hearts (จาก Member บนเวที) + Trigger Hearts (จากการ์ดที่เปิดตอน Yell) + All Trigger (เติมสีไหนก็ได้)

### Multi-Live
เล่นได้สูงสุด 3 Live ต่อเทิร์น — required hearts ของทุก Live ที่เลือก **รวมกันทั้งหมด** ต้องครบใน Yell เดียว

## Architecture

```
lovelive_calculator/
├── app.py              # Streamlit UI — run with `streamlit run app.py`
├── models.py           # Data classes: Color, DeckComposition, LiveRequirement, GameState
├── probability.py      # Multivariate Hypergeometric (exact calculation)
├── simulator.py        # Monte Carlo simulation
├── test_math.py        # Verification tests (must reproduce 90.85% from Google Sheet)
├── requirements.txt    # streamlit, pandas
└── README.md
```

### Separation of Concerns
- **models.py**: ไม่มี logic คำนวณ — แค่ data classes
- **probability.py**: pure math, ไม่ depend Streamlit — ใช้ซ้ำได้ใน CLI/API/Tests
- **simulator.py**: pure math เช่นกัน — cross-check probability.py
- **app.py**: UI only — ห้ามมี business logic ซ่อนใน UI layer

## การคำนวณหลัก (verified)

**Reference scenario (from Google Sheet — must always = 90.85%):**
- Deck: Red=26, Purple=5, Yellow=14, All=8, Non-Trigger=7 (total 60)
- Waiting: Red=15, Purple=3, Yellow=10, All=3, Non-Trigger=4 (35 out)
- Remaining: Red=11, Purple=2, Yellow=4, All=5, Non-Trigger=3 (25 in deck)
- Stage: 10 blades, no basic hearts
- Live: {RED: 5, GRAY: 3}
- **Result: 90.85%** — รันไฟล์ `test_math.py` เพื่อ verify

## Development Commands

```bash
# Run tests (must pass before committing)
python test_math.py

# Run the app locally
streamlit run app.py

# Format code (if black installed)
black .
```

## Code Style Guidelines
- ใช้ **dataclasses** สำหรับ data models
- ใช้ **type hints** ทุกที่ที่เป็นไปได้
- Function name ใช้ `snake_case`
- Class name ใช้ `PascalCase`
- **เขียน docstring** สำหรับ public function/class ทุกตัว
- Comment เป็นภาษาไทยได้ในส่วนที่เกี่ยวกับกฎเกม

## Edge Cases ที่ต้องระวัง
1. `blade_count > remaining_deck.total()` — ต้อง cap ที่ N (ไม่ handle reshuffle)
2. `blade_count == 0` — success iff basic hearts cover requirements
3. Impossible scenario (draws < required colors) — return 0.0
4. Gray requirement กับ excess basic hearts — basic hearts ที่เกินจาก required color ช่วยเติม gray ได้

## Testing Policy
**ห้าม** modify `test_math.py` ให้ pass โดยไม่ verify ว่าผลลัพธ์ตรงกับ Google Sheet reference (90.85%)
ถ้าเพิ่ม feature ใหม่ — เพิ่ม test case ใหม่ใน `test_math.py` อย่าลบ test เดิม

## Ideas for Future Work
- [ ] เชื่อมกับ LLOCG Thai DB (https://llocg-th.vercel.app) เพื่อ import card list
- [ ] Optimizer: หา combination Member 3 ใบบน Stage ที่ให้ probability สูงสุด
- [ ] Save/load deck as JSON
- [ ] Deck analyzer — แนะนำ Live สีไหนเหมาะกับ deck นี้
- [ ] Multi-turn simulation — จำลองการเล่นทั้งเกม (ไม่ใช่แค่เทิร์นเดียว)
- [ ] i18n — English translation
