# 📚 Mustaqil Ta'lim Tekshiruv Boti

Telegram bot — talabalar mustaqil ta'lim topshiriqlarini yuboradi, ustoz baholaydi.

---

## ⚙️ O'rnatish

```bash
pip install python-telegram-bot[job-queue]
```

---

## 🔧 Sozlash (`bot.py`)

Faylning yuqorisidagi ikkita qatorni o'zgartiring:

```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"   # @BotFather dan olingan token
ADMIN_IDS  = [123456789]            # Ustoz(lar)ning Telegram ID si
```

> Telegram ID ni bilish uchun @userinfobot ga /start yuboring.

---

## 🚀 Ishga tushirish

```bash
python bot.py
```

---

## 👤 Talaba oqimi

```
/start
  → Ism, familiya, sharif (kamida 3 so'z)
  → Telefon raqam
  → Guruh nomi
  → Mavzu tanlash (4 ta)
  → Dalil yuborish (rasm / PDF / link)
  → "Ustoz ko'rib chiqqandan so'ng ball qo'shiladi" xabari
```

**Asosiy menyu:**
- 📚 Mavzu tanlash / Topshiriq yuborish
- ✉️ Ustoga xabar yuborish

---

## 👨‍🏫 Ustoz (Admin) oqimi

**Ustoz paneli (`/start`):**
- 📋 Kutayotgan topshiriqlar — fayl/rasm ko'rish + ball qo'yish
- 📊 Statistika — ro'yxatdan o'tgan / topshirgan / topshirmagan
- 🔔 Eslatma yuborish — hali topshirmagan talabalarga xabar

**Ball qo'yish:**
1. Topshiriq kelganda `⭐ Ball qo'yish` tugmasi bosiladi
2. 2 / 3 / 4 tanlanadi
3. Ixtiyoriy izoh yoziladi (yoki `/skip`)
4. Talabaga avtomatik xabar ketadi

---

## 📊 Statistika (faqat ustoz uchun)
- Jami ro'yxatdan o'tganlar
- Topshiriq yubordilar
- Hali yuklamadilar
- Baholangan topshiriqlar soni

---

## ⏰ Kunlik eslatma
Har 24 soatda topshiriq yubormaganlar talabalariga avtomatik eslatma yuboriladi.

---

## 🗃️ Bazasi
SQLite — `mustaqil.db` fayli bot ishga tushganda avtomatik yaratiladi.
