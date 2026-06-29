"""
Employee Manager
=================
Run this script to add, update, deactivate, or list employees
who receive the newsletter.

All changes go to the SQLite database (data/newsletter.db).
No code files need to be edited.

USAGE EXAMPLES:
---------------

  # See all employees
  python manage_employees.py list

  # See only active employees
  python manage_employees.py list --status active

  # Add a new employee
  python manage_employees.py add --id EMP001 --name "Rahul Sharma" \
      --email rahul@company.com --dept "IT"

  # Deactivate an employee (they stop receiving emails)
  python manage_employees.py deactivate --id EMP001

  # Reactivate an employee
  python manage_employees.py activate --id EMP001

  # Update someone's email address
  python manage_employees.py update-email --id EMP001 --email newemail@company.com

  # Permanently delete (prefer deactivate instead)
  python manage_employees.py delete --id EMP001
"""

import argparse
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent))

from utils.database import (
    init_db,
    add_employee,
    update_employee_status,
    update_employee_email,
    remove_employee,
    list_employees,
    get_active_recipients,
)


def cmd_list(args):
    status = args.status if hasattr(args, "status") and args.status else None
    employees = list_employees(status_filter=status)

    if not employees:
        print("No employees found.")
        return

    print(f"\n{'ID':<12} {'Name':<25} {'Email':<35} {'Department':<20} {'Status'}")
    print("-" * 100)
    for e in employees:
        status_icon = "✅" if e["status"] == "active" else "❌"
        print(f"{e['employee_id']:<12} {e['name']:<25} {e['email']:<35} "
              f"{e['department']:<20} {status_icon} {e['status']}")
    print(f"\nTotal: {len(employees)}")


def cmd_add(args):
    if not all([args.id, args.name, args.email]):
        print("ERROR: --id, --name, and --email are required")
        sys.exit(1)

    success = add_employee(
        employee_id=args.id,
        name=args.name,
        email=args.email,
        department=args.dept or "",
        status="active",
    )
    if success:
        print(f"✅ Added: {args.name} ({args.email}) — ID: {args.id}")
    else:
        print(f"❌ Failed. Employee ID or email may already exist.")


def cmd_deactivate(args):
    if not args.id:
        print("ERROR: --id is required")
        sys.exit(1)
    success = update_employee_status(args.id, "inactive")
    if success:
        print(f"✅ Employee {args.id} deactivated — they will no longer receive emails.")
    else:
        print(f"❌ Failed to deactivate employee {args.id}")


def cmd_activate(args):
    if not args.id:
        print("ERROR: --id is required")
        sys.exit(1)
    success = update_employee_status(args.id, "active")
    if success:
        print(f"✅ Employee {args.id} activated — they will receive emails again.")
    else:
        print(f"❌ Failed to activate employee {args.id}")


def cmd_update_email(args):
    if not all([args.id, args.email]):
        print("ERROR: --id and --email are required")
        sys.exit(1)
    success = update_employee_email(args.id, args.email)
    if success:
        print(f"✅ Email updated for {args.id} → {args.email}")
    else:
        print(f"❌ Failed to update email for {args.id}")


def cmd_delete(args):
    if not args.id:
        print("ERROR: --id is required")
        sys.exit(1)
    confirm = input(f"Permanently delete employee {args.id}? Type YES to confirm: ")
    if confirm.strip().upper() == "YES":
        success = remove_employee(args.id)
        if success:
            print(f"✅ Employee {args.id} permanently deleted.")
        else:
            print(f"❌ Failed to delete employee {args.id}")
    else:
        print("Cancelled.")


def cmd_active_emails(args):
    emails = get_active_recipients()
    print(f"\nActive recipient emails ({len(emails)} total):")
    for e in emails:
        print(f"  {e}")


def main():
    init_db()

    parser = argparse.ArgumentParser(
        description="Manage newsletter employee recipients",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    # list
    p_list = sub.add_parser("list", help="List all employees")
    p_list.add_argument("--status", choices=["active", "inactive"],
                        help="Filter by status")

    # add
    p_add = sub.add_parser("add", help="Add a new employee")
    p_add.add_argument("--id",    required=True, help="Employee ID (e.g. EMP001)")
    p_add.add_argument("--name",  required=True, help="Full name")
    p_add.add_argument("--email", required=True, help="Email address")
    p_add.add_argument("--dept",  default="",   help="Department (optional)")

    # deactivate
    p_deact = sub.add_parser("deactivate", help="Stop sending emails to employee")
    p_deact.add_argument("--id", required=True, help="Employee ID")

    # activate
    p_act = sub.add_parser("activate", help="Resume sending emails to employee")
    p_act.add_argument("--id", required=True, help="Employee ID")

    # update-email
    p_email = sub.add_parser("update-email", help="Change employee email address")
    p_email.add_argument("--id",    required=True, help="Employee ID")
    p_email.add_argument("--email", required=True, help="New email address")

    # delete
    p_del = sub.add_parser("delete", help="Permanently delete employee (use deactivate instead)")
    p_del.add_argument("--id", required=True, help="Employee ID")

    # show-emails
    sub.add_parser("show-emails", help="Show all active recipient emails")

    args = parser.parse_args()

    commands = {
        "list":         cmd_list,
        "add":          cmd_add,
        "deactivate":   cmd_deactivate,
        "activate":     cmd_activate,
        "update-email": cmd_update_email,
        "delete":       cmd_delete,
        "show-emails":  cmd_active_emails,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()