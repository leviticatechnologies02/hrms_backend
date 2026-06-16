import os

uploads_dir = "uploads"
print("--- Directories and Files in uploads/ ---")
if os.path.exists(uploads_dir):
    for root, dirs, files in os.walk(uploads_dir):
        print(f"Directory: {root}")
        for f in files[:10]: # Print first 10 files
            print(f"  File: {f}")
else:
    print("uploads directory does not exist!")
