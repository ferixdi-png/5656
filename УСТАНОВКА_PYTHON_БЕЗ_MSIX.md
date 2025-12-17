# Установка Python без MSIX (альтернативные способы)

## Способ 1: Официальный установщик Python.org (РЕКОМЕНДУЕТСЯ)

1. **Скачайте Python напрямую:**
   - Перейдите на: https://www.python.org/downloads/
   - Нажмите большую желтую кнопку "Download Python 3.x.x"
   - Это скачает файл `.exe` (НЕ MSIX!)

2. **Установите Python:**
   - Запустите скачанный `.exe` файл
   - **ВАЖНО:** В самом начале установки отметьте галочку **"Add Python to PATH"**
   - Нажмите "Install Now"
   - Дождитесь завершения установки

3. **Проверьте установку:**
   - Откройте новый терминал (закройте старый и откройте новый)
   - Выполните: `python --version`
   - Должна показаться версия Python

## Способ 2: Через winget (Windows Package Manager)

Если у вас Windows 10/11 с обновлениями:

```powershell
winget install Python.Python.3.12
```

Или для Python 3.11:
```powershell
winget install Python.Python.3.11
```

## Способ 3: Через Chocolatey (если установлен)

```powershell
choco install python --version=3.12
```

## Способ 4: Портативная версия Python (без установки)

1. Скачайте портативную версию:
   - https://www.python.org/downloads/windows/
   - Выберите "Windows embeddable package" (64-bit)
   - Распакуйте в папку, например: `C:\Python312`

2. Добавьте в PATH вручную:
   - Нажмите `Win + R`, введите `sysdm.cpl`, нажмите Enter
   - Вкладка "Дополнительно" → "Переменные среды"
   - В "Системные переменные" найдите `Path`, нажмите "Изменить"
   - Нажмите "Создать" и добавьте: `C:\Python312`
   - Нажмите "Создать" и добавьте: `C:\Python312\Scripts`
   - Нажмите OK везде
   - Перезапустите VS Code

## Способ 5: Использовать уже установленный Python

Если Python уже установлен, но не в PATH:

1. Найдите где установлен Python:
   - Обычно: `C:\Users\ВашеИмя\AppData\Local\Programs\Python\`
   - Или: `C:\Program Files\Python312\`
   - Или: `C:\Python312\`

2. Добавьте в PATH (см. Способ 4, шаг 2)

3. Или используйте полный путь в скриптах:
   ```powershell
   C:\Python312\python.exe -m pip install -r requirements.txt
   ```

## После установки Python

1. **Перезапустите VS Code** (важно!)

2. **Установите зависимости:**
   ```powershell
   python -m pip install -r requirements.txt
   ```

3. **Или используйте готовый скрипт:**
   ```powershell
   powershell -ExecutionPolicy Bypass -File setup_python.ps1
   ```

## Проверка установки

Откройте новый терминал и выполните:
```powershell
python --version
pip --version
```

Если обе команды работают - Python установлен правильно!







