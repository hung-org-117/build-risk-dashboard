import logging
from typing import Any, Dict, List

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.config import settings

logger = logging.getLogger(__name__)


class MetricsExporter:
    """Export metrics from SonarQube API for a given component."""

    def __init__(self):
        db_settings = self._get_db_settings()
        self.host = db_settings["host_url"]
        self.token = db_settings["token"]
        self.session = self._build_session()
        self.chunk_size = 25

    def _get_db_settings(self) -> Dict[str, Any]:
        """Load SonarQube settings from database (consistent with SonarQubeTool)."""
        try:
            from app.database.mongo import get_database
            from app.services.settings_service import SettingsService

            db = get_database()
            service = SettingsService(db)
            app_settings = service.get_settings()

            # Get decrypted token for actual use
            token = service.get_decrypted_token("sonarqube") or ""

            return {
                "host_url": app_settings.sonarqube.host_url.rstrip("/"),
                "token": token,
            }
        except Exception as e:
            logger.warning(f"Could not load SonarQube settings from DB: {e}")

        # Fallback to ENV vars
        return {
            "host_url": settings.SONAR_HOST_URL.rstrip("/"),
            "token": settings.SONAR_TOKEN or "",
        }

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        retry = Retry(
            total=3,
            read=3,
            connect=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.auth = (self.token, "")
        session.headers.update({"Accept": "application/json"})
        return session

    def _chunks(self, items: List[str]):
        for idx in range(0, len(items), self.chunk_size):
            yield items[idx : idx + self.chunk_size]

    def _fetch_measures(self, project_key: str, metrics: List[str]) -> Dict[str, str]:
        """Fetch specific metrics from SonarQube API."""
        url = f"{self.host}/api/measures/component"
        payload: Dict[str, str] = {}

        for chunk in self._chunks(metrics):
            resp = self.session.get(
                url,
                params={"component": project_key, "metricKeys": ",".join(chunk)},
                timeout=30,
            )
            resp.raise_for_status()
            component = resp.json().get("component", {})
            for measure in component.get("measures", []):
                payload[measure.get("metric")] = measure.get("value")

        return payload

    def collect_metrics(
        self,
        component_key: str,
        selected_metrics: List[str],
    ) -> Dict[str, Any]:
        """
        Collect metrics from SonarQube for a component.

        Args:
            component_key: SonarQube project/component key
            selected_metrics: List of metric keys to fetch. Metric keys can have 'sonar_' prefix which will be stripped.

        Returns:
            Dict mapping metric key to value (properly typed based on MetricDefinition)
        """
        # Strip 'sonar_' prefix if present (user selection may have it)
        metrics_to_fetch = [
            m.replace("sonar_", "") if m.startswith("sonar_") else m
            for m in selected_metrics
        ]

        logger.debug(f"Fetching {len(metrics_to_fetch)} metrics for {component_key}")
        raw_metrics = self._fetch_measures(component_key, metrics_to_fetch)

        # Convert string values to proper types based on MetricDefinition
        return self._convert_metrics_types(raw_metrics)

    def _convert_metrics_types(self, raw_metrics: Dict[str, str]) -> Dict[str, Any]:
        """
        Convert string metric values to proper types using SONARQUBE_METRICS definitions.

        SonarQube API returns all values as strings. This method converts them
        to the expected data type (INTEGER -> int, FLOAT -> float, BOOLEAN -> bool,
        JSON -> parsed dict/list).
        """
        import json

        from app.integrations.base import MetricDataType

        try:
            from app.integrations.tools.sonarqube.metrics import SONARQUBE_METRICS

            # Build lookup: metric_key -> MetricDefinition
            metric_defs = {m.key: m for m in SONARQUBE_METRICS}
        except ImportError:
            logger.warning("Could not import SONARQUBE_METRICS, returning raw strings")
            return raw_metrics

        converted: Dict[str, Any] = {}
        for key, value in raw_metrics.items():
            if value is None:
                converted[key] = None
                continue

            metric_def = metric_defs.get(key)
            if not metric_def:
                # Unknown metric, keep as string
                converted[key] = value
                continue

            try:
                if metric_def.data_type == MetricDataType.INTEGER:
                    # Handle floats like "3.0" -> 3
                    converted[key] = int(float(value))
                elif metric_def.data_type == MetricDataType.FLOAT:
                    converted[key] = float(value)
                elif metric_def.data_type == MetricDataType.BOOLEAN:
                    converted[key] = value.lower() in ("true", "1", "yes")
                elif metric_def.data_type == MetricDataType.JSON:
                    # Parse JSON string to Python object
                    converted[key] = json.loads(value)
                else:
                    # STRING, DATETIME - keep as is
                    converted[key] = value
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON metric {key}={value}: {e}")
                converted[key] = value
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to convert metric {key}={value}: {e}")
                converted[key] = value

        return converted
