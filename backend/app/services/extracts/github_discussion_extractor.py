import logging
from typing import Any, Dict

from app.models.entities.build_sample import BuildSample
from app.models.entities.imported_repository import ImportedRepository
from app.models.entities.workflow_run import WorkflowRunRaw
from app.services.github.github_client import (
    get_app_github_client,
    get_public_github_client,
)
from pymongo.database import Database

logger = logging.getLogger(__name__)


class GitHubDiscussionExtractor:
    def __init__(self, db: Database):
        self.db = db

    def extract(
        self,
        build_sample: BuildSample,
        workflow_run: WorkflowRunRaw,
        repo: ImportedRepository,
    ) -> Dict[str, Any]:
        commit_sha = build_sample.tr_original_commit
        if not commit_sha:
            return self._empty_result()

        # Calculate gh_description_complexity
        payload = workflow_run.raw_payload
        pull_requests = payload.get("pull_requests", [])
        pr_number = None
        description_complexity = None

        if pull_requests:
            pr_data = pull_requests[0]
            pr_number = pr_data.get("number")
            title = pr_data.get("title", "")
            body = pr_data.get("body", "")
            description_complexity = len((title or "").split()) + len(
                (body or "").split()
            )
        elif payload.get("event") == "pull_request":
            # If event is PR but pull_requests list is empty (unlikely but possible in some payloads)
            # Try to get from payload directly
            pr_number = payload.get("number")

        installation_id = repo.installation_id
        if not installation_id:
            logger.warning(f"No installation ID for repo {repo.full_name}")
            # Return what we have if we can't access API
            return {
                **self._empty_result(),
                "gh_description_complexity": description_complexity,
            }

        try:
            with get_app_github_client(self.db, installation_id) as gh:
                # Fetch PR details if complexity not yet calculated and we have a PR number
                if description_complexity is None and pr_number:
                    try:
                        pr_details = gh.get_pull_request(repo.full_name, pr_number)
                        title = pr_details.get("title", "")
                        body = pr_details.get("body", "")
                        description_complexity = len((title or "").split()) + len(
                            (body or "").split()
                        )
                    except Exception as e:
                        logger.warning(
                            f"Failed to fetch PR details for complexity: {e}"
                        )

                # 1. Commit comments
                commit_comments = gh.list_commit_comments(repo.full_name, commit_sha)
                num_commit_comments = len(commit_comments)

                # 2. PR comments & Issue comments
                # We need to find the PR associated with this commit
                # This is tricky. GitHub API lists PRs associated with a commit.
                # GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls

                # GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls

                # Since our client doesn't have list_pulls_for_commit, we might need to add it or use raw request
                try:
                    prs = gh._rest_request(
                        "GET", f"/repos/{repo.full_name}/commits/{commit_sha}/pulls"
                    )
                except Exception as e:
                    # Check if it's a 403 Forbidden error
                    error_str = str(e)
                    if "403" in error_str or (
                        hasattr(e, "response") and e.response.status_code == 403
                    ):
                        logger.warning(
                            f"Missing permissions to list PRs for {repo.full_name}. "
                            "Please ensure the GitHub App has 'Pull requests: Read-only' permission."
                        )
                    else:
                        logger.warning(
                            f"Failed to list PRs for commit {commit_sha}: {e}"
                        )
                    prs = []

                num_pr_comments = 0
                num_issue_comments = 0

                processed_prs = set()

                if isinstance(prs, list):
                    for pr in prs:
                        pr_number_loop = pr.get("number")
                        if not pr_number_loop or pr_number_loop in processed_prs:
                            continue

                        processed_prs.add(pr_number_loop)

                        # PR Review Comments
                        reviews = gh.list_review_comments(
                            repo.full_name, pr_number_loop
                        )
                        num_pr_comments += len(reviews)

                        # Issue Comments (General conversation on PR)
                        issue_comments = gh.list_issue_comments(
                            repo.full_name, pr_number_loop
                        )
                        num_issue_comments += len(issue_comments)

                return {
                    "gh_num_issue_comments": num_issue_comments,
                    "gh_num_commit_comments": num_commit_comments,
                    "gh_num_pr_comments": num_pr_comments,
                    "gh_description_complexity": description_complexity,
                }

        except Exception as e:
            logger.error(
                f"Failed to extract discussion features for {repo.full_name}: {e}"
            )
            return self._empty_result()

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "gh_num_issue_comments": 0,
            "gh_num_commit_comments": 0,
            "gh_num_pr_comments": 0,
            "gh_description_complexity": None,
        }
