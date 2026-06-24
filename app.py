import os
import re
import json
import time
from dotenv import load_dotenv
# pyrefly: ignore [missing-import]
from flask import Flask, jsonify, request, render_template
from google import genai
from google.genai import types
# pyrefly: ignore [missing-import]
from PIL import Image

load_dotenv()

# Module-level Gemini client (same pattern as test_gemini.py)
_gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

app = Flask(__name__)

# Configure reference path relative to this script
REFERENCE_FILE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '.agents', 'skills', 'fssai-grounding', 'reference.md'
)

def get_fssai_standard_value(milk_type: str = 'cow'):
    """Reads the reference.md file and parses the FSSAI standard value for the given milk type.
    If the file doesn't exist, is empty, or parsing fails, returns a default value of 28.0 (cow) or 30.0 (buffalo).
    """
    milk_type_lower = milk_type.lower() if milk_type else 'cow'
    if milk_type_lower == 'buffalo':
        default_value = 30.0
        pattern = r'MIN_LACTOMETER_READING_BUFFALO[\s:=]*([0-9.]+)'
    else:
        default_value = 28.0
        pattern = r'MIN_LACTOMETER_READING_COW[\s:=]*([0-9.]+)'

    if not os.path.exists(REFERENCE_FILE_PATH):
        return default_value

    try:
        with open(REFERENCE_FILE_PATH, 'r', encoding='utf-8') as f:
            content = f.read()
        
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return float(match.group(1))
    except Exception as e:
        app.logger.error(f"Error parsing reference.md: {e}")
    
    return default_value

def vision_screen(lactometer_photo_path: str):
    """Uses the Gemini Vision API to read a lactometer scale value from an image.

    Sends the photo to gemini-2.5-flash with a structured prompt that asks the
    model to return a JSON object containing:
      - "reading"    : the numeric lactometer value it can see on the scale
      - "confidence" : a float in [0, 1] reflecting how clearly the scale is
                       visible and how certain the model is about the reading

    Returns:
        (reading: float, confidence: float)
    """
    # --- load image -----------------------------------------------------------
    try:
        img = Image.open(lactometer_photo_path)
    except Exception as exc:
        app.logger.error("vision_screen: cannot open image '%s': %s", lactometer_photo_path, exc)
        # Return a sentinel that will cause risk_reasoner to mark it INVALID
        return 0.0, 0.0

    # --- build prompt ---------------------------------------------------------
    prompt = (
        "You are reading a lactometer scale — a graduated tube with evenly "
        "spaced numeric markings. Your ONLY task is to find the numeric value "
        "on the graduated scale where the liquid surface meets the scale "
        "markings. Ignore ALL of the following completely: product codes, "
        "barcodes, text labels, packaging numbers, brand names, or any number "
        "not printed directly on the graduated scale itself. If multiple scale "
        "numbers are visible, report the one closest to the liquid surface line. "
        'Respond with ONLY a valid JSON object in this exact format: '
        '{"reading": <number>, "confidence": <0.0-1.0>} '
        "Where confidence reflects how clearly the liquid surface line and "
        "scale markings are visible — not how confident you are about other "
        "numbers in the image."
    )

    # --- call Gemini Vision API -----------------------------------------------
    try:
        response = _gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt, img],
            config=types.GenerateContentConfig(temperature=0),
        )
        raw_text = response.text.strip()
    except Exception as exc:
        app.logger.error("vision_screen: Gemini API call failed: %s", exc)
        return 0.0, 0.0

    # --- parse JSON response --------------------------------------------------
    try:
        # Strip optional markdown code fences the model may add
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", raw_text)
        cleaned = re.sub(r"\n?```$", "", cleaned).strip()
        data = json.loads(cleaned)
        reading = float(data["reading"])
        confidence = float(data["confidence"])
        # Clamp confidence to [0, 1]
        confidence = max(0.0, min(1.0, confidence))
    except Exception as exc:
        app.logger.error(
            "vision_screen: could not parse Gemini response '%s': %s",
            raw_text, exc
        )
        return 0.0, 0.0

    return reading, confidence

