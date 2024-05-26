from playwright._impl._errors import Error as pw_Error
from playwright.sync_api._generated import Locator
from pydantic import BaseModel, Field
from pydantic.functional_validators import AfterValidator
from typing_extensions import Annotated

from src.config.logger import logger
from src.models import ScannedProduct


def check_product_url(product_locator: Locator) -> Locator:
    # Extract the URL from the string representation
    locator_str = str(product_locator)
    start = locator_str.find("url='") + len("url='")
    end = locator_str.find("'", start)
    url = locator_str[start:end]
    if not "/categories/" in url:
        breakpoint()
    assert "/categories/" in url, f"Invalid product URL: {url}"
    return product_locator


ProductLocator = Annotated[Locator, AfterValidator(check_product_url)]


class ProductState(BaseModel):
    category_locator: Locator = Field(repr=False)
    category_name: str
    subcategory_locator: Locator | None = Field(default=None, repr=False)
    subcategory_name: str | None = None
    product_locator: ProductLocator | None = Field(default=None, repr=False)
    product_name: str | None = None
    scanned_product: ScannedProduct | None = Field(default=None, repr=False)

    class Config:
        arbitrary_types_allowed = True

    def __eq__(self, other):
        if not isinstance(other, ProductState):
            return NotImplemented
        return (
            self.category_name == other.category_name
            and str(self.category_locator) == str(other.category_locator)
            and self.subcategory_name == other.subcategory_name
            and str(self.subcategory_locator) == str(other.subcategory_locator)
            and self.product_name == other.product_name
            and str(self.product_locator) == str(other.product_locator)
            and self.scanned_product == other.scanned_product
        )

    def __hash__(self):
        return hash(
            (self.category_name, self.subcategory_name, self.product_name, self.scanned_product)
        )


