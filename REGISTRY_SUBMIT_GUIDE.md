# Registry Submission Guide
> วันที่เตรียม: 2026-06-21 | ไฟล์ทุกอย่างพร้อมแล้ว — Chairman ทำตาม steps ด้านล่าง

---

## สรุป Files ที่เตรียมไว้

| ไฟล์ | ใช้กับ |
|------|--------|
| `README.md` | GitHub |
| `langchain_tool.py` | LangChain Hub + GitHub |
| `gpt_system_prompt.txt` | GPT Store |
| `rapidapi_listing.md` | RapidAPI |
| `.well-known/mcp.json` | MCP Registry |
| `.well-known/ai-plugin.json` | GPT Actions |
| `.well-known/function-schemas.json` | OpenAI / Gemini Function Calling |

---

## 1. GitHub — ทำก่อนทุก registry (5 นาที)

**ทำไมก่อน:** registry อื่นๆ จะ link กลับมา GitHub repo

### Steps:
1. ไปที่ https://github.com/bankbitcoin2/ai-to-ai-holding
2. **Settings → About (เมนูขวามือ)** → เพิ่ม Topics:
   ```
   thai-customs hs-code import-duty fta halal trade-compliance mcp langchain gpt-actions ai-agent asean rcep openapi fastapi thailand
   ```
3. ใส่ Website URL: `https://web-production-c9da4.up.railway.app`
4. Push README.md ใหม่ (ทำใน PowerShell):
   ```powershell
   cd D:\AI_AI\AI_TO_AI_HOLDING
   git add README.md langchain_tool.py gpt_system_prompt.txt rapidapi_listing.md
   git commit -m "docs: add registry submission materials + updated README"
   git push
   ```

---

## 2. RapidAPI (15 นาที)

### Steps:
1. ไป https://rapidapi.com/provider
2. Login หรือ Create account ด้วย email `bankbitcoin2@gmail.com`
3. คลิก **"Add New API"**
4. กรอกข้อมูลจาก `rapidapi_listing.md`:
   - Name: `Thai Trade Intelligence — HS Code, FTA Rates, OGA & Halal`
   - Short Description: copy จากไฟล์
   - Base URL: `https://web-production-c9da4.up.railway.app`
5. Tab **Endpoints** → Import OpenAPI:
   - URL: `https://web-production-c9da4.up.railway.app/openapi.json`
   - คลิก Import
6. Tab **Pricing** → สร้าง 2 tiers ตามไฟล์ (Free + Pro pay-per-use)
7. Tab **About** → ใส่ Long Description จากไฟล์
8. คลิก **"Submit for Review"**

⏱ Review ใช้เวลา 1-3 วันทำการ

---

## 3. GPT Store / Custom GPT (20 นาที)

### Steps:
1. ไป https://chatgpt.com/gpts/editor (ต้องมี ChatGPT Plus หรือ Team account)
2. คลิก **"Create a GPT"**
3. Tab **Configure**:
   - Name: `Thai Trade Intelligence`
   - Description: `One call: Thai HS code + import duty + 13 FTA rates + OGA permits + Halal (21 countries). Thai & English input.`
   - Instructions: copy ทั้งหมดจาก `gpt_system_prompt.txt`
   - Profile picture: upload logo จาก `https://web-production-c9da4.up.railway.app/static/logo.png`
4. Tab **Actions** → คลิก **"Add actions"**:
   - Import from URL: `https://web-production-c9da4.up.railway.app/openapi.json`
   - Authentication: API Key → Header name: `X-API-Key`
5. คลิก **Save** → เลือก **"Public"** หรือ **"Everyone with a link"**
6. Copy URL ของ GPT → แจ้งให้ทีมรู้

⚠️ GPT Store review อาจใช้เวลา 2-7 วัน หรือขึ้น "Not approved" ให้ใช้ "Anyone with a link" แทนก่อน

---

## 4. MCP Registry (10 นาที)

Anthropic ยังไม่มี official submission form — submit ผ่าน community directories แทน:

### 4A. mcp.so (ง่ายที่สุด)
1. ไป https://mcp.so/submit
2. กรอก:
   - Name: `Thai Trade Intelligence`
   - Server URL: `https://web-production-c9da4.up.railway.app/.well-known/mcp.json`
   - GitHub: `https://github.com/bankbitcoin2/ai-to-ai-holding`
   - Description: copy จาก `.well-known/mcp.json` → `description`

### 4B. glama.ai
1. ไป https://glama.ai/mcp/submit
2. กรอก GitHub URL: `https://github.com/bankbitcoin2/ai-to-ai-holding`
3. Submit

### 4C. GitHub modelcontextprotocol/servers (optional — ได้ exposure สูงสุด)
1. Fork https://github.com/modelcontextprotocol/servers
2. แก้ `README.md` → เพิ่มในส่วน "Community servers":
   ```markdown
   - [Thai Trade Intelligence](https://github.com/bankbitcoin2/ai-to-ai-holding) — Thai customs HS code, FTA rates, OGA permits, Halal status. Accepts Thai & English.
   ```
3. Open Pull Request

---

## 5. LangChain Hub (5 นาที)

LangChain Hub เน้น prompts — tool wrappers อยู่ที่ GitHub แทน

1. Push `langchain_tool.py` ขึ้น GitHub แล้ว (step 1)
2. ไป https://smith.langchain.com → Login
3. **Prompts** → **"New Prompt"** → ใส่ system prompt จาก `gpt_system_prompt.txt`
4. Tag: `thai-customs`, `hs-code`, `trade-compliance`
5. Publish as Public

---

## ลำดับที่แนะนำ

```
Day 1 (วันนี้):
  ✅ GitHub push (5 min)
  ✅ RapidAPI submit (15 min)
  ✅ mcp.so + glama.ai (10 min)

Day 2:
  ✅ GPT Store (ต้องมี ChatGPT Plus)
  ✅ LangChain Hub

Day 3-7:
  ⏳ รอ review จาก RapidAPI + GPT Store
```

---

## URLs ที่ต้องรู้

| | URL |
|--|-----|
| Production | `https://web-production-c9da4.up.railway.app` |
| Sandbox | `/v1/sandbox/classify` |
| OpenAPI | `/openapi.json` |
| MCP manifest | `/.well-known/mcp.json` |
| Plugin manifest | `/.well-known/ai-plugin.json` |
| GitHub | `https://github.com/bankbitcoin2/ai-to-ai-holding` |
| Contact | `bankbitcoin2@gmail.com` |
