import requests
import load_dotenv
import os
import sys

load_dotenv.load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
DEPOSITION_ID = "18786215"

pdf_path = "../kubook/book/kubernetes-system-design.pdf"

if not os.path.exists(pdf_path):
    print(f"Error: PDF file not found at {pdf_path}")
    print("Please build the book first using: mdbook build kubook")
    sys.exit(1)

headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
r = requests.get(f'https://zenodo.org/api/deposit/depositions/{DEPOSITION_ID}',
                 headers=headers)

if r.status_code != 200:
    print(f"Error getting deposition: {r.status_code}")
    print(r.json())
    sys.exit(1)

bucket_url = r.json()["links"]["bucket"]
print(f"Bucket URL: {bucket_url}")

filename = "kubernetes-system-design.pdf"

with open(pdf_path, "rb") as fp:
    r = requests.put(
        f"{bucket_url}/{filename}",
        data=fp,
        headers=headers,
    )

if r.status_code in [200, 201]:
    print(f"Successfully uploaded {filename}")
    print(f"Response: {r.json()}")
else:
    print(f"Upload failed with status {r.status_code}")
    print(r.json())
    sys.exit(1)

print(f"View your deposition at: https://zenodo.org/deposit/{DEPOSITION_ID}")
