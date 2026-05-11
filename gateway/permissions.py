from rest_framework.permissions import BasePermission

PATIENT = 'PATIENT'
DOCTOR = 'DOCTOR'
CLERK = 'CLERK'
ADMIN = 'ADMIN'
SYSTEM = 'SYSTEM'

ALL_ROLES = {PATIENT, DOCTOR, CLERK, ADMIN, SYSTEM}


def _role(request) -> str | None:
    return getattr(request.user, 'role', None)


class IsPatient(BasePermission):
    def has_permission(self, request, view):
        return _role(request) == PATIENT


class IsDoctor(BasePermission):
    def has_permission(self, request, view):
        return _role(request) == DOCTOR


class IsClerk(BasePermission):
    def has_permission(self, request, view):
        return _role(request) == CLERK


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return _role(request) == ADMIN


class IsAdminOrClerk(BasePermission):
    def has_permission(self, request, view):
        return _role(request) in (ADMIN, CLERK)


class IsAnyKnownRole(BasePermission):
    """Passes for any authenticated user whose role is one of the system roles."""

    def has_permission(self, request, view):
        return _role(request) in ALL_ROLES
