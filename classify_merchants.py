"""
Auto-classify all merchants by name keywords.
Run: python classify_merchants.py
"""
import asyncio
import re
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://voxaora:voxaora_pass@postgres:5432/voxaora_db"
)

# ── Classification rules (first match wins, order matters) ────────────────────
# Each entry: (category_value, [keywords_in_name_ar_or_name])
RULES = [
    ("coffee",   ["مقهى","قهوة","كافيه","كافيتيريا","كوفي","قشر","صاحي","coffee","cafe","caphe","قهوي","نسكافيه"]),
    ("bakery",   ["مخبز","فرن","خباز","بيكري","معجنات","كيك","تورت","حلويات","حلوى","لقيمات","دونات","دونتس","بقلاوة","كنافة","كنافه","وفل","وافل","bakery","pastry"]),
    ("mandi",    ["مندي","كبسة","مضبي","زرب","حضرمي","فريدة","رز يمني","أرز يمني","مطبخ يمني","مطبخ صنعاني","مطعم صنعاء","مطعم عدن","مطعم تعز","مطعم حضرموت","مطعم اليمن","اليمني الأصيل","الأصيل","الحضرمي","برياني"]),
    ("fastfood", ["برجر","بيتزا","شاورما","شاورمة","دجاج","فروج","كنتاكي","ماكدونالدز","ساندوتش","سندوتش","ويفر","كريسبي","تشيكن","فلافل","كبده","بيف","ستيك","تاكو","هوت دوج","hotdog","burger","pizza","chicken","wings","بروست","وجبة سريعة","وجبات سريعة"]),
    ("meat",     ["ملحمة","لحمية","لحام","سمك","أسماك","مسقط","ذبح","طازج","مطعم السمك","بحري","جمبري","ربيان","نيل","سيفود","seafood"]),
    ("breakfast",["فطور","ريوق","إفطار","صاحي","فول","لحوح","فطيرة","فطائر","بيض","عسل","مناحل","ريوق","صبحية","صباحية","بسطة فطور"]),
    ("drinks",   ["عصير","عصائر","مشروب","مشروبات","جوس","خلاط","عروس","طازجة","سموذي","smoothie","juice","ليمون","قصب","رمان"]),
    ("healthy",  ["صحي","دايت","رجيم","سلطة","diet","healthy","عضوي","organic","طبيعي","نظام غذائي","بروتين","سلطات"]),
    ("grocery",  ["سوبرماركت","سوبر ماركت","بقالة","دكان","متجر عام","محل","مواد غذائية","تموين","جملة","wholesale"]),
    ("pharmacy", ["صيدلية","صيدل","دواء","أدوية","pharmacy"]),
    ("popular",  ["مأكولات شعبية","شعبي","تقليدي","بلدي","أصيل","مرق","سلتة","عصيد","فتة","هريسة","وليمة","مجلس"]),
]
DEFAULT_CATEGORY = "restaurant"

def classify(name_ar: str | None, name: str | None) -> str:
    combined = ((name_ar or "") + " " + (name or "")).lower()
    for category, keywords in RULES:
        if any(kw.lower() in combined for kw in keywords):
            return category
    return DEFAULT_CATEGORY


async def main():
    engine = create_async_engine(DB_URL, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        from app.models.merchant import Merchant
        result = await session.execute(select(Merchant))
        merchants = result.scalars().all()

        counts: dict[str, int] = {}
        updates = []
        for m in merchants:
            new_cat = classify(m.name_ar, m.name)
            counts[new_cat] = counts.get(new_cat, 0) + 1
            updates.append({"id": m.id, "category": new_cat})

        for u in updates:
            await session.execute(
                update(Merchant).where(Merchant.id == u["id"]).values(category=u["category"])
            )

        await session.commit()

    print(f"✅ Classified {len(updates)} merchants:")
    for cat, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"   {cat:15s} → {n}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
