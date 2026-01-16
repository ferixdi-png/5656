# Топ-50 Критичных Проблем

**Всего найдено:** 357 проблем
**Топ-50:** 50 проблем

## 1. [P2] Performance

**Файл:** `app\services\generation_service_v2.py:17`

**Проблема:** HTTP request without timeout

**Код:**
```python
- Idempotent (duplicate requests return existing job)
```

**Исправление:** Add timeout parameter

---

## 2. [P2] Performance

**Файл:** `app\services\job_service_v2.py:35`

**Проблема:** HTTP request without timeout

**Код:**
```python
- Idempotent operations (duplicate requests handled gracefully)
```

**Исправление:** Add timeout parameter

---

## 3. [P2] Performance

**Файл:** `app\kie\client_v4.py:10`

**Проблема:** HTTP request without timeout

**Код:**
```python
import requests
```

**Исправление:** Add timeout parameter

---

## 4. [P2] Performance

**Файл:** `app\kie\client_v4.py:52`

**Проблема:** HTTP request without timeout

**Код:**
```python
retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
```

**Исправление:** Add timeout parameter

---

## 5. [P2] Performance

**Файл:** `app\kie\client_v4.py:55`

**Проблема:** HTTP request without timeout

**Код:**
```python
def _make_request(self, url: str, payload: Dict[str, Any]) -> requests.Response:
```

**Исправление:** Add timeout parameter

---

## 6. [P2] Performance

**Файл:** `app\kie\client_v4.py:67`

**Проблема:** HTTP request without timeout

**Код:**
```python
return requests.post(
```

**Исправление:** Add timeout parameter

---

## 7. [P2] Performance

**Файл:** `app\kie\client_v4.py:173`

**Проблема:** HTTP request without timeout

**Код:**
```python
except requests.RequestException as exc:
```

**Исправление:** Add timeout parameter

---

## 8. [P2] Performance

**Файл:** `app\kie\client_v4.py:187`

**Проблема:** HTTP request without timeout

**Код:**
```python
if isinstance(exc, requests.Timeout):
```

**Исправление:** Add timeout parameter

---

## 9. [P2] Performance

**Файл:** `app\kie\client_v4.py:189`

**Проблема:** HTTP request without timeout

**Код:**
```python
elif isinstance(exc, requests.ConnectionError):
```

**Исправление:** Add timeout parameter

---

## 10. [P2] Performance

**Файл:** `app\kie\client_v4.py:233`

**Проблема:** HTTP request without timeout

**Код:**
```python
requests.get,
```

**Исправление:** Add timeout parameter

---

## 11. [P2] Performance

**Файл:** `app\kie\error_handler.py:17`

**Проблема:** HTTP request without timeout

**Код:**
```python
import requests
```

**Исправление:** Add timeout parameter

---

## 12. [P2] Performance

**Файл:** `app\kie\error_handler.py:52`

**Проблема:** HTTP request without timeout

**Код:**
```python
if isinstance(exc, requests.ConnectionError):
```

**Исправление:** Add timeout parameter

---

## 13. [P2] Performance

**Файл:** `app\kie\error_handler.py:158`

**Проблема:** HTTP request without timeout

**Код:**
```python
except (requests.ConnectionError, requests.RequestException) as e:
```

**Исправление:** Add timeout parameter

---

## 14. [P2] Performance

**Файл:** `app\kie\error_handler.py:184`

**Проблема:** HTTP request without timeout

**Код:**
```python
def handle_api_response(response: requests.Response) -> dict:
```

**Исправление:** Add timeout parameter

---

## 15. [P2] Performance

**Файл:** `app\kie\error_handler.py:189`

**Проблема:** HTTP request without timeout

**Код:**
```python
response: requests.Response object
```

**Исправление:** Add timeout parameter

---

## 16. [P2] Performance

**Файл:** `app\kie\error_handler.py:255`

**Проблема:** HTTP request without timeout

**Код:**
```python
requests.post,
```

**Исправление:** Add timeout parameter

---

