import json
import os

def convert_cookies(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"Error: {input_path} not found.")
        return

    with open(input_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(f"Error: {input_path} is not a valid JSON file.")
            return

    # If it's already in storageState format, just check it
    if isinstance(data, dict) and "cookies" in data:
        print("Format is already in storageState format.")
        return

    # If it's a list (standard cookie export), wrap it
    if isinstance(data, list):
        new_cookies = []
        for c in data:
            # Map expirationDate -> expires
            new_c = {
                "name": c.get("name"),
                "value": c.get("value"),
                "domain": c.get("domain"),
                "path": c.get("path"),
                "httpOnly": c.get("httpOnly", False),
                "secure": c.get("secure", False),
                "sameSite": "None" if c.get("sameSite") == "no_restriction" else (c.get("sameSite", "Lax").capitalize() if c.get("sameSite") else "Lax")
            }
            if "expirationDate" in c:
                new_c["expires"] = c["expirationDate"]
            
            # Map sameSite 'unspecified' or others to something valid for Playwright
            if new_c["sameSite"] not in ["Lax", "Strict", "None"]:
                new_c["sameSite"] = "Lax"

            new_cookies.append(new_c)

        storage_state = {
            "cookies": new_cookies,
            "origins": []
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(storage_state, f, indent=2)
        print(f"Successfully converted cookies to {output_path}")

if __name__ == "__main__":
    convert_cookies("data/cookies.json", "data/cookies.json")
