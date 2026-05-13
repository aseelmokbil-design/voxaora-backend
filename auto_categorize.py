"""Auto-categorize merchants based on Arabic name keywords."""
import psycopg2

conn = psycopg2.connect(
    host="localhost", port=5432,
    dbname="voxaora_db", user="voxaora", password="voxaora_pass"
)
cur = conn.cursor()

# Fetch all merchants
cur.execute("SELECT id, name_ar, name FROM merchants WHERE status='active'")
merchants = cur.fetchall()

RULES = [
    # (category, keywords_in_name)
    ("coffee",      ["قهوة", "كافيه", "cafe", "coffee", "عصائر", "عصير", "مشروبات", "جوسرية", "smoothie", "juice", "بارد", "ماتشا", "شاي"]),
    ("bakery",      ["مخبوزات", "مخبز", "خبز", "كرواسون", "فطائر", "معجنات", "بيكري", "bakery", "حلويات", "كيك", "جاتوه", "تورتة", "كنافة", "عجين", "بسبوسة", "زلابيا", "حلوى", "جاناش", "ganache", "pastry", "sweets"]),
    ("grocery",     ["خضروات", "بقالة", "سوبرماركت", "سوبر ماركت", "grocery", "supermarket", "تموينات", "عسل", "طبيعي", "مواد غذائية", "فواكه"]),
    ("fastfood",    ["بروست", "برجر", "شاورما", "فلافل", "وجبة", "ساندوتش", "سندوتش", "ساندويش", "زنجر", "كنتاكي", "ماكدونالد", "بيتزا", "pizza", "burger", "broast", "shawarma", "fast", "كرسبي"]),
    ("seafood",     ["سمك", "أسماك", "اسماك", "مأكولات بحرية", "جمبري", "ربيان", "fish", "seafood", "تونة", "هامور"]),
    ("mandi",       ["مندي", "مضبي", "كبسة", "مجبوس", "فريدة", "حنيذ", "هريس", "عصيد", "فحسة", "سلتة", "فحم", "شواية", "كباب", "مشاوي", "مشوي"]),
    ("restaurant",  ["مطعم", "restaurant", "مطاعم"]),
]

def categorize(name_ar: str, name: str) -> str:
    text = (name_ar or "").lower() + " " + (name or "").lower()
    for category, keywords in RULES:
        if any(kw.lower() in text for kw in keywords):
            return category
    return "restaurant"

updates = {}
for mid, name_ar, name in merchants:
    cat = categorize(name_ar or "", name or "")
    updates.setdefault(cat, []).append(str(mid))

print("Category distribution:")
for cat, ids in sorted(updates.items(), key=lambda x: -len(x[1])):
    print(f"  {cat:15} -> {len(ids)} merchants")

# Apply updates
total = 0
for cat, ids in updates.items():
    cur.execute(
        f"UPDATE merchants SET category = %s WHERE id = ANY(%s::uuid[])",
        (cat, ids)
    )
    total += cur.rowcount

conn.commit()
print(f"\nUpdated {total} merchants successfully.")
cur.close()
conn.close()
