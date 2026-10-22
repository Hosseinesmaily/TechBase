"""Seed realistic wiki content.

~15 pages of genuine Persian technical writing about the seeded catalog: what
the parts are, why they matter, and how they fit together. The content is
written to be *linked* — each page mentions other entities by name so the
auto-linker has something to work with.

Idempotent: pages are matched by slug and updated in place.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, cast

from django.core.management.base import BaseCommand
from django.db import transaction
from wagtail.models import Page

from apps.catalog.models import Entity, Product
from apps.linking.services import link_page

from ...models import WikiPage

# The wiki lives under a dedicated section page.
WIKI_ROOT_SLUG = "wiki"

#: (slug, title, summary, entity_slug, review_days, body)
PAGES: list[dict] = [
    {
        "slug": "ryzen-7-7800x3d",
        "title": "ای‌ام‌دی رایزن ۷ ۷۸۰۰X3D",
        "summary": "پردازندهٔ هشت هسته‌ای با فناوری 3D V-Cache که در بازی‌ها بالاترین فریم‌ریت را ارائه می‌دهد.",
        "entity": "ryzen-7-7800x3d",
        "type": "component",
        "review_days": 60,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "رایزن ۷ ۷۸۰۰X3D پرچمدار گیمینگ ای‌ام‌دی است. ترکیب هشت هستهٔ Zen 4 با ۹۶ مگابایت کش L3 سه‌بعدی باعث می‌شود بازی‌ها تا ۲۰٪ فریم‌ریت بیشتری نسبت به پردازنده‌های هم‌رده بگیرند.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("سوکت", "AM5"),
                    ("هسته / رشته", "۸ / ۱۶"),
                    ("توان مصرفی", "۱۲۰ وات"),
                    ("کش L3", "۹۶ مگابایت"),
                    ("حداکثر حافظه", "DDR5-5200"),
                ],
            ),
            ("heading", "h3", "سازگاری"),
            (
                "paragraph",
                "برای استفاده از این پردازنده به یک مادربرد با سوکت AM5 مانند ASUS TUF Gaming B650-PLUS نیاز دارید. حافظهٔ DDR5 نیز باید با مادربرد سازگار باشد. اگر بودجهٔ محدودی دارید، Ryzen 5 7600 گزینهٔ ارزان‌تری است.",
            ),
            (
                "callout",
                "warning",
                "نکتهٔ مهم",
                "پیش از خرید، از سازگاری پردازنده با مادربرد خود مطمئن شوید — سوکت LGA1700 با AM5 یکسان نیست.",
            ),
            ("heading", "h2", "کارایی در بازی"),
            (
                "paragraph",
                "در بازی‌های رقابتی مانند کانتر استرایک ۲، این پردازنده می‌تواند تا ۳۱۰ فریم بر ثانیه در رزولوشن 1080p روی گرافیک‌های میان‌رده مانند RTX 4060 برساند.",
            ),
        ],
    },
    {
        "slug": "rtx-4060",
        "title": "انویدیا جی‌فورس RTX 4060",
        "summary": "کارت گرافیک میان‌رده با ۸ گیگابایت حافظه و پشتیبانی کامل از DLSS 3 و Ray Tracing.",
        "entity": "rtx-4060",
        "type": "component",
        "review_days": 60,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "RTX 4060 کارت گرافیک میان‌رده‌ای است که با ۸ گیگابایت حافظهٔ GDDR6، برای گیمینگ ۱۰۸۰p با فریم‌ریت بالا طراحی شده است. پشتیبانی از DLSS 3 و قابلیت‌های Ray Tracing آن را برای بازی‌های روز به‌روز مناسب می‌کند.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("حافظه", "۸ گیگابایت GDDR6"),
                    ("توان مصرفی", "۱۱۵ وات"),
                    ("طول کارت", "۲۴۵ میلی‌متر"),
                    ("کانکتور برق", "۸ پین"),
                    ("منبع تغذیهٔ پیشنهادی", "۵۵۰ وات"),
                ],
            ),
            ("heading", "h2", "سازگاری"),
            (
                "paragraph",
                "این کارت در اکثر کیس‌های استاندارد جا می‌شود، اما باید از نظر منبع تغذیه بررسی شود. در ترکیب با پردازنده‌ای مانند Ryzen 5 7600، منبع تغذیهٔ ۴۵۰ واتی کافی است. برای سیستم‌های پرقدرت‌تر مانند RTX 4080 SUPER به منبع ۸۵۰ واتی نیاز دارید.",
            ),
            ("heading", "h2", "کارایی در بازی"),
            (
                "paragraph",
                "در سایبرپانک ۲۰۷۷ با تنظیمات بالا در رزولوشن 1080p حدود ۷۸ فریم بر ثانیه و در 1440p حدود ۴۲ فریم بر ثانیه ثبت شده است.",
            ),
        ],
    },
    {
        "slug": "rtx-4070-super",
        "title": "انویدیا جی‌فورس RTX 4070 SUPER",
        "summary": "بهترین گزینه برای گیمینگ ۱۴۴۰p با فریم‌ریت بالا و پشتیبانی کامل از DLSS 3.",
        "entity": "rtx-4070-super",
        "type": "component",
        "review_days": 60,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "RTX 4070 SUPER تعادل خوبی میان قیمت و کارایی دارد. با ۱۲ گیگابایت حافظهٔ GDDR6X، در رزولوشن 1440p می‌تواند در بازی‌های روز فریم‌ریت بالای ۶۰ فریم بر ثانیه ارائه دهد.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("حافظه", "۱۲ گیگابایت GDDR6X"),
                    ("توان مصرفی", "۲۲۰ وات"),
                    ("طول کارت", "۲۶۷ میلی‌متر"),
                    ("کانکتور برق", "۸ پین"),
                    ("منبع تغذیهٔ پیشنهادی", "۶۵۰ وات"),
                ],
            ),
            ("heading", "h2", "سازگاری"),
            (
                "paragraph",
                "کارت‌هایی با این طول در اکثر کیس‌های ATX جا می‌شوند، ولی در کیس‌های کوچک مانند NZXT H5 Flow باید بررسی شود. منبع تغذیهٔ Corsair RM650x برای این کارت کافی است.",
            ),
            ("heading", "h2", "کارایی در بازی"),
            (
                "paragraph",
                "در سایبرپانک ۲۰۷۷ با تنظیمات بالا در رزولوشن 1440p حدود ۶۸ فریم بر ثانیه ثبت شده است. در 4K این عدد به ۳۳ فریم بر ثانیه می‌رسد.",
            ),
        ],
    },
    {
        "slug": "asus-tuf-gaming-b650-plus",
        "title": "ایسوس TUF Gaming B650-PLUS WiFi",
        "summary": "مادربرد ATX با سوکت AM5، چهار اسلات حافظه و سه خروجی M.2 — گزینهٔ اصلی برای پردازنده‌های رایزن.",
        "entity": "asus-tuf-gaming-b650-plus",
        "type": "component",
        "review_days": 45,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "TUF Gaming B650-PLUS یکی از محبوب‌ترین مادربردهای میان‌ردهٔ AM5 است. چهار اسلات حافظه و سه اسالت M.2 آن را برای ارتقاهای آینده مناسب می‌کند.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("سوکت", "AM5"),
                    ("نوع حافظه", "DDR5"),
                    ("اسلات حافظه", "۴"),
                    ("حداکثر حافظه", "۱۲۸ گیگابایت"),
                    ("اسلات M.2", "۳"),
                ],
            ),
            ("heading", "h2", "سازگاری"),
            (
                "paragraph",
                "این مادربرد از پردازنده‌های سری رایزن ۷۰۰۰ مانند Ryzen 7 7800X3D و Ryzen 5 7600 پشتیبانی می‌کند. حافظهٔ DDR5 با پروفایل EXPO مانند Corsair Vengeance RGB 32GB DDR5-6000 بهترین نتیجه را می‌دهد.",
            ),
            ("callout", "tip", "نکته", "برای پایداری حافظه، پروفایل EXPO را در BIOS فعال کنید."),
        ],
    },
    {
        "slug": "corsair-vengeance-rgb-32gb-ddr5-6000",
        "title": "کورسیر ونجنس RGB ۳۲ گیگابایت DDR5-6000",
        "summary": "دو ماژول ۱۶ گیگابایتی DDR5 با پروفایل EXPO — استاندارد پیشنهادی ما برای سیستم‌های گیمینگ.",
        "entity": "corsair-vengeance-rgb-32gb-ddr5-6000",
        "type": "component",
        "review_days": 45,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "Corsair Vengeance RGB با سرعت ۶۰۰۰ مگاهرتز و پروفایل EXPO، بهترین توازن بین قیمت و کارایی را برای پلتفرم AM5 فراهم می‌کند.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("ظرفیت", "۳۲ گیگابایت (۲×۱۶)"),
                    ("نوع", "DDR5"),
                    ("سرعت", "۶۰۰۰ مگاهرتز"),
                    ("تأخیر", "CL30"),
                    ("ولتاژ", "۱٫۳۵ ولت"),
                ],
            ),
            ("heading", "h2", "سازگاری"),
            (
                "paragraph",
                "این حافظه فقط با مادربردهای DDR5 کار می‌کند. مادربردهایی مانند ASUS TUF Gaming B650-PLUS یا MSI MAG B650 Tomahawk از آن پشتیبانی می‌کنند. برای پلتفرم LGA1700 باید سراغ DDR4 مانند Kingston FURY Beast بروید.",
            ),
        ],
    },
    {
        "slug": "corsair-rm650x",
        "title": "کورسیر RM650x ۶۵۰ وات",
        "summary": "منبع تغذیهٔ ۶۵۰ واتی با گواهی 80+ Gold، ماژولار کامل و گارانتی ۱۰ ساله.",
        "entity": "corsair-rm650x",
        "type": "component",
        "review_days": 90,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "RM650x یکی از مطمئن‌ترین منابع تغذیهٔ بازار است. طراحی کاملاً ماژولار، کیفیت ساخت بالا و گارانتی ۱۰ ساله، آن را برای سیستم‌های گیمینگ به انتخابی بی‌دردسر تبدیل کرده است.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("توان", "۶۵۰ وات"),
                    ("راندمان", "80+ Gold"),
                    ("ماژولار", "کامل"),
                    ("کانکتورها", "۲۴ پین، ۸ پین CPU، دو ۸ پین PCIe، ۱۲VHPWR"),
                ],
            ),
            ("heading", "h2", "چه توانی لازم است؟"),
            (
                "paragraph",
                "قانون سرانگشتی: توان مصرفی پردازنده و کارت گرافیک را جمع کنید و ۲۵٪ حاشیه اطمینان اضافه کنید. برای ترکیب Ryzen 7 7800X3D با RTX 4070 SUPER حدود ۴۶۰ وات لازم است، پس ۶۵۰ وات کافی است. برای RTX 4080 SUPER به ۸۵۰ وات نیاز دارید.",
            ),
            (
                "callout",
                "info",
                "چرا حاشیه اطمینان؟",
                "منبع تغذیه برای مدت طولانی نزدیک حداکثر توان کار نمی‌کند؛ این حاشیه عمر و پایداری را بیشتر می‌کند.",
            ),
        ],
    },
    {
        "slug": "nzxt-h5-flow",
        "title": "ان‌زد‌ایکس‌تی H5 Flow",
        "summary": "کیس micro-ATX جمع‌وجور با پنل شیشه‌ای و گردش هوای خوب — جایگاه کارت گرافیک تا ۳۶۵ میلی‌متر.",
        "entity": "nzxt-h5-flow",
        "type": "component",
        "review_days": 90,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "H5 Flow یک کیس micro-ATX خوش‌ساخت است که با وجود ابعاد کوچک، فضای داخلی قابل قبولی برای کارت‌های گرافیک بزرگ دارد.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("فرمت", "micro-ATX"),
                    ("حداکثر طول کارت گرافیک", "۳۶۵ میلی‌متر"),
                    ("حداکثر ارتفاع خنک‌کننده", "۱۶۵ میلی‌متر"),
                    ("اسلات M.2", "۴"),
                    ("فن همراه", "۲ عدد"),
                ],
            ),
            ("heading", "h2", "سازگاری"),
            (
                "paragraph",
                "با وجود فرمت micro-ATX، این کیس مادربردهای ATX را هم می‌پذیرد. حداکثر طول کارت ۳۶۵ میلی‌متر یعنی کارت‌هایی مانند RTX 4080 SUPER با طول ۳۰۴ میلی‌متر به‌راحتی جا می‌شوند. خنک‌کننده‌هایی مانند Cooler Master Hyper 212 با ارتفاع ۱۵۹ میلی‌متر نیز سازگارند.",
            ),
        ],
    },
    {
        "slug": "cooler-master-hyper-212",
        "title": "کولر ماستر هایپر ۲۱۲ بلک",
        "summary": "خنک‌کنندهٔ بادی تک‌فن پرفروش با پشتیبانی از پردازنده‌های ای‌ام‌دی و اینتل.",
        "entity": "cooler-master-hyper-212",
        "type": "component",
        "review_days": 90,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "هایپر ۲۱۲ سال‌ها یکی از محبوب‌ترین خنک‌کننده‌های بازار بوده است. قیمت مناسب، کیفیت ساخت خوب و پشتیبانی گسترده از سوکت‌ها، دلیل محبوبیت آن است.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("نوع", "بادی"),
                    ("ارتفاع", "۱۵۹ میلی‌متر"),
                    ("سوکت‌های پشتیبانی‌شده", "AM4، AM5، LGA1700، LGA1200"),
                    ("فن", "۱۲۰ میلی‌متری"),
                ],
            ),
            ("heading", "h2", "سازگاری"),
            (
                "paragraph",
                "این خنک‌کننده از Ryzen 7 7800X3D با سوکت AM5 و پردازنده‌های اینتل با سوکت LGA1700 پشتیبانی می‌کند. برای خنک‌کننده‌های آبی مانند NZXT Kraken Elite 360 RGB که ارتفاع ندارند، محدودیت ارتفاع کیس اعمال نمی‌شود.",
            ),
        ],
    },
    {
        "slug": "samsung-990-pro-2tb",
        "title": "سامسونگ ۹۹۰ پرو ۲ ترابایت",
        "summary": "اس‌اس‌د پرسرعت PCIe 4.0 با خواندن ۷۴۵۰ مگابایت بر ثانیه — بارگذاری بازی‌ها عملاً آنی است.",
        "entity": "samsung-990-pro-2tb",
        "type": "component",
        "review_days": 120,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "۹۹۰ پروFlagship سامسونگ در ردهٔ اس‌اس‌دهای سریع PCIe 4.0 قرار می‌گیرد و در بیشتر مادربردهای امروزی مانند ASUS TUF Gaming B650-PLUS جا می‌شود.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("ظرفیت", "۲ ترابایت"),
                    ("رابط", "PCIe 4.0 x4"),
                    ("سرعت خواندن", "۷۴۵۰ مگابایت بر ثانیه"),
                    ("فرمت", "M.2 2280"),
                ],
            ),
            ("heading", "h2", "چرا ظرفیت مهم است؟"),
            (
                "paragraph",
                "بازی‌های روز به‌روز گاهی بیش از ۱۰۰ گیگابایت فضا نیاز دارند. یک اس‌اس‌د ۲ ترابایتی مانند ۹۹۰ پرو جای همهٔ آن‌ها را می‌دهد و فضای کافی برای نصب چند بازی هم باقی می‌گذارد.",
            ),
        ],
    },
    {
        "slug": "ddr5",
        "title": "حافظهٔ DDR5 چیست؟",
        "summary": "نسل پنجم حافظهٔ DDR با سرعت بالاتر، ولتاژ پایین‌تر و چند کاناله — توضیح فنی و کاربردی.",
        "entity": None,
        "type": "concept",
        "review_days": 120,
        "body": [
            ("heading", "h2", "DDR5 چیست؟"),
            (
                "paragraph",
                "DDR5 نسل پنجم استاندارد حافظهٔ SDRAM است که در مقایسه با DDR4 حدود ۵۰٪ سرعت بیشتر، ولتاژ کاری پایین‌تر (۱٫۱ ولت در برابر ۱٫۲ ولت) و معماری چندکاناله دارد. هر کانال DDR5 ظرفیت بیشتری نسبت به DDR4 پوشش می‌دهد.",
            ),
            ("heading", "h2", "سازگاری با مادربرد"),
            (
                "paragraph",
                "حافظهٔ DDR5 فقط با مادربردهای DDR5 کار می‌کند. برای مثال ASUS TUF Gaming B650-PLUS از DDR5 پشتیبانی می‌کند، اما Gigabyte B760M DS3H نیز DDR5 است — در مقابل برای DDR4 باید مادربردی با پشتیبانی DDR4 انتخاب کنید. این ناسازگاری در موتور سازگاری محصول به‌صورت خودکار تشخیص داده می‌شود.",
            ),
            ("heading", "h2", "EXPO چیست؟"),
            (
                "paragraph",
                "پروفایل EXPO اورکلک روی مادربردهای رایزن، تنظیمات بهینهٔ حافظه را با یک کلیک فعال می‌کند. ماژول‌هایی مانند Corsair Vengeance RGB 32GB DDR5-6000 با پروفایل EXPO عرضه می‌شوند.",
            ),
            (
                "callout",
                "warning",
                "توجه",
                "استفاده از حافظهٔ DDR5 روی مادربرد DDR4 یا برعکس، باعث عدم روشن شدن سیستم می‌شود.",
            ),
        ],
    },
    {
        "slug": "ray-tracing",
        "title": "ری تریسینگ چیست و چه زمانی ارزش دارد؟",
        "summary": "راهنمای کاربردی ری تریسینگ: تفاوت با ری‌شیدر، تأثیر واقعی بر فریم‌ریت و اینکه چه وقت باید روشنش کنید.",
        "entity": None,
        "type": "concept",
        "review_days": 90,
        "body": [
            ("heading", "h2", "ری تریسینگ چیست؟"),
            (
                "paragraph",
                "ری تریسینگ روشی برای محاسبهٔ نور واقعی در بازی است. برخلاف ری‌شیدر که از داده‌های از پیش محاسبه‌شده استفاده می‌کند، ری تریسینگ مسیر نور را به‌صورت لحظه‌ای دنبال می‌کند.",
            ),
            ("heading", "h2", "تأثیر بر فریم‌ریت"),
            (
                "paragraph",
                "روشن کردن ری تریسینگ معمولاً بین ۲۰٪ تا ۴۰٪ افت فریم‌ریت ایجاد می‌کند. با این حال، در بازی‌هایی مانند سایبرپانک ۲۰۷۷، جلوه‌های نوری ری تریسینگ تفاوت چشمگیری با ری‌شیدر ایجاد می‌کند.",
            ),
            ("heading", "h2", "آیا ارزش دارد؟"),
            (
                "paragraph",
                "اگر روی 1440p بازی می‌کنید و کارت گرافیک شما RTX 4070 SUPER است، DLSS 3 افت فریم ری تریسینگ را تا حد زیادی جبران می‌کند. برای 1080p با RTX 4060، بهتر است ری تریسینگ را خاموش بگذارید.",
            ),
        ],
    },
    {
        "slug": "psu-sizing",
        "title": "چطور منبع تغذیهٔ مناسب انتخاب کنیم؟",
        "summary": "محاسبهٔ توان مورد نیاز با حاشیهٔ اطمینان، بررسی کانکتورها و نکات انتخاب برند.",
        "entity": None,
        "type": "concept",
        "review_days": 120,
        "body": [
            ("heading", "h2", "قانون ۲۵ درصد"),
            (
                "paragraph",
                "توان مصرفی پردازنده و کارت گرافیک را جمع کنید و ۲۵٪ حاشیه اطمینان اضافه کنید. برای نمونه، Ryzen 7 7800X3D (۱۲۰ وات) به‌علاوهٔ RTX 4070 SUPER (۲۲۰ وات) یعنی ۳۴۰ وات، و با حاشیهٔ اطمینان ۴۲۵ وات. منبع Corsair RM650x با ۶۵۰ وات انتخاب مطمئنی است.",
            ),
            ("heading", "h2", "کانکتورها مهم‌تر از وات هستند"),
            (
                "paragraph",
                "حتی اگر وات کافی داشته باشید، بدون کانکتور مناسب کارت اصلاً روشن نمی‌شود. کارت‌های پرچمدار مانند RTX 4080 SUPER به کانکتور 12VHPWR نیاز دارند که باید در منبع تغذیه موجود باشد.",
            ),
            ("heading", "h2", "کیفیت مهم‌تر از عدد است"),
            (
                "paragraph",
                "دو منبع ۶۵۰ واتی با کیفیت ساخت متفاوت، تجربهٔ کاملاً متفاوتی می‌دهند. گواهی 80+ Gold و گارانتی بلندمدت نشانهٔ کیفیت است.",
            ),
            (
                "callout",
                "tip",
                "نکته",
                "توان بیشتر همیشه بهتر نیست — منبع بزرگ‌تر اگر همیشه زیر بار کم کار کند، بازدهی پایین‌تری دارد.",
            ),
        ],
    },
    {
        "slug": "best-gaming-pcs-1080p-high-fps",
        "title": "بهترین سیستم‌های گیمینگ برای 1080p با فریم‌ریت بالا",
        "summary": "راهنمای انتخاب سیستم گیمینگ ۱۰۸۰p رقابتی — از ۳۹٫۵ تا ۶۸٫۵ میلیون تومان، با توضیح اینکه هر کدام برای چه کسی است.",
        "entity": None,
        "type": "guide",
        "review_days": 30,
        "use_case": "گیمینگ 1080p با فریم‌ریت بالا",
        "resolution": "1080p",
        "budget_max": "70000000",
        "products": [
            "tb-sku-vanguard-1080",
            "tb-sku-striker-1080",
            "tb-sku-ranger-1080",
            "tb-sku-drifter-1080",
        ],
        "body": [
            ("heading", "h2", "چه چیزی برای 1080p مهم است؟"),
            (
                "paragraph",
                "در رزولوشن 1080p، پردازنده مهم‌تر از کارت گرافیک است. در بازی‌های رقابتی مانند کانتر استرایک ۲، همین تفاوت می‌تواند ۵۰ فریم بر ثانیه باشد.",
            ),
            ("heading", "h2", "پیشنهاد ما"),
            (
                "paragraph",
                "برای بالاترین فریم‌ریت، سیستمی با پردازندهٔ Ryzen 7 7800X3D انتخاب درستی است. این پردازنده با کش ۹۶ مگابایتی خود در بازی‌های رقابتی می‌درخشد و می‌تواند روی RTX 4060 به ۳۰۰+ فریم بر ثانیه برسد.",
            ),
            ("heading", "h3", "انتخاب‌های اقتصادی"),
            (
                "paragraph",
                "اگر بودجه محدودتر است، TechBase Drifter 1080 با Ryzen 5 7600 و Radeon RX 7600 گزینهٔ به‌صرفه‌ای است. این ترکیب در بازی‌های 1080p فریم‌ریت قابل قبولی می‌دهد.",
            ),
            ("heading", "h2", "نکتهٔ مهم دربارهٔ مانیتور"),
            (
                "paragraph",
                "برای بهره‌برداری از این سیستم‌ها، مانیتور ۱۴۴ هرتز یا ۱۶۵ هرتز با رزولوشن 1080p لازم است. با مانیتور ۶۰ هرتز، بخش بزرگی از این فریم‌ریت اضافه هدر می‌رود.",
            ),
        ],
    },
    {
        "slug": "best-gaming-pcs-1440p",
        "title": "بهترین سیستم‌های گیمینگ برای 1440p",
        "summary": "برای 1440p باید سراغ RTX 4070 SUPER و پردازندهٔ نسل هشتم رایزن رفت. راهنمای کامل با مقایسهٔ گزینه‌ها.",
        "entity": None,
        "type": "guide",
        "review_days": 30,
        "use_case": "گیمینگ 1440p",
        "resolution": "1440p",
        "budget_max": "120000000",
        "products": [
            "tb-sku-phantom-1440",
            "tb-sku-valor-1440",
            "tb-sku-legend-1440",
        ],
        "body": [
            ("heading", "h2", "مشخصات لازم برای 1440p"),
            (
                "paragraph",
                "در 1440p کارت گرافیک تعیین‌کننده است. RTX 4070 SUPER با ۱۲ گیگابایت حافظه، نقطهٔ بهینه برای این رزولوشن است.",
            ),
            ("heading", "h2", "ای‌ام‌دی یا اینتل؟"),
            (
                "paragraph",
                "گزینهٔ TechBase Legend 1440 با Radeon RX 7800 XT ارزش خرید بهتری دارد و در بازی‌های 1440p به RTX 4070 SUPER نزدیک می‌شود. اگر بازی‌های استراتژیک و کارهای رندر هم دارید، Ryzen 9 7950X در TechBase Apex 4K انتخاب بهتری است.",
            ),
            ("heading", "h2", "مقایسهٔ کارت‌ها"),
            (
                "spec_table",
                "",
                [
                    ("سیستم", "فریم‌ریت در سایبرپانک ۲۰۷۷ (1440p)"),
                    ("Legend 1440", "۵۴ فریم بر ثانیه"),
                    ("Phantom 1440", "۶۶ فریم بر ثانیه"),
                    ("Valor 1440", "۶۴ فریم بر ثانیه"),
                ],
            ),
        ],
    },
    {
        "slug": "how-to-choose-a-prebuilt-pc",
        "title": "راهنمای خرید سیستم آماده",
        "summary": "پیش از خرید یک سیستم آماده، این هفت مورد را بررسی کنید — از سازگاری قطعات تا تاریخ به‌روزرسانی قیمت.",
        "entity": None,
        "type": "guide",
        "review_days": 45,
        "use_case": "خرید سیستم آماده",
        "products": [],
        "body": [
            ("heading", "h2", "۱. سازگاری قطعات را بررسی کنید"),
            (
                "paragraph",
                "مهم‌ترین نکته: پردازنده و مادربرد باید سوکت یکسان داشته باشند. یک سیستم با Ryzen 5 7600 (سوکت AM5) و مادربرد B760M (سوکت LGA1700) اصلاً روشن نمی‌شود. همین بررسی در موتور سازگاری تک‌بیس به‌صورت خودکار انجام می‌شود.",
            ),
            ("heading", "h2", "۲. منبع تغذیه"),
            (
                "paragraph",
                "منبع تغذیه را بر اساس مجموع توان قطعات انتخاب کنید. برای RTX 4070 SUPER حداقل ۶۵۰ وات توصیه می‌شود.",
            ),
            ("heading", "h2", "۳. تاریخ به‌روزرسانی قیمت"),
            (
                "paragraph",
                "قیمت‌ها در فروشگاه‌ها روزانه تغییر می‌کنند. هر کارت محصول در تک‌بیس تاریخ آخرین به‌روزرسانی را نشان می‌دهد تا بدانید قیمت چقدر تازه است.",
            ),
            ("heading", "h2", "۴. فضای ذخیره‌سازی"),
            (
                "paragraph",
                "بازی‌های روز به‌روز گاهی بیش از ۱۰۰ گیگابایت فضا می‌خواهند. یک اس‌اس‌د ۲ ترابایتی مانند Samsung 990 Pro خیال شما را راحت می‌کند.",
            ),
            ("heading", "h2", "۵. گارانتی"),
            ("paragraph", "گارانتی معتبر و قابل پیگیری، نشانهٔ یک فروشندهٔ قابل اعتماد است."),
        ],
    },
    {
        "slug": "rx-7800-xt",
        "title": "ای‌ام‌دی رadeon RX 7800 XT",
        "summary": "بهترین گزینهٔ ای‌ام‌دی برای 1440p — ۱۶ گیگابایت حافظه و ارزش خرید بالا.",
        "entity": "rx-7800-xt",
        "type": "component",
        "review_days": 60,
        "body": [
            ("heading", "h2", "معرفی"),
            (
                "paragraph",
                "RX 7800 XT با ۱۶ گیگابایت حافظهٔ GDDR6، در رزولوشن 1440p ارزش خرید بسیار خوبی دارد و در بسیاری از بازی‌ها به RTX 4070 SUPER نزدیک می‌شود.",
            ),
            ("heading", "h2", "مشخصات کلیدی"),
            (
                "spec_table",
                "",
                [
                    ("حافظه", "۱۶ گیگابایت GDDR6"),
                    ("توان مصرفی", "۲۶۳ وات"),
                    ("طول کارت", "۲۶۷ میلی‌متر"),
                    ("منبع تغذیهٔ پیشنهادی", "۷۰۰ وات"),
                ],
            ),
            ("heading", "h2", "سازگاری"),
            (
                "paragraph",
                "با ۲۶۷ میلی‌متر طول، این کارت در کیس‌هایی مانند Lian Li Lancool 216 جا می‌شود. منبع Corsair RM650x برای آن کافی است، هرچند منبع ۷۰۰ واتی حاشیهٔ اطمینان بیشتری می‌دهد.",
            ),
        ],
    },
    {
        "slug": "tb-prebuilt-phantom-1440",
        "title": "تک‌بیس فانتوم ۱۴۴۰",
        "summary": "سیستم گیمینگ ۱۴۴۰p با RTX 4070 SUPER و Ryzen 7 7800X3D — انتخاب متعادل برای گیمینگ جدید.",
        "entity": "tb-prebuilt-phantom-1440",
        "type": "component",
        "review_days": 30,
        "body": [
            ("heading", "h2", "مشخصات سیستم"),
            (
                "spec_table",
                "",
                [
                    ("پردازنده", "Ryzen 7 7800X3D"),
                    ("کارت گرافیک", "RTX 4070 SUPER"),
                    ("حافظه", "۳۲ گیگابایت DDR5-6000"),
                    ("مادربرد", "MSI MAG B650 Tomahawk"),
                    ("منبع تغذیه", "Corsair RM650x ۶۵۰ وات"),
                    ("کیس", "Lian Li Lancool 216"),
                ],
            ),
            ("heading", "h2", "کارایی"),
            (
                "paragraph",
                "در سایبرپانک ۲۰۷۷ با تنظیمات بالا در 1440p حدود ۶۶ فریم بر ثانیه ثبت شده است. در فورزا هورایزن ۵ با تنظیمات فوق‌العاده در همین رزولوشن به ۱۵۵ فریم بر ثانیه می‌رسد.",
            ),
            ("heading", "h2", "مناسب برای چه کسی؟"),
            (
                "paragraph",
                "این سیستم برای کسی است که ۱۴۴۰p بازی می‌کند و می‌خواهد همه‌چیز روان باشد. اگر بودجه کمتری دارید، TechBase Legend 1440 گزینهٔ به‌صرفه‌تری است.",
            ),
        ],
    },
]


class Command(BaseCommand):
    help = "Seed the wiki with realistic Persian content pages."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--relink",
            action="store_true",
            default=True,
            help="Run the auto-linker over the seeded pages (default).",
        )

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        root = self._wiki_root()
        created = 0
        updated = 0

        for spec in PAGES:
            page = self._upsert_page(root, spec)
            if page is None:
                continue
            if page.pk and page.first_published_at is None:
                created += 1
            else:
                updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(PAGES)} wiki pages ({created} new, {updated} updated)."
            )
        )

        if options.get("relink", True):
            self._relink()

    # --- helpers ------------------------------------------------------------

    def _wiki_root(self) -> Page:
        """The section page that holds every wiki page.

        The section lives under the **site root** (the page the default Wagtail
        site is rooted at), not under the tree root — otherwise Wagtail treats
        the pages as belonging to no site and the admin cannot manage them.
        """
        from apps.content.models import WikiPage

        # Look for the section by slug at any depth under the tree root.
        root = Page.objects.filter(slug=WIKI_ROOT_SLUG).first()
        if root:
            return root

        site_root = self._site_root()
        return site_root.add_child(instance=WikiPage(title="ویکی", slug=WIKI_ROOT_SLUG))

    def _site_root(self) -> Page:
        """The page the default site is rooted at."""
        from wagtail.models import Site

        site = Site.objects.filter(is_default_site=True).first() or Site.objects.first()
        if site is not None:
            return site.root_page

        # No site yet (a fresh database): fall back to the tree root's first
        # child, which is the conventional "home" page.
        tree_root = Page.get_first_root_node()
        if tree_root is None:
            raise RuntimeError("the Wagtail page tree has no root node")
        return tree_root.get_children().first() or tree_root

    def _upsert_page(self, root: Page, spec: dict) -> WikiPage | None:
        from apps.content.models import BuyerGuidePage, ComponentPage, ConceptPage

        model = {
            "component": ComponentPage,
            "guide": BuyerGuidePage,
            "concept": ConceptPage,
        }[spec["type"]]

        entity = None
        if spec.get("entity"):
            entity = Entity.objects.filter(slug=spec["entity"]).first()
            if entity is None:
                self.stderr.write(
                    self.style.WARNING(
                        f"unknown entity {spec['entity']!r} for page {spec['slug']!r}"
                    )
                )
                return None

        existing = root.get_children().filter(slug=spec["slug"]).first()
        if existing is None:
            # `add_child` copies the instance into the tree; the original
            # object stays unsaved, so work on the stored copy.
            root.add_child(instance=model(title=spec["title"], slug=spec["slug"]))
            page = cast("WikiPage", root.get_children().get(slug=spec["slug"]).specific)
        else:
            # The page may have been created as another type; rebuild it.
            page = cast("WikiPage", existing.specific)

        page.title = spec["title"]
        page.summary = spec["summary"]
        page.entity = entity
        page.review_by = date.today() + timedelta(days=spec.get("review_days", 90))
        page.tags = spec.get("tags", [])
        # The body and the guide fields live on the concrete page type.
        concrete = cast("Any", page)
        concrete.body = self._build_body(spec.get("body", []))

        # Every field must be set *before* the revision is published, or the
        # published revision keeps the old (empty) values.
        if spec["type"] == "guide" and entity is None:
            products = Product.objects.filter(sku__in=spec.get("products", []))
            concrete.recommended_products.set(products)
            concrete.use_case = spec.get("use_case", "")
            concrete.resolution = spec.get("resolution", "")
            if spec.get("budget_max"):
                from decimal import Decimal

                concrete.budget_max = Decimal(spec["budget_max"])

        page.save_revision().publish()
        # The guide's product list is a many-to-many on the revision, so it
        # has to be written after the page has a primary key.
        if spec["type"] == "guide" and entity is None:
            products = Product.objects.filter(sku__in=spec.get("products", []))
            concrete.recommended_products.set(products)
            page.save_revision().publish()

        return page

    def _build_body(self, blocks: list[tuple]) -> Any:
        """Turn the compact tuple format into StreamField child blocks."""
        from apps.content.blocks import BodyBlock

        stream = []
        for item in blocks:
            kind = item[0]
            if kind == "heading":
                _, level, text = item
                stream.append(("heading", {"level": level, "text": text}))
            elif kind == "paragraph":
                stream.append(("paragraph", item[1]))
            elif kind == "spec_table":
                _, title, rows = item
                stream.append(
                    (
                        "spec_table",
                        {
                            "title": title,
                            "rows": [{"label": label, "value": value} for label, value in rows],
                        },
                    )
                )
            elif kind == "callout":
                _, ckind, title, text = item
                stream.append(("callout", {"kind": ckind, "title": title, "text": text}))
            elif kind == "list":
                _, style, items = item
                stream.append(("list", {"style": style, "items": items}))
            else:
                continue
        return BodyBlock().to_python(stream)

    def _relink(self) -> None:
        """Run the auto-linker over every seeded page."""
        from apps.content.models import WikiPage

        created = 0
        red = 0
        for page in WikiPage.objects.live().select_related("entity"):
            result = link_page(page)
            created += len(result.created)
            red += len(result.red_links)
        self.stdout.write(
            self.style.SUCCESS(f"Auto-linked pages: {created} links created, {red} red links.")
        )
