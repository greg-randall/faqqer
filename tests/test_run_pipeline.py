import os
import sys
import json
import time
import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import import_step


@pytest.fixture
def pipeline_module():
    return import_step("run_pipeline")


class TestRunPipeline:
    def test_successful_run(self, pipeline_module, tmp_path):
        """All steps succeed — pipeline completes without exit."""
        xml_file = str(tmp_path / "test.xml")
        with open(xml_file, 'w') as f:
            f.write("<rss></rss>")

        run_dir = str(tmp_path / "runs" / "test_run")

        with patch.object(pipeline_module.subprocess, 'run',
                         return_value=MagicMock(returncode=0)) as mock_run, \
             patch.object(pipeline_module, 'os') as mock_os, \
             patch('sys.argv', ['run_pipeline.py', xml_file, '--run-dir', run_dir]):
            mock_os.path.exists.return_value = True
            mock_os.environ = os.environ.copy()
            pipeline_module.main()

        # Should have called subprocess.run 6 times (steps 01-06)
        assert mock_run.call_count == 6

    def test_mid_pipeline_failure(self, pipeline_module, tmp_path):
        """If a step fails, pipeline should exit with that return code."""
        xml_file = str(tmp_path / "test.xml")
        with open(xml_file, 'w') as f:
            f.write("<rss></rss>")

        run_dir = str(tmp_path / "runs" / "test_run")
        fail_result = MagicMock(returncode=1)
        success_result = MagicMock(returncode=0)

        with patch.object(pipeline_module.subprocess, 'run',
                         side_effect=[success_result, fail_result]) as mock_run, \
             patch.object(pipeline_module, 'os') as mock_os, \
             patch('sys.argv', ['run_pipeline.py', xml_file, '--run-dir', run_dir]):
            mock_os.path.exists.return_value = True
            mock_os.environ = os.environ.copy()
            with pytest.raises(SystemExit) as exc_info:
                pipeline_module.main()

        assert exc_info.value.code == 1

    def test_env_var_passed_to_steps(self, pipeline_module, tmp_path):
        """Steps 02-06 should receive FAQQER_RUN_DIR in their environment."""
        xml_file = str(tmp_path / "test.xml")
        with open(xml_file, 'w') as f:
            f.write("<rss></rss>")

        run_dir = str(tmp_path / "runs" / "test_run")
        captured_envs = []

        def capture_env(cmd, env=None):
            if env:
                captured_envs.append(env.get('FAQQER_RUN_DIR'))
            return MagicMock(returncode=0)

        with patch.object(pipeline_module.subprocess, 'run', side_effect=capture_env), \
             patch.object(pipeline_module, 'os') as mock_os, \
             patch('sys.argv', ['run_pipeline.py', xml_file, '--run-dir', run_dir]):
            mock_os.path.exists.return_value = True
            mock_os.environ = os.environ.copy()
            pipeline_module.main()

        # Step 01 doesn't get env (uses --run-dir arg), steps 02-06 get it
        assert captured_envs[0] is None  # step 01
        for env_val in captured_envs[1:]:
            assert env_val == run_dir

    def test_missing_xml_file(self, pipeline_module, tmp_path, capsys):
        """Should print error and exit if XML file doesn't exist."""
        with patch('sys.argv', ['run_pipeline.py', '/nonexistent/file.xml']):
            with pytest.raises(SystemExit) as exc_info:
                pipeline_module.main()

        assert exc_info.value.code == 1


class TestFindRunDir:
    def test_finds_latest_run(self, pipeline_module, tmp_path, monkeypatch):
        """Should find the most recently modified .run_info.json."""
        monkeypatch.chdir(tmp_path)

        # Create two run dirs
        run1 = os.path.join("runs", "a.com_2026-01-01_100000")
        run2 = os.path.join("runs", "b.com_2026-01-02_100000")
        os.makedirs(run1)
        os.makedirs(run2)

        # Write run_info files with staggered times
        with open(os.path.join(run1, ".run_info.json"), 'w') as f:
            json.dump({"domain": "a.com"}, f)
        time.sleep(0.05)
        with open(os.path.join(run2, ".run_info.json"), 'w') as f:
            json.dump({"domain": "b.com"}, f)

        result = pipeline_module.find_run_dir_from_step01()
        assert result == run2

    def test_returns_none_without_runs_dir(self, pipeline_module, tmp_path, monkeypatch):
        """Should return None if runs/ doesn't exist."""
        monkeypatch.chdir(tmp_path)
        assert pipeline_module.find_run_dir_from_step01() is None

    def test_returns_none_empty_runs_dir(self, pipeline_module, tmp_path, monkeypatch):
        """Should return None if runs/ exists but has no .run_info.json files."""
        monkeypatch.chdir(tmp_path)
        os.makedirs("runs/some_dir")
        assert pipeline_module.find_run_dir_from_step01() is None
