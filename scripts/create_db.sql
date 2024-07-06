DROP TABLE IF EXISTS product CASCADE;
DROP TABLE IF EXISTS badge CASCADE;
DROP TABLE IF EXISTS photo CASCADE;
DROP TABLE IF EXISTS supplier CASCADE;
DROP TABLE IF EXISTS category CASCADE;
DROP TABLE IF EXISTS product_category CASCADE;
DROP TABLE IF EXISTS price_instruction CASCADE;
DROP TABLE IF EXISTS nutrition_information CASCADE;
DROP TABLE IF EXISTS scanned_products CASCADE;


-- Badge Table
CREATE TABLE badge (
    id SERIAL PRIMARY KEY,
    is_water BOOLEAN,
    requires_age_check BOOLEAN
);

-- Supplier Table
CREATE TABLE supplier (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255)
);

-- Product Table
CREATE TABLE product (
    id NUMERIC(10,3) PRIMARY KEY,
    ean VARCHAR(50),
    slug TEXT,
    brand VARCHAR(100),
    limit_value INTEGER,
    origin VARCHAR(255),
    packaging VARCHAR(100),
    published BOOLEAN,
    share_url TEXT,
    thumbnail TEXT,
    display_name VARCHAR(255),
    unavailable_from DATE,
    is_variable_weight BOOLEAN,
    legal_name VARCHAR(255),
    description TEXT,
    counter_info TEXT,
    danger_mentions TEXT,
    alcohol_by_volume NUMERIC(10,2),
    mandatory_mentions TEXT,
    product_variant VARCHAR(255),
    usage_instructions TEXT,
    storage_instructions TEXT,
    badge_id INT REFERENCES badge(id),
    supplier_id INT REFERENCES supplier(id)
);

-- Photo Table
CREATE TABLE photo (
    id SERIAL PRIMARY KEY,
    product_id NUMERIC(10,3) REFERENCES product(id),
    zoom TEXT,
    regular TEXT,
    thumbnail TEXT,
    perspective INTEGER
);

-- Category Table
CREATE TABLE category (
    id INTEGER PRIMARY KEY,
    name TEXT,
    level INTEGER,
    order_value INTEGER
);

-- Product_Category Table
CREATE TABLE product_category (
    product_id NUMERIC(10,3) REFERENCES product(id),
    category_id INTEGER REFERENCES category(id),
    PRIMARY KEY (product_id, category_id)
);

-- Price_Instruction Table
CREATE TABLE price_instruction (
    id SERIAL PRIMARY KEY,
    product_id NUMERIC(10,3) REFERENCES product(id),
    iva NUMERIC(10,2),
    is_new BOOLEAN,
    is_pack BOOLEAN,
    pack_size NUMERIC(10,2),
    unit_name VARCHAR(50),
    unit_size NUMERIC(10,2),
    bulk_price NUMERIC(10,2),
    unit_price NUMERIC(10,2),
    approx_size BOOLEAN,
    size_format VARCHAR(10),
    total_units INTEGER,
    unit_selector BOOLEAN,
    bunch_selector BOOLEAN,
    drained_weight NUMERIC(10,2),
    selling_method INTEGER,
    price_decreased BOOLEAN,
    reference_price NUMERIC(10,2),
    min_bunch_amount NUMERIC(10,2),
    reference_format VARCHAR(10),
    previous_unit_price NUMERIC(10,2),
    increment_bunch_amount NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Nutrition_Information Table
CREATE TABLE nutrition_information (
    id SERIAL PRIMARY KEY,
    product_id NUMERIC(10,3) REFERENCES product(id),
    allergens TEXT,
    ingredients TEXT
);

-- Scanned_Products Table
CREATE TABLE scanned_products (
    product_id NUMERIC(10,3) PRIMARY KEY,
    category_name VARCHAR(255),
    subcategory_name VARCHAR(255),
    scanned_at TIMESTAMP
);
