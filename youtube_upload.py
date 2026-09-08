# NEEDS TO RUN USING VIRTUAL ENVIRONMENT LIKE THIS:
# ./.venv/bin/python youtube_upload.py

## CHANGE FOR EACH PLAYLIST!
VIDEO_DIR = "./Raisanen-8mm-YouTube1"
PLAYLIST_ID = "PLZU-iO-9yMMo"

import os
import glob
import re
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configurable variables
SECRETS_FILE = "youtube_secrets.json"
TOKEN_FILE = "token.json"  # Saved credentials token
SCOPES = ["https://www.googleapis.com/auth/youtube"]

def authenticate():
    creds = None
    
    # 1. Load existing token if available
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except ValueError:
            # Token file was corrupted or missing refresh_token
            creds = None
    
    # 2. If no valid credentials, refresh or prompt browser login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Refreshing expired authentication token...")
            creds.refresh(Request())
        else:
            print("No valid token found. Opening browser for OAuth login...")
            flow = InstalledAppFlow.from_client_secrets_file(SECRETS_FILE, SCOPES)
            
            # Force Google to issue a refresh_token and show consent screen
            creds = flow.run_local_server(
                port=8080,
                prompt="consent",
                access_type="offline"
            )
        
        # 3. Save credentials for future script runs
        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
            print(f"Credentials saved to {TOKEN_FILE}")

    return build("youtube", "v3", credentials=creds)

def upload_video(youtube, file_path, title, raw_filename):
    body = {
        "snippet": {
            "title": title,
            "description": f"Original filename: {raw_filename}",
            "tags": [],
            "categoryId": "22"  # People & Blogs
        },
        "status": {
            "privacyStatus": "unlisted",
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
    
    print(f"Uploading {title}...")
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
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
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id
            }
        }
    }
    youtube.playlistItems().insert(part="snippet", body=body).execute()
    print(f"  Added to playlist {playlist_id}")

def main():
    if not os.path.exists(VIDEO_DIR):
        print(f"Error: Directory {VIDEO_DIR} does not exist.")
        return

    youtube = authenticate()

    mp4_files = sorted(glob.glob(os.path.join(VIDEO_DIR, "*.mp4")))
    if not mp4_files:
        print(f"No .mp4 files found in {VIDEO_DIR}")
        return

    for file_path in mp4_files:
        full_filename = os.path.basename(file_path)
        filename = re.sub(r"_YouTube(?=\.[^.]+$)", "", full_filename, flags=re.IGNORECASE)
        
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
