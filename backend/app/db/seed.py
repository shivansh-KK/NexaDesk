import random
from datetime import datetime, timedelta
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.db.models import (
    Customer,
    Order,
    OrderItem,
    Product,
    RefundRequest,
)
from app.db.session import SessionLocal, reset_db

# Fixed reference date to ensure absolute determinism across all environments and runs
REFERENCE_DATE = datetime(2026, 11, 15, 12, 0, 0)


def get_seed_products() -> List[dict]:
    return [
        {
            "id": 1,
            "name": "Apple iPhone 15 Pro 128GB",
            "category": "smartphones",
            "price_aed": 4299.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 2,
            "name": "Samsung Galaxy S24 Ultra 256GB",
            "category": "smartphones",
            "price_aed": 4899.0,
            "warranty_months": 24,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 3,
            "name": "Apple MacBook Pro 16 M3 Max",
            "category": "laptops",
            "price_aed": 12499.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 4,
            "name": "Dell XPS 15 OLED",
            "category": "laptops",
            "price_aed": 6499.0,
            "warranty_months": 24,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 5,
            "name": "Sony WH-1000XM5 Wireless Headphones",
            "category": "audio",
            "price_aed": 1299.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 6,
            "name": "Apple AirPods Pro 2nd Gen",
            "category": "audio",
            "price_aed": 899.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 7,
            "name": "Bose QuietComfort Ultra",
            "category": "audio",
            "price_aed": 1450.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 8,
            "name": "Apple Watch Ultra 2",
            "category": "wearables",
            "price_aed": 3199.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 9,
            "name": "Samsung Galaxy Watch 6 Classic",
            "category": "wearables",
            "price_aed": 1199.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 10,
            "name": "LG C3 65-inch OLED 4K TV",
            "category": "displays",
            "price_aed": 5999.0,
            "warranty_months": 24,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 11,
            "name": "Samsung Odyssey G9 49-inch Curved Gaming Monitor",
            "category": "displays",
            "price_aed": 4499.0,
            "warranty_months": 36,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 12,
            "name": "Sony PlayStation 5 Slim Digital",
            "category": "gaming",
            "price_aed": 1749.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 13,
            "name": "Nintendo Switch OLED Model",
            "category": "gaming",
            "price_aed": 1299.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 14,
            "name": "Logitech MX Master 3S Wireless Mouse",
            "category": "accessories",
            "price_aed": 399.0,
            "warranty_months": 24,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 15,
            "name": "Keychron Q1 Pro Mechanical Keyboard",
            "category": "accessories",
            "price_aed": 749.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 16,
            "name": "Anker 737 Power Bank 24,000mAh",
            "category": "accessories",
            "price_aed": 499.0,
            "warranty_months": 18,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 17,
            "name": "SanDisk 2TB Extreme Portable SSD",
            "category": "storage",
            "price_aed": 649.0,
            "warranty_months": 60,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 18,
            "name": "ShopAssist AED 500 Electronic Gift Card",
            "category": "gift_cards",
            "price_aed": 500.0,
            "warranty_months": 0,
            "is_software": False,
            "is_gift_card": True,
        },
        {
            "id": 19,
            "name": "ShopAssist AED 1000 Electronic Gift Card",
            "category": "gift_cards",
            "price_aed": 1000.0,
            "warranty_months": 0,
            "is_software": False,
            "is_gift_card": True,
        },
        {
            "id": 20,
            "name": "Microsoft Office Home & Business 2024 (Box/Opened)",
            "category": "software",
            "price_aed": 999.0,
            "warranty_months": 0,
            "is_software": True,
            "is_gift_card": False,
        },
        {
            "id": 21,
            "name": "CyberSecurity Suite Ultimate 1-Year License",
            "category": "software",
            "price_aed": 299.0,
            "warranty_months": 0,
            "is_software": True,
            "is_gift_card": False,
        },
        {
            "id": 22,
            "name": "Kindle Paperwhite 16GB",
            "category": "ereaders",
            "price_aed": 599.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 23,
            "name": "DJI Mini 4 Pro Drone Fly More Combo",
            "category": "cameras",
            "price_aed": 3899.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 24,
            "name": "GoPro HERO12 Black Action Camera",
            "category": "cameras",
            "price_aed": 1499.0,
            "warranty_months": 12,
            "is_software": False,
            "is_gift_card": False,
        },
        {
            "id": 25,
            "name": "Sonos Era 300 Smart Speaker",
            "category": "audio",
            "price_aed": 1799.0,
            "warranty_months": 24,
            "is_software": False,
            "is_gift_card": False,
        },
    ]


