"""
Telefon raqamlarni yagona formatga (+998901234567) keltirish.

Nima uchun kerak: raqamlar turli ko'rinishda saqlangan bo'lsa
(`901234567`, `+998 90 123 45 67`, `998901234567`), qarzdor Mini App'da
o'z qarzini ko'rmaydi — chunki qidiruv aynan mos kelishni talab qiladi.

Ishlatish (backend/ papkasidan):

    # 1) Avval nima o'zgarishini ko'rish (hech narsa yozilmaydi)
    python scripts/migrate_phones.py

    # 2) Haqiqiy o'zgartirish
    python scripts/migrate_phones.py --apply

Railway'da:  Settings → Deploy → "Run command" yoki `railway run python scripts/migrate_phones.py --apply`
"""
import argparse
import asyncio
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Windows konsoli sukut bo'yicha cp1251 — o'zbekcha belgilar va emoji buzilmasin
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

from app.database import init_db, close_db          # noqa: E402
from app.models import User, Client, utcnow         # noqa: E402
from app.utils.helpers import normalize_phone, is_valid_phone   # noqa: E402


async def migrate_users(apply: bool) -> tuple[int, list[str]]:
    changed = 0
    warnings: list[str] = []
    seen: dict[str, str] = {}       # normalizatsiyadan keyingi raqam → egasi

    async for user in User.find_all():
        new_phone = normalize_phone(user.phone) if user.phone else ""
        new_extra = []
        for p in user.extra_phones:
            n = normalize_phone(p)
            if n and n not in new_extra and n != new_phone:
                new_extra.append(n)

        if user.phone and not is_valid_phone(new_phone):
            warnings.append(f"  ! Noto'g'ri raqam: {user.full_name} — «{user.phone}» → «{new_phone}»")

        for p in [new_phone, *new_extra]:
            if not p:
                continue
            if p in seen and seen[p] != str(user.id):
                warnings.append(f"  ! Takrorlanuvchi raqam {p}: {user.full_name} va boshqa akkaunt")
            seen[p] = str(user.id)

        if new_phone != user.phone or new_extra != user.extra_phones:
            changed += 1
            print(f"  User «{user.full_name}»: {user.phone!r} → {new_phone!r}"
                  + (f", extra {user.extra_phones} → {new_extra}" if new_extra != user.extra_phones else ""))
            if apply:
                user.phone = new_phone
                user.extra_phones = new_extra
                user.updated_at = utcnow()
                await user.save()

    return changed, warnings


async def migrate_clients(apply: bool) -> tuple[int, list[str]]:
    changed = 0
    warnings: list[str] = []
    # Bitta do'konda bir xil raqam ikki marta uchrashi mumkin — ogohlantiramiz
    per_shop: dict[tuple, list[str]] = defaultdict(list)

    async for client in Client.find_all():
        new_phone = normalize_phone(client.phone) if client.phone else ""

        if client.status == "active":
            per_shop[(str(client.shop_id), new_phone)].append(client.full_name)

        if client.phone and not is_valid_phone(new_phone):
            warnings.append(f"  ! Noto'g'ri raqam: mijoz {client.full_name} — «{client.phone}» → «{new_phone}»")

        if new_phone != client.phone:
            changed += 1
            print(f"  Client «{client.full_name}»: {client.phone!r} → {new_phone!r}")
            if apply:
                client.phone = new_phone
                client.updated_at = utcnow()
                await client.save()

    for (shop_id, phone), names in per_shop.items():
        if len(names) > 1:
            warnings.append(
                f"  ! Do'kon {shop_id} da {phone} raqami {len(names)} marta: {', '.join(names)}"
                " — unikal indeks yaratilmaydi, dublikatni qo'lda birlashtiring"
            )

    return changed, warnings


async def main(apply: bool):
    await init_db()
    try:
        print("=" * 70)
        print("TELEFON RAQAMLARNI STANDARTLASHTIRISH" + ("" if apply else "  [SINOV — hech narsa yozilmaydi]"))
        print("=" * 70)

        print("\n[1/2] Foydalanuvchilar…")
        u_changed, u_warn = await migrate_users(apply)

        print("\n[2/2] Mijozlar…")
        c_changed, c_warn = await migrate_clients(apply)

        print("\n" + "-" * 70)
        print(f"O'zgartirilishi kerak: {u_changed} foydalanuvchi, {c_changed} mijoz")

        warnings = u_warn + c_warn
        if warnings:
            print(f"\nOgohlantirishlar ({len(warnings)}):")
            for w in warnings:
                print(w)

        if apply:
            print("\n✅ O'zgarishlar bazaga yozildi.")
        else:
            print("\nℹ️  Hech narsa o'zgartirilmadi. Qo'llash uchun: --apply")
        print("-" * 70)
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Telefon raqamlarni normallashtirish")
    parser.add_argument("--apply", action="store_true", help="O'zgarishlarni bazaga yozish")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
