import os
import sys
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

        with patch.object(pipeline_module.subprocess, 'run',
                         return_value=MagicMock(returncode=0)) as mock_run, \
             patch.object(pipeline_module, 'os') as mock_os, \
             patch('sys.argv', ['run_pipeline.py', xml_file]):
            mock_os.path.exists.return_value = True
            pipeline_module.main()

        # Should have called subprocess.run 6 times (steps 01-06)
        assert mock_run.call_count == 6

    def test_mid_pipeline_failure(self, pipeline_module, tmp_path):
        """If a step fails, pipeline should exit with that return code."""
        xml_file = str(tmp_path / "test.xml")
        with open(xml_file, 'w') as f:
            f.write("<rss></rss>")

        fail_result = MagicMock(returncode=1)
        success_result = MagicMock(returncode=0)

        with patch.object(pipeline_module.subprocess, 'run',
                         side_effect=[success_result, fail_result]) as mock_run, \
             patch.object(pipeline_module, 'os') as mock_os, \
             patch('sys.argv', ['run_pipeline.py', xml_file]):
            mock_os.path.exists.return_value = True
            with pytest.raises(SystemExit) as exc_info:
                pipeline_module.main()

        assert exc_info.value.code == 1

    def test_missing_xml_file(self, pipeline_module, tmp_path, capsys):
        """Should print error and exit if XML file doesn't exist."""
        with patch('sys.argv', ['run_pipeline.py', '/nonexistent/file.xml']):
            with pytest.raises(SystemExit) as exc_info:
                pipeline_module.main()

        assert exc_info.value.code == 1
