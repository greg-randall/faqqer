import os
import sys
import json
import subprocess
import argparse
import xml.etree.ElementTree as ET


def run_step(script_name, args=None, env=None):
    """Runs a python script and exits if it fails."""
    if args is None:
        args = []
    print(f"\n{'='*60}")
    print(f"RUNNING: {script_name}")
    print(f"{'='*60}")

    cmd = [sys.executable, script_name] + args
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
    result = subprocess.run(cmd, env=run_env)

    if result.returncode != 0:
        print(f"\nError: {script_name} failed with exit code {result.returncode}.")
        sys.exit(result.returncode)


def find_run_dir_from_step01():
    """Find the most recently created .run_info.json under runs/."""
    runs_dir = 'runs'
    if not os.path.isdir(runs_dir):
        return None

    latest = None
    latest_mtime = 0
    for entry in os.listdir(runs_dir):
        info_path = os.path.join(runs_dir, entry, '.run_info.json')
        if os.path.isfile(info_path):
            mtime = os.path.getmtime(info_path)
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest = os.path.join(runs_dir, entry)
    return latest


def main():
    parser = argparse.ArgumentParser(description="Run the Faqqer pipeline (Steps 01-06).")
    parser.add_argument("xml_file", help="Path to the WordPress XML export file.")
    parser.add_argument("--run-dir", dest="run_dir", default=None,
                        help="Resume into an existing run directory instead of creating a new one.")
    args = parser.parse_args()

    if not os.path.exists(args.xml_file):
        print(f"Error: File '{args.xml_file}' not found.")
        sys.exit(1)

    # --- PIPELINE EXECUTION ---

    # Step 1: Extract (creates run dir)
    step01_args = [args.xml_file]
    if args.run_dir:
        step01_args += ['--run-dir', args.run_dir]
    run_step("01_extract_content.py", step01_args)

    # Determine run dir: either specified or find the one step 01 just created
    if args.run_dir:
        run_dir = args.run_dir
    else:
        run_dir = find_run_dir_from_step01()
        if not run_dir:
            print("Error: Could not find run directory created by step 01.")
            sys.exit(1)

    print(f"\nRun directory: {run_dir}")
    step_env = {'FAQQER_RUN_DIR': run_dir}

    # Step 2: Process (Atomize)
    run_step("02_process_content.py", env=step_env)

    # Step 3: Embeddings
    run_step("03_generate_embeddings.py", env=step_env)

    # Step 4: Clustering
    run_step("04_cluster_facts.py", env=step_env)

    # Step 5: FAQ Generation
    run_step("05_generate_faq.py", env=step_env)

    # Step 6: Enrich (Categorize + URLs + Audit/Score)
    run_step("06_enrich_faq.py", env=step_env)

    # --- HANDOFF ---
    print(f"\n{'='*60}")
    print("AUTOMATED PIPELINE COMPLETE")
    print(f"{'='*60}")
    print(f"\nAll output saved to: {run_dir}/")
    print("\nNext Steps:")
    print("1. Start the Review Server:")
    print(f"   FAQQER_RUN_DIR={run_dir} php -S localhost:8000")
    print("\n2. Open your browser to review FAQs:")
    print(f"   http://localhost:8000/07_faq_reviewer.php?run_dir={run_dir}")
    print("\n3. When finished approving items, run:")
    print(f"   FAQQER_RUN_DIR={run_dir} python 08_generate_wp_html.py")

if __name__ == "__main__":
    main()
