import shutil
import tempfile
import unittest
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

# Mocking modules that might not be easily importable or initialized in test env
sys.modules["app.pipeline.resources"] = MagicMock()
sys.modules["app.pipeline.resources.git_repo"] = MagicMock()
from app.pipeline.resources import ResourceNames
from app.pipeline.resources.git_repo import GitRepoHandle

# Import the nodes under test
from app.pipeline.features.git.commit_info import GitCommitInfoNode
from app.pipeline.features.git.team_stats import TeamStatsNode
from app.pipeline.core.context import ExecutionContext

class TestGitPipelineFeatures(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self._init_repo()
        
        # Common Mock Setup
        self.db = MagicMock()
        self.build_sample = MagicMock()
        self.build_sample.repo_id = "test_repo_id"
        self.build_sample.workflow_run_id = 100
        self.build_sample.created_at = datetime.now(timezone.utc)
        
        self.git_handle = MagicMock()
        self.git_handle.path = self.test_dir
        self.git_handle.is_commit_available = True
        
        # Use real git repo object for handle
        from git import Repo
        self.repo = Repo(self.test_dir)
        self.git_handle.repo = self.repo
        
        self.context = MagicMock(spec=ExecutionContext)
        self.context.db = self.db
        self.context.build_sample = self.build_sample
        self.context.get_resource.side_effect = lambda name: \
            self.git_handle if name == ResourceNames.GIT_REPO else None
            
        # Feature dictionary for context
        self.features = {}
        self.context.get_feature.side_effect = lambda name, default=None: self.features.get(name, default)


    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _init_repo(self):
        subprocess.run(["git", "init"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "branch", "-M", "main"], cwd=self.test_dir, check=True)
        self._set_git_identity("Test User", "test@example.com")
        
    def _set_git_identity(self, name, email):
        subprocess.run(["git", "config", "user.name", name], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.email", email], cwd=self.test_dir, check=True)

    def _commit(self, message, allow_empty=False):
        if not allow_empty:
            (self.test_dir / "file.txt").write_text(f"content {message}")
            subprocess.run(["git", "add", "file.txt"], cwd=self.test_dir, check=True)
        
        subprocess.run(["git", "commit", "--allow-empty", "-m", message], cwd=self.test_dir, check=True)
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.test_dir, text=True).strip()

    def test_commit_info_walking(self):
        """Test that GitCommitInfoNode correctly walks history to find previous build."""
        
        # History: C1 -> C2 -> C3
        c1 = self._commit("C1")
        c2 = self._commit("C2")
        c3 = self._commit("C3")
        
        self.git_handle.effective_sha = c3
        
        # Mock DB: C1 was a completed build
        # The node calls: db["build_samples"].find_one(...)
        
        def find_one_side_effect(query):
            # Check if query matches C1
            if query.get("tr_original_commit") == c1 and query.get("status") == "completed":
                return {
                    "workflow_run_id": 99,
                    "tr_original_commit": c1,
                    "status": "completed"
                }
            return None
            
        self.db.__getitem__.return_value.find_one.side_effect = find_one_side_effect
        
        node = GitCommitInfoNode()
        result = node.extract(self.context)
        
        # Expectation:
        # Prev built commit should be C1
        # Built commits should be [C3, C2] (or reverse, depending on implementation detail)
        # Note: Implementation logic was:
        # walker = repo.iter_commits(c3)
        # C3 -> loop, not built, append
        # C2 -> loop, not built, append
        # C1 -> loop, built! break.
        # prev_commits_objs = [C3, C2]
        
        self.assertEqual(result["git_prev_built_commit"], c1)
        self.assertEqual(result["tr_prev_build"], 99)
        self.assertEqual(result["git_prev_commit_resolution_status"], "build_found")
        
        # Verify built commits list
        self.assertIn(c2, result["git_all_built_commits"])
        self.assertIn(c3, result["git_all_built_commits"])
        self.assertNotIn(c1, result["git_all_built_commits"])
        self.assertEqual(result["git_num_all_built_commits"], 2)

    def test_team_stats_logic(self):
        """Test TeamStatsNode with mix of direct, PR, and squash commits."""
        
        start_date = datetime.now(timezone.utc) - timedelta(days=10)
        
        # 1. Direct Commit by Alice
        self._set_git_identity("Alice", "alice@example.com")
        c1 = self._commit("Feature A")
        
        # 2. Squash Commit by Bob (should be ignored)
        self._set_git_identity("Bob", "bob@example.com")
        c2 = self._commit("Squash (#123)")
        
        # 3. PR Merge Logic (simulated via DB)
        # We need to mock _get_pr_mergers return value or the DB call
        # Let's mock the DB call inside _get_pr_mergers
        # The node calls: db["build_samples"].find(...)
        
        # We'll just patch the helper method to avoid complex DB mocking for this part
        with patch.object(TeamStatsNode, '_get_pr_mergers', return_value={"charlie"}) as mock_mergers:
            
            self.git_handle.effective_sha = c2
            self.features["git_all_built_commits"] = [c2, c1]
            
            node = TeamStatsNode()
            result = node.extract(self.context)
            
            # Expected Team:
            # Alice (Direct)
            # Charlie (PR Merger)
            # Bob (Squashed - excluded)
            
            self.assertEqual(result["gh_team_size"], 2) 
            
            # Check Core Team Membership
            # Current commit (c2) author is Bob.
            # Bob is NOT in core team (he only did a squash).
            self.assertFalse(result["gh_by_core_team_member"])
            
            self.assertFalse(result["gh_by_core_team_member"])

    def test_get_pr_mergers_db_integration(self):
        """Test _get_pr_mergers method logic against mocked DB."""
        node = TeamStatsNode()
        
        # Mock DB Cursor
        start = datetime.now(timezone.utc)
        end = datetime.now(timezone.utc)
        
        # Run 1: PR run by "dev1"
        run1 = {
            "raw_payload": {
                "pull_requests": [{"number": 1}],
                "triggering_actor": {"login": "dev1"}
            }
        }
        # Run 2: Push run by "dev2" (not PR)
        run2 = {
            "raw_payload": {
                "event": "push",
                "pull_requests": [],
                "triggering_actor": {"login": "dev2"}
            }
        }
        # Run 3: PR event run by "dev3"
        run3 = {
            "raw_payload": {
                "event": "pull_request",
                "triggering_actor": {"login": "dev3"}
            }
        }
        
        mock_cursor = [run1, run2, run3]
        self.db.__getitem__.return_value.find.return_value = mock_cursor
        
        mergers = node._get_pr_mergers(self.db, "dummy_repo_id", start, end)
        
        self.assertIn("dev1", mergers)
        self.assertIn("dev3", mergers)
        self.assertNotIn("dev2", mergers)

