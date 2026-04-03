from app.models import (
    Product, ProductVariant, ProductImage,
    Collection, CollectionProduct,
    Location, InventoryItem, InventoryLevel,
    Customer, CustomerAddress,
    Order, LineItem, Fulfillment,
    Discount,
)


def test_product_table_name():
    assert Product.__tablename__ == "products"

def test_product_variant_table_name():
    assert ProductVariant.__tablename__ == "product_variants"

def test_product_image_table_name():
    assert ProductImage.__tablename__ == "product_images"

def test_collection_table_name():
    assert Collection.__tablename__ == "collections"

def test_collection_product_table_name():
    assert CollectionProduct.__tablename__ == "collection_products"

def test_location_table_name():
    assert Location.__tablename__ == "locations"

def test_inventory_item_table_name():
    assert InventoryItem.__tablename__ == "inventory_items"

def test_inventory_level_table_name():
    assert InventoryLevel.__tablename__ == "inventory_levels"

def test_customer_table_name():
    assert Customer.__tablename__ == "customers"

def test_customer_address_table_name():
    assert CustomerAddress.__tablename__ == "customer_addresses"

def test_order_table_name():
    assert Order.__tablename__ == "orders"

def test_line_item_table_name():
    assert LineItem.__tablename__ == "line_items"

def test_fulfillment_table_name():
    assert Fulfillment.__tablename__ == "fulfillments"

def test_discount_table_name():
    assert Discount.__tablename__ == "discounts"
