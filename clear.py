# Above-95 delete the all files in the folder code 


"""Script to check and fix Azure Blob Storage folder issues."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient

# Load environment variables from backend/.env
backend_env_path = Path(__file__).parent / "backend" / ".env"
if backend_env_path.exists():
    load_dotenv(backend_env_path)
    print(f"Loaded environment from: {backend_env_path}")
else:
    # Try loading from current directory
    load_dotenv()
    print("Loaded environment from current directory")

connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
container_name = os.getenv('AZURE_BLOB_CONTAINER', 'ocr-documents')

if not connection_string:
    print("ERROR: AZURE_STORAGE_CONNECTION_STRING not found in environment")
    print(f"Checked: {backend_env_path}")
    sys.exit(1)

# Initialize blob service client
blob_service_client = BlobServiceClient.from_connection_string(connection_string)
container_client = blob_service_client.get_container_client(container_name)

print(f"Checking container: {container_name}")
print("=" * 80)

# List all blobs in the main folder
all_folders = set()
problematic_blobs = []

print("\nScanning for folders...")
blob_list = container_client.list_blobs(name_starts_with="main/")

for blob in blob_list:
    path_parts = blob.name.split('/')
    if len(path_parts) >= 2:
        folder_name = path_parts[1]  # Get the folder after "main/"
        all_folders.add(folder_name)
        
        # Check for "Above-95" (without %) - this is the problematic folder
        # Make sure it's NOT "Above-95%" (which is correct)
        if len(path_parts) >= 2 and path_parts[1] == "Above-95":
            problematic_blobs.append(blob.name)

print(f"\nFound {len(all_folders)} unique folders under 'main/':")
for folder in sorted(all_folders):
    if folder == "Above-95":
        print(f"  - {folder} ⚠️  PROBLEMATIC (should be 'Above-95%')")
    elif folder == "Above-95%":
        print(f"  - {folder} ✓ CORRECT")
    else:
        print(f"  - {folder}")

if problematic_blobs:
    print(f"\n⚠️  Found {len(problematic_blobs)} files in problematic 'Above-95' folder (without %):")
    for blob_name in problematic_blobs[:10]:  # Show first 10
        print(f"  - {blob_name}")
    if len(problematic_blobs) > 10:
        print(f"  ... and {len(problematic_blobs) - 10} more")
    
    print("\n" + "=" * 80)
    print("SOLUTION OPTIONS:")
    print("1. Delete all files in 'Above-95' folder (without %)")
    print("2. Move files from 'Above-95' to 'Above-95%' folder")
    print("3. Exit without changes")
    
    choice = input("\nEnter your choice (1/2/3): ").strip()
    
    if choice == "1":
        print("\nDeleting files in 'Above-95' folder...")
        for blob_name in problematic_blobs:
            try:
                blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
                blob_client.delete_blob()
                print(f"  ✓ Deleted: {blob_name}")
            except Exception as e:
                print(f"  ✗ Failed to delete {blob_name}: {e}")
        print("\n✅ Cleanup complete!")
        
    elif choice == "2":
        print("\nMoving files from 'Above-95' to 'Above-95%'...")
        for blob_name in problematic_blobs:
            try:
                # Replace "Above-95" with "Above-95%" (only the folder part)
                new_blob_name = blob_name.replace("main/Above-95/", "main/Above-95%/")
                
                source_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
                dest_client = blob_service_client.get_blob_client(container=container_name, blob=new_blob_name)
                
                # Copy to new location
                dest_client.start_copy_from_url(source_client.url)
                
                # Wait a moment for copy to complete
                import time
                time.sleep(0.5)
                
                # Delete original
                source_client.delete_blob()
                
                print(f"  ✓ Moved: {blob_name} -> {new_blob_name}")
            except Exception as e:
                print(f"  ✗ Failed to move {blob_name}: {e}")
        print("\n✅ Migration complete!")
        
    else:
        print("\nExiting without changes.")
else:
    print("\n✅ No problematic 'Above-95' folders found!")
    print("All folders are using the correct naming convention.")
