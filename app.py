# app.py (Updated to use gemini-2.5-pro-exp-03-25)
import os
import re
import requests
import pyperclip
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# --- Configuration ---
# <<< CHANGE: Updated MODEL_NAME based on previous errors >>>
MODEL_NAME = "gemini-2.5-pro-exp-03-25" # Use the experimental model
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("CRITICAL ERROR: GEMINI_API_KEY environment variable not set or found.")
    import sys
    sys.exit("Exiting: GEMINI_API_KEY not configured.")

GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={GEMINI_API_KEY}"

SYSTEM_INSTRUCTION = (
    "You are a helpful coding assistant specialized in Python. Based on the following question and context, "
    "provide only the Python code snippet as the answer, formatted using Markdown code blocks (e.g., ```python ... ```). "
    "Keep explanations minimal and strictly outside the code block."
)

# --- Single Endpoint for Processing ---
@app.route('/process', methods=['POST'])
def process_combined_input():
    print("\n--- Received request to /process ---")

    if not GEMINI_API_KEY:
         print("Error: API Key is missing. Cannot process request.")
         return jsonify({"status": "error", "message": "Server configuration error: API key missing"}), 503

    if not request.is_json:
        print("Error: Request content type is not JSON.")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    data = request.get_json()
    combined_input_text = data.get('question')

    if not combined_input_text or not isinstance(combined_input_text, str) or not combined_input_text.strip():
        print("Error: Missing or empty 'question' field in JSON payload.")
        return jsonify({"status": "error", "message": "Missing or empty 'question' field (should contain combined text)"}), 400

    print(f"Received combined input (start): {combined_input_text[:200]}...")

    prompt = f"{SYSTEM_INSTRUCTION}\n\n--- Combined User Input ---\n{combined_input_text}"
    print(f"\nSending final prompt to Gemini ({MODEL_NAME}) (truncated):\n---\n{prompt[:500]}...\n---")

    # --- Prepare API Payload ---
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        # "generationConfig": { # Keep commented out to use API defaults for now
        #    "temperature": 0.4,
        #    "responseMimeType": "text/plain"
        # },
        # "safetySettings": [ ... ] # Add if needed
    }
    headers = {'Content-Type': 'application/json'}

    # --- Call Gemini API ---
    response = None
    try:
        print(f"Attempting POST request to: {GEMINI_API_URL.split('?')[0]}") # Log URL without key
        response = requests.post(GEMINI_API_URL, headers=headers, json=payload, timeout=180) # Increased timeout just in case
        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
    except requests.exceptions.Timeout:
        print(f"Error: Gemini API ({MODEL_NAME}) request timed out after 180 seconds.")
        return jsonify({"status": "error", "message": "Gemini API request timed out"}), 504
    except requests.exceptions.RequestException as e:
        status_code = getattr(response, 'status_code', None)
        error_message = f"Request failed: {e}"
        http_status = 502 # Default Bad Gateway

        # Try to get more details from response if available
        error_detail = ""
        try:
            if response is not None:
                 error_detail = response.json().get('error', {}).get('message', '')
                 print(f"Raw Error Response Text: {response.text[:500]}") # Log raw error text
        except Exception as parse_err:
            print(f"Could not parse error response JSON: {parse_err}")
            if response is not None: print(f"Raw Error Response Text: {response.text[:500]}")

        if status_code:
             http_status = status_code # Use the actual status code if we have it
             if status_code == 429:
                 print("Error: Rate limit exceeded (429).")
                 error_message = f"Rate limit exceeded for Gemini API ({MODEL_NAME}). Please wait and try again. {error_detail}".strip()
             elif status_code == 401 or status_code == 403:
                 print(f"Error: Authentication/Permission issue ({status_code}). Check API Key.")
                 error_message = f"Authentication/Permission error ({status_code}) accessing Gemini API ({MODEL_NAME}). Check API Key. {error_detail}".strip()
             elif status_code == 400:
                 print(f"Error: Bad Request (400). Check prompt, model name, or API arguments.")
                 error_message = f"Bad Request (400) to Gemini API ({MODEL_NAME}). {error_detail}".strip()
             elif status_code == 404:
                  print(f"Error: Model Not Found (404). Check MODEL_NAME: {MODEL_NAME}")
                  error_message = f"Model '{MODEL_NAME}' not found or not supported (404). {error_detail}".strip()
             elif status_code == 413:
                  print("Error: Payload too large (413).")
                  error_message = f"Request payload too large (413) for Gemini API ({MODEL_NAME}). {error_detail}".strip()
             elif status_code == 500:
                  print("Error: Internal Server Error (500) from Gemini API.")
                  error_message = f"Internal Server Error (500) received from Gemini API ({MODEL_NAME}). {error_detail}".strip()
             elif status_code == 503:
                  print("Error: Service Unavailable (503) from Gemini API.")
                  error_message = f"Gemini API ({MODEL_NAME}) Service Unavailable (503). {error_detail}".strip()
             else: # Catch other 4xx/5xx errors
                 print(f"Error calling Gemini API ({MODEL_NAME}) with status {status_code}: {e}")
                 error_message = f"Error {status_code} calling Gemini API ({MODEL_NAME}). {error_detail}".strip()
        else:
            # Error likely happened before getting a response (e.g., DNS, connection refused)
            print(f"Error calling Gemini API ({MODEL_NAME}) - network/connection issue: {e}")
            error_message = f"Network or connection error calling Gemini API ({MODEL_NAME}): {e}"
            http_status = 503 # Service unavailable might be appropriate

        return jsonify({"status": "error", "message": error_message}), http_status

    # --- Parse Response & Extract Code ---
    try:
        gemini_data = response.json()
        # print(f"Raw Gemini JSON Response: {gemini_data}") # Uncomment for deep debugging

        full_answer_text = ""
        candidates = gemini_data.get('candidates') # Removed default []

        if not candidates:
             # Handle cases where the 'candidates' key might be missing entirely or null
             prompt_feedback = gemini_data.get('promptFeedback')
             if prompt_feedback and prompt_feedback.get('blockReason'):
                 block_reason = prompt_feedback['blockReason']
                 block_details = prompt_feedback.get('blockReasonMessage', 'No details provided.')
                 print(f"Error: Prompt blocked by Gemini. Reason: {block_reason}. Details: {block_details}")
                 return jsonify({"status": "error", "message": f"Prompt blocked by safety/policy settings: {block_reason}. {block_details}"}), 400
             else:
                 # Unknown state - no candidates and no clear block reason
                 print("Error: Gemini response missing 'candidates' array and no block reason found.")
                 print(f"Full Gemini Response: {gemini_data}")
                 return jsonify({"status": "error", "message": "Invalid response structure from Gemini (missing candidates)"}), 500

        if isinstance(candidates, list) and len(candidates) > 0:
            candidate = candidates[0]
            finish_reason = candidate.get('finishReason')

            if finish_reason == 'SAFETY':
                 safety_ratings = candidate.get('safetyRatings', [])
                 print(f"Error: Gemini response content blocked due to safety settings. Ratings: {safety_ratings}")
                 # Provide more specific feedback if possible
                 blocked_categories = [r['category'] for r in safety_ratings if r.get('probability') not in ['NEGLIGIBLE', 'LOW']]
                 message = f"Response content blocked by safety settings. Blocked categories: {', '.join(blocked_categories) if blocked_categories else 'details unavailable'}."
                 return jsonify({"status": "error", "message": message}), 400
            elif finish_reason == 'RECITATION':
                 print("Warning: Gemini response flagged for recitation.")
                 # Potentially still process, but log it.
            elif finish_reason not in ['STOP', 'MAX_TOKENS', None]: # None might occur, treat as success
                 print(f"Warning: Unusual finish reason '{finish_reason}'. Proceeding cautiously.")

            content = candidate.get('content', {})
            parts = content.get('parts', [])
            if parts and isinstance(parts, list) and len(parts) > 0:
                # Handle potential multi-part responses if needed, for now assume first part
                full_answer_text = parts[0].get('text', '').strip()
        else:
             # Candidates array is empty or not a list
             print("Error: 'candidates' array is empty or invalid in Gemini response.")
             print(f"Full Gemini Response: {gemini_data}")
             return jsonify({"status": "error", "message": "Invalid response structure from Gemini (empty or invalid candidates)"}), 500


        if not full_answer_text:
            print("Warning: No response text extracted from Gemini response candidates.")
            # Check if maybe the finish reason tells us why (e.g., MAX_TOKENS but empty?)
            finish_reason = candidates[0].get('finishReason', 'UNKNOWN') if candidates else 'UNKNOWN'
            if finish_reason == 'MAX_TOKENS':
                return jsonify({"status": "error", "message": "Received empty response, possibly due to reaching max output tokens."}), 500
            else:
                return jsonify({"status": "error", "message": "No response text received from Gemini"}), 500

        print(f"Full Gemini Response Text (truncated): {full_answer_text[:200]}...")
        code_pattern = r"```(?:python)?\s*\n(.*?)\n```"
        match = re.search(code_pattern, full_answer_text, re.DOTALL | re.IGNORECASE)
        extracted_code = None

        if match:
            extracted_code = match.group(1).strip()
            print(f"Extracted code block (truncated): {extracted_code[:100]}...")
        else:
            print("Warning: No markdown code block found. Checking fallback...")
            # Improved fallback: look for common Python start patterns but be cautious
            lines = full_answer_text.strip().splitlines()
            if lines and (lines[0].strip().startswith(('import ', 'def ', 'class ', 'from ', '#')) or \
                         (len(lines) > 1 and lines[1].strip().startswith(('import ', 'def ', 'class ', 'from ', '#')))): # Check first two lines
                print("Warning: Using fallback - assuming response starting with Python keywords is code.")
                extracted_code = full_answer_text.strip() # Take the whole thing
            else:
                print("Error: No Python code block found and fallback conditions not met.")
                print(f"Response Text that failed extraction: {full_answer_text[:500]}...")
                # Return the full text in the error message for debugging
                return jsonify({
                    "status": "error",
                    "message": "No Python code block found in the response.",
                    "full_response": full_answer_text # Include full text in error
                }), 400 # Use 400 as it's a client-side expectation failure

        if extracted_code is None: # Should technically not happen if logic above is correct, but safety check
             print("CRITICAL: extracted_code is None after extraction logic.")
             return jsonify({"status": "error", "message": "Internal server error during code extraction."}), 500

    except ValueError as e: # JSON decoding error
         print(f"Error decoding Gemini JSON response: {e}")
         print(f"Raw Response Status Code: {getattr(response, 'status_code', 'N/A')}")
         print(f"Raw Response Text (if available): {getattr(response, 'text', 'N/A')[:500]}")
         return jsonify({"status": "error", "message": "Error decoding response from Gemini API."}), 500
    except Exception as e:
        print(f"Error parsing response or extracting code: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Unexpected error processing Gemini response: {e}"}), 500

    # --- Copy to Clipboard ---
    try:
        pyperclip.copy(extracted_code)
        print("Successfully copied extracted code to clipboard.")
        clipboard_message_suffix = ""
    except pyperclip.PyperclipException as e: # Catch specific pyperclip errors
        print(f"ERROR copying to clipboard (PyperclipException): {e}")
        print(f"         Ensure a clipboard mechanism (like xclip/xsel on Linux, or pbcopy on macOS) is available.")
        print(f"         Extracted code (start): {extracted_code[:200]}...")
        clipboard_message_suffix = f" (Clipboard copy failed: {e})"
    except Exception as e: # Catch any other unexpected clipboard error
        print(f"ERROR copying to clipboard (Unexpected): {e}")
        print(f"         Extracted code (start): {extracted_code[:200]}...")
        clipboard_message_suffix = f" (Clipboard copy failed unexpectedly: {e})"


    # --- Return Final Success Response ---
    print("Process completed.")
    final_message = f"Code extracted and copied to clipboard{clipboard_message_suffix}"
    return jsonify({"status": "success", "message": final_message, "extracted_code_preview": extracted_code[:100]+"..."}) # Optionally add preview


# --- Run Flask App ---
if __name__ == '__main__':
    print("------------------------------------------")
    print("Starting Flask server for Gemini Context Builder")
    print(f"Using Gemini Model: {MODEL_NAME}")
    print(f"API Endpoint: {GEMINI_API_URL.split('?')[0]}")
    print("Listening on http://127.0.0.1:5000")
    if not GEMINI_API_KEY:
         print("WARNING: Server running without GEMINI_API_KEY!")
    else:
         # Avoid printing the key itself, just confirm it's loaded
         print("GEMINI_API_KEY loaded successfully.")
    # Turn off debug mode for production generally, but keep for testing
    use_debug = os.getenv('FLASK_DEBUG', 'True').lower() in ('true', '1', 't')
    print(f"Mode: {'Debug' if use_debug else 'Production'}")
    print("------------------------------------------")
    # Use reloader=False if you encounter issues with pyperclip in debug mode sometimes
    app.run(host='127.0.0.1', port=5000, debug=use_debug, use_reloader=False) # use_reloader=False can help with clipboard issues in debug