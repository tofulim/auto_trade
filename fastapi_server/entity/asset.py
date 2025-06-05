from sqlmodel import Field, SQLModel


class AssetBase(SQLModel):
    budget: int


class Asset(AssetBase, table=True):
    id: int = Field(default=None, primary_key=True)
