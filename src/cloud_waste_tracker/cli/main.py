# cloud_waste_tracker/cli/main.py
from __future__ import annotations
from pathlib import Path
from typing import Iterable

from cloud_waste_tracker.scanners import ec2_scanner, s3_scanner
from cloud_waste_tracker.reports import summarize, emailer
from cloud_waste_tracker.actions import ec2_actions, s3_actions
from cloud_waste_tracker.utils.utils import (
    path_waste_csv,
    path_s3_csv,
    path_summary_txt,
)

TO_ADDR = "mikey.a729@gmail.com"

MENU_MAIN = """
=============================
 Cloud Waste Tracker - Main
=============================
1) Run EC2 scan
2) Run S3 scan
3) Actions
0) Exit
Choose an option: """

MENU_ACTIONS = """
=============================
 Actions
=============================
1) EC2: Stop idle instances (from last scan)
2) S3: Apply lifecycle to buckets (from last scan)
9) Back
Choose an option: """

# ----------------------------------------------------------
# Helpers
# ----------------------------------------------------------
def ask_yes_no(prompt: str) -> bool:
    while True:
        v = input(f"{prompt} (1=yes, 0=no): ").strip()
        if v in ("1", "0"):
            return v == "1"
        print("Please enter 1 or 0.")

def _existing(files: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for p in files:
        p = Path(p) if not isinstance(p, Path) else p
        if p.exists():
            out.append(p)
        else:
            print(f"[i] Skipping missing file: {p}")
    return out

def send_email(subject: str, files: Iterable[Path]) -> None:
    files_ok = _existing(files)
    if not files_ok:
        print("[!] No files to attach. Skipping email.")
        return
    emailer.send(
        to_addr=TO_ADDR,
        subject=subject,
        body="Hi, attached the report you requested.",
        files=files_ok,
    )
    print("[✓] Email sent.")

# ----------------------------------------------------------
# Scan Flows
# ----------------------------------------------------------
def run_ec2_flow() -> None:
    try:
        ec2_scanner.run()
        print("[✓] EC2 scan completed -> waste_report.csv")
    except Exception as e:
        print(f"[!] EC2 scan failed: {e}")
        return

    try:
        summary_p, _ = summarize.run()
        print(f"[✓] Summary updated -> {summary_p.name}")
    except Exception as e:
        print(f"[!] summarize failed: {e}")

    if ask_yes_no("Send EC2 report by email now?"):
        send_email(
            subject="Cloud Waste Report (EC2)",
            files=[path_waste_csv(), path_summary_txt()],
        )

def run_s3_flow() -> None:
    try:
        s3_scanner.run()
        print("[✓] S3 scan completed -> s3_waste_report.csv")
    except Exception as e:
        print(f"[!] S3 scan failed: {e}")
        return

    try:
        summary_p, _ = summarize.run()
        print(f"[✓] Summary updated -> {summary_p.name}")
    except Exception as e:
        print(f"[!] summarize failed: {e}")

    if ask_yes_no("Send S3 report by email now?"):
        send_email(
            subject="Cloud Waste Report (S3)",
            files=[path_s3_csv(), path_summary_txt()],
        )

# ----------------------------------------------------------
# Actions Menu
# ----------------------------------------------------------
def run_actions_menu() -> None:
    while True:
        choice = input(MENU_ACTIONS).strip()

        # --- EC2: stop idle ---
        if choice == "1":
            plan = ec2_actions.plan_stop_idle()
            if not plan:
                print("[i] No idle instances found in waste_report.csv.")
                continue

            print(f"[?] Found {len(plan)} idle instance(s):")
            print("    " + ", ".join([iid for iid, _ in plan]))
            if ask_yes_no("Proceed to STOP these instances now?"):
                ec2_actions.stop_plan_grouped(plan)
                print("[✓] Stop commands sent.")
            else:
                print("[i] Skipped EC2 stop.")

        # --- S3: apply lifecycle ---
        elif choice == "2":
            buckets = s3_actions.plan_lifecycle()
            if not buckets:
                print("[i] No buckets missing lifecycle according to s3_waste_report.csv.")
                continue

            print(f"[?] Buckets missing lifecycle ({len(buckets)}):")
            print("    " + ", ".join(buckets))
            if ask_yes_no("Apply lifecycle now?"):
                s3_actions.apply_lifecycle(buckets=buckets, dry_run=False)
                print("[✓] Lifecycle applied.")
            else:
                # show dry-run plan for visibility
                s3_actions.apply_lifecycle(buckets=buckets, dry_run=True)
                print("[i] Dry-run only. No changes made.")

        elif choice == "9":
            break
        else:
            print("Invalid choice. Enter 1, 2 or 9.")

# ----------------------------------------------------------
# Main
# ----------------------------------------------------------
def main() -> None:
    while True:
        choice = input(MENU_MAIN).strip()
        if choice == "1":
            run_ec2_flow()
        elif choice == "2":
            run_s3_flow()
        elif choice == "3":
            run_actions_menu()
        elif choice == "0":
            print("Bye.")
            break
        else:
            print("Invalid choice. Enter 1, 2, 3, or 0.")

if __name__ == "__main__":
    main()
