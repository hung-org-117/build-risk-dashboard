import logging
import shutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from git import Repo, Commit
from pymongo.database import Database

from app.models.entities.build_sample import BuildSample
from app.models.entities.imported_repository import ImportedRepository
from app.models.entities.workflow_run import WorkflowRunRaw
from app.repositories.build_sample import BuildSampleRepository
from app.repositories.workflow_run import WorkflowRunRepository
from app.services.github.github_app import get_installation_token
from app.utils.locking import repo_lock
from app.services.extracts.diff_analyzer import (
    _count_test_cases,
    _is_doc_file,
    _is_source_file,
    _is_test_file,
)

logger = logging.getLogger(__name__)

REPOS_DIR = Path("repos")
REPOS_DIR.mkdir(exist_ok=True)


class GitFeatureExtractor:
    def __init__(self, db: Database):
        self.db = db
        self.build_sample_repo = BuildSampleRepository(db)
        self.workflow_run_repo = WorkflowRunRepository(db)

    def extract(
        self, build_sample: BuildSample, repo: ImportedRepository
    ) -> Dict[str, Any]:
        commit_sha = build_sample.tr_original_commit
        if not commit_sha:
            logger.warning(f"No commit SHA for build {build_sample.id}")
            return self._empty_result()

        repo_path = REPOS_DIR / str(repo.id)

        try:
            with repo_lock(str(repo.id)):
                self._ensure_repo(repo, repo_path)
                # Fetch to ensure we have the commit
                self._run_git(repo_path, ["fetch", "origin"])

            # Check if commit exists
            if not self._commit_exists(repo_path, commit_sha):
                logger.warning(f"Commit {commit_sha} not found in {repo.full_name}")
                return self._empty_result()

            git_repo = Repo(str(repo_path))

            # Calculate build stats (history traversal)
            build_stats = self._calculate_build_stats(
                build_sample, git_repo, repo.full_name
            )

            # Calculate team stats
            team_stats = self._calculate_team_stats(
                build_sample, git_repo, build_stats.get("git_all_built_commits", [])
            )

            # Calculate diff stats
            diff_stats = {}
            parent_sha = self._get_parent_commit(repo_path, commit_sha)
            if parent_sha:
                diff_stats = self._analyze_diff(
                    repo_path, parent_sha, commit_sha, repo.main_lang
                )

            return {**build_stats, **team_stats, **diff_stats}

        except Exception as e:
            logger.error(
                f"Failed to extract git features for {repo.full_name}: {e}",
                exc_info=True,
            )
            return self._empty_result()

    def _get_parent_commit(self, cwd: Path, sha: str) -> str | None:
        try:
            return self._run_git(cwd, ["rev-parse", f"{sha}^"])
        except subprocess.CalledProcessError:
            return None

    def _analyze_diff(
        self, cwd: Path, parent: str, current: str, language: str | None
    ) -> Dict[str, Any]:
        stats = {
            "git_diff_src_churn": 0,
            "git_diff_test_churn": 0,
            "gh_diff_files_added": 0,
            "gh_diff_files_deleted": 0,
            "gh_diff_files_modified": 0,
            "gh_diff_tests_added": 0,
            "gh_diff_tests_deleted": 0,
            "gh_diff_src_files": 0,
            "gh_diff_doc_files": 0,
            "gh_diff_other_files": 0,
        }

        # Get name-status to count files
        # git diff --name-status parent current
        name_status_out = self._run_git(cwd, ["diff", "--name-status", parent, current])

        for line in name_status_out.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            status_code = parts[0][0]
            path = parts[-1]  # Handle renames if needed, but usually last is dest

            if status_code == "A":
                stats["gh_diff_files_added"] += 1
            elif status_code == "D":
                stats["gh_diff_files_deleted"] += 1
            elif status_code == "M":
                stats["gh_diff_files_modified"] += 1

            if _is_doc_file(path):
                stats["gh_diff_doc_files"] += 1
            elif _is_source_file(path):
                stats["gh_diff_src_files"] += 1
            elif not _is_test_file(path):
                stats["gh_diff_other_files"] += 1

        # Get numstat for churn
        # git diff --numstat parent current
        numstat_out = self._run_git(cwd, ["diff", "--numstat", parent, current])

        for line in numstat_out.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            try:
                added = int(parts[0]) if parts[0] != "-" else 0
                deleted = int(parts[1]) if parts[1] != "-" else 0
            except ValueError:
                continue
            path = parts[2]

            if _is_source_file(path):
                stats["git_diff_src_churn"] += added + deleted
            elif _is_test_file(path):
                stats["git_diff_test_churn"] += added + deleted

        # Get patch for test cases
        # This might be heavy for large diffs
        patch_out = self._run_git(cwd, ["diff", parent, current])
        added_tests, deleted_tests = _count_test_cases(patch_out, language)
        stats["gh_diff_tests_added"] = added_tests
        stats["gh_diff_tests_deleted"] = deleted_tests

        return stats

    def _ensure_repo(self, repo: ImportedRepository, repo_path: Path):
        if repo_path.exists():
            if (repo_path / ".git").exists():
                return
            else:
                shutil.rmtree(repo_path)

        auth_url = f"https://github.com/{repo.full_name}.git"

        if repo.installation_id:
            token = get_installation_token(repo.installation_id, self.db)
            auth_url = f"https://x-access-token:{token}@github.com/{repo.full_name}.git"
        else:
            # Try public tokens from settings
            from app.config import settings

            tokens = settings.GITHUB_TOKENS
            if tokens and tokens[0]:
                token = tokens[0]
                auth_url = f"https://{token}@github.com/{repo.full_name}.git"

        logger.info(f"Cloning {repo.full_name} to {repo_path}")
        subprocess.run(
            ["git", "clone", auth_url, str(repo_path)],
            check=True,
            capture_output=True,
        )

    def _run_git(self, cwd: Path, args: List[str]) -> str:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def _commit_exists(self, cwd: Path, sha: str) -> bool:
        try:
            subprocess.run(
                ["git", "cat-file", "-e", sha],
                cwd=cwd,
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def _calculate_build_stats(
        self, build_sample: BuildSample, repo: Repo, repo_slug: str
    ) -> Dict[str, Any]:
        commit_sha = build_sample.tr_original_commit
        try:
            build_commit = repo.commit(commit_sha)
        except Exception:
            return {}

        prev_commits_objs: List[Commit] = [build_commit]
        status = "no_previous_build"
        last_commit = None
        prev_build_id = None

        # Walk backwards to find previous build
        # Limit to avoid infinite loops in weird histories
        walker = repo.iter_commits(commit_sha, max_count=1000)
        first = True

        for commit in walker:
            if first:
                if len(commit.parents) > 1:
                    status = "merge_found"
                    break
                first = False
                continue

            last_commit = commit

            # Check if this commit triggered a build
            # Use WorkflowRunRaw to find previous builds (metadata pass ensures they exist)
            existing_build = self.workflow_run_repo.find_one(
                {
                    "repo_id": build_sample.repo_id,
                    "head_sha": commit.hexsha,
                    "status": "completed",
                    "workflow_run_id": {"$ne": build_sample.workflow_run_id},
                }
            )

            if existing_build:
                status = "build_found"
                prev_build_id = existing_build.run_number
                break

            prev_commits_objs.append(commit)

            if len(commit.parents) > 1:
                status = "merge_found"
                break

        commits_hex = [c.hexsha for c in prev_commits_objs]

        return {
            "git_prev_commit_resolution_status": status,
            "git_prev_built_commit": last_commit.hexsha if last_commit else None,
            "tr_prev_build": prev_build_id,
            "git_all_built_commits": commits_hex,
            "git_num_all_built_commits": len(commits_hex),
        }

    def _calculate_team_stats(
        self,
        build_sample: BuildSample,
        repo: Repo,
        built_commits: List[str],
        chunk_size=50,
    ) -> Dict[str, Any]:
        if not built_commits:
            return {}

        # Get trigger commit (first in list)
        trigger_commit_sha = built_commits[0]
        try:
            trigger_commit = repo.commit(trigger_commit_sha)
            trigger_date = datetime.fromtimestamp(trigger_commit.committed_date)
        except Exception:
            return {}

        start_date = trigger_date - timedelta(days=90)  # 3 months back

        # Find team members (committers) in the last 3 months
        # We use git log since date to find all commits
        team_members: Set[str] = set()

        try:
            # Use git log to get authors efficiently
            # Format: %ae (author email) or %an (author name)
            # We'll use email as identifier if possible, or name
            log_args = [
                "--since",
                start_date.isoformat(),
                "--until",
                trigger_date.isoformat(),
                "--format=%ae",
            ]
            # Note: repo.git.log can return large string
            authors_log = repo.git.log(*log_args).splitlines()
            team_members = set(a.strip() for a in authors_log if a.strip())
        except Exception as e:
            logger.warning(f"Failed to calculate team size: {e}")
            return {}

        # Check if current build is by core team member
        current_author = trigger_commit.author.email
        is_core_member = current_author in team_members

        # Commits on files touched
        # 1. Identify files touched in built_commits
        files_touched: Set[str] = set()
        for sha in built_commits:
            try:
                commit = repo.commit(sha)
                if commit.parents:
                    diffs = commit.diff(commit.parents[0])
                    for d in diffs:
                        if d.b_path:
                            files_touched.add(d.b_path)
                        if d.a_path:
                            files_touched.add(d.a_path)
                else:
                    # Initial commit, add all files? Or just skip diff
                    pass
            except Exception:
                pass

        # 2. Count unique commits on these files in the last 3 months
        num_commits_on_files = 0
        all_shas = set()
        if files_touched:
            try:
                paths = list(files_touched)
                for i in range(0, len(paths), chunk_size):
                    chunk = paths[i : i + chunk_size]
                    # Use trigger_commit_sha as starting point to walk backwards
                    commits_on_files = repo.git.log(
                        trigger_commit_sha,
                        "--since",
                        start_date.isoformat(),
                        "--format=%H",
                        "--",
                        *chunk,
                    ).splitlines()
                    all_shas.update(set(commits_on_files))

                # Exclude the build commits themselves, matching Ruby's logic:
                # "not commits_in_pr.include? c.oid"
                for sha in built_commits:
                    if sha in all_shas:
                        all_shas.remove(sha)

                num_commits_on_files = len(all_shas)
            except Exception as e:
                logger.warning(f"Failed to count commits on files: {e}")

        return {
            "gh_team_size": len(team_members),
            "gh_by_core_team_member": is_core_member,
            "gh_num_commits_on_files_touched": num_commits_on_files,
        }

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "git_prev_commit_resolution_status": None,
            "git_prev_built_commit": None,
            "tr_prev_build": None,
            "gh_team_size": None,
            "git_all_built_commits": [],
            "git_num_all_built_commits": None,
            "gh_by_core_team_member": None,
            "gh_num_commits_on_files_touched": None,
            "git_diff_src_churn": 0,
            "git_diff_test_churn": 0,
            "gh_diff_files_added": 0,
            "gh_diff_files_deleted": 0,
            "gh_diff_files_modified": 0,
            "gh_diff_tests_added": 0,
            "gh_diff_tests_deleted": 0,
            "gh_diff_src_files": 0,
            "gh_diff_doc_files": 0,
            "gh_diff_other_files": 0,
        }