class ProductsState:
    def __init__(self):
        self.products = []
        self._is_finished = False

    @property
    def is_finished(self) -> bool:
        return bool(self._is_finished)

    @is_finished.setter
    def is_finished(self, value: bool) -> None:
        self._is_finished = value

    def get_pending_categories(self) -> list[Locator]:
        pending_categories_set = set()
        for product in self.products:
            if product.scanned_product is None:
                # Add only the category information
                # try:
                #     product.category_locator.inner_text()
                # except pw_Error:
                #     breakpoint()
                pending_categories_set.add(
                    ProductState(
                        category_locator=product.category_locator,
                        category_name=product.category_locator.inner_text(),
                    )
                )

        # Sort pending categories by the alphabetical order of the category name
        pending_categories = list(pending_categories_set)
        pending_categories = sorted(pending_categories, key=lambda x: x.category_name)
        for pc in pending_categories:
            logger.debug("Pending categs: %s", pc)
        pending_categories_locs = [p.category_locator for p in pending_categories]
        return pending_categories_locs

    def get_pending_subcategories(self, category_loc: Locator) -> list[Locator]:
        pending_subcategories_set = set()
        for product in self.products:
            if (
                product.subcategory_name is not None
                and product.scanned_product is None
                and product.category_locator == category_loc
            ):
                # Add only the category and subcategory information
                pending_subcategories_set.add(
                    ProductState(
                        category_locator=product.category_locator,
                        category_name=product.category_locator.inner_text(),
                        subcategory_locator=product.subcategory_locator,
                        subcategory_name=product.subcategory_locator.inner_text(),
                    )
                )

        # Sort pending subcategories by the alphabetical order of the subcategory name
        pending_subcategories = list(pending_subcategories_set)
        pending_subcategories = sorted(pending_subcategories, key=lambda x: str(x.subcategory_name))
        for ps in pending_subcategories:
            logger.debug("Pending subcategs: %s", ps)
        pending_subcategories_locs = [p.subcategory_locator for p in pending_subcategories]
        pending_subcategories_locs_clean = [p for p in pending_subcategories_locs if p is not None]

        return pending_subcategories_locs_clean

    def get_pending_products(
        self,
        category_loc: Locator,
        subcategory_loc: Locator | None,
    ) -> list[Locator]:
        if subcategory_loc is None:
            raise ValueError("Subcategory locator cannot be None")

        pending_products_set = set()
        for product in self.products:
            if (
                product.scanned_product is None
                and product.category_locator == category_loc
                and product.subcategory_locator == subcategory_loc
            ):
                pending_products_set.add(product)

        # Sort pending products by the alphabetical order of the product locator
        pending_products = list(pending_products_set)
        pending_products = sorted(pending_products, key=lambda x: str(x.product_locator))
        # for pp in pending_products:
        #     logger.debug("Pending products: %s", pp)

        pending_products_locs = [p.product_locator for p in pending_products]
        pending_products_locs = [p for p in pending_products_locs if p is not None]
        for pending_product_loc in pending_products_locs:
            try:
                pending_product_loc.inner_text()
            except pw_Error:
                breakpoint()

        return pending_products_locs

    def sync_categories(self, categories_locs: list[Locator]) -> None:
        """
        Sync the *pending* categories with the provided new locators.
        Notice that all elements containing those categories will be synced, which may include
        categories, subcategories and products.
        """
        for product in self.products:
            if product.scanned_product:
                continue

            for categories_loc in categories_locs:
                if product.category_name == categories_loc.inner_text():
                    product.category_locator = categories_loc
                    logger.debug("Synced categ: %s", product)

    def sync_subcategories(self, category_loc: Locator, subcategories_locs: list[Locator]) -> None:
        """
        Sync the *pending* subcategories with the provided new locators.
        Notice that all elements containing those subcategories will be synced, which may include
        subcategories and products.
        """
        category_name = category_loc.inner_text()
        products_cat = [p for p in self.products if p.category_name == category_name]

        for product in products_cat:
            if product.scanned_product:
                continue

            for subcategory_loc in subcategories_locs:
                if product.subcategory_name == subcategory_loc.inner_text():
                    product.subcategory_locator = subcategory_loc
                    logger.debug("Synced subcateg: %s", product)

    def add_categories(self, categories_locs: list[Locator]) -> None:
        # Sync if categories already exist
        if len(self.products) > 0:
            self.sync_categories(categories_locs)
            return

        for category_loc in categories_locs:
            new_prod_state = ProductState(
                category_locator=category_loc,
                category_name=category_loc.inner_text(),
            )
            self.products.append(new_prod_state)
            logger.debug("Added: %s", new_prod_state)

    def add_subcategories(self, category_loc: Locator, subcategories_locs: list[Locator]) -> None:
        category_name = category_loc.inner_text()
        index_product_cat_tuples = [
            p for p in enumerate(self.products) if p[1].category_name == category_name
        ]
        if len(index_product_cat_tuples) == 0:
            raise ValueError(f"Category `{category_name}` not found")

        if len(index_product_cat_tuples) > 1:
            # Subcategories already added, sync them
            self.sync_subcategories(category_loc, subcategories_locs)
            return

        product_cat = index_product_cat_tuples[0][1]
        index = index_product_cat_tuples[0][0]
        # Remove the category without subcategories, since we are going to add them
        self.products.pop(index)
        for subcategory_loc in subcategories_locs:
            new_prod_state = ProductState(
                category_locator=product_cat.category_locator,
                category_name=product_cat.category_name,
                subcategory_locator=subcategory_loc,
                subcategory_name=subcategory_loc.inner_text(),
            )
            self.products.append(new_prod_state)
            logger.debug("Added: %s", new_prod_state)

    def add_products(
        self,
        category_loc: Locator,
        subcategory_loc: Locator,
        products_locs: list[Locator],
    ) -> None:
        category_name = category_loc.inner_text()

        # Ensure the category exists
        products_cat = [p for p in self.products if p.category_name == category_name]
        if len(products_cat) == 0:
            raise ValueError(f"Category `{category_name}` not found")

        # 1.- Search products with the same category and subcategory
        subcategory_name = subcategory_loc.inner_text()
        index_product_subcat_tuples = []
        for i, p in enumerate(self.products):
            # Only check subcategories of the belonging to the given category
            if p.category_name == category_name and p.subcategory_name == subcategory_name:
                index_product_subcat_tuples.append((i, p))

        if len(index_product_subcat_tuples) == 0:
            raise ValueError(f"Subcategory `{subcategory_name}` not found")

        # 2.- Two scenarios: (i) only the subcategory has been added or (ii) the subcategory and
        # product has been previously added.
        # 2.1.- In the first case, we need to remove the subcategory (which has no products), since
        # we are going to add them
        if len(index_product_subcat_tuples) == 1:
            assert index_product_subcat_tuples[0][1].product_locator is None
            index = index_product_subcat_tuples[0][0]
            self.products.pop(index)

            product_subcat = index_product_subcat_tuples[0][1]

            # Ensure the subcategory product locator is not stale
            product_subcat.subcategory_locator.inner_text()

        # 2.2.- In the second case, we need to take the subcategory info of a non-stale product
        elif len(index_product_subcat_tuples) > 1:
            # Take a non stale product (those with scanned_product are not synced anymore, so they
            # are stale)
            products_subcat = [
                ipc[1]
                for ipc in index_product_subcat_tuples
                if ipc[1].product_locator and not ipc[1].scanned_product
            ]
            product_subcat = products_subcat[0]

        else:
            breakpoint()
            raise ValueError("Unexpected state while adding products")

        # Create new products
        new_prods_state = []
        for product_loc in products_locs:
            check_product_url(product_loc)  # TODO: Remove this line
            logger.debug("URL checked for: %s", product_loc)
            new_prods_state.append(
                ProductState(
                    category_locator=product_subcat.category_locator,
                    category_name=product_subcat.category_name,
                    subcategory_locator=product_subcat.subcategory_locator,
                    subcategory_name=product_subcat.subcategory_name,
                    product_locator=product_loc,
                    product_name=product_loc.inner_text(),
                )
            )

        # Remove pending products in self.products which are going to be added/synced
        for product in self.products[:]:
            if product in new_prods_state:
                self.products.remove(product)

        # Remove products which are already scanned
        products_scanned = [p for p in self.products if p.scanned_product]
        products_scanned_names = [p.product_name for p in products_scanned]
        for product in new_prods_state[:]:
            if product.product_name in products_scanned_names:
                new_prods_state.remove(product)

        # Add the new products
        self.products.extend(new_prods_state)

        for new_prod_state in new_prods_state:
            logger.debug("Added: %s, %s", new_prod_state, new_prod_state.product_locator)

        for p in self.products:
            logger.debug("---- DEBUG ---  Product: %s, %s", p, p.product_locator)

    def add_scanned_product(
        self,
        category_loc: Locator,
        subcategory_loc: Locator,
        product_loc: Locator,
        scanned_product: ScannedProduct,
    ) -> None:
        category_name = category_loc.inner_text()
        products_cat = [p for p in self.products if p.category_name == category_name]
        if len(products_cat) == 0:
            raise ValueError(f"Category `{category_name}` not found")

        subcategory_name = subcategory_loc.inner_text()
        products_subcat = []
        for p in products_cat:
            # Only check subcategories of the belonging to the given category
            if p.subcategory_name == subcategory_name:
                products_subcat.append((p))

        if len(products_subcat) == 0:
            raise ValueError(f"Subcategory `{subcategory_name}` not found")

        input_product_name = product_loc.inner_text()
        for p in products_subcat:
            if (
                p.scanned_product is None
                and p.product_locator is not None
                and p.product_locator.inner_text() == input_product_name
            ):
                p.scanned_product = scanned_product
                logger.debug("Scanned: %s", p)
                return

    def get_scanned_products(self) -> list[ScannedProduct]:
        scanned_products = [
            p.scanned_product for p in self.products if p.scanned_product is not None
        ]
        for sp in scanned_products:
            logger.debug("Scanned product: %s", sp)
        return scanned_products
