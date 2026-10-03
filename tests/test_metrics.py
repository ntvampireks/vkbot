"""Тесты для MetricsCollector."""

import threading

from bot.utils.metrics import MetricsCollector


class TestGetAllMetrics:
    """Тесты снятия полного снимка метрик."""

    def test_get_all_metrics_does_not_deadlock(self):
        """get_all_metrics не зависает при непустых гистограммах.

        Regression: вложенный захват threading.Lock в get_histogram_stats
        вешал поток, обслуживающий GET /health, навсегда.
        """
        metrics = MetricsCollector()
        metrics.record_processing_time(0.12)
        metrics.record_message_received()

        result = {}
        worker = threading.Thread(
            target=lambda: result.update(metrics.get_all_metrics()),
            daemon=True,
        )
        worker.start()
        worker.join(timeout=3)

        assert not worker.is_alive(), 'get_all_metrics() привёл к взаимоблокировке'
        assert result['counters']['messages_received_total'] == 1
        assert result['histograms']['message_processing_seconds']['count'] == 1


class TestGetPrometheusFormat:
    """Тесты сериализации в формат Prometheus."""

    def test_get_prometheus_format_does_not_deadlock(self):
        """get_prometheus_format не зависает при непустых гистограммах."""
        metrics = MetricsCollector()
        metrics.record_processing_time(0.5)

        result = []
        worker = threading.Thread(
            target=lambda: result.append(metrics.get_prometheus_format()),
            daemon=True,
        )
        worker.start()
        worker.join(timeout=3)

        assert not worker.is_alive(), 'get_prometheus_format() привёл к взаимоблокировке'
        assert 'message_processing_seconds_stats' in result[0]

    def test_get_prometheus_format_holds_lock_while_iterating(self, monkeypatch):
        """Обход словарей метрик происходит удерживая блокировку.

        Regression: итерация по _counters/_histograms без блокировки давала
        RuntimeError: dictionary changed size during iteration, если параллельно
        появлялась новая метрика. Гонка по времени невоспроизводима стабильно,
        поэтому проверяется сам факт удержания блокировки в момент обхода.
        """
        metrics = MetricsCollector()
        metrics.observe('hist_0', 1.0)

        original = metrics.get_histogram_stats
        lock_held = []

        def spy(name):
            lock_held.append(metrics._lock.locked())
            return original(name)

        monkeypatch.setattr(metrics, 'get_histogram_stats', spy)

        metrics.get_prometheus_format()

        assert lock_held, 'get_histogram_stats не был вызван — обход гистограмм изменился'
        assert all(lock_held), 'словари метрик обходятся без блокировки'
