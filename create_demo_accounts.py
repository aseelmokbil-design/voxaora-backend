"""
Creates 3 demo accounts if they don't exist:
  Admin:    +966500000001 / Admin@12345
  Driver:   +966500000002 / Driver@12345
  Customer: +966500000003 / Customer@12345
"""
import asyncio, os, uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from app.core.config import settings
from app.core.security import hash_password
from app.models.user import User, UserRole, UserStatus
from app.models.driver import Driver, DriverStatus

engine = create_async_engine(settings.DATABASE_URL, echo=False)
Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

ACCOUNTS = [
    {
        "phone": "+966500000001",
        "full_name": "مدير النظام",
        "password": "Admin@12345",
        "role": UserRole.SUPER_ADMIN,
        "driver": False,
    },
    {
        "phone": "+966500000002",
        "full_name": "سائق تجريبي",
        "password": "Driver@12345",
        "role": UserRole.DRIVER,
        "driver": True,
    },
    {
        "phone": "+966500000003",
        "full_name": "عميل تجريبي",
        "password": "Customer@12345",
        "role": UserRole.CUSTOMER,
        "driver": False,
    },
]


async def main():
    async with Session() as db:
        for acc in ACCOUNTS:
            res = await db.execute(select(User).where(User.phone == acc["phone"]))
            if res.scalar_one_or_none():
                print(f"  exists: {acc['phone']}")
                continue

            user = User(
                id=uuid.uuid4(),
                phone=acc["phone"],
                full_name=acc["full_name"],
                hashed_password=hash_password(acc["password"]),
                role=acc["role"],
                status=UserStatus.ACTIVE,
                preferred_language="ar",
            )
            db.add(user)
            await db.flush()

            if acc["driver"]:
                drv = Driver(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    vehicle_type="motorcycle",
                    status=DriverStatus.OFFLINE,
                    city="صنعاء",
                    is_verified=True,
                )
                db.add(drv)

            print(f"  created: {acc['phone']} ({acc['role']})")

        await db.commit()
    print("Demo accounts ready.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
