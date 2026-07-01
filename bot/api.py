"""FastAPI приложение для health-check и метрик."""
from fastapi import FastAPI, Depends
from fastapi.responses import PlainTextResponse

from bot.utils.metrics import MetricsCollector, get_metrics

app = FastAPI(title='VK Bot Health Check')

# Глобальная переменная для метрик (заполняется при старте из main.py)
_metrics: MetricsCollector | None = None


def set_metrics(metrics: MetricsCollector) -> None:
    """Установить экземпляр метрик (вызывается из main.py при старте)."""
    global _metrics
    _metrics = metrics


def get_metrics_dependency() -> MetricsCollector:
    """Dependency для инъекции метрик в FastAPI endpoints."""
    if _metrics is None:
        return get_metrics()  # Fallback на глобальный singleton
    return _metrics


@app.get('/health')
async def health_check(metrics: MetricsCollector = Depends(get_metrics_dependency)):
    """Получить статус здоровья бота.

    Returns:
        JSON с статусом, uptime и счётчиками сообщений
    """
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
    """Проверка готовности к работе.

    Returns:
        JSON с статусом готовности
    """
    return {
        'status': 'ready',
        'config_valid': True,
    }


@app.get('/metrics', response_class=PlainTextResponse)
async def metrics_endpoint(metrics: MetricsCollector = Depends(get_metrics_dependency)):
    """Получить метрики в формате Prometheus.

    Returns:
        Текстовый ответ в формате Prometheus metrics
    """
    return metrics.get_prometheus_format()
