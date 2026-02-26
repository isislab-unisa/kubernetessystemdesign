#!/usr/bin/env python3
import requests
import os
import sys
import argparse

def upload_to_zenodo(pdf_path, access_token, deposition_id):
    """
    Upload a PDF file to a Zenodo deposition.

    Args:
        pdf_path: Path to the PDF file
        access_token: Zenodo API access token
        deposition_id: Zenodo deposition ID

    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(pdf_path):
        print(f"PDF file not found at {pdf_path}")
        return False

    print(f"PDF file found: {pdf_path}")
    file_size = os.path.getsize(pdf_path) / (1024 * 1024)
    print(f"File size: {file_size:.2f} MB")

    headers = {'Authorization': f'Bearer {access_token}'}
    print(f"🔍 Fetching deposition {deposition_id}...")

    r = requests.get(f'https://zenodo.org/api/deposit/depositions/{deposition_id}',
                     headers=headers)

    if r.status_code != 200:
        print(f"Error getting deposition: HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return False

    deposition = r.json()
    bucket_url = deposition["links"]["bucket"]
    filename = os.path.basename(pdf_path)

    with open(pdf_path, "rb") as fp:
        r = requests.put(
            f"{bucket_url}/{filename}",
            data=fp,
            headers=headers,
        )

    if r.status_code in [200, 201]:
        print(f"Successfully uploaded {filename}")
        upload_info = r.json()
        print(f"   - Checksum: {upload_info.get('checksum', 'N/A')}")
        print(f"   - File ID: {upload_info.get('id', 'N/A')}")
        print(f"   - Size: {upload_info.get('filesize', 'N/A')} bytes")
    else:
        print(f"Upload failed with HTTP {r.status_code}")
        print(f"Response: {r.text}")
        return False

    print(f"View your deposition at: https://zenodo.org/deposit/{deposition_id}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Upload PDF to Zenodo deposition for GitHub Actions'
    )
    parser.add_argument(
        '--pdf',
        type=str,
        default='kubook/book/kubernetes-system-design.pdf',
        help='Path to the PDF file (default: kubook/book/kubernetes-system-design.pdf)'
    )
    parser.add_argument(
        '--deposition-id',
        type=str,
        default='18786215',
        help='Zenodo deposition ID (default: 18786215)'
    )

    args = parser.parse_args()

    # Get access token from environment
    access_token = os.getenv('ZENODO_TOKEN')
    if not access_token:
        print("❌ Error: ZENODO_TOKEN environment variable not set")
        print("Please set it in GitHub Secrets and pass it to the action")
        sys.exit(1)

    # Upload to Zenodo
    success = upload_to_zenodo(args.pdf, access_token, args.deposition_id)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()
