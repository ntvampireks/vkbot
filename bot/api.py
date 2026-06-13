"""FastAPI приложение для health-check и метрик."""
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from bot.utils.metrics import get_metrics

app = FastAPI(title='VK Bot Health Check')


@app.get('/health')
async def health_check():
    """Получить статус здоровья бота."""
    metrics = get_metrics()
    metrics_data = metrics.get_all_metrics()

    return {
        'status': 'healthy',
        'uptime_seconds': metrics_data['uptime_seconds'],
        'messages_received': metrics_data['counters'].get('messages_received_total', 0),
        'messages_sent': metrics_data['counters'].get('messages_sent_total', 0),
        'errors': metrics_data['counters'].get('message_errors_total', 0),
    }


@app.get('/ready')
async def ready_check():
    """Проверка готовности к работе."""
    return {
        'status': 'ready',
        'config_valid': True,
    }


@app.get('/metrics', response_class=PlainTextResponse)
async def metrics():
    """Получить метрики в формате Prometheus."""
    metrics = get_metrics()
    return metrics.get_prometheus_format()
