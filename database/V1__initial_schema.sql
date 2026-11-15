CREATE TABLE product (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    barcode VARCHAR(32) UNIQUE,
    name VARCHAR(255) NOT NULL,
    brand VARCHAR(120),
    ingredients_text TEXT,
    source VARCHAR(40) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE nutrition_fact (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id BIGINT NOT NULL,
    nutrient VARCHAR(60) NOT NULL,
    value DECIMAL(10, 3),
    unit VARCHAR(20) NOT NULL,
    basis VARCHAR(30) NOT NULL,
    CONSTRAINT fk_nutrition_product FOREIGN KEY (product_id) REFERENCES product(id),
    UNIQUE (product_id, nutrient, basis)
);

CREATE INDEX idx_product_barcode ON product(barcode);