CUSTOMER_NAMES = [
    ("Alice Smith", "alice.smith@example.com", "+971-50-1000001"),
    ("Bob Jones", "bob.jones@example.com", "+971-50-1000002"),
    ("Carol White", "carol.white@example.com", "+971-50-1000003"),
    ("David Brown", "david.brown@example.com", "+971-50-1000004"),
    ("Eva Green", "eva.green@example.com", "+971-50-1000005"),
    ("Frank Miller", "frank.miller@example.com", "+971-50-1000006"),
    ("Grace Lee", "grace.lee@example.com", "+971-50-1000007"),
    ("Hassan Ali", "hassan.ali@example.com", "+971-50-1000008"),
    ("Isla Taylor", "isla.taylor@example.com", "+971-50-1000009"),
    ("Jack Wilson", "jack.wilson@example.com", "+971-50-1000010"),
    ("Kareem Mansour", "kareem.mansour@example.com", "+971-50-1000011"),
    ("Layla Haddad", "layla.haddad@example.com", "+971-50-1000012"),
    ("Mohammed Al-Falasi", "mohammed.falasi@example.com", "+971-50-1000013"),
    ("Nour Al-Sabah", "nour.sabah@example.com", "+971-50-1000014"),
    ("Omar Farooq", "omar.farooq@example.com", "+971-50-1000015"),
    ("Priya Sharma", "priya.sharma@example.com", "+971-50-1000016"),
    ("Qasim Khan", "qasim.khan@example.com", "+971-50-1000017"),
    ("Rania Salem", "rania.salem@example.com", "+971-50-1000018"),
    ("Sari Khoury", "sari.khoury@example.com", "+971-50-1000019"),
    ("Tariq Mahmoud", "tariq.mahmoud@example.com", "+971-50-1000020"),
    ("Uma Patel", "uma.patel@example.com", "+971-50-1000021"),
    ("Vikram Singh", "vikram.singh@example.com", "+971-50-1000022"),
    ("Waleed Darwish", "waleed.darwish@example.com", "+971-50-1000023"),
    ("Xavier Dupont", "xavier.dupont@example.com", "+971-50-1000024"),
    ("Yara Nader", "yara.nader@example.com", "+971-50-1000025"),
    ("Zaid Qureshi", "zaid.qureshi@example.com", "+971-50-1000026"),
    ("Amira Saeed", "amira.saeed@example.com", "+971-50-1000027"),
    ("Bilal Nassar", "bilal.nassar@example.com", "+971-50-1000028"),
    ("Chloe Martin", "chloe.martin@example.com", "+971-50-1000029"),
    ("Daniel Craig", "daniel.craig@example.com", "+971-50-1000030"),
    ("Elena Rostova", "elena.rostova@example.com", "+971-50-1000031"),
    ("Faisal Hashmi", "faisal.hashmi@example.com", "+971-50-1000032"),
    ("Gita Rao", "gita.rao@example.com", "+971-50-1000033"),
    ("Hamza Obeid", "hamza.obeid@example.com", "+971-50-1000034"),
    ("Iman Kassam", "iman.kassam@example.com", "+971-50-1000035"),
    ("Jad Tannous", "jad.tannous@example.com", "+971-50-1000036"),
    ("Kavita Nair", "kavita.nair@example.com", "+971-50-1000037"),
    ("Leo Rossi", "leo.rossi@example.com", "+971-50-1000038"),
    ("Maya Angel", "maya.angel@example.com", "+971-50-1000039"),
    ("Nabil Saleh", "nabil.saleh@example.com", "+971-50-1000040"),
]


