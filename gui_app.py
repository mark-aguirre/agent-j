"""
Trading Bot Desktop Application
Main entry point for the GUI version
"""
import tkinter as tk
from tkinter import messagebox
import sys
import subprocess
import os
from pathlib import Path
from dotenv import load_dotenv

# Set working directory to executable location when frozen
if getattr(sys, 'frozen', False):
    # Running as compiled executable
    exe_dir = Path(sys.executable).parent
    # Only change directory if we're in a system directory
    if 'system32' in str(Path.cwd()).lower() or 'windows' in str(Path.cwd()).lower():
        os.chdir(exe_dir)
        print(f"Changed working directory to: {exe_dir}")

from src.__version__ import __version__, __app_name__
from src.config import load_config
from src.gui.main_window import MainWindow

def check_and_install_dependencies():
    """Check if dependencies are installed and install if needed"""
    try:
        # Try importing key dependencies
        import discord
        import MetaTrader5
        return True
    except ImportError:
        # Show installation dialog
        response = messagebox.askyesno(
            "Install Dependencies",
            "Required dependencies are missing.\n\n"
            "Would you like to install them now?\n"
            "(This may take a few minutes)"
        )
        
        if response:
            try:
                # Get the requirements.txt path
                app_dir = Path(__file__).parent
                requirements_file = app_dir / "requirements.txt"
                
                if not requirements_file.exists():
                    messagebox.showerror("Error", f"requirements.txt not found at:\n{requirements_file}")
                    return False
                
                # Show progress message
                progress_window = tk.Tk()
                progress_window.title("Installing Dependencies")
                progress_window.geometry("400x100")
                progress_window.resizable(False, False)
                
                tk.Label(progress_window, 
                        text="Installing dependencies...\nPlease wait, this may take a few minutes.",
                        font=("Segoe UI", 10),
                        pady=20).pack()
                
                progress_window.update()
                
                # Install dependencies
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
                    capture_output=True,
                    text=True
                )
                
                progress_window.destroy()
                
                if result.returncode == 0:
                    messagebox.showinfo(
                        "Success",
                        "Dependencies installed successfully!\n\n"
                        "Please restart the application."
                    )
                    return False  # Exit to restart
                else:
                    messagebox.showerror(
                        "Installation Failed",
                        f"Failed to install dependencies:\n\n{result.stderr}"
                    )
                    return False
                    
            except Exception as e:
                messagebox.showerror("Error", f"Failed to install dependencies:\n{str(e)}")
                return False
        else:
            return False
    except Exception as e:
        messagebox.showerror("Error", f"Error checking dependencies:\n{str(e)}")
        return False

def main():
    """Entry point for GUI application"""
    try:
        # Check and install dependencies if needed
        if not check_and_install_dependencies():
            sys.exit(0)
        
        # Load environment variables
        load_dotenv()
        
        # Load configuration
        config = load_config()
        
        # Create main window
        root = tk.Tk()
        app = MainWindow(root, config)
        
        # Start the GUI event loop
        root.mainloop()
        
    except Exception as e:
        messagebox.showerror("Fatal Error", f"Failed to start application:\n{str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
