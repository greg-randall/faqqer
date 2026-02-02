import os
import sys
import subprocess
import argparse

def run_step(script_name, args=[]):
    """Runs a python script and exits if it fails."""
    print(f"\n{'='*60}")
    print(f"RUNNING: {script_name}")
    print(f"{'='*60}")
    
    cmd = [sys.executable, script_name] + args
    result = subprocess.run(cmd)
    
    if result.returncode != 0:
        print(f"\n❌ Error: {script_name} failed with exit code {result.returncode}.")
        sys.exit(result.returncode)

def main():
    parser = argparse.ArgumentParser(description="Run the Faqqer pipeline (Steps 01-08).")
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
    run_step("04_cluster_facts_hdbscan.py")

    # Step 5: FAQ Generation
    run_step("05_generate_faq.py")

    # Step 6: Categorization
    run_step("06_categories.py")

    # Step 7: URL Enrichment
    run_step("07_add_urls_to_sources.py")

    # Step 8: Audit & Eval
    run_step("08_faq_llm_review.py")

    # --- HANDOFF ---
    print(f"\n{'='*60}")
    print("✅ AUTOMATED PIPELINE COMPLETE")
    print(f"{'='*60}")
    print("\nNext Steps:")
    print("1. Start the Review Server:")
    print("   php -S localhost:8000")
    print("\n2. Open your browser to review FAQs:")
    print("   http://localhost:8000/09_faq_reviewer.php")
    print("\n3. When finished approving items, run:")
    print("   python 10_generate_wp_html.py")

if __name__ == "__main__":
    main()
