import os
import sys
import tkinter as tk
from tkinter import messagebox

# Adjust path to import from app package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.config import RESOURCES_DIR
from app.pet import DesktopPet

def verify_assets():
    """Verify that all required processed assets are present in the resources directory."""
    required_files = ["idle.png", "dragged.png", "action.png", "sleeping.png"]
    missing = []
    
    for f in required_files:
        path = os.path.join(RESOURCES_DIR, f)
        if not os.path.exists(path):
            missing.append(f)
            
    if missing:
        # Create a basic tk root for showing error box if needed
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Missing Assets",
            f"Required transparent character assets are missing from the resources folder:\n"
            f"{', '.join(missing)}\n\n"
            "Please ensure you've run the image generation and processing steps."
        )
        sys.exit(1)

def main():
    # Make sure resources folder and processed PNGs exist
    verify_assets()
    
    # Initialize and run Desktop Pet app
    print("Launching Anika, your Bangladeshi Witch companion...")
    app = DesktopPet()
    
    # Run the tkinter mainloop
    app.mainloop()

if __name__ == "__main__":
    main()
