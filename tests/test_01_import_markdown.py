import os
import json
import pytest
from tests.conftest import import_step


@pytest.fixture
def md_module():
    return import_step("01_import_markdown")


class TestImportMarkdown:
    def test_copies_md_files(self, md_module, tmp_path):
        """Should copy all .md files from source to output directory."""
        source = tmp_path / "docs"
        source.mkdir()
        (source / "one.md").write_text("# One")
        (source / "two.md").write_text("# Two")

        output = tmp_path / "content"
        count = md_module.import_markdown(str(source), str(output))

        assert count == 2
        assert (output / "one.md").read_text() == "# One"
        assert (output / "two.md").read_text() == "# Two"

    def test_ignores_non_md_files(self, md_module, tmp_path):
        """Should only copy .md files, not other file types."""
        source = tmp_path / "docs"
        source.mkdir()
        (source / "readme.md").write_text("# Readme")
        (source / "notes.txt").write_text("not markdown")
        (source / "data.json").write_text("{}")

        output = tmp_path / "content"
        count = md_module.import_markdown(str(source), str(output))

        assert count == 1
        assert (output / "readme.md").exists()
        assert not (output / "notes.txt").exists()
        assert not (output / "data.json").exists()

    def test_preserves_source_url_header(self, md_module, tmp_path):
        """Files with Source URL headers should be copied verbatim."""
        source = tmp_path / "docs"
        source.mkdir()
        content = "# My Page\n**Source URL:** https://example.com/page\n\nBody text."
        (source / "page.md").write_text(content)

        output = tmp_path / "content"
        md_module.import_markdown(str(source), str(output))

        assert (output / "page.md").read_text() == content

    def test_exits_on_nonexistent_source(self, md_module, tmp_path):
        """Should exit with code 1 if source directory doesn't exist."""
        with pytest.raises(SystemExit) as exc_info:
            md_module.import_markdown(str(tmp_path / "nope"), str(tmp_path / "out"))

        assert exc_info.value.code == 1

    def test_exits_on_empty_folder(self, md_module, tmp_path):
        """Should exit with code 1 if source has no .md files."""
        source = tmp_path / "empty"
        source.mkdir()
        (source / "notes.txt").write_text("not markdown")

        with pytest.raises(SystemExit) as exc_info:
            md_module.import_markdown(str(source), str(tmp_path / "out"))

        assert exc_info.value.code == 1

    def test_creates_output_dir(self, md_module, tmp_path):
        """Should create the output directory if it doesn't exist."""
        source = tmp_path / "docs"
        source.mkdir()
        (source / "a.md").write_text("# A")

        output = tmp_path / "nested" / "content"
        md_module.import_markdown(str(source), str(output))

        assert output.is_dir()
        assert (output / "a.md").exists()


class TestCreateRunDir:
    def test_creates_named_run_dir(self, md_module, tmp_path, monkeypatch):
        """Should create runs/<name>_<timestamp>/ directory."""
        monkeypatch.chdir(tmp_path)
        run_dir = md_module.create_run_dir("my-docs")

        assert os.path.isdir(run_dir)
        assert run_dir.startswith("runs/my-docs_")

    def test_different_names_different_dirs(self, md_module, tmp_path, monkeypatch):
        """Different names should produce different directory prefixes."""
        monkeypatch.chdir(tmp_path)
        dir1 = md_module.create_run_dir("alpha")
        dir2 = md_module.create_run_dir("beta")

        assert "alpha_" in dir1
        assert "beta_" in dir2


class TestWriteRunInfo:
    def test_writes_run_info_json(self, md_module, tmp_path):
        """Should write .run_info.json with expected fields."""
        run_dir = str(tmp_path / "test_run")
        os.makedirs(run_dir)
        md_module.write_run_info(run_dir, "my-docs", "/some/source")

        info_path = os.path.join(run_dir, ".run_info.json")
        assert os.path.exists(info_path)

        with open(info_path) as f:
            info = json.load(f)

        assert info["name"] == "my-docs"
        assert info["source_type"] == "markdown"
        assert "timestamp" in info
        assert "source_dir" in info

    def test_source_type_is_markdown(self, md_module, tmp_path):
        """source_type should always be 'markdown'."""
        run_dir = str(tmp_path / "run")
        os.makedirs(run_dir)
        md_module.write_run_info(run_dir, "test", "/tmp")

        with open(os.path.join(run_dir, ".run_info.json")) as f:
            info = json.load(f)

        assert info["source_type"] == "markdown"