def seed_database(db: Session) -> Tuple[int, int, int, int]:
    """Seed the database deterministically. Returns (num_customers, num_products, num_orders, num_items)."""
    random.seed(42)

    # 1. Seed 40 Customers
    customers = []
    for i, (name, email, phone) in enumerate(CUSTOMER_NAMES, start=1):
        c = Customer(id=i, name=name, email=email, phone=phone)
        customers.append(c)
        db.add(c)
    db.flush()

    # 2. Seed 25 Products
    product_records = []
    for p_data in get_seed_products():
        p = Product(**p_data)
        product_records.append(p)
        db.add(p)
    db.flush()

    # 3. Seed 150 Orders with realistic status, items, and refund windows
    # Specific deterministic flagship orders:
    # ORD-10001: Alice Smith (c=1), DELIVERED 4 days ago, iPhone 15 Pro (4299 AED) -> ELIGIBLE
    # ORD-10002: Bob Jones (c=2), DELIVERED 25 days ago, Sony Headphones (1299 AED) -> INELIGIBLE (outside 14-day window)
    # ORD-10003: Carol White (c=3), CANCELLED, AirPods Pro (899 AED) -> INELIGIBLE (cancelled)
    # ORD-10004: David Brown (c=4), RETURNED, Bose QC Ultra (1450 AED) -> INELIGIBLE (already returned)
    # ORD-10005: Eva Green (c=5), DELIVERED 3 days ago, MacBook Pro (12499 AED) -> HIGH VALUE (>5000 AED, needs escalation)
    # ORD-10006: Frank Miller (c=6), DELIVERED 4 days ago, Office Suite (999 AED, opened=True) -> INELIGIBLE (opened software)
    # ORD-10007: Grace Lee (c=7), DELIVERED 2 days ago, Gift Card (500 AED) -> INELIGIBLE (gift card)
    # ORD-10008: Hassan Ali (c=8), DELIVERED 6 days ago, Apple Watch (3199 AED), already has refund request -> INELIGIBLE (duplicate)
    # ORD-10009: Isla Taylor (c=9), PROCESSING, Logitech MX Master (399 AED) -> INELIGIBLE (not delivered)
    # ORD-10010: Jack Wilson (c=10), SHIPPED, Anker Power Bank (499 AED) -> INELIGIBLE (not delivered)
    # ORD-10011: Kareem Mansour (c=11), DELIVERED 5 days ago, SanDisk 2TB SSD (649 AED) -> ELIGIBLE
    # ORD-10012: Layla Haddad (c=12), DELIVERED 2 days ago, Keychron Q1 Pro (749 AED) -> ELIGIBLE
    # ORD-10013: Mohammed Al-Falasi (c=13), DELIVERED 30 days ago, LG C3 OLED (5999 AED) -> INELIGIBLE (outside window & high value)
    # ORD-10014: Nour Al-Sabah (c=14), DELIVERED 8 days ago, Sony PS5 (1749 AED) -> ELIGIBLE
    # ORD-10015: Omar Farooq (c=15), DELIVERED 10 days ago, Nintendo Switch (1299 AED) -> ELIGIBLE

    orders = []
    order_items = []

    # Flagship curated orders (1 to 15)
    flagship_configs = [
        # (order_num, cust_id, status, days_ago_ordered, days_ago_delivered, [(product_id, qty, is_opened)])
        (10001, 1, "delivered", 8, 4, [(1, 1, False)]),
        (10002, 2, "delivered", 32, 25, [(5, 1, False)]),
        (10003, 3, "cancelled", 12, None, [(6, 1, False)]),
        (10004, 4, "returned", 40, 35, [(7, 1, False)]),
        (10005, 5, "delivered", 7, 3, [(3, 1, False)]),
        (10006, 6, "delivered", 9, 4, [(20, 1, True)]),  # opened software
        (10007, 7, "delivered", 6, 2, [(18, 1, False)]),  # gift card
        (10008, 8, "delivered", 11, 6, [(8, 1, False)]),  # has refund request
        (10009, 9, "processing", 2, None, [(14, 1, False)]),
        (10010, 10, "shipped", 4, None, [(16, 1, False)]),
        (10011, 11, "delivered", 10, 5, [(17, 1, False)]),
        (10012, 12, "delivered", 5, 2, [(15, 1, False)]),
        (10013, 13, "delivered", 38, 30, [(10, 1, False)]),
        (10014, 14, "delivered", 14, 8, [(12, 1, False)]),
        (10015, 15, "delivered", 16, 10, [(13, 1, False)]),
    ]

    for ord_num, cust_id, status, days_ord, days_deliv, items in flagship_configs:
        order_date = REFERENCE_DATE - timedelta(days=days_ord)
        deliv_date = REFERENCE_DATE - timedelta(days=days_deliv) if days_deliv else None
        total = 0.0
        for pid, qty, _ in items:
            p = next(x for x in product_records if x.id == pid)
            total += p.price_aed * qty
        ord_id = f"ORD-{ord_num}"
        order = Order(
            id=ord_id,
            customer_id=cust_id,
            status=status,
            order_date=order_date,
            delivery_date=deliv_date,
            total_aed=round(total, 2),
        )
        orders.append(order)
        db.add(order)
        db.flush()

        for pid, qty, opened in items:
            p = next(x for x in product_records if x.id == pid)
            item = OrderItem(
                order_id=ord_id,
                product_id=pid,
                quantity=qty,
                unit_price_aed=p.price_aed,
                is_opened=opened,
            )
            order_items.append(item)
            db.add(item)

    # ORD-10008 has an existing refund request in DB to test duplicate refund rejection
    existing_refund = RefundRequest(
        order_id="ORD-10008",
        reason="Screen had dead pixels on arrival",
        amount_aed=3199.0,
        status="pending_approval",
        created_at=REFERENCE_DATE - timedelta(days=3),
    )
    db.add(existing_refund)

    # Remaining orders from 10016 to 10150
    statuses_pool = [
        "delivered",
        "delivered",
        "delivered",
        "shipped",
        "processing",
        "cancelled",
        "returned",
    ]

    for ord_num in range(10016, 10151):
        cust_id = ((ord_num - 10001) % 40) + 1
        status = random.choice(statuses_pool)
        days_ord = random.randint(3, 90)
        order_date = REFERENCE_DATE - timedelta(days=days_ord)

        if status in ("delivered", "returned"):
            # Mix of within 14 days and outside 14 days
            if random.random() < 0.5:
                days_deliv = random.randint(1, 13)
            else:
                days_deliv = random.randint(15, 60)
            delivery_date = REFERENCE_DATE - timedelta(days=days_deliv)
            if delivery_date < order_date:
                delivery_date = order_date + timedelta(days=2)
        else:
            delivery_date = None

        # Pick 1 to 3 items
        num_items = random.choices([1, 2, 3], weights=[0.7, 0.2, 0.1])[0]
        chosen_products = random.sample(product_records, num_items)
        ord_id = f"ORD-{ord_num}"

        total = 0.0
        current_items = []
        for p in chosen_products:
            qty = random.randint(1, 2)
            total += p.price_aed * qty
            is_opened = p.is_software and (random.random() < 0.5)
            current_items.append((p.id, qty, p.price_aed, is_opened))

        order = Order(
            id=ord_id,
            customer_id=cust_id,
            status=status,
            order_date=order_date,
            delivery_date=delivery_date,
            total_aed=round(total, 2),
        )
        orders.append(order)
        db.add(order)
        db.flush()

        for pid, qty, price, opened in current_items:
            item = OrderItem(
                order_id=ord_id,
                product_id=pid,
                quantity=qty,
                unit_price_aed=price,
                is_opened=opened,
            )
            order_items.append(item)
            db.add(item)

    db.commit()
    return len(customers), len(product_records), len(orders), len(order_items)


def run_seed() -> None:
    reset_db()
    db = SessionLocal()
    try:
        n_cust, n_prod, n_ord, n_items = seed_database(db)
        print("Database seeded successfully:")
        print(f"  Customers:    {n_cust}")
        print(f"  Products:     {n_prod}")
        print(f"  Orders:       {n_ord}")
        print(f"  Order Items:  {n_items}")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
