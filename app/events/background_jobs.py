# """Background jobs functions"""

# from fastapi_utils.tasks import repeat_every
# from motor.motor_asyncio import AsyncIOMotorDatabase
# from pymongo import UpdateMany

# from app.core.depends import get_database


# @repeat_every(seconds=86400)
# async def user_ranking():
#     db: AsyncIOMotorDatabase = await get_database()
#     orders = await db.orders.find({}).to_list(length=await db.orders.count_documents({}))
#     total_orders = sum(map(lambda x: x.get("total_price"), orders))
#     B = total_orders / 4 * 3
#     C = total_orders / 4 * 2
#     D = total_orders / 4
#     requests = [
#         UpdateMany({"total_orders": {"$gt": B}}, {"$set": {"rank": "A"}}),
#         UpdateMany({"total_orders": {"$gt": C, "$lte": B}}, {"$set": {"rank": "B"}}),
#         UpdateMany({"total_orders": {"$gt": D, "$lte": C}}, {"$set": {"rank": "C"}}),
#         UpdateMany({"total_orders": {"$lte": D}}, {"$set": {"rank": "D"}}),
#     ]
#     await db.users.bulk_write(requests)


# @repeat_every(seconds=86400)
# async def check_shop_subscription():
#     db = await get_database()
#     await set_shop_plan(db=db)
