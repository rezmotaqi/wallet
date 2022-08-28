"""Convert and Import xls product data into the mongodb database."""

import datetime
import xlrd

from app.core.depends import get_database


async def import_xls_to_products(path):
    print("Converting started. It's taking some minutes ... .")
    trans_unit = {
        "تن": "TON",
        "سي سي": "CC",
        "شمارش پذير": "NUMBER",
        "قيراط": "CARAT",
        "كيلوگرم": "KILO",
        "کیلوگرم": "KILO",
        "ليتر": "LITER",
        "متر": "METER",
        "مترمربع": "SQUARE_METER",
        "مترمكعب": "CUBIC_METER",
        "ميلي ليتر": "MILI_LITER",
        "ميلي گرم": "MILI_GRAM",
        "گرم": "GRAM",
        "بسته": "PACKAGE"
    }
    db = await get_database()
    book = xlrd.open_workbook(path)

    # Sheet0 is kala[products]
    sheet1 = book.sheet_by_index(0)

    row_num = 1
    altered_items = 1
    for row in sheet1:
        if row_num > 1:
            name = row[0].value
            name = name.replace("ي", "ی")
            name = name.replace("ك", "ک")
            doc = {
                "name": name,
                "category": row[1].value,
                "code": str(int(row[3].value)),
                "sku": 0,
                "price": 0,
                "unit": trans_unit[(row[4].value).strip()],
                "created_at": datetime.datetime.now(),
                "updated_at": datetime.datetime.now()
            }
            criteria = {"code": doc["code"], "category": doc["category"]}
            result = await db.products.update_one(criteria, {"$set": doc}, upsert=True)
            if result.acknowledged:
                altered_items += 1

        row_num += 1

    print(f"Task done: total rows: {row_num}  ---  total altered items: {altered_items}")
