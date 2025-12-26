"""
DevOps file detection and related features.

Features for detecting and analyzing DevOps/CI configuration changes:
- num_of_devops_files: Count of DevOps files changed in build
- devops_change_size: Lines changed in DevOps files
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from hamilton.function_modifiers import extract_fields, tag

from app.tasks.pipeline.feature_dag._inputs import (
    GitHistoryInput,
)
from app.tasks.pipeline.feature_dag._metadata import (
    FeatureCategory,
    FeatureDataType,
    FeatureResource,
    feature_metadata,
)

logger = logging.getLogger(__name__)


# DevOps File Detection Patterns
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
    """
    Check if a file is a DevOps/CI configuration file.

    Args:
        filepath: File path to check

    Returns:
        True if file is a DevOps file, False otherwise
    """
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
    """
    Identify which DevOps tool a file belongs to.

    Args:
        filepath: File path to check

    Returns:
        Tool name if identified, None otherwise
    """
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
        "num_of_devops_files": int,
        "devops_change_size": int,
        "devops_tools_used": list,
    }
)
@feature_metadata(
    display_name="DevOps File Features",
    description="Count and change size of DevOps configuration files in build",
    category=FeatureCategory.DEVOPS,
    data_type=FeatureDataType.JSON,
    required_resources=[FeatureResource.GIT_HISTORY],
)
@tag(group="devops")
def devops_file_features(
    git_history: GitHistoryInput,
    git_all_built_commits: List[str],
) -> Dict[str, Any]:
    """
    Extract DevOps file metrics from build commits.

    Features:
    - num_of_devops_files: Count of unique DevOps files changed
    - devops_change_size: Total lines changed in DevOps files
    - devops_tools_used: List of DevOps tools detected

    Analyzes all commits included in this build.
    """
    if not git_history.is_commit_available or not git_history.effective_sha:
        return {
            "num_of_devops_files": 0,
            "devops_change_size": 0,
            "devops_tools_used": [],
        }

    repo_path = git_history.path
    devops_files: Set[str] = set()
    devops_tools: Set[str] = set()
    total_change_size = 0

    # Determine diff range
    commits_to_analyze = git_all_built_commits or [git_history.effective_sha]

    for commit_sha in commits_to_analyze:
        try:
            # Get files changed in this commit with their stats
            files_changed, change_sizes = _get_commit_file_changes(repo_path, commit_sha)

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
        "num_of_devops_files": len(devops_files),
        "devops_change_size": total_change_size,
        "devops_tools_used": sorted(devops_tools),
    }


def _get_commit_file_changes(repo_path: Path, commit_sha: str) -> Tuple[List[str], List[int]]:
    """
    Get files changed in a commit with their line change counts.

    Returns:
        Tuple of (file_paths, change_sizes)
    """
    import subprocess

    try:
        # git diff-tree --numstat for file-level change counts
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
