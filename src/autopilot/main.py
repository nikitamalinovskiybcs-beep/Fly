"""Fly Autopilot Agent — entry point.

Usage:
    python -m src.autopilot.main              # Run scheduler (background)
    python -m src.autopilot.main --once       # Run one full cycle and exit
    python -m src.autopilot.main --health     # Check health and exit
    python -m src.autopilot.main --stop       # Engage kill switch
    python -m src.autopilot.main --resume     # Disengage kill switch
"""

import argparse
import logging
import signal
import sys
import time

from src.autopilot.monitor import SystemMonitor
from src.autopilot.safety import SafetySystem
from src.autopilot.scheduler import AutopilotScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("autopilot")


def main() -> None:
    """Parse args and run the appropriate mode."""
    parser = argparse.ArgumentParser(description="Fly Autopilot Agent")
    parser.add_argument("--once", action="store_true", help="Run one cycle and exit")
    parser.add_argument("--health", action="store_true", help="Check health and exit")
    parser.add_argument("--stop", action="store_true", help="Engage kill switch")
    parser.add_argument("--resume", action="store_true", help="Disengage kill switch")
    args = parser.parse_args()

    safety = SafetySystem()

    if args.stop:
        safety.engage_kill_switch("manual CLI stop")
        print("Kill switch ENGAGED. Autopilot stopped.")
        return

    if args.resume:
        safety.disengage_kill_switch()
        print("Kill switch DISENGAGED. Autopilot can resume.")
        return

    if args.health:
        monitor = SystemMonitor()
        health = monitor.check_health()
        print(f"Status:     {health.status.value}")
        print(f"Sharpe 30d: {health.sharpe_30d:.2f}")
        print(f"Win Rate:   {health.win_rate_20:.0%}" if health.win_rate_20 >= 0 else "Win Rate:   N/A")
        print(f"Max DD:     {health.max_drawdown:.1%}")
        print(f"Positions:  {health.open_positions}")
        print(f"Disk:       {health.disk_usage_pct:.1f}%")
        if health.alerts:
            print("\nAlerts:")
            for a in health.alerts:
                print(f"  [{a['level']}] {a['msg']}")
        return

    scheduler = AutopilotScheduler()

    if args.once:
        logger.info("Running single cycle...")
        results = scheduler.run_once()
        print(f"Health:       {results.get('health', {})}")
        print(f"Analysis:     {len(results.get('analysis', []))} insights")
        print(f"Optimization: {len(results.get('optimization', []))} changes")
        print(f"Report:       {results.get('report', {})}")
        return

    def handle_signal(signum: int, frame: object) -> None:
        logger.info("Signal %d received, stopping...", signum)
        scheduler.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info("Starting Fly Autopilot Agent (24/7 mode)")
    logger.info("Kill switch file: data/KILL_SWITCH")
    logger.info("Press Ctrl+C to stop")

    scheduler.start()

    try:
        while scheduler.running:
            time.sleep(5)
    except KeyboardInterrupt:
        scheduler.stop()


if __name__ == "__main__":
    main()
