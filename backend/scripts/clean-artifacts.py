import os
import shutil
import argparse

def get_project_root():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Assuming script is in backend/scripts/, root is ../../
    return os.path.abspath(os.path.join(script_dir, "..", ".."))

def clean_artifacts(dry_run=False):
    root = get_project_root()
    artifact_dir = os.path.join(root, ".harborpilot")
    
    print(f"Project Root: {root}")
    print(f"Artifact Dir: {artifact_dir}")
    
    if not os.path.exists(artifact_dir):
        print("Artifact directory does not exist. Nothing to clean.")
        return

    print("\n[Contents to appear to be deleted:]")
    for root_dir, dirs, files in os.walk(artifact_dir):
        for name in files:
            print(f" - {os.path.join(root_dir, name)}")
    
    if dry_run:
        print("\n[DRY RUN] No files were actually deleted.")
        return

    confirm = input("\nAre you sure you want to delete all runtime artifacts? (y/N): ").strip().lower()
    if confirm != 'y':
        print("Aborted.")
        return

    try:
        shutil.rmtree(artifact_dir)
        print(f"\nSuccessfully deleted {artifact_dir}")
    except Exception as e:
        print(f"Error deleting artifacts: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean HarborPilot runtime artifacts")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be deleted without actually deleting")
    args = parser.parse_args()
    
    clean_artifacts(dry_run=args.dry_run)
