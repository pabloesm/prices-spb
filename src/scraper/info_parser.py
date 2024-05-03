class InfoParser:
    @staticmethod
    def product(data: dict) -> dict:
        product_data = {
            "id": data.get("id"),
            "ean": data.get("ean"),
            "slug": data.get("slug"),
            "brand": data.get("brand"),
            "limit_value": data.get("limit"),
            "origin": data.get("origin"),
            "packaging": data.get("packaging"),
            "published": data.get("published"),
            "share_url": data.get("share_url"),
            "thumbnail": data.get("thumbnail"),
            "display_name": data.get("display_name"),
            "unavailable_from": data.get("unavailable_from"),
            "is_variable_weight": data.get("is_variable_weight"),
            "legal_name": data.get("details", {}).get("legal_name"),
            "description": data.get("details", {}).get("description"),
            "counter_info": data.get("details", {}).get("counter_info"),
            "danger_mentions": data.get("details", {}).get("danger_mentions"),
            "alcohol_by_volume": sntz(data.get("details", {}).get("alcohol_by_volume")),
            "mandatory_mentions": data.get("details", {}).get("mandatory_mentions"),
            "product_variant": data.get("details", {}).get("production_variant"),
            "usage_instructions": data.get("details", {}).get("usage_instructions"),
            "storage_instructions": data.get("details", {}).get("storage_instructions"),
        }
        return product_data

    @staticmethod
    def badge(data: dict) -> dict:
        badge_data = {
            "is_water": data.get("badges", {}).get("is_water"),
            "requires_age_check": data.get("badges", {}).get("requires_age_check"),
        }
        return badge_data

    @staticmethod
    def supplier(data: dict) -> dict:
        if "details" in data and data["details"]["suppliers"]:
            supplier_data = {
                "name": data["details"]["suppliers"][0].get("name"),
            }
        else:
            supplier_data = {
                "name": None,
            }
        return supplier_data

    @staticmethod
    def photo(data: dict) -> list[dict]:
        photos_data = []
        if "photos" in data:
            for photo in data["photos"]:
                photo_data = {
                    "zoom": photo.get("zoom"),
                    "regular": photo.get("regular"),
                    "thumbnail": photo.get("thumbnail"),
                    "perspective": photo.get("perspective"),
                }
                photos_data.append(photo_data)
        return photos_data

    @staticmethod
    def category(data: dict) -> list:
        categories_data = []

        def parse_category(category):
            category_data = {
                "id": category.get("id"),
                "name": category.get("name"),
                "level": category.get("level"),
                "order_value": category.get("order"),
            }
            categories_data.append(category_data)
            if "categories" in category:
                for subcategory in category["categories"]:
                    parse_category(subcategory)

        if "categories" in data:
            for category in data["categories"]:
                parse_category(category)

        return categories_data

    @staticmethod
    def nutrition_information(data: dict) -> dict:
        nutrition_data = {}
        if "nutrition_information" in data:
            nutrition_data = {
                "allergens": data.get("nutrition_information", {}).get("allergens"),
                "ingredients": data.get("nutrition_information", {}).get("ingredients"),
            }

        return nutrition_data

    @staticmethod
    def price_instruction(data: dict) -> dict:
        price_instruction_data = {}
        if "price_instructions" in data:
            price_instruction = data["price_instructions"]

            price_instruction_data = {
                "iva": price_instruction.get("iva"),
                "is_new": price_instruction.get("is_new"),
                "is_pack": price_instruction.get("is_pack"),
                "pack_size": price_instruction.get("pack_size"),
                "unit_name": price_instruction.get("unit_name"),
                "unit_size": price_instruction.get("unit_size"),
                "bulk_price": price_instruction.get("bulk_price"),
                "unit_price": price_instruction.get("unit_price"),
                "approx_size": price_instruction.get("approx_size"),
                "size_format": price_instruction.get("size_format"),
                "total_units": price_instruction.get("total_units"),
                "unit_selector": price_instruction.get("unit_selector"),
                "bunch_selector": price_instruction.get("bunch_selector"),
                "drained_weight": price_instruction.get("drained_weight"),
                "selling_method": price_instruction.get("selling_method"),
                "price_decreased": price_instruction.get("price_decreased"),
                "reference_price": price_instruction.get("reference_price"),
                "min_bunch_amount": price_instruction.get("min_bunch_amount"),
                "reference_format": price_instruction.get("reference_format"),
                "previous_unit_price": sntz(price_instruction.get("previous_unit_price")),
                "increment_bunch_amount": price_instruction.get("increment_bunch_amount"),
            }

        return price_instruction_data


def sntz(s: str | None) -> str | None:
    """Sanitize numeric string."""
    if s is None:
        return None

    s = s.strip()
    s = s.replace(",", ".")
    s = s.replace("€", "")
    s = s.replace("º", "")
    return s.replace(" ", "_").lower()
