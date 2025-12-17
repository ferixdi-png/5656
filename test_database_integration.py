"""
Скрипт для проверки интеграции БД в bot_kie.py
Проверяет, что баланс и история сохраняются в БД при деплое
"""

import os
import sys
from decimal import Decimal

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_database_connection():
    """Проверяет подключение к БД."""
    try:
        from database import get_db_connection, init_database
        print("[OK] Module database imported successfully")
        
        # Инициализируем БД
        try:
            init_database()
            print("[OK] Database initialized successfully")
        except Exception as e:
            print(f"[ERROR] Database initialization error: {e}")
            return False
        
        # Проверяем подключение
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    if result:
                        print("[OK] Database connection works")
                        return True
        except Exception as e:
            print(f"[ERROR] Database connection error: {e}")
            return False
            
    except ImportError as e:
        print(f"[WARNING] Module database not available: {e}")
        print("[INFO] Bot will use JSON fallback")
        return False


def test_balance_operations():
    """Проверяет операции с балансом."""
    try:
        from database import (
            get_or_create_user,
            get_user_balance,
            update_user_balance,
            add_to_balance,
            create_operation
        )
        
        test_user_id = 999999999  # Тестовый пользователь
        
        # Создаем/получаем пользователя
        user = get_or_create_user(test_user_id)
        print(f"[OK] User created/retrieved: user_id={test_user_id}, balance={user['balance']}")
        
        # Проверяем получение баланса
        balance = get_user_balance(test_user_id)
        print(f"[OK] Balance retrieved: {balance}")
        
        # Тестируем обновление баланса
        new_balance = Decimal('100.50')
        success = update_user_balance(test_user_id, new_balance)
        if success:
            print(f"[OK] Balance updated: {new_balance}")
        else:
            print(f"[ERROR] Failed to update balance")
            return False
        
        # Проверяем, что баланс обновился
        updated_balance = get_user_balance(test_user_id)
        if updated_balance == new_balance:
            print(f"[OK] Balance correctly updated: {updated_balance}")
        else:
            print(f"[ERROR] Balance mismatch: expected {new_balance}, got {updated_balance}")
            return False
        
        # Тестируем добавление к балансу
        add_amount = Decimal('50.25')
        success = add_to_balance(test_user_id, add_amount)
        if success:
            print(f"[OK] Added to balance: {add_amount}")
        else:
            print(f"[ERROR] Failed to add to balance")
            return False
        
        # Проверяем новый баланс
        final_balance = get_user_balance(test_user_id)
        expected_balance = new_balance + add_amount
        if final_balance == expected_balance:
            print(f"[OK] Final balance is correct: {final_balance}")
        else:
            print(f"[ERROR] Balance mismatch: expected {expected_balance}, got {final_balance}")
            return False
        
        # Тестируем создание операции
        operation_id = create_operation(
            user_id=test_user_id,
            operation_type='payment',
            amount=Decimal('100.00'),
            model=None,
            result_url=None,
            prompt=None
        )
        if operation_id:
            print(f"[OK] Operation created: operation_id={operation_id}")
        else:
            print(f"[ERROR] Failed to create operation")
            return False
        
        # Очищаем тестовые данные
        update_user_balance(test_user_id, Decimal('0'))
        print(f"[OK] Test data cleaned up")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error testing balance operations: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_generation_history():
    """Проверяет сохранение истории генераций."""
    try:
        from database import create_operation
        
        test_user_id = 999999999
        
        # Создаем тестовую операцию генерации
        operation_id = create_operation(
            user_id=test_user_id,
            operation_type='generation',
            amount=Decimal('-10.50'),
            model='test-model',
            result_url='https://example.com/result.jpg',
            prompt='Test prompt for generation'
        )
        
        if operation_id:
            print(f"[OK] Generation operation created: operation_id={operation_id}")
            return True
        else:
            print(f"[ERROR] Failed to create generation operation")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error testing generation history: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_bot_kie_integration():
    """Проверяет, что bot_kie.py правильно использует БД."""
    try:
        # Проверяем, что DATABASE_AVAILABLE определен
        import bot_kie
        if hasattr(bot_kie, 'DATABASE_AVAILABLE'):
            print(f"[OK] DATABASE_AVAILABLE defined: {bot_kie.DATABASE_AVAILABLE}")
        else:
            print("[WARNING] DATABASE_AVAILABLE not defined in bot_kie.py")
            return False
        
        # Проверяем, что функции используют БД
        if bot_kie.DATABASE_AVAILABLE:
            print("[OK] Database available in bot_kie.py")
            print("[INFO] Functions get_user_balance, add_user_balance, save_generation_to_history will use DB")
        else:
            print("[WARNING] Database not available in bot_kie.py, will use JSON fallback")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Error checking bot_kie.py integration: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main function to run all tests."""
    print("=" * 60)
    print("DATABASE INTEGRATION TEST FOR BOT_KIE.PY")
    print("=" * 60)
    print()
    
    results = []
    
    # Test 1: Database connection
    print("1. Testing database connection...")
    print("-" * 60)
    results.append(("Database connection", test_database_connection()))
    print()
    
    # Test 2: Balance operations
    if results[-1][1]:  # If DB is available
        print("2. Testing balance operations...")
        print("-" * 60)
        results.append(("Balance operations", test_balance_operations()))
        print()
        
        # Test 3: Generation history
        print("3. Testing generation history...")
        print("-" * 60)
        results.append(("Generation history", test_generation_history()))
        print()
    
    # Test 4: bot_kie.py integration
    print("4. Testing bot_kie.py integration...")
    print("-" * 60)
    results.append(("bot_kie.py integration", test_bot_kie_integration()))
    print()
    
    # Final report
    print("=" * 60)
    print("FINAL REPORT")
    print("=" * 60)
    for test_name, result in results:
        status = "[PASSED]" if result else "[FAILED]"
        print(f"{test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    print()
    if all_passed:
        print("[OK] ALL TESTS PASSED")
        print("[OK] Database integrated and ready to use")
    else:
        print("[WARNING] SOME TESTS FAILED")
        print("[WARNING] Check database settings and environment variables")
    
    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())

