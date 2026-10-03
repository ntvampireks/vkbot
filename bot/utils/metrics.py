"""Метрики для мониторинга бота."""
import time
import threading
from typing import Dict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class MetricValue:
    """Значение метрики с временной меткой."""
    value: float
    timestamp: float = field(default_factory=time.time)


class MetricsCollector:
    """Сборщик метрик для мониторинга бота."""

    def __init__(self):
        """Инициализирует сборщик метрик."""
        # RLock, а не Lock: get_all_metrics/get_prometheus_format держат блокировку
        # и вызывают get_histogram_stats, повторный захват того же лока иначе
        # привёл бы к взаимоблокировке потока, обслуживающего /health
        self._lock = threading.RLock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, list] = {}
        self._start_time: float = time.time()

    # --- Counters (счётчики) ---

    def inc_counter(self, name: str, value: int = 1) -> None:
        """Увеличить счётчик."""
        with self._lock:
            self._counters[name] = self._counters.get(name, 0) + value

    def get_counter(self, name: str) -> int:
        """Получить значение счётчика."""
        with self._lock:
            return self._counters.get(name, 0)

    # --- Gauges (гauge-метрики) ---

    def set_gauge(self, name: str, value: float) -> None:
        """Установить значение gauge."""
        with self._lock:
            self._gauges[name] = value

    def get_gauge(self, name: str) -> Optional[float]:
        """Получить значение gauge."""
        with self._lock:
            return self._gauges.get(name)

    # --- Histograms (гистограммы для latencies) ---

    def observe(self, name: str, value: float) -> None:
        """Записать значение в гистограмму."""
        with self._lock:
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)
            # Ограничиваем размер истории
            if len(self._histograms[name]) > 1000:
                self._histograms[name] = self._histograms[name][-1000:]

    def get_histogram_stats(self, name: str) -> Optional[Dict[str, float]]:
        """Получить статистику по гистограмме."""
        with self._lock:
            values = self._histograms.get(name, [])
            if not values:
                return None
            return {
                'count': len(values),
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
            }

    # --- Convenience methods ---

    def record_message_received(self) -> None:
        """Записать получение сообщения."""
        self.inc_counter('messages_received_total')

    def record_message_sent(self) -> None:
        """Запись отправки сообщения."""
        self.inc_counter('messages_sent_total')

    def record_message_error(self) -> None:
        """Записать ошибку при обработке сообщения."""
        self.inc_counter('message_errors_total')

    def record_processing_time(self, duration_seconds: float) -> None:
        """Записать время обработки сообщения."""
        self.observe('message_processing_seconds', duration_seconds)
        self.set_gauge('message_processing_seconds_current', duration_seconds)

    def record_response_time(self, duration_seconds: float) -> None:
        """Записать время отправки ответа."""
        self.observe('response_send_seconds', duration_seconds)

    @property
    def uptime_seconds(self) -> float:
        """Время работы бота в секундах."""
        return time.time() - self._start_time

    def get_all_metrics(self) -> Dict[str, Any]:
        """Получить все метрики."""
        with self._lock:
            return {
                'counters': dict(self._counters),
                'gauges': dict(self._gauges),
                'histograms': {
                    name: self.get_histogram_stats(name)
                    for name in self._histograms
                },
                'uptime_seconds': self.uptime_seconds,
            }

    def get_prometheus_format(self) -> str:
        """Получить метрики в формате Prometheus."""
        # Снимок под блокировкой: итерация по словарям без неё даёт
        # RuntimeError: dictionary changed size during iteration,
        # если параллельно пишется новая метрика
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            histograms = {
                name: self.get_histogram_stats(name)
                for name in self._histograms
            }

        lines = []

        # Counters
        for name, value in counters.items():
            lines.append(f'# HELP {name} Total count')
            lines.append(f'# TYPE {name} counter')
            lines.append(f'{name} {value}')

        # Gauges
        for name, value in gauges.items():
            lines.append(f'# HELP {name} Current value')
            lines.append(f'# TYPE {name} gauge')
            lines.append(f'{name} {value}')

        # Histograms
        for name, histogram_stats in histograms.items():
            if histogram_stats:
                lines.append(f'# HELP {name}_stats Statistics')
                lines.append(f'# TYPE {name}_stats gauge')
                lines.append(f'{name}_stats_count{{type="count"}} {histogram_stats["count"]}')
                lines.append(f'{name}_stats{{type="min"}} {histogram_stats["min"]}')
                lines.append(f'{name}_stats{{type="max"}} {histogram_stats["max"]}')
                lines.append(f'{name}_stats{{type="avg"}} {histogram_stats["avg"]}')

        # Uptime
        lines.append(f'# HELP uptime_seconds Uptime in seconds')
        lines.append(f'# TYPE uptime_seconds gauge')
        lines.append(f'uptime_seconds {self.uptime_seconds}')

        return '\n'.join(lines)


# Глобальный экземпляр метрик
_metrics: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Получить глобальный экземпляр метрик."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics
