import os, base64, json, logging, urllib.request, urllib.error, re

class WasteClassifier:
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY', '')
        if self.api_key:
            logging.info(f"✅ Gemini API key loaded ({len(self.api_key)} chars)")
        else:
            logging.error("❌ GEMINI_API_KEY not found in environment!")

    def predict(self, image_path):
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set on server.")
        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            ext = os.path.splitext(image_path)[1].lower()
            mime_type = {".jpg":"image/jpeg",".jpeg":"image/jpeg",
                         ".png":"image/png",".webp":"image/webp"}.get(ext,"image/jpeg")

            prompt = """You are an expert waste classification system for India's Swachh Bharat Mission.

STEP 1 - First check: Is this ANY kind of electronic or electrical item?
Electronic/E-Waste includes ANY of these:
- Mobile phones, smartphones, feature phones (even broken/old ones)
- Laptops, computers, tablets, iPads
- Chargers, cables, USB wires, power adapters
- Batteries (any type: AA, AAA, phone battery, car battery)
- Circuit boards, motherboards, chips
- TVs, monitors, screens
- Keyboards, mice, headphones, earphones
- Cameras, printers, scanners
- Routers, modems, remotes
- Refrigerators, washing machines, fans, ACs (home appliances)
- Light bulbs, tube lights, CFLs, LEDs
- Any device that uses electricity or has a battery
IF YES → waste_type MUST be "ewaste"

STEP 2 - If NOT electronic:
- "wet" = food waste, fruit/vegetable peels, cooked food, garden waste, leaves, meat, dairy
- "dry" = plastic bags, bottles, paper, cardboard, glass, metal cans, rubber, fabric, styrofoam

CRITICAL RULES:
- A phone/mobile = ALWAYS ewaste, never dry
- A charger/cable = ALWAYS ewaste, never dry  
- Any battery = ALWAYS ewaste, never dry
- Any screen/monitor = ALWAYS ewaste, never dry
- When in doubt between dry and ewaste → choose ewaste

Respond ONLY in this exact JSON format, no markdown, no extra text:
{"waste_type":"ewaste","confidence":95,"detected_items":"old mobile phone","disposal_tip":"Drop at e-waste centre"}"""

            payload = json.dumps({
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": mime_type, "data": image_data}},
                    {"text": prompt}
                ]}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 120}
            }).encode("utf-8")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            logging.info(f"Gemini raw response: {raw}")

            # Strip markdown fences if present
            if "```" in raw:
                for part in raw.split("```"):
                    part = part.strip()
                    if part.lower().startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        raw = part
                        break

            # Extract JSON object
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            else:
                # Fallback: extract waste_type from raw text
                wt_match = re.search(r'"waste_type"\s*:\s*"(\w+)"', raw)
                conf_match = re.search(r'"confidence"\s*:\s*(\d+)', raw)
                wt = wt_match.group(1).lower() if wt_match else "dry"
                conf = float(conf_match.group(1)) if conf_match else 80.0
                return self._build_result(wt, conf, "waste material", "")

            parsed   = json.loads(raw)
            wt       = parsed.get("waste_type", "dry").lower().strip()
            conf     = float(parsed.get("confidence", 80))
            detected = parsed.get("detected_items", "waste material")
            tip      = parsed.get("disposal_tip", "")

            # Extra safety: keyword-based override
            detected_lower = detected.lower()
            ewaste_keywords = ["phone","mobile","charger","cable","laptop","computer","battery",
                               "tablet","keyboard","mouse","screen","monitor","circuit","wire",
                               "adapter","earphone","headphone","camera","printer","router",
                               "tv","television","bulb","led","appliance","electronic","device"]
            if any(kw in detected_lower for kw in ewaste_keywords):
                wt = "ewaste"
                logging.info(f"Keyword override → ewaste (detected: {detected})")

            return self._build_result(wt, conf, detected, tip)

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            logging.error(f"Gemini API error {e.code}: {body}")
            raise ValueError(f"Gemini API error ({e.code}): {body}")
        except json.JSONDecodeError as e:
            logging.error(f"JSON parse error: {e}")
            raise ValueError(f"Failed to parse Gemini response: {e}")
        except Exception as e:
            import traceback; traceback.print_exc()
            raise

    def _build_result(self, wt, conf, detected, tip):
        if wt == "wet":
            return {
                "waste_type":      "wet",
                "confidence":      conf,
                "bin_color":       "Green",
                "disposal_method": tip or "Dispose in GREEN bin — biodegradable organic waste.",
                "waste_examples":  f"Detected: {detected}. E.g. fruit peels, vegetable scraps, cooked food.",
            }
        elif wt == "ewaste":
            return {
                "waste_type":      "ewaste",
                "confidence":      conf,
                "bin_color":       "Red",
                "disposal_method": tip or "Take to certified e-waste collection centre. Never mix with regular waste.",
                "waste_examples":  f"Detected: {detected}. E.g. phones, laptops, cables, batteries, circuit boards.",
            }
        else:
            return {
                "waste_type":      "dry",
                "confidence":      conf,
                "bin_color":       "Blue",
                "disposal_method": tip or "Dispose in BLUE bin — non-biodegradable recyclable waste.",
                "waste_examples":  f"Detected: {detected}. E.g. plastic bottles, paper, metal cans, glass.",
            }