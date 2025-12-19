# PowerShell скрипт для экстренной разблокировки токена Telegram бота
# Удаляет webhook и очищает очередь апдейтов

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "🔓 Разблокировка токена Telegram бота" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Проверка наличия токена
if (-not $env:BOT_TOKEN) {
    Write-Host "❌ Ошибка: BOT_TOKEN не установлен" -ForegroundColor Red
    Write-Host ""
    Write-Host "Использование:" -ForegroundColor Yellow
    Write-Host "  `$env:BOT_TOKEN='your_bot_token_here'"
    Write-Host "  .\unlock_bot_token.ps1"
    Write-Host ""
    Write-Host "Или:"
    Write-Host "  `$env:BOT_TOKEN='your_bot_token'; .\unlock_bot_token.ps1"
    exit 1
}

# Маскируем токен для вывода (первые 4 и последние 4 символа)
$tokenMasked = $env:BOT_TOKEN.Substring(0, 4) + "..." + $env:BOT_TOKEN.Substring($env:BOT_TOKEN.Length - 4)
Write-Host "📋 Токен: $tokenMasked" -ForegroundColor Yellow
Write-Host ""

# URL API Telegram
$apiUrl = "https://api.telegram.org/bot$($env:BOT_TOKEN)"

Write-Host "🔍 Шаг 1: Проверка текущего состояния webhook..." -ForegroundColor Cyan
try {
    $webhookInfo = Invoke-RestMethod -Uri "$apiUrl/getWebhookInfo" -Method Get
    $webhookInfo | ConvertTo-Json -Depth 10
    Write-Host ""
    
    # Проверяем, есть ли webhook
    if ($webhookInfo.url) {
        Write-Host "⚠️  Обнаружен webhook: $($webhookInfo.url)" -ForegroundColor Yellow
        Write-Host ""
    } else {
        Write-Host "✅ Webhook не установлен" -ForegroundColor Green
        Write-Host ""
    }
} catch {
    Write-Host "❌ Ошибка при проверке webhook: $_" -ForegroundColor Red
    exit 1
}

Write-Host "🗑️  Шаг 2: Удаление webhook и очистка очереди апдейтов..." -ForegroundColor Cyan
try {
    $deleteResult = Invoke-RestMethod -Uri "$apiUrl/deleteWebhook?drop_pending_updates=true" -Method Get
    $deleteResult | ConvertTo-Json -Depth 10
    Write-Host ""
    
    if ($deleteResult.ok) {
        Write-Host "✅ Webhook успешно удалён!" -ForegroundColor Green
        Write-Host ""
        
        Write-Host "🔍 Шаг 3: Проверка результата..." -ForegroundColor Cyan
        Start-Sleep -Seconds 2
        $finalCheck = Invoke-RestMethod -Uri "$apiUrl/getWebhookInfo" -Method Get
        $finalCheck | ConvertTo-Json -Depth 10
        Write-Host ""
        
        # Проверяем, что webhook действительно удалён
        if (-not $finalCheck.url) {
            Write-Host "✅✅✅ Токен разблокирован! Webhook удалён, очередь очищена." -ForegroundColor Green
            Write-Host ""
            Write-Host "Теперь можно:" -ForegroundColor Cyan
            Write-Host "  1. Остановить все локальные экземпляры бота"
            Write-Host "  2. Проверить Render Dashboard на дубликаты сервисов"
            Write-Host "  3. Перезапустить Render worker"
        } else {
            Write-Host "❌ Webhook всё ещё установлен. Возможно, другой экземпляр бота активен." -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "❌ Ошибка при удалении webhook" -ForegroundColor Red
        exit 1
    }
} catch {
    Write-Host "❌ Ошибка при удалении webhook: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ Готово!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan

