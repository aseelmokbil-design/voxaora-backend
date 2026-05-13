"""
VOXAORA Seed Data — Full Catalog
Run: cd backend && python seed.py
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole, UserStatus
from app.models.merchant import Merchant, MerchantStatus
from app.models.product import Product, Category, ProductStatus
from app.models.driver import Driver, DriverStatus

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

MERCHANTS_DATA = [
    # ─── RESTAURANTS ────────────────────────────────────────────
    {
        "name": "Al-Baik", "name_ar": "البيك",
        "category": "restaurant",
        "description": "Famous Saudi fried chicken restaurant",
        "description_ar": "مطعم البيك الشهير للدجاج المقلي السعودي",
        "latitude": 24.7136, "longitude": 46.6753, "city": "Riyadh",
        "delivery_fee": 5.0, "min_order_amount": 20.0, "free_delivery_above": 80.0,
        "avg_preparation_time": 15, "rating": 4.8, "total_orders": 15420, "is_open_now": True,
        "categories": [
            {"name": "Chicken Meals", "name_ar": "وجبات الدجاج"},
            {"name": "Broasted", "name_ar": "البروستد"},
            {"name": "Sides", "name_ar": "الإضافات"},
            {"name": "Drinks", "name_ar": "المشروبات"},
        ],
        "products": [
            {"name": "Broasted Chicken Meal", "name_ar": "وجبة دجاج مقلي", "price": 28.0, "prep": 15, "cat": 0},
            {"name": "Chicken Burger", "name_ar": "برجر دجاج", "price": 18.0, "prep": 10, "cat": 0},
            {"name": "Family Meal (8 pcs)", "name_ar": "وجبة عائلية 8 قطع", "price": 89.0, "prep": 20, "cat": 0},
            {"name": "Half Chicken Broasted", "name_ar": "نصف دجاجة مقلية", "price": 32.0, "prep": 20, "cat": 1},
            {"name": "Full Chicken Broasted", "name_ar": "دجاجة كاملة مقلية", "price": 55.0, "prep": 25, "cat": 1},
            {"name": "French Fries Large", "name_ar": "بطاطس مقلية كبيرة", "price": 10.0, "prep": 5, "cat": 2},
            {"name": "Coleslaw", "name_ar": "سلطة كولسلو", "price": 6.0, "prep": 2, "cat": 2},
            {"name": "Garlic Bread", "name_ar": "خبز بالثوم", "price": 5.0, "prep": 3, "cat": 2},
            {"name": "Pepsi 500ml", "name_ar": "بيبسي 500 مل", "price": 5.0, "prep": 1, "cat": 3},
            {"name": "Orange Juice", "name_ar": "عصير برتقال", "price": 8.0, "prep": 2, "cat": 3},
            {"name": "Water 500ml", "name_ar": "مياه 500 مل", "price": 3.0, "prep": 1, "cat": 3},
        ],
    },
    {
        "name": "Pizza Hut", "name_ar": "بيتزا هت",
        "category": "restaurant",
        "description": "World's largest pizza restaurant chain",
        "description_ar": "أكبر سلسلة بيتزا في العالم",
        "latitude": 24.7180, "longitude": 46.6820, "city": "Riyadh",
        "delivery_fee": 7.0, "min_order_amount": 30.0, "free_delivery_above": 100.0,
        "avg_preparation_time": 25, "rating": 4.5, "total_orders": 12300, "is_open_now": True,
        "categories": [
            {"name": "Pizzas", "name_ar": "البيتزا"},
            {"name": "Pasta", "name_ar": "المعكرونة"},
            {"name": "Sides & Starters", "name_ar": "المقبلات والإضافات"},
            {"name": "Drinks", "name_ar": "المشروبات"},
        ],
        "products": [
            {"name": "Pepperoni Pizza Large", "name_ar": "بيتزا بيبروني كبيرة", "price": 65.0, "prep": 25, "cat": 0},
            {"name": "Pepperoni Pizza Medium", "name_ar": "بيتزا بيبروني وسط", "price": 48.0, "prep": 20, "cat": 0},
            {"name": "Margherita Pizza Large", "name_ar": "بيتزا مارغريتا كبيرة", "price": 55.0, "prep": 25, "cat": 0},
            {"name": "BBQ Chicken Pizza Large", "name_ar": "بيتزا دجاج بي بي كيو كبيرة", "price": 68.0, "prep": 25, "cat": 0},
            {"name": "Veggie Supreme Pizza", "name_ar": "بيتزا خضار سوبريم", "price": 58.0, "prep": 25, "cat": 0},
            {"name": "Meat Lovers Pizza", "name_ar": "بيتزا محبي اللحوم", "price": 72.0, "prep": 30, "cat": 0},
            {"name": "Creamy Chicken Pasta", "name_ar": "معكرونة دجاج كريمة", "price": 35.0, "prep": 20, "cat": 1},
            {"name": "Penne Arrabbiata", "name_ar": "مكرونة أرابياتا", "price": 30.0, "prep": 20, "cat": 1},
            {"name": "Chicken Wings (6 pcs)", "name_ar": "أجنحة دجاج 6 قطع", "price": 32.0, "prep": 15, "cat": 2},
            {"name": "Mozzarella Sticks", "name_ar": "أصابع موزاريلا", "price": 22.0, "prep": 10, "cat": 2},
            {"name": "Garlic Bread with Cheese", "name_ar": "خبز ثوم بالجبن", "price": 18.0, "prep": 8, "cat": 2},
            {"name": "Pepsi 1.5L", "name_ar": "بيبسي 1.5 لتر", "price": 8.0, "prep": 1, "cat": 3},
            {"name": "7UP 1.5L", "name_ar": "سفن أب 1.5 لتر", "price": 8.0, "prep": 1, "cat": 3},
        ],
    },
    {
        "name": "KFC Saudi", "name_ar": "كنتاكي",
        "category": "restaurant",
        "description": "Kentucky Fried Chicken — finger lickin good",
        "description_ar": "كنتاكي فرايد تشيكن — لا يقاوم",
        "latitude": 24.7050, "longitude": 46.6720, "city": "Riyadh",
        "delivery_fee": 6.0, "min_order_amount": 25.0, "free_delivery_above": 90.0,
        "avg_preparation_time": 18, "rating": 4.6, "total_orders": 18900, "is_open_now": True,
        "categories": [
            {"name": "Meals", "name_ar": "الوجبات"},
            {"name": "Buckets", "name_ar": "الباكيت"},
            {"name": "Burgers", "name_ar": "برجر"},
            {"name": "Sides", "name_ar": "الإضافات"},
            {"name": "Drinks", "name_ar": "مشروبات"},
        ],
        "products": [
            {"name": "Zinger Meal", "name_ar": "وجبة زنجر", "price": 32.0, "prep": 12, "cat": 0},
            {"name": "Crispy Strips Meal", "name_ar": "وجبة شرائح مقرمشة", "price": 30.0, "prep": 12, "cat": 0},
            {"name": "Chicken Meal 2 pcs", "name_ar": "وجبة دجاج قطعتان", "price": 28.0, "prep": 15, "cat": 0},
            {"name": "Family Bucket 9 pcs", "name_ar": "باكيت عائلي 9 قطع", "price": 85.0, "prep": 20, "cat": 1},
            {"name": "Bargain Bucket 6 pcs", "name_ar": "باكيت اقتصادي 6 قطع", "price": 62.0, "prep": 18, "cat": 1},
            {"name": "Zinger Burger", "name_ar": "برجر زنجر", "price": 22.0, "prep": 10, "cat": 2},
            {"name": "Double Zinger", "name_ar": "دبل زنجر", "price": 32.0, "prep": 12, "cat": 2},
            {"name": "Chicken Fillet Burger", "name_ar": "برجر فيليه دجاج", "price": 20.0, "prep": 10, "cat": 2},
            {"name": "Coleslaw", "name_ar": "سلطة كولسلو", "price": 7.0, "prep": 2, "cat": 3},
            {"name": "Corn on the Cob", "name_ar": "ذرة", "price": 6.0, "prep": 3, "cat": 3},
            {"name": "French Fries Regular", "name_ar": "بطاطس مقلية عادية", "price": 9.0, "prep": 5, "cat": 3},
            {"name": "Pepsi Large", "name_ar": "بيبسي كبير", "price": 6.0, "prep": 1, "cat": 4},
            {"name": "Mirinda Orange", "name_ar": "ميرندا برتقال", "price": 6.0, "prep": 1, "cat": 4},
        ],
    },
    {
        "name": "Kudu", "name_ar": "كودو",
        "category": "restaurant",
        "description": "Saudi fast food chain — burgers and more",
        "description_ar": "سلسلة الوجبات السريعة السعودية",
        "latitude": 24.7250, "longitude": 46.6650, "city": "Riyadh",
        "delivery_fee": 5.0, "min_order_amount": 20.0, "free_delivery_above": 75.0,
        "avg_preparation_time": 15, "rating": 4.4, "total_orders": 9200, "is_open_now": True,
        "categories": [
            {"name": "Burgers", "name_ar": "برجر"},
            {"name": "Chicken", "name_ar": "دجاج"},
            {"name": "Sandwiches", "name_ar": "ساندويتشات"},
            {"name": "Drinks & Desserts", "name_ar": "مشروبات وحلويات"},
        ],
        "products": [
            {"name": "Kudu Burger", "name_ar": "برجر كودو", "price": 22.0, "prep": 12, "cat": 0},
            {"name": "Double Kudu Burger", "name_ar": "دبل برجر كودو", "price": 30.0, "prep": 15, "cat": 0},
            {"name": "Mushroom Swiss Burger", "name_ar": "برجر مشروم وجبن سويسي", "price": 28.0, "prep": 15, "cat": 0},
            {"name": "Crispy Chicken Sandwich", "name_ar": "ساندويتش دجاج مقرمش", "price": 20.0, "prep": 10, "cat": 1},
            {"name": "Grilled Chicken", "name_ar": "دجاج مشوي", "price": 25.0, "prep": 18, "cat": 1},
            {"name": "Shawarma Sandwich", "name_ar": "ساندويتش شاورما", "price": 18.0, "prep": 8, "cat": 2},
            {"name": "Falafel Wrap", "name_ar": "لفة فلافل", "price": 14.0, "prep": 8, "cat": 2},
            {"name": "Lemonade Fresh", "name_ar": "ليمون طازج", "price": 12.0, "prep": 3, "cat": 3},
            {"name": "Milkshake Chocolate", "name_ar": "ميلك شيك شوكولاتة", "price": 15.0, "prep": 5, "cat": 3},
        ],
    },
    {
        "name": "Herfy", "name_ar": "هرفي",
        "category": "restaurant",
        "description": "Saudi fast food chain",
        "description_ar": "سلسلة مطاعم هرفي السعودية",
        "latitude": 24.7200, "longitude": 46.6900, "city": "Riyadh",
        "delivery_fee": 6.0, "min_order_amount": 25.0, "free_delivery_above": 100.0,
        "avg_preparation_time": 20, "rating": 4.5, "total_orders": 8900, "is_open_now": True,
        "categories": [
            {"name": "Burgers", "name_ar": "برجر"},
            {"name": "Pizzas", "name_ar": "بيتزا"},
            {"name": "Grills", "name_ar": "مشويات"},
            {"name": "Drinks", "name_ar": "مشروبات"},
        ],
        "products": [
            {"name": "Herfy Burger Classic", "name_ar": "برجر هرفي كلاسيك", "price": 22.0, "prep": 12, "cat": 0},
            {"name": "Double Herfy Burger", "name_ar": "دبل برجر هرفي", "price": 32.0, "prep": 15, "cat": 0},
            {"name": "Spicy Burger", "name_ar": "برجر حار", "price": 25.0, "prep": 12, "cat": 0},
            {"name": "Margherita Pizza", "name_ar": "بيتزا مارغريتا", "price": 35.0, "prep": 20, "cat": 1},
            {"name": "Pepperoni Pizza", "name_ar": "بيتزا بيبروني", "price": 42.0, "prep": 25, "cat": 1},
            {"name": "Mixed Grill Platter", "name_ar": "طبق مشويات مشكلة", "price": 75.0, "prep": 30, "cat": 2},
            {"name": "Grilled Chicken", "name_ar": "دجاج مشوي", "price": 38.0, "prep": 25, "cat": 2},
            {"name": "Soft Drink", "name_ar": "مشروب غازي", "price": 5.0, "prep": 1, "cat": 3},
            {"name": "Fresh Juice", "name_ar": "عصير طازج", "price": 12.0, "prep": 3, "cat": 3},
        ],
    },

    # ─── COFFEE & BAKERY ────────────────────────────────────────
    {
        "name": "Starbucks", "name_ar": "ستاربكس",
        "category": "coffee",
        "description": "Premium coffee experience",
        "description_ar": "تجربة القهوة المميزة",
        "latitude": 24.6950, "longitude": 46.6780, "city": "Riyadh",
        "delivery_fee": 8.0, "min_order_amount": 20.0, "free_delivery_above": 80.0,
        "avg_preparation_time": 12, "rating": 4.7, "total_orders": 22000, "is_open_now": True,
        "categories": [
            {"name": "Hot Espresso", "name_ar": "إسبريسو ساخن"},
            {"name": "Cold & Iced", "name_ar": "مشروبات باردة"},
            {"name": "Frappuccino", "name_ar": "فرابوتشينو"},
            {"name": "Food", "name_ar": "طعام"},
        ],
        "products": [
            {"name": "Caramel Latte", "name_ar": "لاتيه كراميل", "price": 22.0, "prep": 5, "cat": 0},
            {"name": "Cappuccino", "name_ar": "كابتشينو", "price": 20.0, "prep": 5, "cat": 0},
            {"name": "Americano", "name_ar": "أمريكانو", "price": 16.0, "prep": 4, "cat": 0},
            {"name": "Flat White", "name_ar": "فلات وايت", "price": 20.0, "prep": 5, "cat": 0},
            {"name": "Caramel Macchiato", "name_ar": "ماكياتو كراميل", "price": 24.0, "prep": 5, "cat": 0},
            {"name": "Iced Caramel Latte", "name_ar": "لاتيه كراميل بارد", "price": 24.0, "prep": 5, "cat": 1},
            {"name": "Cold Brew", "name_ar": "كولد برو", "price": 22.0, "prep": 3, "cat": 1},
            {"name": "Iced Matcha Latte", "name_ar": "ماتشا لاتيه بارد", "price": 24.0, "prep": 5, "cat": 1},
            {"name": "Caramel Frappuccino", "name_ar": "فرابوتشينو كراميل", "price": 28.0, "prep": 7, "cat": 2},
            {"name": "Mocha Frappuccino", "name_ar": "فرابوتشينو موكا", "price": 28.0, "prep": 7, "cat": 2},
            {"name": "Java Chip Frappuccino", "name_ar": "فرابوتشينو جافا تشيب", "price": 30.0, "prep": 7, "cat": 2},
            {"name": "Butter Croissant", "name_ar": "كرواسان بالزبدة", "price": 12.0, "prep": 2, "cat": 3},
            {"name": "Chocolate Cake Slice", "name_ar": "قطعة كيك شوكولاتة", "price": 18.0, "prep": 2, "cat": 3},
            {"name": "Cheese Sandwich", "name_ar": "ساندويتش جبن", "price": 16.0, "prep": 5, "cat": 3},
        ],
    },
    {
        "name": "Tim Hortons", "name_ar": "تيم هورتنز",
        "category": "coffee",
        "description": "Canadian coffee chain",
        "description_ar": "سلسلة القهوة الكندية",
        "latitude": 24.6900, "longitude": 46.6800, "city": "Riyadh",
        "delivery_fee": 7.0, "min_order_amount": 20.0, "free_delivery_above": 80.0,
        "avg_preparation_time": 10, "rating": 4.4, "total_orders": 7800, "is_open_now": True,
        "categories": [
            {"name": "Hot Drinks", "name_ar": "مشروبات ساخنة"},
            {"name": "Cold Drinks", "name_ar": "مشروبات باردة"},
            {"name": "Food", "name_ar": "طعام"},
        ],
        "products": [
            {"name": "Original Blend Coffee", "name_ar": "قهوة أوريجينال بلند", "price": 12.0, "prep": 5, "cat": 0},
            {"name": "Latte", "name_ar": "لاتيه", "price": 18.0, "prep": 5, "cat": 0},
            {"name": "Cappuccino", "name_ar": "كابتشينو", "price": 18.0, "prep": 5, "cat": 0},
            {"name": "Hot Chocolate", "name_ar": "شوكولاتة ساخنة", "price": 16.0, "prep": 4, "cat": 0},
            {"name": "Iced Capp", "name_ar": "آيسد كاب", "price": 20.0, "prep": 5, "cat": 1},
            {"name": "Iced Latte", "name_ar": "لاتيه بارد", "price": 20.0, "prep": 5, "cat": 1},
            {"name": "Bagel with Cream Cheese", "name_ar": "بيغل مع جبن كريمي", "price": 14.0, "prep": 3, "cat": 2},
            {"name": "Muffin Chocolate Chip", "name_ar": "مافن رقائق شوكولاتة", "price": 10.0, "prep": 2, "cat": 2},
            {"name": "Chicken Sandwich", "name_ar": "ساندويتش دجاج", "price": 18.0, "prep": 8, "cat": 2},
        ],
    },
    {
        "name": "Cinnabon", "name_ar": "سينابون",
        "category": "bakery",
        "description": "World famous cinnamon rolls",
        "description_ar": "أشهر لفائف القرفة في العالم",
        "latitude": 24.7100, "longitude": 46.6700, "city": "Riyadh",
        "delivery_fee": 8.0, "min_order_amount": 25.0, "free_delivery_above": 80.0,
        "avg_preparation_time": 8, "rating": 4.6, "total_orders": 6500, "is_open_now": True,
        "categories": [
            {"name": "Rolls", "name_ar": "اللفائف"},
            {"name": "Bites & Minis", "name_ar": "المينيز"},
            {"name": "Beverages", "name_ar": "المشروبات"},
        ],
        "products": [
            {"name": "Classic Roll", "name_ar": "لفافة كلاسيك", "price": 22.0, "prep": 5, "cat": 0},
            {"name": "Caramel Pecanbon", "name_ar": "لفافة كراميل بيكانبون", "price": 28.0, "prep": 5, "cat": 0},
            {"name": "Chocobon", "name_ar": "تشوكوبون", "price": 26.0, "prep": 5, "cat": 0},
            {"name": "4-Pack Classic Rolls", "name_ar": "4 لفائف كلاسيك", "price": 75.0, "prep": 5, "cat": 0},
            {"name": "Minibon 4 pcs", "name_ar": "مينيبون 4 قطع", "price": 38.0, "prep": 5, "cat": 1},
            {"name": "Bites Box 9 pcs", "name_ar": "صندوق بايتس 9 قطع", "price": 45.0, "prep": 5, "cat": 1},
            {"name": "Cinnabon Blast Coffee", "name_ar": "قهوة سينابون بلاست", "price": 18.0, "prep": 3, "cat": 2},
            {"name": "Cold Brew with Cream", "name_ar": "كولد برو بالكريمة", "price": 20.0, "prep": 3, "cat": 2},
            {"name": "Classic Milkshake", "name_ar": "ميلك شيك كلاسيك", "price": 18.0, "prep": 5, "cat": 2},
        ],
    },

    # ─── SUPERMARKETS ────────────────────────────────────────────
    {
        "name": "Carrefour Express", "name_ar": "كارفور إكسبريس",
        "category": "grocery",
        "description": "Fresh groceries delivered fast",
        "description_ar": "بقالة طازجة توصيل سريع",
        "latitude": 24.7080, "longitude": 46.6750, "city": "Riyadh",
        "delivery_fee": 9.0, "min_order_amount": 40.0, "free_delivery_above": 180.0,
        "avg_preparation_time": 25, "rating": 4.4, "total_orders": 8800, "is_open_now": True,
        "categories": [
            {"name": "Fruits & Vegetables", "name_ar": "فواكه وخضروات"},
            {"name": "Dairy & Eggs", "name_ar": "ألبان وبيض"},
            {"name": "Meat & Poultry", "name_ar": "لحوم ودواجن"},
            {"name": "Beverages", "name_ar": "مشروبات"},
            {"name": "Snacks & Bakery", "name_ar": "سناكات ومخبوزات"},
            {"name": "Household", "name_ar": "منزلية"},
        ],
        "products": [
            # Fruits & Veg
            {"name": "Banana (1kg)", "name_ar": "موز 1 كيلو", "price": 9.0, "prep": 3, "cat": 0},
            {"name": "Apple Red (1kg)", "name_ar": "تفاح أحمر 1 كيلو", "price": 14.0, "prep": 3, "cat": 0},
            {"name": "Tomato (1kg)", "name_ar": "طماطم 1 كيلو", "price": 6.0, "prep": 3, "cat": 0},
            {"name": "Cucumber (1kg)", "name_ar": "خيار 1 كيلو", "price": 5.0, "prep": 3, "cat": 0},
            {"name": "Potato (2kg)", "name_ar": "بطاطس 2 كيلو", "price": 8.0, "prep": 3, "cat": 0},
            {"name": "Onion (1kg)", "name_ar": "بصل 1 كيلو", "price": 4.0, "prep": 3, "cat": 0},
            {"name": "Avocado (3 pcs)", "name_ar": "أفوكادو 3 حبات", "price": 18.0, "prep": 3, "cat": 0},
            {"name": "Strawberry (500g)", "name_ar": "فراولة 500 جرام", "price": 20.0, "prep": 3, "cat": 0},
            # Dairy
            {"name": "Full Cream Milk 1L", "name_ar": "حليب كامل الدسم 1 لتر", "price": 7.0, "prep": 2, "cat": 1},
            {"name": "Low Fat Milk 1L", "name_ar": "حليب قليل الدسم 1 لتر", "price": 7.0, "prep": 2, "cat": 1},
            {"name": "Eggs (12 pcs)", "name_ar": "بيض 12 حبة", "price": 12.0, "prep": 2, "cat": 1},
            {"name": "Labneh 400g", "name_ar": "لبنة 400 جرام", "price": 10.0, "prep": 2, "cat": 1},
            {"name": "Butter 200g", "name_ar": "زبدة 200 جرام", "price": 12.0, "prep": 2, "cat": 1},
            {"name": "Yogurt 400g", "name_ar": "زبادي 400 جرام", "price": 8.0, "prep": 2, "cat": 1},
            {"name": "Cheddar Cheese 400g", "name_ar": "جبنة شيدر 400 جرام", "price": 22.0, "prep": 2, "cat": 1},
            # Meat
            {"name": "Chicken Breast (1kg)", "name_ar": "صدر دجاج 1 كيلو", "price": 28.0, "prep": 5, "cat": 2},
            {"name": "Ground Beef (500g)", "name_ar": "لحم مفروم 500 جرام", "price": 25.0, "prep": 5, "cat": 2},
            {"name": "Lamb Chops (500g)", "name_ar": "ضلوع خروف 500 جرام", "price": 45.0, "prep": 5, "cat": 2},
            # Beverages
            {"name": "Pepsi 6-Pack 330ml", "name_ar": "بيبسي 6 علب 330 مل", "price": 18.0, "prep": 2, "cat": 3},
            {"name": "Water 6x1.5L", "name_ar": "مياه 6 زجاجات 1.5 لتر", "price": 15.0, "prep": 2, "cat": 3},
            {"name": "Orange Juice 1L", "name_ar": "عصير برتقال 1 لتر", "price": 12.0, "prep": 2, "cat": 3},
            {"name": "Red Bull 250ml", "name_ar": "ريد بول 250 مل", "price": 8.0, "prep": 2, "cat": 3},
            # Snacks
            {"name": "Pringles Original", "name_ar": "برينجلز أوريجينال", "price": 12.0, "prep": 2, "cat": 4},
            {"name": "Lay's Chips 150g", "name_ar": "ليز شيبس 150 جرام", "price": 8.0, "prep": 2, "cat": 4},
            {"name": "Bread Loaf White", "name_ar": "خبز توست أبيض", "price": 5.0, "prep": 3, "cat": 4},
            {"name": "Croissant (4 pcs)", "name_ar": "كرواسان 4 حبات", "price": 14.0, "prep": 3, "cat": 4},
            {"name": "Chocolate Bar Kit-Kat", "name_ar": "شوكولاتة كيت كات", "price": 6.0, "prep": 2, "cat": 4},
            # Household
            {"name": "Fairy Dish Soap 750ml", "name_ar": "فيري سائل غسيل أطباق 750 مل", "price": 12.0, "prep": 2, "cat": 5},
            {"name": "Ariel Detergent 2kg", "name_ar": "أريال مسحوق غسيل 2 كيلو", "price": 28.0, "prep": 2, "cat": 5},
            {"name": "Tissue Box 4-Pack", "name_ar": "مناديل 4 علب", "price": 14.0, "prep": 2, "cat": 5},
        ],
    },
    {
        "name": "Panda Supermarket", "name_ar": "بنده",
        "category": "grocery",
        "description": "Saudi supermarket chain",
        "description_ar": "سلسلة بنده السعودية للبقالة",
        "latitude": 24.7300, "longitude": 46.6800, "city": "Riyadh",
        "delivery_fee": 8.0, "min_order_amount": 35.0, "free_delivery_above": 150.0,
        "avg_preparation_time": 30, "rating": 4.2, "total_orders": 11000, "is_open_now": True,
        "categories": [
            {"name": "Fresh Produce", "name_ar": "منتجات طازجة"},
            {"name": "Dairy & Refrigerated", "name_ar": "ألبان ومبردات"},
            {"name": "Bakery", "name_ar": "مخبوزات"},
            {"name": "Cleaning & Household", "name_ar": "تنظيف ومنزلية"},
            {"name": "Canned & Dry Goods", "name_ar": "معلبات وبقالة جافة"},
        ],
        "products": [
            {"name": "Mango (2 pcs)", "name_ar": "مانجو 2 حبات", "price": 12.0, "prep": 3, "cat": 0},
            {"name": "Watermelon (whole)", "name_ar": "بطيخ كامل", "price": 15.0, "prep": 3, "cat": 0},
            {"name": "Grapes (500g)", "name_ar": "عنب 500 جرام", "price": 16.0, "prep": 3, "cat": 0},
            {"name": "Carrot (1kg)", "name_ar": "جزر 1 كيلو", "price": 5.0, "prep": 3, "cat": 0},
            {"name": "Full Cream Milk 2L", "name_ar": "حليب كامل الدسم 2 لتر", "price": 12.0, "prep": 2, "cat": 1},
            {"name": "Almarai Fresh Juice 1L", "name_ar": "عصير المراعي 1 لتر", "price": 10.0, "prep": 2, "cat": 1},
            {"name": "Cream Cheese 200g", "name_ar": "جبن كريمي 200 جرام", "price": 18.0, "prep": 2, "cat": 1},
            {"name": "Whole Wheat Bread", "name_ar": "خبز أسمر كامل", "price": 6.0, "prep": 3, "cat": 2},
            {"name": "French Baguette", "name_ar": "خبز باجيت فرنسي", "price": 8.0, "prep": 3, "cat": 2},
            {"name": "Dettol Soap 3-Pack", "name_ar": "صابون ديتول 3 قطع", "price": 15.0, "prep": 2, "cat": 3},
            {"name": "Pril Dish Soap 1L", "name_ar": "بريل سائل جلي 1 لتر", "price": 10.0, "prep": 2, "cat": 3},
            {"name": "Tuna Can (3-Pack)", "name_ar": "تونة معلبة 3 علب", "price": 18.0, "prep": 2, "cat": 4},
            {"name": "Chickpeas 400g", "name_ar": "حمص 400 جرام", "price": 6.0, "prep": 2, "cat": 4},
            {"name": "Olive Oil 500ml", "name_ar": "زيت زيتون 500 مل", "price": 28.0, "prep": 2, "cat": 4},
            {"name": "Rice Basmati 2kg", "name_ar": "أرز بسمتي 2 كيلو", "price": 18.0, "prep": 2, "cat": 4},
        ],
    },
    {
        "name": "Tamimi Markets", "name_ar": "أسواق تميمي",
        "category": "grocery",
        "description": "Premium grocery store",
        "description_ar": "أسواق تميمي المتميزة",
        "latitude": 24.7050, "longitude": 46.6680, "city": "Riyadh",
        "delivery_fee": 10.0, "min_order_amount": 50.0, "free_delivery_above": 200.0,
        "avg_preparation_time": 30, "rating": 4.5, "total_orders": 5200, "is_open_now": True,
        "categories": [
            {"name": "Fruits & Vegetables", "name_ar": "فواكه وخضروات"},
            {"name": "Dairy", "name_ar": "منتجات الألبان"},
            {"name": "Meat & Seafood", "name_ar": "لحوم وأسماك"},
            {"name": "Bakery", "name_ar": "مخبوزات"},
            {"name": "International Foods", "name_ar": "أطعمة عالمية"},
        ],
        "products": [
            {"name": "Apple (1kg)", "name_ar": "تفاح 1 كيلو", "price": 14.0, "prep": 5, "cat": 0},
            {"name": "Pomegranate (3 pcs)", "name_ar": "رمان 3 حبات", "price": 18.0, "prep": 5, "cat": 0},
            {"name": "Mixed Lettuce 300g", "name_ar": "خس مشكل 300 جرام", "price": 12.0, "prep": 5, "cat": 0},
            {"name": "Premium Milk 1L", "name_ar": "حليب ممتاز 1 لتر", "price": 9.0, "prep": 2, "cat": 1},
            {"name": "Greek Yogurt 200g", "name_ar": "زبادي يوناني 200 جرام", "price": 12.0, "prep": 2, "cat": 1},
            {"name": "Parmesan Cheese 150g", "name_ar": "جبن بارميزان 150 جرام", "price": 28.0, "prep": 2, "cat": 1},
            {"name": "Salmon Fillet (500g)", "name_ar": "فيليه سلمون 500 جرام", "price": 65.0, "prep": 5, "cat": 2},
            {"name": "Beef Tenderloin (500g)", "name_ar": "لحم بقري 500 جرام", "price": 70.0, "prep": 5, "cat": 2},
            {"name": "Sourdough Bread", "name_ar": "خبز ساوردو", "price": 16.0, "prep": 5, "cat": 3},
            {"name": "Croissant Fresh", "name_ar": "كرواسان طازج", "price": 8.0, "prep": 3, "cat": 3},
            {"name": "Pasta Barilla 500g", "name_ar": "مكرونة باريلا 500 جرام", "price": 12.0, "prep": 2, "cat": 4},
            {"name": "Tomato Sauce 500ml", "name_ar": "صلصة طماطم 500 مل", "price": 10.0, "prep": 2, "cat": 4},
        ],
    },

    # ─── PHARMACY ────────────────────────────────────────────────
    {
        "name": "Al-Dawaa Pharmacy", "name_ar": "صيدلية الدواء",
        "category": "pharmacy",
        "description": "Leading pharmacy chain in Saudi Arabia",
        "description_ar": "سلسلة صيدليات الدواء الرائدة في السعودية",
        "latitude": 24.7300, "longitude": 46.6600, "city": "Riyadh",
        "delivery_fee": 8.0, "min_order_amount": 30.0, "free_delivery_above": 150.0,
        "avg_preparation_time": 15, "rating": 4.6, "total_orders": 3100, "is_open_now": True,
        "categories": [
            {"name": "Medicines", "name_ar": "أدوية"},
            {"name": "Vitamins & Supplements", "name_ar": "فيتامينات ومكملات"},
            {"name": "Personal Care", "name_ar": "عناية شخصية"},
            {"name": "Baby Care", "name_ar": "عناية بالأطفال"},
        ],
        "products": [
            {"name": "Panadol Extra 24 tabs", "name_ar": "بنادول إكسترا 24 قرص", "price": 15.0, "prep": 3, "cat": 0},
            {"name": "Brufen 400mg 20 tabs", "name_ar": "بروفين 400 مجم 20 قرص", "price": 18.0, "prep": 3, "cat": 0},
            {"name": "Antinal 12 caps", "name_ar": "أنتينال 12 كبسولة", "price": 22.0, "prep": 3, "cat": 0},
            {"name": "Flagyl 250mg", "name_ar": "فلاجيل 250 مجم", "price": 12.0, "prep": 3, "cat": 0},
            {"name": "Vitamin C 1000mg 30 tabs", "name_ar": "فيتامين سي 1000 مجم 30 قرص", "price": 28.0, "prep": 3, "cat": 1},
            {"name": "Vitamin D3 5000IU", "name_ar": "فيتامين د3 5000 وحدة", "price": 35.0, "prep": 3, "cat": 1},
            {"name": "Omega-3 Fish Oil 60 caps", "name_ar": "أوميجا 3 زيت سمك 60 كبسولة", "price": 45.0, "prep": 3, "cat": 1},
            {"name": "Zinc 50mg 100 tabs", "name_ar": "زنك 50 مجم 100 قرص", "price": 25.0, "prep": 3, "cat": 1},
            {"name": "Hand Sanitizer 500ml", "name_ar": "معقم يدين 500 مل", "price": 18.0, "prep": 2, "cat": 2},
            {"name": "Vaseline Moisturizer 400ml", "name_ar": "فازلين مرطب 400 مل", "price": 22.0, "prep": 2, "cat": 2},
            {"name": "Sunblock SPF50 150ml", "name_ar": "واقي شمسي SPF50 150 مل", "price": 38.0, "prep": 2, "cat": 2},
            {"name": "Baby Diapers Pampers L 32", "name_ar": "حفاضات بمبرز L 32 حبة", "price": 55.0, "prep": 3, "cat": 3},
            {"name": "Baby Wipes 80 pcs", "name_ar": "مناديل أطفال مبللة 80 قطعة", "price": 18.0, "prep": 2, "cat": 3},
            {"name": "Baby Shampoo 400ml", "name_ar": "شامبو أطفال 400 مل", "price": 22.0, "prep": 2, "cat": 3},
        ],
    },
    {
        "name": "Al-Nahdi Medical", "name_ar": "النهدي الطبية",
        "category": "pharmacy",
        "description": "Healthcare and wellness pharmacy",
        "description_ar": "صيدليات النهدي للرعاية الصحية",
        "latitude": 24.7160, "longitude": 46.6580, "city": "Riyadh",
        "delivery_fee": 7.0, "min_order_amount": 25.0, "free_delivery_above": 120.0,
        "avg_preparation_time": 12, "rating": 4.5, "total_orders": 4200, "is_open_now": True,
        "categories": [
            {"name": "OTC Medicines", "name_ar": "أدوية بدون وصفة"},
            {"name": "Supplements", "name_ar": "المكملات الغذائية"},
            {"name": "Skincare", "name_ar": "العناية بالبشرة"},
        ],
        "products": [
            {"name": "Panadol Cold & Flu", "name_ar": "بنادول للبرد والإنفلونزا", "price": 22.0, "prep": 3, "cat": 0},
            {"name": "Strepsils 24 lozenges", "name_ar": "ستربسيلز 24 قرص", "price": 20.0, "prep": 3, "cat": 0},
            {"name": "Voltaren Gel 50g", "name_ar": "فولتارين جل 50 جرام", "price": 28.0, "prep": 3, "cat": 0},
            {"name": "Centrum Multivitamin 30 tabs", "name_ar": "سنتروم متعدد الفيتامينات 30 قرص", "price": 45.0, "prep": 3, "cat": 1},
            {"name": "Protein Shake Vanilla 1kg", "name_ar": "بروتين شيك فانيليا 1 كيلو", "price": 120.0, "prep": 3, "cat": 1},
            {"name": "Nivea Body Lotion 400ml", "name_ar": "نيفيا لوشن جسم 400 مل", "price": 28.0, "prep": 2, "cat": 2},
            {"name": "Garnier Face Wash 150ml", "name_ar": "جارنييه غسول وجه 150 مل", "price": 25.0, "prep": 2, "cat": 2},
        ],
    },
]


async def seed():
    async with AsyncSessionLocal() as db:
        print("Truncating old data...")
        tables = [
            "voice_sessions", "payments", "deliveries", "order_items", "orders",
            "products", "categories", "drivers", "merchants",
            "users",
        ]
        for t in tables:
            try:
                await db.execute(text(f'TRUNCATE TABLE "{t}" RESTART IDENTITY CASCADE'))
            except Exception:
                await db.rollback()
                break
        await db.commit()
        print("Seeding VOXAORA database...")

        async with AsyncSessionLocal() as db:
            admin_user = User(
                phone="+966500000001", email="admin@voxaora.com",
                full_name="VOXAORA Admin",
                hashed_password=hash_password("Admin@12345"),
                role=UserRole.ADMIN, status=UserStatus.ACTIVE,
                preferred_language="ar", is_phone_verified=True,
            )
            db.add(admin_user)

            test_customer = User(
                phone="+966500000002", email="customer@test.com",
                full_name="أحمد محمد العتيبي",
                hashed_password=hash_password("Test@12345"),
                role=UserRole.CUSTOMER, status=UserStatus.ACTIVE,
                preferred_language="ar", is_phone_verified=True,
            )
            db.add(test_customer)
            await db.flush()

            for i, m_data in enumerate(MERCHANTS_DATA):
                owner = User(
                    phone=f"+9665001{i:04d}",
                    email=f"merchant{i}@voxaora.com",
                    full_name=m_data["name_ar"],
                    hashed_password=hash_password("Merchant@12345"),
                    role=UserRole.MERCHANT, status=UserStatus.ACTIVE,
                    preferred_language="ar",
                )
                db.add(owner)
                await db.flush()

                merchant = Merchant(
                    owner_id=owner.id,
                    name=m_data["name"], name_ar=m_data["name_ar"],
                    description=m_data.get("description"),
                    description_ar=m_data.get("description_ar"),
                    category=m_data["category"],
                    latitude=m_data["latitude"], longitude=m_data["longitude"],
                    full_address=f"{m_data['name_ar']}، الرياض، المملكة العربية السعودية",
                    city=m_data["city"],
                    status=MerchantStatus.ACTIVE,
                    delivery_fee=m_data["delivery_fee"],
                    min_order_amount=m_data["min_order_amount"],
                    free_delivery_above=m_data.get("free_delivery_above"),
                    avg_preparation_time=m_data["avg_preparation_time"],
                    rating=m_data["rating"],
                    total_orders=m_data["total_orders"],
                    is_open_now=m_data["is_open_now"],
                    commission_rate=15.0,
                    phone=f"+9665002{i:04d}",
                )
                db.add(merchant)
                await db.flush()

                created_cats = []
                for j, cat_data in enumerate(m_data.get("categories", [])):
                    cat = Category(
                        merchant_id=merchant.id,
                        name=cat_data["name"], name_ar=cat_data.get("name_ar"),
                        sort_order=j, is_active=True,
                    )
                    db.add(cat)
                    created_cats.append(cat)
                await db.flush()

                for k, prod_data in enumerate(m_data.get("products", [])):
                    cat_index = prod_data.get("cat", 0)
                    cat_id = created_cats[cat_index].id if cat_index < len(created_cats) else None
                    product = Product(
                        merchant_id=merchant.id, category_id=cat_id,
                        name=prod_data["name"], name_ar=prod_data.get("name_ar"),
                        price=prod_data["price"],
                        status=ProductStatus.AVAILABLE,
                        preparation_time=prod_data.get("prep", 15),
                        sort_order=k,
                        rating=round(4.0 + (k % 5) * 0.15, 1),
                        total_orders=max(50, int(m_data["total_orders"] / max(len(m_data["products"]), 1))),
                    )
                    db.add(product)

                print(f"  OK: {m_data['name']} ({m_data['category']}) - {len(m_data['products'])} products")

            driver_user = User(
                phone="+966500000010", email="driver@test.com",
                full_name="محمد خالد السائق",
                hashed_password=hash_password("Driver@12345"),
                role=UserRole.DRIVER, status=UserStatus.ACTIVE, preferred_language="ar",
            )
            db.add(driver_user)
            await db.flush()

            driver = Driver(
                user_id=driver_user.id, vehicle_type="motorcycle",
                vehicle_plate="ABC 1234", status=DriverStatus.ONLINE,
                current_latitude=24.7136, current_longitude=46.6753,
                city="Riyadh", is_verified=True, rating=4.7,
            )
            db.add(driver)
            await db.commit()

        print("\nSeed complete!")
        print(f"   {len(MERCHANTS_DATA)} merchants seeded")
        print("   Admin:    +966500000001 / Admin@12345")
        print("   Customer: +966500000002 / Test@12345")


if __name__ == "__main__":
    asyncio.run(seed())