## 17. [P2] Performance

**Файл:** `app\kie\error_handler.py:266`

**Проблема:** HTTP request without timeout

**Код:**
```python
except requests.RequestException as e:
```

**Исправление:** Add timeout parameter

---

## 18. [P2] Performance

**Файл:** `app\kie\generator.py:684`

**Проблема:** HTTP request without timeout

**Код:**
```python
from aiohttp import ClientError
```

**Исправление:** Add timeout parameter

---

## 19. [P2] Performance

**Файл:** `app\kie\mock_client.py:4`

**Проблема:** HTTP request without timeout

**Код:**
```python
Returns fake responses without making real HTTP requests.
```

**Исправление:** Add timeout parameter

---

## 20. [P2] Performance

**Файл:** `app\kie\z_image_client.py:25`

**Проблема:** HTTP request without timeout

**Код:**
```python
import httpx
```

**Исправление:** Add timeout parameter

---

## 21. [P2] Performance

**Файл:** `app\delivery\coordinator.py:23`

**Проблема:** HTTP request without timeout

**Код:**
```python
import aiohttp
```

**Исправление:** Add timeout parameter

---

## 22. [P2] Performance

**Файл:** `app\delivery\coordinator.py:335`

**Проблема:** HTTP request without timeout

**Код:**
```python
except (TelegramAPIError, aiohttp.ClientError, asyncio.TimeoutError) as e1:
```

**Исправление:** Add timeout parameter

---

## 23. [P2] Performance

**Файл:** `app\delivery\coordinator.py:348`

**Проблема:** HTTP request without timeout

**Код:**
```python
except (TelegramAPIError, aiohttp.ClientError, asyncio.TimeoutError, OSError) as e2:
```

**Исправление:** Add timeout parameter

---

## 24. [P2] Performance

**Файл:** `app\delivery\coordinator.py:371`

**Проблема:** HTTP request without timeout

**Код:**
```python
except (TelegramAPIError, aiohttp.ClientError, asyncio.TimeoutError) as e:
```

**Исправление:** Add timeout parameter

---

## 25. [P2] Performance

**Файл:** `app\delivery\coordinator.py:389`

**Проблема:** HTTP request without timeout

**Код:**
```python
except (TelegramAPIError, aiohttp.ClientError, asyncio.TimeoutError) as e:
```

**Исправление:** Add timeout parameter

---

## 26. [P2] Performance

**Файл:** `bot\handlers\marketing.py:670`

**Проблема:** HTTP request without timeout

**Код:**
```python
# This prevents race conditions where two concurrent requests both pass the limit check
```

**Исправление:** Add timeout parameter

---

## 27. [P1] Error Handling

**Файл:** `app\database\services.py:57`

**Проблема:** Silent exception handling without logging

**Код:**
```python
except Exception:
```

**Исправление:** Add logging with exc_info=True before pass

---

## 28. [P1] Idempotency

**Файл:** `app\database\services.py:591`

**Проблема:** INSERT without ON CONFLICT for idempotency

**Код:**
```python
INSERT INTO jobs (user_id, model_id, category, input_json, price_rub,
```

**Исправление:** Add ON CONFLICT (ref) DO NOTHING

---

## 29. [P1] Input Validation

**Файл:** `app\database\services.py:308`

**Проблема:** Missing validation for user_id parameter

**Код:**
```python
async def hold(self, user_id: int, amount_rub: Decimal,
```

**Исправление:** Add: if not isinstance(user_id, int) or user_id <= 0: raise ValueError

---

## 30. [P1] Input Validation

**Файл:** `app\database\services.py:395`

**Проблема:** Missing validation for user_id parameter

**Код:**
```python
async def charge(self, user_id: int, amount_rub: Decimal,
```

**Исправление:** Add: if not isinstance(user_id, int) or user_id <= 0: raise ValueError

---

## 31. [P1] Idempotency

**Файл:** `app\services\job_service_v2.py:194`

**Проблема:** INSERT without ON CONFLICT for idempotency

