"""Проверка KIE API ключа"""
import os
from dotenv import load_dotenv
load_dotenv()

from kie_client import KIEClient

client = KIEClient()
if client.api_key:
    print(f"API Key установлен: Да")
    print(f"API Key длина: {len(client.api_key)}")
    print(f"API Key первые 10 символов: {client.api_key[:10]}...")
    print(f"Base URL: {client.base_url}")
else:
    print("API Key установлен: Нет")
