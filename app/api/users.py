from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.schemas.user import UserPatch, UserProfile
from app.services.auth_security import audit
from app.services.sessions import lock_user

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserProfile)
def me(user: CurrentUser):
    return user


@router.patch("/me", response_model=UserProfile)
def update_me(data: UserPatch, user: CurrentUser, session: SessionDep):
    user = lock_user(session, user.id)
    user.display_name = data.display_name
    audit(session, "profile_updated", user.id)
    session.commit()
    session.refresh(user)
    return user