**Код:**
```python
INSERT INTO jobs (
```

**Исправление:** Add ON CONFLICT (ref) DO NOTHING

---

## 32. [P1] Input Validation

**Файл:** `app\storage\base.py:264`

**Проблема:** Missing validation for user_id parameter

**Код:**
```python
async def release_balance_reserve(
```

**Исправление:** Add: if not isinstance(user_id, int) or user_id <= 0: raise ValueError

---

## 33. [P1] Error Handling

**Файл:** `app\storage\json_storage.py:729`

**Проблема:** Silent exception handling without logging

**Код:**
```python
except Exception:
```

**Исправление:** Add logging with exc_info=True before pass

---

## 34. [P1] Input Validation

**Файл:** `app\storage\json_storage.py:630`

**Проблема:** Missing validation for user_id parameter

**Код:**
```python
async def release_balance_reserve(self, user_id: int, task_id: str, model_id: str) -> bool:
```

**Исправление:** Add: if not isinstance(user_id, int) or user_id <= 0: raise ValueError

---

## 35. [P1] Error Handling

**Файл:** `app\storage\migrations.py:101`

**Проблема:** Silent exception handling without logging

**Код:**
```python
except Exception:
```

**Исправление:** Add logging with exc_info=True before pass

---

## 36. [P1] Error Handling

**Файл:** `app\storage\migrations.py:122`

**Проблема:** Silent exception handling without logging

**Код:**
```python
except Exception:
```

**Исправление:** Add logging with exc_info=True before pass

---

## 37. [P1] Error Handling

**Файл:** `app\storage\migrations.py:135`

**Проблема:** Silent exception handling without logging

**Код:**
```python
except Exception:
```

**Исправление:** Add logging with exc_info=True before pass

---

## 38. [P1] Error Handling

**Файл:** `app\storage\migrations.py:150`

**Проблема:** Silent exception handling without logging

**Код:**
```python
except Exception:
```

**Исправление:** Add logging with exc_info=True before pass

---

## 39. [P1] Input Validation

**Файл:** `app\storage\pg_storage.py:1584`

**Проблема:** Missing validation for user_id parameter

**Код:**
```python
async def release_balance_reserve(
```

**Исправление:** Add: if not isinstance(user_id, int) or user_id <= 0: raise ValueError

---

## 40. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:71`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
@router.callback_query(F.data == "admin_stats")
```

**Исправление:** Add: if not message.from_user: return

---

## 41. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:129`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
await callback.message.edit_text(text, reply_markup=keyboard)
```

**Исправление:** Add: if not message.from_user: return

---

## 42. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:132`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
@router.callback_query(F.data == "admin_cleanup")
```

**Исправление:** Add: if not message.from_user: return

---

## 43. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:149`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
@router.message(Command("admin_stats"))
```

**Исправление:** Add: if not message.from_user: return

---

## 44. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:188`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
logger.info("Admin %s requested 24h stats", message.from_user.id)
```

**Исправление:** Add: if not message.from_user: return

---

## 45. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:201`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
@router.message(Command("admin_user"))
```

**Исправление:** Add: if not message.from_user: return

---

## 46. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:246`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
logger.info("Admin %s requested user info for %s", message.from_user.id, user_id)
```

**Исправление:** Add: if not message.from_user: return

---

## 47. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:261`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
@router.message(Command("admin_ops_snapshot"))
```

**Исправление:** Add: if not message.from_user: return

---

## 48. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:312`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
logger.info("Admin %s requested ops snapshot", message.from_user.id)
```

**Исправление:** Add: if not message.from_user: return

---

## 49. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:323`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
@router.message(Command("admin_toggle_model"))
```

**Исправление:** Add: if not message.from_user: return

---

## 50. [P1] Null Safety

**Файл:** `bot\handlers\admin.py:357`

**Проблема:** Missing None check before accessing Telegram object attribute

**Код:**
```python
logger.info("Admin %s toggled model %s -> %s", message.from_user.id, model_id, action)
```

**Исправление:** Add: if not message.from_user: return

---

