import unittest
from unittest.mock import MagicMock, patch
from app.entities.dataset_scan import DatasetScan, DatasetScanStatus
from app.entities.dataset_scan_result import DatasetScanResult
from app.tasks.integration_scan import retry_scan_result
from app.integrations import ToolType, ScanMode


class TestScanRetryLogic(unittest.TestCase):

    @patch("app.tasks.integration_scan.get_database")
    @patch("app.tasks.integration_scan.DatasetScanRepository")
    @patch("app.tasks.integration_scan.DatasetScanResultRepository")
    @patch("app.tasks.integration_scan.DatasetRepoConfigRepository")
    @patch("app.tasks.integration_scan.get_tool")
    @patch("app.tasks.integration_scan._run_trivy_scan")
    @patch("app.tasks.integration_scan._start_sonar_scan")
    @patch("app.services.dataset_scan_service.DatasetScanService")
    def test_retry_logic_config_hierarchy(
        self,
        MockService,
        mock_start_sonar,
        mock_run_trivy,
        mock_get_tool,
        MockRepoConfigRepo,
        MockResultRepo,
        MockScanRepo,
        mock_get_db,
    ):
        # Setup common mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_scan_repo = MockScanRepo.return_value
        mock_result_repo = MockResultRepo.return_value
        mock_repo_config_repo = MockRepoConfigRepo.return_value

        # Setup Tool (SonarQube)
        mock_tool = MagicMock()
        mock_tool.is_available.return_value = True
        mock_tool.scan_mode = ScanMode.ASYNC
        mock_get_tool.return_value = mock_tool

        # --- Test Case 1: Override Config takes precedence ---
        scan_id = "scan_1"
        result_id = "result_1"

        # Mock Scan with default config
        scan_1 = MagicMock(spec=DatasetScan)
        scan_1.tool_type = "sonarqube"
        scan_1.scan_config = "default_config"
        mock_scan_repo.find_by_id.return_value = scan_1

        # Mock Result with override config
        result_1 = MagicMock(spec=DatasetScanResult)
        result_1.override_config = "override_config"
        mock_result_repo.find_by_id.return_value = result_1

        # Run task
        retry_scan_result(result_id, scan_id)

        # Verify _start_sonar_scan called with override_config
        mock_start_sonar.assert_called_with(
            result_1,
            mock_tool,
            mock_result_repo,
            mock_repo_config_repo,
            "override_config",
        )

        # --- Test Case 2: Scan Config used when no override ---
        result_1.override_config = None
        mock_start_sonar.reset_mock()

        # Run task
        retry_scan_result(result_id, scan_id)

        # Verify _start_sonar_scan called with scan_config
        mock_start_sonar.assert_called_with(
            result_1,
            mock_tool,
            mock_result_repo,
            mock_repo_config_repo,
            "default_config",
        )

        # --- Test Case 3: No config used when neither present ---
        scan_1.scan_config = None
        mock_start_sonar.reset_mock()

        # Run task
        retry_scan_result(result_id, scan_id)

        # Verify _start_sonar_scan called with None (or passed correctly)
        mock_start_sonar.assert_called_with(
            result_1, mock_tool, mock_result_repo, mock_repo_config_repo, None
        )

    @patch("app.tasks.integration_scan.get_database")
    @patch("app.tasks.integration_scan.DatasetScanRepository")
    @patch("app.tasks.integration_scan.DatasetScanResultRepository")
    @patch("app.tasks.integration_scan.DatasetRepoConfigRepository")
    @patch("app.tasks.integration_scan.get_tool")
    @patch("app.tasks.integration_scan._run_trivy_scan")
    @patch("app.services.dataset_scan_service.DatasetScanService")
    def test_retry_logic_trivy(
        self,
        MockService,
        mock_run_trivy,
        mock_get_tool,
        MockRepoConfigRepo,
        MockResultRepo,
        MockScanRepo,
        mock_get_db,
    ):
        # Setup common mocks
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db

        mock_scan_repo = MockScanRepo.return_value
        mock_result_repo = MockResultRepo.return_value
        mock_repo_config_repo = MockRepoConfigRepo.return_value

        # Setup Tool (Trivy - SYNC)
        mock_tool = MagicMock()
        mock_tool.is_available.return_value = True
        mock_tool.scan_mode = ScanMode.SYNC
        mock_get_tool.return_value = mock_tool

        scan_id = "scan_valid"
        result_id = "result_valid"

        scan = MagicMock(spec=DatasetScan)
        scan.tool_type = "trivy"
        scan.scan_config = "trivy_yaml_content"
        mock_scan_repo.find_by_id.return_value = scan

        result = MagicMock(spec=DatasetScanResult)
        result.override_config = None
        mock_result_repo.find_by_id.return_value = result

        # Run task
        retry_scan_result(result_id, scan_id)

        # Verify _run_trivy_scan called with config
        mock_run_trivy.assert_called_with(
            result,
            mock_tool,
            mock_result_repo,
            mock_repo_config_repo,
            "trivy_yaml_content",
        )


if __name__ == "__main__":
    unittest.main()
