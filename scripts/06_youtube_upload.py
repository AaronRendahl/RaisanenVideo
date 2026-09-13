#!/usr/bin/env python3

# NEEDS TO RUN USING VIRTUAL ENVIRONMENT LIKE THIS:
# ./.venv/bin/python youtube_upload.py

import glob
import os
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Set to True to test filenames/titles without uploading. Set to False when ready to run for real!
DRY_RUN = False

# Select active dataset
#a = ["Raisanen-8mm-YouTube", "PLZU-iO-9yMMo"]
#a = ["Raisanen-1987a", "PLMk6OgsEIKZ0"]
a = ["Raisanen-1987-Willy-40th", "PLS3A71dZhi3k"]

VIDEO_DIR, PLAYLIST_ID = a

# Configurable variables
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
SECRETS_FILE = CREDENTIALS_DIR / "youtube_secrets.json"
TOKEN_FILE = CREDENTIALS_DIR / "token.json"

SCOPES = ["https://www.googleapis.com/auth/youtube"]

def authenticate():
    creds = None

    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except ValueError:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired authentication token...")
            creds.refresh(Request())
        else:
            print("No valid token found. Opening browser for OAuth login...")
            flow = InstalledAppFlow.from_client_secrets_file(
                SECRETS_FILE, SCOPES
            )
            creds = flow.run_local_server(
                port=8080, prompt="consent", access_type="offline"
            )

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
            print(f"Credentials saved to {TOKEN_FILE}")

    return build("youtube", "v3", credentials=creds)


def upload_video(youtube, file_path, title, raw_filename):

    if DRY_RUN:
        print(f"path:  {file_path}\ntitle: '{title}'\nfile:  {raw_filename}")
        return "MOCK_VIDEO_ID_123"

    body = {
        "snippet": {
            "title": title,
            "description": f"Original filename: {raw_filename}",
            "tags": [],
            "categoryId": "22",  # People & Blogs
        },
        "status": {
            "privacyStatus": "unlisted",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    print(f"  Finished upload! Video ID: {video_id}")
    return video_id


def add_to_playlist(youtube, video_id, playlist_id):

    if DRY_RUN:
        print(f"list:  {playlist_id}")
        return

    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {"kind": "youtube#video", "videoId": video_id},
        }
    }
    youtube.playlistItems().insert(part="snippet", body=body).execute()
    print(f"  Added to playlist {playlist_id}")


def main():
    if not os.path.exists(VIDEO_DIR):
        print(f"Error: Directory {VIDEO_DIR} does not exist.")
        return

    # Skip authenticating if doing a dry run to avoid opening browser unnecessarily
    youtube = None if DRY_RUN else authenticate()

    mp4_files = sorted(glob.glob(os.path.join(VIDEO_DIR, "*.mp4")))
    if not mp4_files:
        print(f"No .mp4 files found in {VIDEO_DIR}")
        return

    if DRY_RUN:
        print(f"[DRY RUN] Here's what this code will do...")
    
    for file_path in mp4_files:
        full_filename = os.path.basename(file_path)
        filename = re.sub(
            r"_YouTube(?=\.[^.]+$)", "", full_filename, flags=re.IGNORECASE
        )

        raw_title = os.path.splitext(filename)[0]
        # 1. Clean delimiters to spaces
        t = raw_title.replace("_", " ").replace("-", " ")
        # 2. Strip leading "Raisanen "
        t = re.sub(r"^Raisanen\s*", "", t, flags=re.IGNORECASE)
        # 3. Remove standalone 2-digit numbers and optional leading space, replacing with ": "
        title = re.sub(r"\s*\b\d{2}\b\s*", ": ", t).strip()

        print("=" * 50)
        print(f"Processing: {title}")
        print("=" * 50)

        try:
            video_id = upload_video(youtube, file_path, title, filename)
            add_to_playlist(youtube, video_id, PLAYLIST_ID)
        except Exception as e:
            print(f"Failed to upload {title}: {e}")

        print("")

    print("All videos processed successfully!")


if __name__ == "__main__":
    main()
