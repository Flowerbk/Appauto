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
the_t = 5
end_date1 = datetime.date(2028, 6, 28)
def resource_path(relative_path):
    """ Lấy đường dẫn tuyệt đối đến tài nguyên (cho cả script và exe) """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def authenticate():
    creds = None
    # SỬA TẠI ĐÂY: Dùng resource_path cho credentials.json
    #token_path = resource_path(os.path.join("assets", "token.json"))
    #creds_path = resource_path(os.path.join("assets", "credentials.json"))
    # 1. Nhúng nội dung credentials.json
    CLIENT_CONFIG = {"installed":{"client_id":"535452856280-hmv3kut6gf9od70fmjohq95p3510kocb.apps.googleusercontent.com","project_id":"united-yeti-482813-q5","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","client_secret":"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","redirect_uris":["http://localhost"]}}

    # 2. Nhúng nội dung token.json hiện tại của bạn
    TOKEN_DATA = {"token": "ya29.a0Aa7pCA_ZSKNMywDKqSJ0g3yTsX9II4d6YdXfFti3D8lvJFSiOAK6ass3r_WR0Jpw0MsJ14ts2KC-7aM_ocsnlKlQavnbS74TpvF3nN3ONrmv7TC6oRkIJ_o9L9n--Y1L50Wi9Bw4F-Yby5vti5jYu3XGaZC2VFnCvUEyz8zdUbW7jC_DmIKUFJ6uwQgBC1lLhivwaIsaCgYKARgSARYSFQHGX2MioD7yu1xPR4cocXfDBvdJ9w0206", "refresh_token": "1//0eZLATcQ9nUJsCgYIARAAGA4SNwF-L9Ir37_xqcTw2vQN5wM_z8YK7z83P87QJD9gcLTEeDwthVPplXfCTDdI3IBkFyGEaVn5wvc", "token_uri": "https://oauth2.googleapis.com/token", "client_id": "535452856280-hmv3kut6gf9od70fmjohq95p3510kocb.apps.googleusercontent.com", "client_secret": "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", "scopes": ["https://www.googleapis.com/auth/drive"], "universe_domain": "googleapis.com", "account": "", "expiry": "2025-12-30T21:44:53Z"}

    # Khởi tạo Credentials từ dữ liệu nhúng
    creds = Credentials.from_authorized_user_info(TOKEN_DATA, SCOPES)
    
    # Kiểm tra và làm mới token nếu cần
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_config(CLIENT_CONFIG, SCOPES)
            creds = flow.run_local_server(port=0)
        # Lưu lại token cho lần chạy sau
        #with open('token.json', 'w') as token:
            #token.write(creds.to_json())    
        # Lưu ý: Khi token được làm mới, dữ liệu mới sẽ chỉ nằm trong bộ nhớ.
        # Nếu muốn lưu lại cho lần sau mà không phải đăng nhập lại, 
        # bạn vẫn nên có cơ chế ghi ra file vật lý.

    return build('drive', 'v3', credentials=creds)

def check_exists(service, name, parent_id=None, is_folder=False):
    """Kiểm tra sự tồn tại trên Drive."""
    query = f"name = '{name}' and trashed = false"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    if is_folder:
        query += " and mimeType = 'application/vnd.google-apps.folder'"
    else:
        query += " and mimeType != 'application/vnd.google-apps.folder'"
    
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
    """Tải thư mục lên Drive (có kiểm tra trùng)."""
    item_name = os.path.basename(local_path)
    drive_item_id = check_exists(service, item_name, drive_parent_id, is_folder=True)
    
    if not drive_item_id:
        file_metadata = {
            'name': item_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [drive_parent_id]
        }
        file = service.files().create(body=file_metadata, fields='id').execute()
        drive_item_id = file.get('id')
        #print(f"Đã tạo thư mục: {item_name}")
    #else:
        #print(f"Thư mục đã có: {item_name}, kiểm tra nội dung...")

    for item in os.listdir(local_path):
        item_path = os.path.join(local_path, item)
        if os.path.isfile(item_path):
            if not check_exists(service, item, drive_item_id, is_folder=False):
                file_metadata = {'name': item, 'parents': [drive_item_id]}
                media = MediaFileUpload(item_path, resumable=True)
                service.files().create(body=file_metadata, media_body=media).execute()
                #print(f"  -> Uploaded: {item}")
            #else:
                #print(f"  -> Skipped: {item}")
        elif os.path.isdir(item_path):
            upload_directory(service, item_path, drive_item_id)

def run_backup_process():
    # 1. Khởi tạo dịch vụ
    #print("Đang xác thực Google Drive...")
    service = authenticate()
    pictures_path = str(Path.home() / "Pictures")
    # 2. Xác định thư mục đích trên Drive (theo tên PC User)
    user_drive_id = get_or_create_user_folder(service)
    
    # 3. Danh sách các thư mục cần upload từ file này
    #the_t = 3
    my_folders = [
        r'C:\Ersports\Summary',
        r'C:\Ersports\Summary2',
        r'C:\Ersports\ER.xlsx',
        #pictures_path
    ]
    
    # 4. Chạy vòng lặp upload
    for folder_path in my_folders:
        if os.path.exists(folder_path):
            #print(f"\nĐang xử lý thư mục: {folder_path}")
            upload_directory(service, folder_path, user_drive_id)
        #else:
            #print(f"Lỗi: Không tìm thấy đường dẫn {folder_path}")
    #print(f"--->")
if __name__ == '__main__':
    LIST_OF_PATHS = [
        r'C:\Ersports\Summary',
        r'C:\Ersports\Summary2',
    ]
    
    service = authenticate()
    
    # 1. Lấy hoặc tạo thư mục theo tên User máy tính
    user_drive_folder_id = get_or_create_user_folder(service)
    
    # 2. Tải các mục vào thư mục User đó
    for path in LIST_OF_PATHS:
        if os.path.exists(path):
            print(f"\nBắt đầu tải mục: {path}")
            upload_directory(service, path, user_drive_folder_id)
        else:
            print(f"\n[Lỗi] Không tìm thấy: {path}")
            

    print("\nHoàn tất!")








