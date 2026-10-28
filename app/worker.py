"""Run `python -m app.worker [--once]`. Jobs commit results, never timers."""
import argparse
import time

from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.db import build_engine
from app.services.files import ClamAVScanner, DisabledScanner, process_one
from app.services.notifications import schedule_reminders


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--once",action="store_true")
    args=parser.parse_args()
    settings=get_settings()
    engine=build_engine(settings)
    factory=sessionmaker(bind=engine,expire_on_commit=False)
    scanner=ClamAVScanner(settings.clamav_host,settings.clamav_port) if settings.clamav_host else DisabledScanner()
    try:
        next_reminders=0
        while True:
            if time.monotonic()>=next_reminders:
                schedule_reminders(factory)
                next_reminders=time.monotonic()+60
            worked=process_one(factory,scanner=scanner)
            if args.once: break
            if not worked: time.sleep(settings.worker_poll_seconds)
    finally: engine.dispose()


if __name__=="__main__": main()
