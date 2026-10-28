"""Preference-aware, idempotent in-app reminders. This is not push delivery."""
from datetime import timedelta

from sqlalchemy import select

from app.models.books import Notification, Profile
from app.services.books import profile, rows, tax_year
from app.services.sessions import lock_user
from app.services.tax import deadlines, today


def schedule_reminders(factory,as_of=None):
    day=as_of or today()
    count=0
    with factory() as db:
        owners=list(db.scalars(select(Profile.owner_id).where(Profile.kind=="me")))
    for owner in owners:
        with factory() as db:
            lock_user(db,owner)
            preferences=profile(db,owner,"me").data.get("preferences",{})
            events=[]
            if preferences.get("reminder_weekly") and day.weekday()==(preferences.get("preferred_weekday") or 0):
                events.append((f"weekly:{day}","reminder.weekly",{"week_start":str(day-timedelta(days=7))}))
            if preferences.get("reminder_deadlines"):
                year=tax_year(day)
                start=int(year[:4])
                for target in [year,f"{start-1}-{start%100:02d}"]:
                    for deadline in deadlines(target):
                        remaining=(deadline["due_on"]-day).days
                        if remaining in {0,1,7}:
                            events.append((f"deadline:{deadline['id']}:{day}","reminder.deadline",{
                                "due_on":str(deadline["due_on"]),"tax_year":target,"days_remaining":remaining}))
            for key,kind,params in events:
                previous=db.scalar(rows(db,Notification,owner).where(Notification.params["dedup_key"].astext==key))
                if previous: continue
                db.add(Notification(owner_id=owner,type="reminder",title_key=kind,body_key=kind+".body",params={**params,"dedup_key":key}))
                count+=1
            db.commit()
    return count
