import urllib.request
import json
import ssl

def test_openrouter():
    key = "your-openrouter-api-key-here"
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost",
        "X-Title": "SheetAgent"
    }
    payload = {
        "model": "nvidia/llama-3.1-nemotron-70b-instruct",
        "messages": [{"role": "user", "content": "Reply with 'OpenRouter is working!'"}]
    }
    
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        with urllib.request.urlopen(req, context=ctx) as response:
            print("Status:", response.status)
            print("Response:", response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print(f"HTTPError: {e.code} {e.reason}")
        print("Body:", e.read().decode('utf-8'))
    except Exception as e:
        print("Error:", str(e))

if __name__ == "__main__":
    test_openrouter()
