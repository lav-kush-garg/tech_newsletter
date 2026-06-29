"""
setup_autostart.py
==================
Run this ONCE on any new PC to register the newsletter scheduler
as a Windows Task Scheduler task that auto-starts on boot.

Usage:
    python setup_autostart.py           → install the task
    python setup_autostart.py --remove  → uninstall the task
    python setup_autostart.py --status  → check if task is registered

Run as Administrator for best results (right-click → "Run as administrator").
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

TASK_NAME = "TechNewsletterScheduler"


def get_project_dir() -> str:
    """Returns the absolute path of the folder this script lives in."""
    return str(Path(__file__).resolve().parent)


def get_python_exe() -> str:
    """Returns the Python executable currently running this script."""
    return sys.executable


def is_admin() -> bool:
    """Check if the script is running with admin privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def task_exists() -> bool:
    """Check if the task is already registered in Task Scheduler."""
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        capture_output=True, text=True
    )
    return result.returncode == 0


def install_task():
    project_dir = get_project_dir()
    python_exe  = get_python_exe()
    scheduler   = str(Path(project_dir) / "scheduler.py")

    print(f"\n{'='*60}")
    print(f"  Tech Newsletter — Auto-Start Setup")
    print(f"{'='*60}")
    print(f"  Project folder : {project_dir}")
    print(f"  Python         : {python_exe}")
    print(f"  Script         : {scheduler}")
    print(f"  Task name      : {TASK_NAME}")
    print(f"{'='*60}\n")

    if not is_admin():
        print("⚠️  WARNING: Not running as Administrator.")
        print("   The task will be created for the current user only.")
        print("   For system-wide (runs even when no one is logged in),")
        print("   re-run this script as Administrator.\n")

    if task_exists():
        print(f"✅ Task '{TASK_NAME}' already exists.")
        ans = input("   Do you want to overwrite it? (yes/no): ").strip().lower()
        if ans != "yes":
            print("Cancelled. Existing task left unchanged.")
            return
        remove_task(silent=True)

    # Build the XML definition for the scheduled task
    # /SC ONSTART  = trigger on system boot
    # /DELAY       = wait 30 seconds after boot before starting (network settling)
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Tech Newsletter Scheduler — auto-sends daily digest emails</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT30S</Delay>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>3</Count>
    </RestartOnFailure>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{python_exe}</Command>
      <Arguments>scheduler.py</Arguments>
      <WorkingDirectory>{project_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    # Write XML to a temp file
    xml_path = Path(project_dir) / "_task_temp.xml"
    xml_path.write_text(xml, encoding="utf-16")

    try:
        result = subprocess.run(
            ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_path), "/F"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"✅ Task '{TASK_NAME}' registered successfully!")
            print(f"\n   The newsletter scheduler will now:")
            print(f"   • Start automatically 30 seconds after every PC boot")
            print(f"   • Restart automatically if it crashes (up to 3 times)")
            print(f"   • Send emails at the times set in config/settings.py")
            print(f"\n   To verify: open Task Scheduler and look for '{TASK_NAME}'")
            print(f"   To test now: run  python scheduler.py --run-now\n")
        else:
            print(f"❌ Failed to create task.")
            print(f"   Error: {result.stderr.strip()}")
            print(f"\n   Try running this script as Administrator:")
            print(f"   Right-click setup_autostart.py → 'Run as administrator'")
    finally:
        xml_path.unlink(missing_ok=True)


def remove_task(silent: bool = False):
    if not task_exists():
        if not silent:
            print(f"ℹ️  Task '{TASK_NAME}' is not registered — nothing to remove.")
        return

    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        if not silent:
            print(f"✅ Task '{TASK_NAME}' removed successfully.")
    else:
        if not silent:
            print(f"❌ Failed to remove task: {result.stderr.strip()}")


def check_status():
    print(f"\n{'='*60}")
    print(f"  Task Status: {TASK_NAME}")
    print(f"{'='*60}")

    if not task_exists():
        print(f"  ❌ Not registered — run  python setup_autostart.py  to install\n")
        return

    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME, "/FO", "LIST"],
        capture_output=True, text=True
    )
    print(result.stdout)


def main():
    if sys.platform != "win32":
        print("❌ This script is for Windows only.")
        print("   On Linux/macOS, use a systemd service or cron job instead.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Register the Tech Newsletter scheduler as a Windows auto-start task",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup_autostart.py            Install / re-register the task
  python setup_autostart.py --remove   Remove the task
  python setup_autostart.py --status   Check if the task is registered
        """
    )
    parser.add_argument("--remove", action="store_true", help="Uninstall the scheduled task")
    parser.add_argument("--status", action="store_true", help="Check if task is registered")
    args = parser.parse_args()

    if args.status:
        check_status()
    elif args.remove:
        remove_task()
    else:
        install_task()


if __name__ == "__main__":
    main()