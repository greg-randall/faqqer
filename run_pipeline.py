import os
import sys
import json
import subprocess
import argparse


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
    parser.add_argument("input_path", nargs='?', default=None,
                        help="Path to a WordPress XML file or a directory of .md files.")
    parser.add_argument("--run-dir", dest="run_dir", default=None,
                        help="Resume into an existing run directory (skips step 01).")
    args = parser.parse_args()

    # Validate: need either input_path or --run-dir
    if not args.input_path and not args.run_dir:
        parser.error("Either provide an input path or use --run-dir to resume.")

    # --- STEP 01: Import ---

    if args.run_dir:
        # Skip step 01 entirely — resume from existing run
        run_dir = args.run_dir
        if not os.path.isdir(run_dir):
            print(f"Error: Run directory '{run_dir}' not found.")
            sys.exit(1)
    else:
        input_path = args.input_path

        if not os.path.exists(input_path):
            print(f"Error: '{input_path}' not found.")
            sys.exit(1)

        # Auto-detect input type
        if os.path.isdir(input_path):
            # Markdown folder
            step01_script = "01_import_markdown.py"
            step01_args = [input_path]
        elif input_path.lower().endswith('.xml'):
            # WordPress XML
            step01_script = "01_import_wordpress.py"
            step01_args = [input_path]
        else:
            print(f"Error: Unrecognized input type for '{input_path}'. Expected a directory or .xml file.")
            sys.exit(1)

        run_step(step01_script, step01_args)

        # Find the run dir that step 01 just created
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
