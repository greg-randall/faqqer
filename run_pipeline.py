import os
import sys
import subprocess
import argparse

def run_step(script_name, args=None):
    """Runs a python script and exits if it fails."""
    if args is None:
        args = []
    print(f"\n{'='*60}")
    print(f"RUNNING: {script_name}")
    print(f"{'='*60}")

    cmd = [sys.executable, script_name] + args
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\nError: {script_name} failed with exit code {result.returncode}.")
        sys.exit(result.returncode)

def main():
    parser = argparse.ArgumentParser(description="Run the Faqqer pipeline (Steps 01-06).")
    parser.add_argument("xml_file", help="Path to the WordPress XML export file.")
    args = parser.parse_args()

    if not os.path.exists(args.xml_file):
        print(f"Error: File '{args.xml_file}' not found.")
        sys.exit(1)

    # --- PIPELINE EXECUTION ---

    # Step 1: Extract
    run_step("01_extract_content.py", [args.xml_file])

    # Step 2: Process (Atomize)
    run_step("02_process_content.py")

    # Step 3: Embeddings
    run_step("03_generate_embeddings.py")

    # Step 4: Clustering
    run_step("04_cluster_facts.py")

    # Step 5: FAQ Generation
    run_step("05_generate_faq.py")

    # Step 6: Enrich (Categorize + URLs + Audit/Score)
    run_step("06_enrich_faq.py")

    # --- HANDOFF ---
    print(f"\n{'='*60}")
    print("AUTOMATED PIPELINE COMPLETE")
    print(f"{'='*60}")
    print("\nNext Steps:")
    print("1. Start the Review Server:")
    print("   php -S localhost:8000")
    print("\n2. Open your browser to review FAQs:")
    print("   http://localhost:8000/07_faq_reviewer.php")
    print("\n3. When finished approving items, run:")
    print("   python 08_generate_wp_html.py")

if __name__ == "__main__":
    main()
