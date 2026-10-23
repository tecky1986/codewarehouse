from fastapi import APIRouter, Depends

from app.deps import get_conn
from app.errors import AppError
from app.repos import PackageMasterRepo
from app.response import fail, ok

router = APIRouter(prefix="/api/packages", tags=["packages"])


def _repo(conn=Depends(get_conn)) -> PackageMasterRepo:
    return PackageMasterRepo(conn)


@router.get("")
def list_packages(repo: PackageMasterRepo = Depends(_repo)):
    return ok(repo.list_all())


@router.post("")
def create_package(body: dict, repo: PackageMasterRepo = Depends(_repo)):
    try:
        return ok(repo.create(body))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.put("/{pid}")
def update_package(pid: int, body: dict, repo: PackageMasterRepo = Depends(_repo)):
    try:
        return ok(repo.update(pid, body))
    except AppError as e:
        return fail(e.code, e.message, status=e.status)


@router.delete("/{pid}")
def delete_package(pid: int, repo: PackageMasterRepo = Depends(_repo)):
    try:
        repo.delete(pid)
        return ok(True)
    except AppError as e:
        return fail(e.code, e.message, status=e.status)
