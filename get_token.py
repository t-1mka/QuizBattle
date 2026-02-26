#!/usr/bin/env python3
import os
import json
import uuid
import requests
import time
import urllib3
import threading
from datetime import datetime, timedelta
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv()

def get_gigachat_token():
    auth_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
    scope = 'GIGACHAT_API_PERS'
    credentials = os.getenv('GIGACHAT_CREDENTIALS')
    
    if not credentials:
        return None
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json',
        'RqUID': str(uuid.uuid4()),
        'Authorization': f'Basic {credentials}'
    }
    
    data = f'scope={scope}'
    
    try:
        response = requests.post(auth_url, headers=headers, data=data, timeout=30, verify=False)
        
        if response.status_code == 200:
            token_info = response.json()
            access_token = token_info['access_token']
            expires_at_timestamp = token_info['expires_at']
            expires_at = datetime.fromtimestamp(expires_at_timestamp / 1000)
            env_file = '.env'
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    lines = f.readlines()
                
                updated_lines = []
                token_updated = False
                for line in lines:
                    if line.startswith('GIGACHAT_TOKEN='):
                        updated_lines.append(f'GIGACHAT_TOKEN={access_token}\n')
                        token_updated = True
                    else:
                        updated_lines.append(line)
                
                if not token_updated:
                    updated_lines.append(f'GIGACHAT_TOKEN={access_token}\n')
                
                with open(env_file, 'w') as f:
                    f.writelines(updated_lines)
            
            return access_token
        else:
            return None
        
    except Exception:
        return None

def auto_refresh_token():
    while True:
        time.sleep(1600) 
        if get_gigachat_token():
            print("🔄 Токен обновлен")

if __name__ == "__main__":
    token = get_gigachat_token()
    
    if token:
        print("✅ Токен получен и сохранен")
        refresh_thread = threading.Thread(target=auto_refresh_token, daemon=True)
        refresh_thread.start()
        print("🔄 Автообновление токена запущено")
    else:
        print("❌ Не удалось получить токен")
