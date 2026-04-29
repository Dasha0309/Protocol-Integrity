# Protocol Integrity v5.0.0

Монгол хэл дээрх **хурлын тэмдэглэлийн бүрэн бүтэн байдлыг хангах** программ.
Дуу бичлэгийг автоматаар бичвэрт хөрвүүлж, мэдрэмтгий мэдээллийг хиймэл оюунаар таньж нууцлан, баримтын хашийг **Ethereum блокчэйнд** anchoring хийнэ.

---

## ✨ Үндсэн боломжууд

-  **Шууд бичлэг + аудио оруулах** — микрофоноор эсвэл `.wav`, `.mp3` файлаар
-  **Чимэгэ STT** — монгол хэлний автомат яриа танилт
-  **Gemini LLM** — мэдрэмжтэй мэдээлэл (нэр, мөнгө, огноо г.м.) автомат таних
-  **Гибрид шифрлэлт** — RSA-2056 OAEP-SHA256 + Fernet (per-token)
-  **Блокчэйн anchor** — Keccak-256 хаш Ethereum (Hardhat/Sepolia)-д хадгалах
-  **PDF экспорт** — албан ёсны протокол бичиг
-  **Хурал тус бүрд тусдаа нууц үг** — fine-grained access control
-  **Архив + хайлт + хогийн сав**

---

## 🛠️ Технологийн стек

| Үе давхарга | Технологи |
|---|---|
| UI | CustomTkinter 5.2.2 + Python 3.13 |
| STT | Чимэгэ REST API |
| LLM | Google Gemini 2.5 |
| Криптограф | `cryptography` (RSA + Fernet) |
| Блокчэйн | Solidity 0.8.20 + Hardhat + web3.py |
| Хадгалалт | JSON (`~/.protocol_integrity/`) |

---

##  Суулгах

### Шаардлага
- Python **3.13+**
- Node.js **18+** (Hardhat-д)
- Чимэгэ API key, Gemini API key

### Сууриулах

```bash
# 1. Repo клонлох
git clone <repo-url>
cd protocol-integrity

# 2. Python хамаарлууд
pip install -r requirements.txt

# 3. Hardhat хамаарлууд
npm install

# 4. API түлхүүрүүд тохируулах
# ~/.protocol_integrity/env.json эсвэл төслийн root дотор env.json үүсгэх:
```

```json
{
  "chimege_api_key": "<your-chimege-key>",
  "gemini_api_key": "<your-gemini-key>",
  "ethereum_rpc_url": "http://127.0.0.1:8545",
  "contract_address": "0x..."
}
```

### Ажиллуулах

```bash
# 1. Hardhat node асаах (тусдаа терминалд)
npx hardhat node

# 2. Smart contract deploy (анх удаа л)
npx hardhat run scripts/deploy.js --network localhost

# 3. Програм асаах
python app.py
```

---

##  Хэрэглээний урсгал

1. **Бүртгүүлэх / Нэвтрэх** → RSA түлхүүр автомат үүснэ
2. **"Шинэ хурал"** товч → нэр, оролцогчид, нууц үг оруулах
3. **Бичлэг хийх** эсвэл **аудио файл оруулах**
4. **Дуусгах** → STT → Gemini → шифрлэлт автомат явагдана
5. **Архив** хэсгээс баримт бичгийг харах
6. **🔓 Тайлах** → хурлын нууц үгээ оруулж нууцлагдсан хэсгийг харах
7. **PDF татах** → албан ёсны баримт

---

## Төслийн бүтэц

```
protocol-integrity/
├── app.py                    # Гол entry point
├── app_config.py             # Тохиргоо, замууд
├── app_services.py           # STT, LLM, Encryption, Blockchain
├── app_utils.py              # Хадгалалт, хайлт, нэвтрэлт
├── ui/
│   ├── login_window.py       # Нэвтрэх / бүртгэх
│   ├── record_page.py        # Бичлэг хийх
│   ├── documents_page.py     # Архив + харах + тайлах
│   ├── trash_page.py         # Хогийн сав
│   ├── admin_page.py         # Админ удирдлага
│   └── ...
├── contracts/                # Solidity smart contracts
│   └── ProtocolIntegrity.sol
└── scripts/                  # Hardhat deploy скрипт
```

Хадгалалтын байршил: `~/.protocol_integrity/`
- `meetings.json` — бүх хурлын мета өгөгдөл
- `keys/` — RSA түлхүүрийн хос
- `recordings/` — аудио файлууд

---

## Аюулгүй байдлын онцлог

- **Zero-trust загвар** — сервер админ хүртэл агуулгыг харах боломжгүй
- **End-to-end шифрлэлт** — диск дээр зөвхөн нууцлагдсан агуулга үлдэнэ
- **Per-meeting password** — нэг түлхүүр алдагдсан тохиолдолд бусад хурал хамгаалагдсан хэвээр
- **Blockchain audit trail** — тэмдэглэл өөрчлөгдсөн эсэхийг математикаар нотолно

---

##  Лицэнз

Дур мэдэн ашиглахыг хориглоно - хөгжүүлэгчээс зөвшөөрөл авна

Энэхүү төсөл нь оюуны өмчөөр хамгаалагдсан болно.
---

**Хөгжүүлэгч:** Дашренчин · 2026
