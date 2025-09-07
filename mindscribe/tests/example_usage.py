#!/usr/bin/env python3
"""
Примеры использования новой структурированной схемы MindScribe
"""

import json
import requests

# Базовый URL для API (замените на ваш)
API_URL = "https://your-mindscribe-api.com"

def example_get_structured_summaries():
    """Пример получения структурированных саммари"""
    
    payload = {
        "session_id": "session_123",
        "action": "get",
        "summary_type": "L1",
        "role": "user", 
        "structured": True
    }
    
    response = requests.post(API_URL, json=payload)
    data = response.json()
    
    if data.get("format") == "structured":
        print("Получены структурированные данные:")
        for summary in data.get("summaries", []):
            print(f"ID: {summary['id']}")
            print(f"Саммари: {summary['summary_text']}")
            print(f"Ключевые точки: {summary['key_points']}")
            print(f"Основные темы: {summary['main_themes']}")
            print(f"Наблюдения: {summary['insights']}")
            print(f"Язык: {summary['language']}")
            print("-" * 50)

def example_process_and_get():
    """Пример обработки сессии и получения результатов в новом формате"""
    
    payload = {
        "session_id": "session_456",
        "user_id": "user_789",
        "summary_type": "LALL",
        "role": "assistant",
        "structured": True
    }
    
    response = requests.post(API_URL, json=payload)
    data = response.json()
    
    print(f"Обработка завершена: {data['message']}")
    
    if "summaries" in data and data.get("format") == "structured":
        print("Результаты в структурированном формате:")
        for summary in data["summaries"]:
            print(f"Саммари: {summary['summary_text']}")
            print(f"Количество ключевых точек: {len(summary['key_points'])}")
            print(f"Количество тем: {len(summary['main_themes'])}")
            print(f"Количество наблюдений: {len(summary['insights'])}")

def example_legacy_compatibility():
    """Пример обратной совместимости со старым форматом"""
    
    payload = {
        "session_id": "session_789", 
        "action": "get",
        "summary_type": "L2",
        "role": "user"
        # structured не указан, используется legacy формат
    }
    
    response = requests.post(API_URL, json=payload)
    data = response.json()
    
    if data.get("format") == "legacy":
        print("Получены данные в legacy формате:")
        for summary in data.get("summaries", []):
            # Используем новые структурированные поля
            print(f"Саммари: {summary.get('summary_text', 'N/A')}")
            
            # Обрабатываем JSONB поля
            key_points = summary.get('key_points', '[]')
            if isinstance(key_points, str):
                key_points = json.loads(key_points)
            print(f"Ключевые точки: {key_points}")
            
            main_themes = summary.get('main_themes', '[]')
            if isinstance(main_themes, str):
                main_themes = json.loads(main_themes)
            print(f"Основные темы: {main_themes}")
            
            # Если доступен content для обратной совместимости
            if 'content' in summary:
                try:
                    content_data = json.loads(summary["content"])
                    print(f"Legacy content саммари: {content_data.get('summary', 'N/A')}")
                except json.JSONDecodeError:
                    print(f"Legacy raw content: {summary['content'][:100]}...")

if __name__ == "__main__":
    print("Примеры использования MindScribe с новой схемой БД (без content column)")
    print("=" * 70)
    
    # Раскомментируйте нужные примеры:
    # example_get_structured_summaries()
    # example_process_and_get() 
    # example_legacy_compatibility()
    
    print("Примеры готовы к использованию!")
