import logging
from http.client import HTTPException

import inject
from database.database import Database
from entity.asset import Asset, AssetBase
from fastapi import APIRouter
from repository.asset_repository_service import AssetRepositoryService

router = APIRouter(prefix="/v1/asset", tags=["Asset"])

db = inject.instance(Database)
asset_repository_service = inject.instance(AssetRepositoryService)


logger = logging.getLogger("api_logger")


# CRUD 엔드포인트 구성
@router.post("/add")
def create_asset(asset: AssetBase):
    asset = Asset(**asset.dict())
    asset_repository_service.add(asset)

    return {"message": "Asset created successfully"}


@router.get("/get")
def read_asset():
    asset = asset_repository_service.get()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.put("/put")
def update_asset(update_number: int):
    asset_repository_service.update(update_number=update_number)

    return {"message": "Asset updated successfully"}


@router.delete("/delete")
def delete_asset():
    asset = asset_repository_service.get()
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    asset_repository_service.delete()

    return {"message": "Asset deleted successfully"}
