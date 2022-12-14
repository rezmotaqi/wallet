from typing import Optional, List

from pydantic.fields import Field

from app.schemas.base import Model, ObjectId, DateTime


class ProductGuaranteeInput(Model):
    """
    Pydantic schema for product guarantee
    """

    name: str = Field()
    price: int = Field()
    expire_duration: int = Field(description="amount of time in days")
    image: Optional[str] = Field(description="path of uploaded file")


class ProductGuaranteeOutput(Model):
    """
    Pydantic schema for returning guarantees
    """

    id: ObjectId = Field()
    name: str = Field()
    price: int = Field()
    expire_duration: int = Field(description="amount of time in days")
    image: Optional[str] = Field(description="path of uploaded file")


class ProductGuaranteeListOutput(Model):
    """
    Pydantic schema for list of guarantees
    """

    guarantees: List[ProductGuaranteeOutput] = Field()
    count: int = Field()


class ProductGuaranteeInProduct(Model):
    """
    Pydantic schema for product guarantee data in product
    """

    id: ObjectId = Field()
    name: str = Field()
    price: int = Field()
    expire_duration: int = Field(description="amount of time in days")
    image: Optional[str] = Field(description="path of uploaded file")


class ProductTrait(Model):
    """
    Pydantic schema for product traits in product
    """

    name: str = Field()
    value: str = Field()


class ProductInput(Model):
    """
    Pydantic schema for creating product
    """

    farsi_name: Optional[str] = Field()
    english_name: str = Field()
    slug: Optional[str] = Field()
    tab_title: Optional[str] = Field()
    keywords: List[str] = Field()
    publish_date: DateTime = Field()
    price: int = Field()
    price_update_date: DateTime = Field()
    is_active: bool = Field()
    is_available: bool = Field()
    traits: Optional[List[ProductTrait]] = Field()
    stock: int = Field(gt=0)
    discount_percent: Optional[int] = Field(description="product internal discount")
    images: Optional[List[str]] = Field()

    # TODO saman what are these fields??
    # model: str = Field()
    # tags: stock = Field()
    # category: str = Field()


class ProductPartialUpdate(Model):
    """
    Pydantic schema for creating product
    """

    farsi_name: Optional[str] = Field()
    english_name: Optional[str] = Field()
    slug: Optional[str] = Field()
    tab_title: Optional[str] = Field()
    keywords: Optional[List[str]] = Field()
    publish_date: Optional[DateTime] = Field()
    price: Optional[int] = Field()
    price_update_date: Optional[DateTime] = Field()
    is_active: Optional[bool] = Field()
    is_available: Optional[bool] = Field()
    traits: Optional[List[ProductTrait]] = Field()
    guarantees: Optional[List[ProductGuaranteeInProduct]] = Field()
    stock: Optional[int] = Field(gt=0)
    discount_percent: Optional[int] = Field(description="product internal discount")
    images: Optional[List[str]] = Field()


class ProductOutput(Model):
    """
    Pydantic schema for returning product
    """
    id: ObjectId = Field()
    farsi_name: Optional[str] = Field()
    english_name: str = Field()
    slug: Optional[str] = Field()
    tab_title: Optional[str] = Field()
    keywords: List[str] = Field()
    publish_date: DateTime = Field(description="?????????? ???????????? ??????????")
    price: int = Field()
    price_update_date: DateTime = Field()
    is_active: bool = Field()
    is_available: bool = Field()
    traits: Optional[List[ProductTrait]] = Field(description="?????????? ???? ??????????")
    guarantees: Optional[List[ProductGuaranteeInProduct]] = Field()
    stock: int = Field(gt=0, description="?????????? ???????????? ??????????")
    discount_percent: Optional[int] = Field(description="product internal discount")
    images: Optional[List[str]] = Field()


class ProductListOutput(Model):
    """
    Pydantic schema for list of guarantees
    """

    products: List[ProductOutput] = Field(default=[])
    count: int = Field(default=0)


class ProductInCartOutput(Model):
    """
    Pydantic schema for returning product data in cart
    """

    id: ObjectId = Field()
    english_name: Optional[str] = Field()
    price: int = Field()


class CartOutput(Model):
    """
    Pydantic schema for returning user's cart
    """

    count: int = Field(default=0)
    items: List[ProductInCartOutput] = Field(default=[])
    owner_id: ObjectId = Field()

