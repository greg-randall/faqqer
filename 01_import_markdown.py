import sys
import os
import json
import shutil
import argparse
from datetime import datetime


def create_run_dir(name):
    """Create a timestamped run directory under runs/."""
    timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
    run_name = f"{name}_{timestamp}"
    run_dir = os.path.join('runs', run_name)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def write_run_info(run_dir, name, source_dir):
    """Write .run_info.json with metadata about this run."""
    info = {
        'name': name,
        'source_type': 'markdown',
        'timestamp': datetime.now().isoformat(),
        'source_dir': os.path.abspath(source_dir),
    }
    info_path = os.path.join(run_dir, '.run_info.json')
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, indent=2)


def import_markdown(source_dir, output_dir):
    """
    Copies all .md files from source_dir into output_dir.
    Returns the count of files copied.
    """
    if not os.path.isdir(source_dir):
        print(f"Error: '{source_dir}' is not a directory.")
        sys.exit(1)

    md_files = [f for f in os.listdir(source_dir) if f.endswith('.md')]

    if not md_files:
        print(f"Error: No .md files found in '{source_dir}'.")
        sys.exit(1)

    os.makedirs(output_dir, exist_ok=True)

    count = 0
    for filename in md_files:
        src = os.path.join(source_dir, filename)
        dst = os.path.join(output_dir, filename)
        shutil.copy2(src, dst)
        count += 1

    print(f"Success! Imported {count} markdown files to '{output_dir}/'.")
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import a folder of Markdown files into the pipeline.")
    parser.add_argument("source_dir", help="Path to a directory containing .md files.")
    parser.add_argument("--name", default=None,
                        help="Name prefix for the run directory (defaults to folder basename).")
    parser.add_argument("--run-dir", dest="run_dir", default=None,
                        help="Resume into an existing run directory instead of creating a new one.")
    args = parser.parse_args()

    source_dir = args.source_dir
    name = args.name or os.path.basename(os.path.normpath(source_dir))

    if args.run_dir:
        run_dir = args.run_dir
        output_folder = os.path.join(run_dir, "content")
    else:
        run_dir = create_run_dir(name)
        write_run_info(run_dir, name, source_dir)
        output_folder = os.path.join(run_dir, "content")
        os.environ['FAQQER_RUN_DIR'] = run_dir

    import_markdown(source_dir, output_folder)
    print(f"FAQQER_RUN_DIR={run_dir}")