def risk_reasoner(reading: float, milk_type: str):
    """Compares the reading against the FSSAI standard.
    Returns: verdict, explanation, and risk_confidence.
    """
    fssai_standard_value = get_fssai_standard_value(milk_type)
    if reading < 10.0 or reading > 45.0:
        return 'INVALID', f"Lactometer reading ({reading:.1f}) is outside plausible ranges for milk (10-45).", 0.98

    diff = reading - fssai_standard_value
    
    if reading >= fssai_standard_value:
        verdict = 'SAFE'
        explanation = f"Lactometer reading of {reading:.1f} meets or exceeds the FSSAI standard threshold of {fssai_standard_value:.1f}."
        # If it's borderline, slightly reduce confidence
        risk_confidence = 0.82 if diff < 0.5 else 0.95
    else:
        verdict = 'RISKY'
        explanation = f"Lactometer reading of {reading:.1f} is below the FSSAI standard of {fssai_standard_value:.1f}, indicating likely water adulteration."
        # Borderline risky reduces confidence slightly
        risk_confidence = 0.85 if abs(diff) < 0.5 else 0.97
        
    return verdict, explanation, risk_confidence

def route_decision(read_confidence: float, risk_confidence: float, threshold: float = 0.80):
    """Checks if either confidence level falls below the threshold.
    Returns: escalate (bool), reason (str)
    """
    reasons = []
    if read_confidence < threshold:
        reasons.append(f"Vision screen confidence ({read_confidence:.2f}) is below threshold ({threshold:.2f})")
    if risk_confidence < threshold:
        reasons.append(f"Risk reasoner confidence ({risk_confidence:.2f}) is below threshold ({threshold:.2f})")
        
    if reasons:
        return True, " & ".join(reasons)
    return False, "Confidence values acceptable. Automatically approved."

@app.route('/')
def index():
    return render_template('index.html')

# Uploads folder lives next to app.py
UPLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}
MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB

@app.route('/api/analyze', methods=['POST'])
def analyze():
    # --- 0. Parse multipart form data ------------------------------------
    milk_type = request.form.get('milk_type', '').strip()
    threshold = float(request.form.get('threshold', 0.80))

    if not milk_type:
        return jsonify({'error': 'Milk type is required.'}), 400
    if milk_type.lower() not in ('cow', 'buffalo'):
        return jsonify({'error': f"Invalid milk type: '{milk_type}'. Must be 'cow' or 'buffalo'."}), 400

    # --- validate uploaded file ------------------------------------------
    photo_file = request.files.get('photo')
    if not photo_file or photo_file.filename == '':
        return jsonify({'error': 'A lactometer photo file is required (field name: photo).'}), 400

    _, ext = os.path.splitext(photo_file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({'error': f"Unsupported file type '{ext}'. Only .jpg and .png are accepted."}), 400

    # Read into memory first to check size without double-seeking
    file_bytes = photo_file.read()
    if len(file_bytes) > MAX_FILE_BYTES:
        return jsonify({'error': f'File exceeds the 5 MB size limit ({len(file_bytes) // 1024} KB uploaded).'}), 400

    # --- save to uploads/ ------------------------------------------------
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    # Prefix with a millisecond timestamp so repeated uploads never collide
    safe_name = os.path.basename(photo_file.filename)
    timestamped_name = f"{int(time.time() * 1000)}_{safe_name}"
    save_path = os.path.join(UPLOADS_DIR, timestamped_name)
    with open(save_path, 'wb') as f:
        f.write(file_bytes)

    # --- 1. Run Gemini vision screening ----------------------------------
    reading, read_confidence = vision_screen(save_path)

    # --- 2. Retrieve FSSAI standards from reference.md -------------------
    standard_value = get_fssai_standard_value(milk_type)

    # --- 3. Assess risk --------------------------------------------------
    verdict, explanation, risk_confidence = risk_reasoner(reading, milk_type)

    # --- 4. Check routing threshold --------------------------------------
    escalate, route_reason = route_decision(read_confidence, risk_confidence, threshold)

    # --- 5. Compile final status -----------------------------------------
    final_status = "ESCALATED TO HUMAN REVIEW" if escalate else verdict

    return jsonify({
        'input': {
            'photo_path': save_path,
            'threshold': threshold,
            'milk_type': milk_type
        },
        'vision_screen': {
            'reading': reading,
            'confidence': read_confidence
        },
        'risk_reasoner': {
            'standard_used': standard_value,
            'verdict': verdict,
            'explanation': explanation,
            'confidence': risk_confidence
        },
        'routing': {
            'escalate': escalate,
            'reason': route_reason,
            'final_status': final_status
        }
    })

@app.route('/api/reference', methods=['GET'])
def reference_api():
    if request.method == 'GET':
        content = ""
        if os.path.exists(REFERENCE_FILE_PATH):
            try:
                with open(REFERENCE_FILE_PATH, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                return jsonify({'error': str(e)}), 500
        
        return jsonify({
            'content': content,
            'parsed_standard': get_fssai_standard_value()
        })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
