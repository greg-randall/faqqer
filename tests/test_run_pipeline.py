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
    def test_successful_run_with_run_dir(self, pipeline_module, tmp_path):
        """With --run-dir, step 01 is skipped — only steps 02-06 run (5 calls)."""
        run_dir = str(tmp_path / "runs" / "test_run")
        os.makedirs(run_dir)

        with patch.object(pipeline_module.subprocess, 'run',
                         return_value=MagicMock(returncode=0)) as mock_run, \
             patch('sys.argv', ['run_pipeline.py', '--run-dir', run_dir]):
            pipeline_module.main()

        assert mock_run.call_count == 5

    def test_successful_run_xml(self, pipeline_module, tmp_path):
        """XML input auto-detects to 01_import_wordpress.py — 6 calls total."""
        xml_file = str(tmp_path / "test.xml")
        with open(xml_file, 'w') as f:
            f.write("<rss></rss>")

        # Create a fake run dir for find_run_dir_from_step01 to discover
        run_dir = str(tmp_path / "runs" / "test_run")
        os.makedirs(run_dir)
        with open(os.path.join(run_dir, ".run_info.json"), 'w') as f:
            json.dump({"domain": "test"}, f)

        with patch.object(pipeline_module.subprocess, 'run',
                         return_value=MagicMock(returncode=0)) as mock_run, \
             patch.object(pipeline_module, 'find_run_dir_from_step01',
                         return_value=run_dir), \
             patch('sys.argv', ['run_pipeline.py', xml_file]):
            pipeline_module.main()

        assert mock_run.call_count == 6
        # First call should be the wordpress importer
        first_cmd = mock_run.call_args_list[0][0][0]
        assert '01_import_wordpress.py' in first_cmd

    def test_successful_run_markdown_dir(self, pipeline_module, tmp_path):
        """Directory input auto-detects to 01_import_markdown.py — 6 calls total."""
        md_dir = str(tmp_path / "my_docs")
        os.makedirs(md_dir)
        with open(os.path.join(md_dir, "test.md"), 'w') as f:
            f.write("# Test")

        run_dir = str(tmp_path / "runs" / "test_run")
        os.makedirs(run_dir)
        with open(os.path.join(run_dir, ".run_info.json"), 'w') as f:
            json.dump({"name": "test"}, f)

        with patch.object(pipeline_module.subprocess, 'run',
                         return_value=MagicMock(returncode=0)) as mock_run, \
             patch.object(pipeline_module, 'find_run_dir_from_step01',
                         return_value=run_dir), \
             patch('sys.argv', ['run_pipeline.py', md_dir]):
            pipeline_module.main()

        assert mock_run.call_count == 6
        first_cmd = mock_run.call_args_list[0][0][0]
        assert '01_import_markdown.py' in first_cmd

    def test_mid_pipeline_failure(self, pipeline_module, tmp_path):
        """If a step fails, pipeline should exit with that return code."""
        run_dir = str(tmp_path / "runs" / "test_run")
        os.makedirs(run_dir)

        fail_result = MagicMock(returncode=1)
        success_result = MagicMock(returncode=0)

        with patch.object(pipeline_module.subprocess, 'run',
                         side_effect=[success_result, fail_result]) as mock_run, \
             patch('sys.argv', ['run_pipeline.py', '--run-dir', run_dir]):
            with pytest.raises(SystemExit) as exc_info:
                pipeline_module.main()

        assert exc_info.value.code == 1

    def test_env_var_passed_to_steps(self, pipeline_module, tmp_path):
        """Steps 02-06 should receive FAQQER_RUN_DIR in their environment."""
        run_dir = str(tmp_path / "runs" / "test_run")
        os.makedirs(run_dir)
        captured_envs = []

        def capture_env(cmd, env=None):
            if env:
                captured_envs.append(env.get('FAQQER_RUN_DIR'))
            else:
                captured_envs.append(None)
            return MagicMock(returncode=0)

        with patch.object(pipeline_module.subprocess, 'run', side_effect=capture_env), \
             patch('sys.argv', ['run_pipeline.py', '--run-dir', run_dir]):
            pipeline_module.main()

        # With --run-dir, step 01 is skipped; all 5 calls (steps 02-06) get env
        assert len(captured_envs) == 5
        for env_val in captured_envs:
            assert env_val == run_dir

    def test_missing_input(self, pipeline_module, tmp_path):
        """Should exit if input path doesn't exist."""
        with patch('sys.argv', ['run_pipeline.py', '/nonexistent/file.xml']):
            with pytest.raises(SystemExit) as exc_info:
                pipeline_module.main()

        assert exc_info.value.code == 1

    def test_no_args_errors(self, pipeline_module):
        """Should error when neither input_path nor --run-dir is given."""
        with patch('sys.argv', ['run_pipeline.py']):
            with pytest.raises(SystemExit):
                pipeline_module.main()


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
