import os
import sys
import logging
from waste_classifier import WasteClassifier

# Configure logging to see the Gemini raw response
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_prediction(image_path):
    print(f"\n--- Testing Classification for: {os.path.basename(image_path)} ---")
    
    # Check if API key is set
    if not os.environ.get('GEMINI_API_KEY'):
        print("Error: GEMINI_API_KEY not found in environment.")
        print("Please run: export GEMINI_API_KEY='your_api_key_here'")
        return

    classifier = WasteClassifier()
    
    try:
        result = classifier.predict(image_path)
        print("\nResult:")
        print(f"  Waste Type: {result['waste_type'].upper()}")
        print(f"  Confidence: {result['confidence']}%")
        print(f"  Bin Color:  {result['bin_color']}")
        print(f"  Examples:   {result['waste_examples']}")
        print(f"  Disposal:   {result['disposal_method']}")
    except Exception as e:
        print(f"Error during prediction: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_classifier.py <path_to_image>")
        sys.exit(1)
    
    image_to_test = sys.argv[1]
    if os.path.exists(image_to_test):
        test_prediction(image_to_test)
    else:
        print(f"Error: File {image_to_test} not found.")
