from cx_Freeze import setup, Executable
import sys

# Include the required packages
build_exe_options = {
    "packages": ["pandas", "tkinter", "pulp", "os", "ttkthemes"],  # Include necessary packages
    "include_files": [],  # Add any additional files you need to include (e.g., CSV files)
}

# Adjust the base on your system
base = None
if sys.platform == "linux":
    base = "Console"  # Use "Console" for terminal applications

setup(
    name="PortfolioBalancer",
    version="0.1",
    description="A simple portfolio balancing tool",
    options={"build_exe": build_exe_options},
    executables=[Executable("portfolio_balancer.py", base=base)],
)
