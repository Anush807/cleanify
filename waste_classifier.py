import os, base64, json, logging, urllib.request, urllib.error, re

class WasteClassifier:
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY', '')
        if self.api_key:
            logging.info(f"✅ Gemini API key loaded ({len(self.api_key)} chars)")
        else:
            logging.error("❌ GEMINI_API_KEY not found in environment!")
        logging.info("WasteClassifier ready (Gemini Vision)")

    def predict(self, image_path):
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set on server.")
        try:
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")

            ext = os.path.splitext(image_path)[1].lower()
            mime_type = {".jpg":"image/jpeg",".jpeg":"image/jpeg",".png":"image/png",".webp":"image/webp"}.get(ext,"image/jpeg")

            prompt = (
                'You are a waste classification expert for India Swachh Bharat.\n'
                'Classify the waste in this image into exactly "wet", "dry", or "ewaste".\n\n'
                '"wet" = organic/biodegradable: food scraps, fruit/vegetable peels, cooked food, '
                'garden waste, leaves, meat, fish, eggs, dairy, tea/coffee grounds.\n\n'
                '"dry" = non-biodegradable non-electronic: plastic, paper, cardboard, metal cans, '
                'glass, rubber, fabric, styrofoam, packaging.\n\n'
                '"ewaste" = electronic waste: mobile phones, laptops, computers, tablets, chargers, '
                'cables, batteries, circuit boards, printers, TVs, monitors, keyboards, mice, '
                'headphones, cameras, routers, hard drives, any electronic device or component.\n\n'
                'IMPORTANT: detected_items must be 3 words MAX. disposal_tip must be 5 words MAX.\n'
                'Respond ONLY with valid JSON, no markdown:\n'
                '{"waste_type":"ewaste","confidence":90,"detected_items":"old mobile phone","disposal_tip":"Drop at e-waste centre"}'
            )

            payload = json.dumps({
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": mime_type, "data": image_data}},
                    {"text": prompt}
                ]}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 256}
            }).encode("utf-8")

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.api_key}"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type":"application/json"}, method="POST")

            with urllib.request.urlopen(req, timeout=30) as response:
                result = json.loads(response.read().decode("utf-8"))

            raw = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            logging.info(f"Gemini raw response: {raw}")

            # Strip markdown fences
            if "```" in raw:
                for part in raw.split("```"):
                    part = part.strip()
                    if part.lower().startswith("json"): part = part[4:].strip()
                    if part.startswith("{"): raw = part; break

            start = raw.find("{"); end = raw.rfind("}") + 1
            if start != -1 and end > start:
                raw = raw[start:end]
            else:
                wt_match = re.search(r'"waste_type"\s*:\s*"(\w+)"', raw)
                conf_match = re.search(r'"confidence"\s*:\s*(\d+)', raw)
                wt = wt_match.group(1).lower() if wt_match else "dry"
                conf = float(conf_match.group(1)) if conf_match else 80.0
                return self._build_result(wt, conf, "waste material", "")

            parsed = json.loads(raw)
            wt       = parsed.get("waste_type", "dry").lower().strip()
            conf     = float(parsed.get("confidence", 80))
            detected = parsed.get("detected_items", "waste material")
            tip      = parsed.get("disposal_tip", "")
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
            logging.error(f"WasteClassifier error: {e}")
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
                "disposal_method": tip or "Drop at certified e-waste collection centre. Do NOT mix with regular waste.",
                "waste_examples":  f"Detected: {detected}. E.g. old phones, laptops, cables, batteries, circuit boards.",
            }
        else:
            return {
                "waste_type":      "dry",
                "confidence":      conf,
                "bin_color":       "Blue",
                "disposal_method": tip or "Dispose in BLUE bin — non-biodegradable recyclable waste.",
                "waste_examples":  f"Detected: {detected}. E.g. plastic bottles, paper, metal cans, glass.",
            }