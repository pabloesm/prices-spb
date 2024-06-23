from playwright.sync_api._generated import ElementHandle, Locator
from pydantic import BaseModel, Field

from src.config.logger import logger
from src.models import ScannedProduct


class ProductState(BaseModel):
    """State of a product being scraped.

    A product state can have:
    - Only category (locator and name). Then all subcategories and products belonging to the
    category are pending.
    - A category (locator and name) and a subcategory (locator and name), then all products
    belonging to that category-subcategory are pending.
    - A category, a subcategory and a product (locator, handle and name), then the product is
    pending.
    - A category, a subcategory and a product with a scanned product, then the product is scanned.

    Notice that `Locator`s become stale between pages reloads, so they need to be refreshed before
    used. On the other hand, `ElementHandle`s are not stale, so they can be used directly.
    """

    category_locator: Locator = Field(repr=False)
    category_name: str
    subcategory_locator: Locator | None = Field(default=None, repr=False)
    subcategory_name: str | None = None
    product_locator: Locator | None = Field(default=None, repr=False)
    product_handle: ElementHandle | None = Field(default=None, repr=False)
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
            and str(self.product_handle) == str(other.product_handle)
            and self.scanned_product == other.scanned_product
        )

    def __hash__(self):
        return hash(
            (self.category_name, self.subcategory_name, self.product_name, self.scanned_product)
        )


class ProductsState:
    """State of the products being scraped.

    Allow to keep track of the products being scraped and resume the scraping process after a
    failure.
    """

    def __init__(self):
        self.products = []
        self._is_finished = False

    @property
    def is_finished(self) -> bool:
        return bool(self._is_finished)

    @is_finished.setter
    def is_finished(self, value: bool) -> None:
        self._is_finished = value

    def add_categories(self, categories_locs: list[Locator]) -> None:
        """Add/sync the categories to the products state."""

        # Sync if categories already exist
        if len(self.products) > 0:
            self._sync_categories(categories_locs)
            return

        # Otherwise, add the categories
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
            self._sync_subcategories(category_loc, subcategories_locs)
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
            assert index_product_subcat_tuples[0][1].product_handle is None
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
                if ipc[1].product_handle and not ipc[1].scanned_product
            ]
            product_subcat = products_subcat[0]

        else:
            raise ValueError("Unexpected state while adding products")

        # Create new products
        new_prods_state = []
        for product_loc in products_locs:
            logger.debug("URL checked for: %s", product_loc)
            new_prods_state.append(
                ProductState(
                    category_locator=product_subcat.category_locator,
                    category_name=product_subcat.category_name,
                    subcategory_locator=product_subcat.subcategory_locator,
                    subcategory_name=product_subcat.subcategory_name,
                    product_locator=product_loc,
                    product_handle=product_loc.element_handle(),
                    product_name=product_loc.inner_text(),
                )
            )

        # Remove pending products in self.products which are going to be added/synced
        for product in self.products[:]:
            if product in new_prods_state:
                self.products.remove(product)

        # Remove products which are already scanned. Since the same product can be in different
        # categories/subcategories (e.g, Carnes -> Carne congelada and Congelados -> Carne), we
        # need to check the product name and the category/subcategory
        products_scanned = [p for p in self.products if p.scanned_product]
        products_scanned_names = [f"{p.category_name}_{p.product_name}" for p in products_scanned]
        for product in new_prods_state[:]:
            cat_and_name = f"{product.category_name}_{product.product_name}"
            if cat_and_name in products_scanned_names:
                new_prods_state.remove(product)

        # Add the new products
        self.products.extend(new_prods_state)

        for new_prod_state in new_prods_state:
            logger.debug("Added: %s, %s", new_prod_state, new_prod_state.product_handle)

    def add_scanned_product(
        self,
        category_loc: Locator,
        subcategory_loc: Locator,
        product_handle: ElementHandle,
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

        input_product_name = product_handle.inner_text()
        for p in products_subcat:
            if (
                p.scanned_product is None
                and p.product_handle is not None
                and p.product_handle.inner_text() == input_product_name
            ):
                p.scanned_product = scanned_product
                logger.debug("Scanned: %s", p)
                return

    def get_pending_categories(self) -> list[Locator]:
        pending_categories_set = set()
        for product in self.products:
            if product.scanned_product is None:
                # Add only the category information
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
    ) -> list[ElementHandle]:
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

        pending_products_handles = [p.product_handle for p in pending_products]
        pending_products_handles = [p for p in pending_products_handles if p is not None]
        for pending_product_handle in pending_products_handles:
            pending_product_handle.inner_text()

        return pending_products_handles

    def get_scanned_products(self) -> list[ScannedProduct]:
        scanned_products = [
            p.scanned_product for p in self.products if p.scanned_product is not None
        ]
        for sp in scanned_products:
            logger.debug("Scanned product: %s", sp)
        return scanned_products

    def _sync_categories(self, categories_locs: list[Locator]) -> None:
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

    def _sync_subcategories(self, category_loc: Locator, subcategories_locs: list[Locator]) -> None:
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
