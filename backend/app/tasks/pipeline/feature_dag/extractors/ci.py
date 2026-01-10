"""
Log and DevOps Features for Hamilton Pipeline.

Extracts test results and DevOps file metrics from CI build logs:
- log_tests_run, log_tests_failed, log_tests_skipped, log_tests_passed
- log_tests_fail_rate
- log_test_duration_sec
- log_test_frameworks
- devops_files_changed, devops_lines_changed, devops_tools_detected
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from hamilton.function_modifiers import extract_fields, tag

from app.tasks.pipeline.feature_dag._inputs import (
    BuildLogsInput,
    FeatureConfigInput,
    GitHistoryInput,
)
from app.tasks.pipeline.feature_dag._metadata import requires_config
from app.tasks.pipeline.feature_dag.log_parsers.registry import TestLogParser

logger = logging.getLogger(__name__)


# =============================================================================
# Test Log Parser Features
# =============================================================================


@extract_fields(
    {
        "log_test_frameworks": list,
        "log_tests_run": int,
        "log_tests_failed": int,
        "log_tests_skipped": int,
        "log_tests_passed": int,
        "log_tests_fail_rate": float,
        "log_test_duration_sec": float,
    }
)
@tag(group="log")
@requires_config(
    test_frameworks={
        "type": "list",
        "scope": "repo",
        "required": False,
        "description": "Test frameworks to detect (leave empty for auto-detection)",
        "default": [],
    },
)
def test_log_features(
    build_logs: BuildLogsInput,
    repo_languages_all: List[str],
    feature_config: FeatureConfigInput,
) -> Dict[str, Any]:
    """
    Parse CI build logs and extract test results.

    Returns aggregated test metrics across all job logs:
    - log_test_frameworks: List of detected test frameworks
    - log_tests_run: Total tests run
    - log_tests_failed: Total tests failed
    - log_tests_skipped: Total tests skipped
    - log_tests_passed: Total tests passed
    - log_tests_fail_rate: Failure rate (failed/run)
    - log_test_duration_sec: Total test duration in seconds
    """
    if not build_logs.is_available:
        return _empty_test_results()

    parser = TestLogParser()

    frameworks: Set[str] = set()
    tests_run_sum = 0
    tests_failed_sum = 0
    tests_skipped_sum = 0
    tests_ok_sum = 0
    test_duration_sum = 0.0

    language_hints = repo_languages_all
    allowed_frameworks = _get_allowed_frameworks(feature_config)

    for log_path_str in build_logs.log_files:
        try:
            log_path = Path(log_path_str)
            if not log_path.exists():
                continue

            content = log_path.read_text(errors="replace")

            # Try parsing with each language hint until we get a match
            parsed = None
            if language_hints:
                for lang_hint in language_hints:
                    parsed = parser.parse(
                        content,
                        language_hint=lang_hint,
                        allowed_frameworks=allowed_frameworks or None,
                    )
                    if parsed.framework:
                        break

            if not parsed or not parsed.framework:
                parsed = parser.parse(
                    content,
                    language_hint=None,
                    allowed_frameworks=allowed_frameworks or None,
                )

            if parsed.framework:
                frameworks.add(parsed.framework)

            tests_run_sum += parsed.tests_run
            tests_failed_sum += parsed.tests_failed
            tests_skipped_sum += parsed.tests_skipped
            tests_ok_sum += parsed.tests_ok

            if parsed.test_duration_seconds:
                test_duration_sum += parsed.test_duration_seconds

        except Exception as e:
            logger.warning(f"Failed to parse log {log_path_str}: {e}")

    # Derived metric
    fail_rate = tests_failed_sum / tests_run_sum if tests_run_sum > 0 else 0.0

    return {
        "log_test_frameworks": list(frameworks),
        "log_tests_run": tests_run_sum,
        "log_tests_failed": tests_failed_sum,
        "log_tests_skipped": tests_skipped_sum,
        "log_tests_passed": tests_ok_sum,
        "log_tests_fail_rate": fail_rate,
        "log_test_duration_sec": test_duration_sum,
    }


def _empty_test_results() -> Dict[str, Any]:
    """Return empty test results when logs are unavailable."""
    return {
        "log_test_frameworks": [],
        "log_tests_run": 0,
        "log_tests_failed": 0,
        "log_tests_skipped": 0,
        "log_tests_passed": 0,
        "log_tests_fail_rate": 0.0,
        "log_test_duration_sec": 0.0,
    }


def _get_allowed_frameworks(feature_config: FeatureConfigInput) -> Optional[List[str]]:
    """Get allowed test frameworks from config."""
    test_frameworks = feature_config.get("test_frameworks", [])
    if not test_frameworks:
        return None
    return [
        f.lower() if isinstance(f, str) else str(f).lower() for f in test_frameworks
    ]


@tag(group="log")
def log_jobs_count(build_logs: BuildLogsInput) -> int:
    """
    Get number of job log files.

    Returns the count of .log files in the logs directory.
    """
    if not build_logs.is_available:
        return 0
    return len(build_logs.log_files)


@tag(group="log")
def log_job_ids(build_logs: BuildLogsInput) -> str:
    """
    Get job IDs from the build logs.

    Extracts job IDs from log file names (e.g., '223085.log' -> '223085').
    Each ID corresponds to a specific job in the CI build run.
    Returns comma-separated string of job IDs.
    """
    if not build_logs.is_available:
        return ""

    job_ids = []
    for log_path_str in build_logs.log_files:
        log_path = Path(log_path_str)
        # Extract job ID from file name (remove .log extension)
        job_id = log_path.stem
        if job_id:
            job_ids.append(job_id)

    return ",".join(job_ids)


# CI/CD tool patterns - mapped by tool name
CI_TOOL_PATTERNS: Dict[str, List[str]] = {
    "Jenkins": [r".*Jenkinsfile$"],
    "Codeship": [
        r".*codeship-steps\.yml$",
        r".*codeship-services\.yml$",
        r".*codeship-steps\.json$",
        r".*codeship-steps\.yaml$",
        r".*codeship-services\.yaml$",
    ],
    "Travis CI": [r".*\.travis\.yml$", r".*\.travis\.yaml$"],
    "Circle CI": [
        r".*\.circleci/config\.yml$",
        r".*circle\.yml$",
        r".*\.circleci/config\.yaml$",
        r".*circle\.yaml$",
    ],
    "GitLab CI": [r".*\.gitlab-ci\.yml$", r".*\.gitlab-ci\.yaml$"],
    "GitHub Actions": [r".*\.github/workflows/.*"],
    "Gradle": [r".*\.gradle$", r".*gradle\.properties$", r".*gradlew.*"],
    "VSTS": [r".*vsts\.yml$", r".*vsts\.yaml$"],
    "AWS CodeBuild": [r".*buildspec\.yml$", r".*buildspec\.yaml$"],
    "Azure Pipeline": [r".*azure-pipelines\.yml$", r".*azure-pipelines\.yaml$"],
    "Octopus Deploy": [r".*octoversion\.json$"],
    "AWS CodeDeploy": [r".*appspec\.yml", r".*appspec\.yaml", r".*appspec\.json"],
    "GoCD": [r".*\.gocd\.yml$", r".*\.gocd\.yaml$"],
}

# Infrastructure as Code (IaC) patterns
IAC_PATTERNS: Dict[str, List[str]] = {
    "Docker": [
        r".*\.dockerfile$",
        r".*[Dd]ockerfile$",
        r".*docker-compose\.yml$",
        r".*docker-compose\.yaml$",
        r".*\.docker/config\.json$",
    ],
    "Kubernetes": [
        r".*deployment\.yml$",
        r".*deployment\.yaml$",
        r".*kubeconfig$",
        r".*kube.*\.yml$",
        r".*kube.*\.yaml$",
    ],
    "Helm": [
        r".*helm\.yml$",
        r".*helm\.yaml$",
        r".*\.tpl$",
        r".*_helpers\.tpl$",
        r".*\.helmignore$",
        r".*Chart\.yaml$",
        r".*Chart\.yml$",
    ],
    "Terraform": [r".*\.tf$", r".*\.tf\.json$"],
    "Ansible": [
        r".*ansible\.cfg$",
        r".*site\.yml$",
        r".*site\.yaml$",
        r".*playbook.*\.yml$",
        r".*playbook.*\.yaml$",
        r".*main\.yml$",
        r".*main\.yaml$",
    ],
    "Puppet": [r".*puppet\.conf$", r".*pe\.conf$"],
    "Packer": [r".*pkr\.hcl$"],
    "Vagrant": [r".*[Vv]agrantfile.*"],
    "Chef": [r".*solo\.rb$", r".*default\.rb$", r".*recipes/.*\.rb", r".*chefignore$"],
    "Salt": [r".*\.sls$", r"^salt/.*", r".*/salt/.*"],
    "Bazel": [r".*\.bzl$", r".*\.bazelci$", r".*\.bazel$"],
    "Mesos": [r".*mesos-master\.sh$"],
    "Rancher": [r".*rancher-pipeline\.yml$", r".*rancher-pipeline\.yaml$"],
}

# Keywords that suggest DevOps files (for generic .yml/.yaml files)
DEVOPS_KEYWORDS = [
    "azure",
    "pipeline",
    "devops",
    "zuul",
    "deployment",
    "production",
    "deploy",
    "heroku",
    "aws",
    "google-cloud",
    "cloudbuild",
    "goreleaser",
    "chart",
    "build",
    "ansible",
    "k8s",
    "kubernetes",
    "traefik",
    "helm",
    "loki",
    "salt",
    "golangci",
    "-ci.",
    "-cd.",
    "roles/",
    "tasks/",
    "jenkin",
    "codeship",
    "travis",
    "gitlab",
    "workflow",
    "gradle",
    "gocd",
    "spinnaker",
    "docker",
    "mesos",
    "rancher",
    "openshift",
    "chef",
    "kitchen",
    "cookbook",
    "terraform",
    "rudder",
    "playbook",
    "puppet",
    "packer",
    "vagrant",
    "cfengine",
    "bazel",
    ".github/workflows",
]

# Patterns to exclude (false positives)
EXCLUDE_PATTERNS = [
    r"recipes/.*/\.meta\.yml",
    r"vendor/",
    r"eslintrc",
    r"lint",
    r"readthedocs",
    r"docs/",
    r"^changelog/",
    r"test_data",
    r"module/",
    r"locales",
    r"dependabot",
    r"yarn",
    r"rubocop",
    r"hound",
    r"snapcraft",
    r"lock",
    r"pullapprove",
    r"prettierrc",
    r"pnpm-workspace",
    r"document",
    r"package",
    r"bettercodehub",
    r"dependencies",
    r"routes",
    r"postcssrc",
    r"codeclimate",
    r"plugin",
    r"istanbul",
    r"/tests/",
    r"node_modules/",
    r"\.test\.",
    r"_test\.",
]


def _is_devops_file(filepath: str) -> bool:
    """Check if a file is a DevOps/CI configuration file."""
    filepath_lower = filepath.lower()

    # Check exclusions first
    for pattern in EXCLUDE_PATTERNS:
        try:
            if re.search(pattern, filepath_lower):
                return False
        except re.error:
            if pattern in filepath_lower:
                return False

    # Check CI tool patterns
    for patterns in CI_TOOL_PATTERNS.values():
        for pattern in patterns:
            try:
                if re.match(pattern, filepath_lower):
                    return True
            except re.error:
                pass

    # Check IaC patterns
    for patterns in IAC_PATTERNS.values():
        for pattern in patterns:
            try:
                if re.match(pattern, filepath_lower):
                    return True
            except re.error:
                pass

    # Check generic .yml/.yaml files with DevOps keywords
    if filepath_lower.endswith((".yml", ".yaml")):
        for keyword in DEVOPS_KEYWORDS:
            if keyword.lower() in filepath_lower:
                return True

    return False


def _get_devops_tool(filepath: str) -> Optional[str]:
    """Identify which DevOps tool a file belongs to."""
    filepath_lower = filepath.lower()

    # Check CI tools
    for tool, patterns in CI_TOOL_PATTERNS.items():
        for pattern in patterns:
            try:
                if re.match(pattern, filepath_lower):
                    return tool
            except re.error:
                pass

    # Check IaC tools
    for tool, patterns in IAC_PATTERNS.items():
        for pattern in patterns:
            try:
                if re.match(pattern, filepath_lower):
                    return tool
            except re.error:
                pass

    return None


@extract_fields(
    {
        "devops_files_changed": int,
        "devops_lines_changed": int,
        "devops_tools_detected": list,
    }
)
@tag(group="devops")
def devops_file_features(
    git_history: GitHistoryInput,
    git_built_commits: List[str],
) -> Dict[str, Any]:
    """
    Extract DevOps file metrics from build commits.

    Features:
    - devops_files_changed: Count of unique DevOps files changed
    - devops_lines_changed: Total lines changed in DevOps files
    - devops_tools_detected: List of DevOps tools detected

    Analyzes all commits included in this build.
    """
    if not git_history.is_commit_available or not git_history.effective_sha:
        return {
            "devops_files_changed": 0,
            "devops_lines_changed": 0,
            "devops_tools_detected": [],
        }

    repo_path = git_history.path
    devops_files: Set[str] = set()
    devops_tools: Set[str] = set()
    total_change_size = 0

    # Determine diff range
    commits_to_analyze = git_built_commits or [git_history.effective_sha]

    for commit_sha in commits_to_analyze:
        try:
            # Get files changed in this commit with their stats
            files_changed, change_sizes = _get_commit_file_changes(
                repo_path, commit_sha
            )

            for filepath, change_size in zip(files_changed, change_sizes, strict=False):
                if _is_devops_file(filepath):
                    devops_files.add(filepath)
                    total_change_size += change_size

                    tool = _get_devops_tool(filepath)
                    if tool:
                        devops_tools.add(tool)

        except Exception as e:
            logger.warning(f"Failed to analyze commit {commit_sha[:8]}: {e}")

    return {
        "devops_files_changed": len(devops_files),
        "devops_lines_changed": total_change_size,
        "devops_tools_detected": sorted(devops_tools),
    }


def _get_commit_file_changes(
    repo_path: Path, commit_sha: str
) -> Tuple[List[str], List[int]]:
    """Get files changed in a commit with their line change counts."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--numstat", "-r", commit_sha],
            cwd=str(repo_path),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )

        files = []
        sizes = []

        for line in result.stdout.strip().split("\n"):
            if not line:
                continue

            parts = line.split("\t")
            if len(parts) >= 3:
                added, deleted, filepath = parts[0], parts[1], parts[2]
                files.append(filepath)

                # Handle binary files (marked with '-')
                try:
                    change_size = int(added) + int(deleted)
                except ValueError:
                    change_size = 0

                sizes.append(change_size)

        return files, sizes

    except Exception as e:
        logger.warning(f"Failed to get commit file changes: {e}")
        return [], []
