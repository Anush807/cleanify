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

            prompt = """You are a waste classification expert. Look at this image carefully and classify the waste.

CATEGORY DEFINITIONS:

"wet" — Organic/Biodegradable waste:
- Fruit scraps, fruit peels, apple cores, grape stems, berries
- Vegetable peels and cuttings, leafy greens, herbs
- Cooked food leftovers, rice, bread, meat, fish, bones
- Eggshells, tea bags, coffee grounds
- Garden waste, dry leaves, flowers, plants
- ANY food item or food waste

"dry" — Recyclable/Non-biodegradable waste:
- Plastic bottles, bags, containers, wrappers
- Paper, newspapers, cardboard boxes
- Glass bottles, metal cans, tins
- Cloth, rubber, wood (non-food items)

"ewaste" — Electronic waste:
- Mobile phones, laptops, tablets
- Chargers, cables, batteries
- Circuit boards, bulbs, appliances
- Any electronic device or component

RULES:
- Fruit and vegetable waste = ALWAYS "wet"
- Food scraps of any kind = ALWAYS "wet"
- Electronics of any kind = ALWAYS "ewaste"
- If multiple categories, pick the most hazardous (ewaste > wet > dry)

Respond ONLY with valid JSON, no markdown:
{"waste_type":"wet","confidence":95,"detected_items":"fruit and vegetable scraps","disposal_tip":"Compost or dispose in green bin"}"""

            payload = json.dumps({
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": mime_type, "data": image_data}},
                    {"text": prompt}
                ]}],
                "generationConfig": {
                    "temperature": 0.0,
                    "maxOutputTokens": 150
                }
            }).encode("utf-8")

            # Use gemini-2.5-flash — best vision model
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
            req = urllib.request.Request(url, data=payload,
                                         headers={"Content-Type": "application/json"}, method="POST")

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            logging.info(f"Gemini raw response: {raw}")

            # Clean markdown fences
            if "```" in raw:
                match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
                if match:
                    raw = match.group(1)

            # Extract JSON object
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]

            parsed   = json.loads(raw)
            wt       = parsed.get("waste_type", "dry").lower().strip()
            conf     = float(parsed.get("confidence", 80))
            detected = parsed.get("detected_items", "waste material")
            tip      = parsed.get("disposal_tip", "")

            # Keyword safety overrides
            detected_lower = detected.lower()
            wet_keywords = ["fruit","vegetable","food","peel","scrap","organic",
                            "apple","banana","grape","berry","mango","onion","carrot",
                            "leaf","leaves","flower","herb","cooked","rice","bread",
                            "meat","fish","egg","coffee","tea","compost"]
            ewaste_keywords = ["phone","mobile","laptop","charger","cable","battery",
                               "circuit","electronic","device","screen","bulb","led",
                               "adapter","keyboard","mouse","tablet","camera","wire"]

            if wt not in ["wet","dry","ewaste"]:
                wt = "dry"

            # Override if keywords clearly match
            if any(kw in detected_lower for kw in ewaste_keywords):
                wt = "ewaste"
                logging.info(f"Keyword override → ewaste")
            elif any(kw in detected_lower for kw in wet_keywords) and wt == "dry":
                wt = "wet"
                logging.info(f"Keyword override → wet")

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