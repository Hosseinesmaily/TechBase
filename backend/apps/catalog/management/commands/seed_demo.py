"""Seed realistic demo data.

The dataset is deliberately small but *realistic*: real socket standards, real
memory types, real benchmark numbers, prices in tomans, Persian display names.
The assistant's answers are only as trustworthy as this data, so it is treated
as product copy, not lorem ipsum.

Idempotent: running it twice updates in place instead of duplicating.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, NotRequired, TypedDict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.benchmarks.models import Benchmark
from apps.catalog.models import (
    Brand,
    Category,
    ComponentSpec,
    Entity,
    EntityStatus,
    EntityType,
    Product,
)
from apps.compat.models import CompatibilityRule


class EntitySeed(TypedDict):
    """One component in the demo catalog."""

    slug: str
    type: str
    title: str
    title_fa: str
    brand: str
    category: str
    summary_fa: str
    summary: NotRequired[str]
    aliases: NotRequired[list[str]]
    common: NotRequired[dict[str, Any]]
    extra: NotRequired[dict[str, Any]]


class PrebuiltSeed(TypedDict):
    """One prebuilt PC in the demo catalog."""

    slug: str
    title: str
    title_fa: str
    summary_fa: str
    price: int
    stock: int
    parts: list[str]
    common: NotRequired[dict[str, Any]]
    extra: NotRequired[dict[str, Any]]


class RuleSeed(TypedDict):
    code: str
    category_a: str
    category_b: str
    description: str
    description_fa: str
    params: dict[str, Any]
    severity: str
    order: int


# --- Reference data ----------------------------------------------------------

BRANDS = [
    ("amd", "AMD", "ای‌ام‌دی", "USA"),
    ("intel", "Intel", "اینتل", "USA"),
    ("nvidia", "NVIDIA", "انویدیا", "USA"),
    ("asus", "ASUS", "ایسوس", "Taiwan"),
    ("msi", "MSI", "ام‌اس‌آی", "Taiwan"),
    ("gigabyte", "GIGABYTE", "گیگابایت", "Taiwan"),
    ("corsair", "Corsair", "کورسیر", "USA"),
    ("kingston", "Kingston", "کینگستون", "USA"),
    ("crucial", "Crucial", "کرویال", "USA"),
    ("samsung", "Samsung", "سامسونگ", "Korea"),
    ("wd", "Western Digital", "Western Digital", "USA"),
    ("seagate", "Seagate", "سیگیت", "USA"),
    ("cooler-master", "Cooler Master", "کولر ماستر", "Taiwan"),
    ("nzxt", "NZXT", "ان‌زد‌ایکس‌تی", "USA"),
    ("lian-li", "Lian Li", "لیان‌لی", "Taiwan"),
]

CATEGORIES = [
    ("cpus", "Processors", "پردازنده‌ها", None),
    ("gpus", "Graphics Cards", "کارت‌های گرافیک", None),
    ("memory", "Memory", "حافظه", None),
    ("motherboards", "Motherboards", "مادربردها", None),
    ("psus", "Power Supplies", "منابع تغذیه", None),
    ("cases", "Cases", "کیس‌ها", None),
    ("coolers", "CPU Coolers", "خنک‌کننده‌ها", None),
    ("storage", "Storage", "حافظه ذخیره‌سازی", None),
    ("prebuilts", "Prebuilt PCs", "سیستم‌های آماده", None),
]

# entity slug, type, title, title_fa, brand slug, category slug, summary_fa, aliases, specs
ENTITIES: list[EntitySeed] = [
    # --- CPUs ---------------------------------------------------------------
    {
        "slug": "ryzen-7-7800x3d",
        "type": EntityType.CPU,
        "title": "AMD Ryzen 7 7800X3D",
        "title_fa": "ای‌ام‌دی رایزن ۷ ۷۸۰۰X3D",
        "brand": "amd",
        "category": "cpus",
        "summary_fa": "پردازنده هشت هسته‌ای با فناوری 3D V-Cache که در بازی‌ها بالاترین فریم‌ریت را می‌دهد.",
        "aliases": ["7800x3d", "ریزن ۷ ۷۸۰۰x3d", "ryzen 7800x3d"],
        "common": {
            "socket": "AM5",
            "cores": 8,
            "threads": 16,
            "tdp": 120,
            "base_clock": 4.2,
            "boost_clock": 5.0,
            "memory_type": "DDR5",
            "l3_cache_mb": 96,
        },
        "extra": {
            "integrated_graphics": False,
            "process_nm": 5,
            "max_memory_speed": 5200,
            "box_cooler": False,
            "unlocked": True,
        },
    },
    {
        "slug": "ryzen-5-7600",
        "type": EntityType.CPU,
        "title": "AMD Ryzen 5 7600",
        "title_fa": "ای‌ام‌دی رایزن ۵ ۷۶۰۰",
        "brand": "amd",
        "category": "cpus",
        "summary_fa": "پردازنده شش هسته‌ای اقتصادی با سوکت AM5؛ انتخاب متعادل برای گیمینگ ۱۰۸۰p.",
        "aliases": ["Ryzen 5 7600", "7600 Ryzen 5", "ریزن ۵ ۷۶۰۰"],
        "common": {
            "socket": "AM5",
            "cores": 6,
            "threads": 12,
            "tdp": 65,
            "base_clock": 3.8,
            "boost_clock": 5.1,
            "memory_type": "DDR5",
            "l3_cache_mb": 32,
        },
        "extra": {
            "integrated_graphics": True,
            "process_nm": 5,
            "max_memory_speed": 5200,
            "box_cooler": True,
            "unlocked": True,
        },
    },
    {
        "slug": "ryzen-9-7950x",
        "type": EntityType.CPU,
        "title": "AMD Ryzen 9 7950X",
        "title_fa": "ای‌ام‌دی رایزن ۹ ۷۹۵۰X",
        "brand": "amd",
        "category": "cpus",
        "summary_fa": "پردازنده شانزده هسته‌ای برای رندر، تدوین و کارهای چندریسمانی.",
        "aliases": ["7950x", "ریزن ۹ ۷۹۵۰x"],
        "common": {
            "socket": "AM5",
            "cores": 16,
            "threads": 32,
            "tdp": 170,
            "base_clock": 4.5,
            "boost_clock": 5.7,
            "memory_type": "DDR5",
            "l3_cache_mb": 64,
        },
        "extra": {
            "integrated_graphics": True,
            "process_nm": 5,
            "max_memory_speed": 5200,
            "box_cooler": False,
            "unlocked": True,
        },
    },
    {
        "slug": "core-i5-13400f",
        "type": EntityType.CPU,
        "title": "Intel Core i5-13400F",
        "title_fa": "اینتل کور i5-13400F",
        "brand": "intel",
        "category": "cpus",
        "summary_fa": "پردازنده ۱۰ هسته‌ای بدون گرافیک مجتمع با گرافیک قوی برای بازی ۱۰۸۰p.",
        "aliases": ["13400f", "کور i5 13400f", "i5-13400f"],
        "common": {
            "socket": "LGA1700",
            "cores": 10,
            "threads": 16,
            "tdp": 65,
            "base_clock": 2.5,
            "boost_clock": 4.6,
            "memory_type": "DDR5",
            "l3_cache_mb": 20,
        },
        "extra": {
            "integrated_graphics": False,
            "process_nm": 10,
            "max_memory_speed": 4800,
            "box_cooler": True,
            "unlocked": False,
        },
    },
    {
        "slug": "core-i7-14700k",
        "type": EntityType.CPU,
        "title": "Intel Core i7-14700K",
        "title_fa": "اینتل کور i7-14700K",
        "brand": "intel",
        "category": "cpus",
        "summary_fa": "پردازنده ۲۰ هسته‌ای با فرکانس بالا برای گیمینگ و کارهای ترکیبی.",
        "aliases": ["14700k", "کور i7 14700k", "i7-14700k"],
        "common": {
            "socket": "LGA1700",
            "cores": 20,
            "threads": 28,
            "tdp": 125,
            "base_clock": 3.4,
            "boost_clock": 5.6,
            "memory_type": "DDR5",
            "l3_cache_mb": 33,
        },
        "extra": {
            "integrated_graphics": True,
            "process_nm": 10,
            "max_memory_speed": 5600,
            "box_cooler": False,
            "unlocked": True,
        },
    },
    # --- GPUs ---------------------------------------------------------------
    {
        "slug": "rtx-4060",
        "type": EntityType.GPU,
        "title": "NVIDIA GeForce RTX 4060",
        "title_fa": "انویدیا جی‌فورس RTX 4060",
        "brand": "nvidia",
        "category": "gpus",
        "summary_fa": "کارت گرافیک میان‌رده با ۸ گیگابایت حافظه و پشتیبانی از DLSS 3 و Ray Tracing.",
        "aliases": ["4060", "rtx4060", "ری تی ایکس ۴۰۶۰"],
        "common": {
            "tdp": 115,
            "vram_gb": 8,
            "memory_type": "GDDR6",
            "length_mm": 245,
            "power_connectors": ["8-pin"],
            "recommended_psu": 550,
        },
        "extra": {
            "boost_clock": 2460,
            "memory_bus": 128,
            "outputs": "3x DisplayPort 1.4a, 1x HDMI 2.1",
            "dlss": True,
            "ray_tracing": True,
            "pcie_gen": 4,
        },
    },
    {
        "slug": "rtx-4070-super",
        "type": EntityType.GPU,
        "title": "NVIDIA GeForce RTX 4070 SUPER",
        "title_fa": "انویدیا جی‌فورس RTX 4070 SUPER",
        "brand": "nvidia",
        "category": "gpus",
        "summary_fa": "بهترین گزینه برای گیمینگ ۱۴۴۰p با فریم‌ریت بالا و DLSS 3.",
        "aliases": ["4070 super", "rtx4070s", "ری تی ایکس ۴۰۷۰ سوپر"],
        "common": {
            "tdp": 220,
            "vram_gb": 12,
            "memory_type": "GDDR6X",
            "length_mm": 267,
            "power_connectors": ["8-pin"],
            "recommended_psu": 650,
        },
        "extra": {
            "boost_clock": 2475,
            "memory_bus": 192,
            "outputs": "3x DisplayPort 1.4a, 1x HDMI 2.1",
            "dlss": True,
            "ray_tracing": True,
            "pcie_gen": 4,
        },
    },
    {
        "slug": "rtx-4080-super",
        "type": EntityType.GPU,
        "title": "NVIDIA GeForce RTX 4080 SUPER",
        "title_fa": "انویدیا جی‌فورس RTX 4080 SUPER",
        "brand": "nvidia",
        "category": "gpus",
        "summary_fa": "کارت گرافیک رده‌بالا برای ۴K با ۱۶ گیگابایت حافظه.",
        "aliases": ["4080 super", "ری تی ایکس ۴۰۸۰ سوپر"],
        "common": {
            "tdp": 320,
            "vram_gb": 16,
            "memory_type": "GDDR6X",
            "length_mm": 304,
            "power_connectors": ["8-pin", "12vhpwr"],
            "recommended_psu": 750,
        },
        "extra": {
            "boost_clock": 2550,
            "memory_bus": 256,
            "outputs": "3x DisplayPort 1.4a, 1x HDMI 2.1",
            "dlss": True,
            "ray_tracing": True,
            "pcie_gen": 4,
        },
    },
    {
        "slug": "rx-7600",
        "type": EntityType.GPU,
        "title": "AMD Radeon RX 7600",
        "title_fa": "ای‌ام‌دی رadeon RX 7600",
        "brand": "amd",
        "category": "gpus",
        "summary_fa": "کارت گرافیک اقتصادی ۱۰۸۰p با ۸ گیگابایت حافظه.",
        "aliases": ["Radeon RX 7600", "RX 7600", "rx7600", "رادیون ۷۶۰۰"],
        "common": {
            "tdp": 165,
            "vram_gb": 8,
            "memory_type": "GDDR6",
            "length_mm": 204,
            "power_connectors": ["8-pin"],
            "recommended_psu": 550,
        },
        "extra": {
            "boost_clock": 2755,
            "memory_bus": 128,
            "outputs": "3x DisplayPort 2.1, 1x HDMI 2.1",
            "dlss": False,
            "ray_tracing": True,
            "pcie_gen": 4,
        },
    },
    {
        "slug": "rx-7800-xt",
        "type": EntityType.GPU,
        "title": "AMD Radeon RX 7800 XT",
        "title_fa": "ای‌ام‌دی رadeon RX 7800 XT",
        "brand": "amd",
        "category": "gpus",
        "summary_fa": "بهترین گزینهٔ ای‌ام‌دی برای ۱۴۴۰p با ۱۶ گیگابایت حافظه.",
        "aliases": ["7800xt", "7800 xt", "رادیون ۷۸۰۰ ایکس تی"],
        "common": {
            "tdp": 263,
            "vram_gb": 16,
            "memory_type": "GDDR6",
            "length_mm": 267,
            "power_connectors": ["8-pin"],
            "recommended_psu": 700,
        },
        "extra": {
            "boost_clock": 2430,
            "memory_bus": 256,
            "outputs": "2x DisplayPort 2.1, 1x HDMI 2.1",
            "dlss": False,
            "ray_tracing": True,
            "pcie_gen": 4,
        },
    },
    # --- RAM ---------------------------------------------------------------
    {
        "slug": "corsair-vengeance-rgb-32gb-ddr5-6000",
        "type": EntityType.RAM,
        "title": "Corsair Vengeance RGB 32GB (2x16GB) DDR5-6000",
        "title_fa": "کورسیر ونجنس RGB ۳۲ گیگابایت DDR5-6000",
        "brand": "corsair",
        "category": "memory",
        "summary_fa": "دو ماژول ۱۶ گیگابایتی DDR5 با پروفایل EXPO؛ انتخاب استاندارد برای AM5.",
        "aliases": ["ddr5 6000", "32gb ddr5", "ونجنس ۳۲ گیگ"],
        "common": {
            "memory_type": "DDR5",
            "capacity_gb": 32,
            "modules": 2,
            "speed_mhz": 6000,
            "latency_cl": 30,
            "voltage": 1.35,
        },
        "extra": {"expo": True, "xmp": True, "rgb": True, "height_mm": 44, "heatspreader": True},
    },
    {
        "slug": "corsair-vengeance-rgb-16gb-ddr5-6000",
        "type": EntityType.RAM,
        "title": "Corsair Vengeance RGB 16GB (2x8GB) DDR5-6000",
        "title_fa": "کورسیر ونجنس RGB ۱۶ گیگابایت DDR5-6000",
        "brand": "corsair",
        "category": "memory",
        "summary_fa": "دو ماژول ۸ گیگابایتی DDR5؛ ارزان‌تر و مناسب سیستم‌های اقتصادی.",
        "aliases": ["16gb ddr5", "ونجنس ۱۶ گیگ"],
        "common": {
            "memory_type": "DDR5",
            "capacity_gb": 16,
            "modules": 2,
            "speed_mhz": 6000,
            "latency_cl": 30,
            "voltage": 1.35,
        },
        "extra": {"expo": True, "xmp": True, "rgb": True, "height_mm": 44, "heatspreader": True},
    },
    {
        "slug": "kingston-fury-beast-32gb-ddr4-3200",
        "type": EntityType.RAM,
        "title": "Kingston FURY Beast 32GB (2x16GB) DDR4-3200",
        "title_fa": "کینگستون فوری بیست ۳۲ گیگابایت DDR4-3200",
        "brand": "kingston",
        "category": "memory",
        "summary_fa": "حافظه DDR4 برای مادربردهای نسل قبلی LGA1700.",
        "aliases": ["ddr4 3200", "32gb ddr4", "فوری بیست"],
        "common": {
            "memory_type": "DDR4",
            "capacity_gb": 32,
            "modules": 2,
            "speed_mhz": 3200,
            "latency_cl": 16,
            "voltage": 1.35,
        },
        "extra": {"expo": False, "xmp": True, "rgb": False, "height_mm": 35, "heatspreader": True},
    },
    # --- Motherboards -------------------------------------------------------
    {
        "slug": "asus-tuf-gaming-b650-plus",
        "type": EntityType.MOTHERBOARD,
        "title": "ASUS TUF Gaming B650-PLUS WiFi",
        "title_fa": "ایسوس TUF Gaming B650-PLUS WiFi",
        "brand": "asus",
        "category": "motherboards",
        "summary_fa": "مادربرد AM5 میان‌رده با سه خروجی M.2 و پشتیبانی EXPO.",
        "aliases": [
            "ASUS TUF Gaming B650-PLUS",
            "TUF Gaming B650-PLUS",
            "b650 plus",
            "b650",
            "تاف ب۶۵۰",
        ],
        "common": {
            "socket": "AM5",
            "memory_type": "DDR5",
            "memory_slots": 4,
            "max_memory_gb": 256,
            "form_factor": "ATX",
            "m2_slots": 3,
            "wifi": True,
        },
        "extra": {
            "max_memory_speed": 6400,
            "pcie_gen": 4,
            "form_factor_fa": "ATX",
            "memory_expo": True,
        },
    },
    {
        "slug": "msi-mag-b650-tomahawk",
        "type": EntityType.MOTHERBOARD,
        "title": "MSI MAG B650 Tomahawk WiFi",
        "title_fa": "ام‌اس‌آی MAG B650 تاماهوک WiFi",
        "brand": "msi",
        "category": "motherboards",
        "summary_fa": "مادربرد ATX با VRM قوی و چهار اسلات M.2 برای AM5.",
        "aliases": ["b650 tomahawk", "تاماهوک", "b650"],
        "common": {
            "socket": "AM5",
            "memory_type": "DDR5",
            "memory_slots": 4,
            "max_memory_gb": 256,
            "form_factor": "ATX",
            "m2_slots": 4,
            "wifi": True,
        },
        "extra": {
            "max_memory_speed": 6800,
            "pcie_gen": 4,
            "form_factor_fa": "ATX",
            "memory_expo": True,
        },
    },
    {
        "slug": "gigabyte-b760m-ds3h",
        "type": EntityType.MOTHERBOARD,
        "title": "Gigabyte B760M DS3H",
        "title_fa": "گیگابایت B760M DS3H",
        "brand": "gigabyte",
        "category": "motherboards",
        "summary_fa": "مادربرد micro-ATX ارزان برای پردازنده‌های نسل ۱۲ و ۱۳ اینتل.",
        "aliases": ["b760m ds3h", "ب۷۶۰ ام"],
        "common": {
            "socket": "LGA1700",
            "memory_type": "DDR5",
            "memory_slots": 4,
            "max_memory_gb": 128,
            "form_factor": "mATX",
            "m2_slots": 2,
            "wifi": False,
        },
        "extra": {
            "max_memory_speed": 5333,
            "pcie_gen": 4,
            "form_factor_fa": "micro-ATX",
            "memory_expo": False,
        },
    },
    # --- PSUs ---------------------------------------------------------------
    {
        "slug": "corsair-rm650x",
        "type": EntityType.PSU,
        "title": "Corsair RM650x 650W 80+ Gold",
        "title_fa": "کورسیر RM650x ۶۵۰ وات گلد",
        "brand": "corsair",
        "category": "psus",
        "summary_fa": "منبع تغذیه ۶۵۰ واتی با ماژول کاملاً ماژولار؛ مناسب RTX 4060 و RTX 4070.",
        "aliases": ["rm650x", "650w", "رام ۶۵۰ ایکس"],
        "common": {
            "wattage": 650,
            "efficiency": "80+ Gold",
            "modular": "full",
            "connectors": ["24-pin", "8-pin CPU", "2x 8-pin PCIe", "1x 12vhpwr"],
        },
        "extra": {
            "length_mm": 160,
            "fan_size_mm": 135,
            "warranty_years": 10,
            "connectors_fa": "۲۴ پین، ۸ پین CPU، دو ۸ پین PCIe، ۱۲VHPWR",
        },
    },
    {
        "slug": "corsair-rm850x",
        "type": EntityType.PSU,
        "title": "Corsair RM850x 850W 80+ Gold",
        "title_fa": "کورسیر RM850x ۸۵۰ وات گلد",
        "brand": "corsair",
        "category": "psus",
        "summary_fa": "منبع تغذیه ۸۵۰ واتی با گارانتی ۱۰ ساله؛ مناسب RTX 4080.",
        "aliases": ["rm850x", "850w", "رام ۸۵۰ ایکس"],
        "common": {
            "wattage": 850,
            "efficiency": "80+ Gold",
            "modular": "full",
            "connectors": ["24-pin", "8-pin CPU", "4x 8-pin PCIe", "1x 12vhpwr"],
        },
        "extra": {
            "length_mm": 160,
            "fan_size_mm": 135,
            "warranty_years": 10,
            "connectors_fa": "۲۴ پین، ۸ پین CPU، چهار ۸ پین PCIe، ۱۲VHPWR",
        },
    },
    {
        "slug": "corsair-rm450",
        "type": EntityType.PSU,
        "title": "Corsair RM450 450W 80+ Gold",
        "title_fa": "کورسیر RM450 ۴۵۰ وات گلد",
        "brand": "corsair",
        "category": "psus",
        "summary_fa": "منبع تغذیه ۴۵۰ واتی برای سیستم‌های بدون کارت گرافیک پرقدرت.",
        "aliases": ["rm450", "450w"],
        "common": {
            "wattage": 450,
            "efficiency": "80+ Gold",
            "modular": "full",
            "connectors": ["24-pin", "8-pin CPU", "2x 8-pin PCIe"],
        },
        "extra": {
            "length_mm": 140,
            "fan_size_mm": 120,
            "warranty_years": 5,
            "connectors_fa": "۲۴ پین، ۸ پین CPU، دو ۸ پین PCIe",
        },
    },
    # --- Cases --------------------------------------------------------------
    {
        "slug": "nzxt-h5-flow",
        "type": EntityType.CASE,
        "title": "NZXT H5 Flow",
        "title_fa": "ان‌زد‌ایکس‌تی H5 فلو",
        "brand": "nzxt",
        "category": "cases",
        "summary_fa": "کیس میکرو-ATX جمع‌وجور با پنل شیشه‌ای و پشتیبانی از کارت گرافیک تا ۳۶۵ میلی‌متر.",
        "aliases": ["h5 flow", "h5"],
        "common": {
            "form_factor": "mATX",
            "max_gpu_length_mm": 365,
            "max_cooler_height_mm": 165,
            "max_psu_length_mm": 200,
            "m2_slots": 4,
            "included_fans": 2,
        },
        "extra": {
            "form_factor_fa": "micro-ATX",
            "front_io": True,
            "glass_panel": True,
            "drive_bays": 2,
        },
    },
    {
        "slug": "lian-li-lancool-216",
        "type": EntityType.CASE,
        "title": "Lian Li Lancool 216",
        "title_fa": "لیان‌لی لَنکول ۲۱۶",
        "brand": "lian-li",
        "category": "cases",
        "summary_fa": "کیس ATX با دو پنل شیشه‌ای، گردش هوای قوی و پشتیبانی از کارت ۴۰۰ میلی‌متری.",
        "aliases": ["lancool 216", "لَنکول"],
        "common": {
            "form_factor": "ATX",
            "max_gpu_length_mm": 392,
            "max_cooler_height_mm": 180,
            "max_psu_length_mm": 220,
            "m2_slots": 4,
            "included_fans": 3,
        },
        "extra": {"form_factor_fa": "ATX", "front_io": True, "glass_panel": True, "drive_bays": 4},
    },
    {
        "slug": "nzxt-h7",
        "type": EntityType.CASE,
        "title": "NZXT H7",
        "title_fa": "ان‌زد‌ایکس‌تی H7",
        "brand": "nzxt",
        "category": "cases",
        "summary_fa": "کیس ATX با پنل شیشه‌ای و فضای داخلی باز.",
        "aliases": ["h7"],
        "common": {
            "form_factor": "ATX",
            "max_gpu_length_mm": 400,
            "max_cooler_height_mm": 185,
            "max_psu_length_mm": 200,
            "m2_slots": 4,
            "included_fans": 2,
        },
        "extra": {"form_factor_fa": "ATX", "front_io": True, "glass_panel": True, "drive_bays": 2},
    },
    # --- Coolers ------------------------------------------------------------
    {
        "slug": "cooler-master-hyper-212",
        "type": EntityType.COOLER,
        "title": "Cooler Master Hyper 212 Black",
        "title_fa": "کولر ماستر هایپر ۲۱۲ بلک",
        "brand": "cooler-master",
        "category": "coolers",
        "summary_fa": "خنک‌کننده بادی تک‌فن پرفروش با پشتیبانی از ای‌ام‌دی و اینتل.",
        "aliases": ["hyper 212", "هایپر ۲۱۲"],
        "common": {
            "height_mm": 159,
            "sockets": ["AM4", "AM5", "LGA1700", "LGA1200"],
            "tdp_rating": 150,
            "fan_size_mm": 120,
        },
        "extra": {"type": "air", "type_fa": "بادی", "noise_db": 27, "rgb": False},
    },
    {
        "slug": "nzxt-kraken-360",
        "type": EntityType.COOLER,
        "title": "NZXT Kraken Elite 360 RGB",
        "title_fa": "ان‌زد‌ایکس‌تی کراکن الیت ۳۶۰ RGB",
        "brand": "nzxt",
        "category": "coolers",
        "summary_fa": "خنک‌کننده آبی ۳۶۰ میلی‌متری با نمایشگر LCD.",
        "aliases": ["kraken 360", "کراکن ۳۶۰"],
        "common": {
            "height_mm": 0,
            "sockets": ["AM4", "AM5", "LGA1700"],
            "tdp_rating": 300,
            "fan_size_mm": 120,
            "radiator_mm": 360,
        },
        "extra": {"type": "liquid", "type_fa": "مایع", "lcd": True, "rgb": True, "pump_rpm": 2800},
    },
    # --- Storage ------------------------------------------------------------
    {
        "slug": "samsung-990-pro-2tb",
        "type": EntityType.STORAGE,
        "title": "Samsung 990 Pro 2TB NVMe",
        "title_fa": "سامسونگ ۹۹۰ پرو ۲ ترابایت",
        "brand": "samsung",
        "category": "storage",
        "summary_fa": "اس‌اس‌د پرسرعت با رابط PCIe 4.0؛ بارگذاری بازی‌ها را چند برابر سریع‌تر می‌کند.",
        "aliases": ["990 pro", "۹۹۰ پرو"],
        "common": {
            "capacity_tb": 2,
            "interface": "PCIe 4.0 x4",
            "read_mbps": 7450,
            "write_mbps": 6900,
            "form_factor": "M.2 2280",
        },
        "extra": {"dram": True, "tbw": 1200, "endurance_fa": "۱۲۰۰ ترابایت نوشتن"},
    },
    {
        "slug": "wd-blue-sn580-1tb",
        "type": EntityType.STORAGE,
        "title": "WD Blue SN580 1TB NVMe",
        "title_fa": "WD Blue SN580 ۱ ترابایت",
        "brand": "wd",
        "category": "storage",
        "summary_fa": "اس‌اس‌د NVMe اقتصادی با گارانتی ۵ ساله.",
        "aliases": ["sn580", "اس ان ۵۸۰"],
        "common": {
            "capacity_tb": 1,
            "interface": "PCIe 4.0 x4",
            "read_mbps": 4150,
            "write_mbps": 3600,
            "form_factor": "M.2 2280",
        },
        "extra": {"dram": False, "tbw": 600, "endurance_fa": "۶۰۰ ترابایت نوشتن"},
    },
    {
        "slug": "ddr5",
        "type": EntityType.CONCEPT,
        "title": "DDR5",
        "title_fa": "حافظهٔ DDR5",
        "brand": "",
        "category": "",
        "summary_fa": "نسل پنجم حافظهٔ SDRAM؛ سازگاری آن به نوع پشتیبانی‌شده توسط پردازنده و مادربرد بستگی دارد.",
        "aliases": ["DDR5 memory", "حافظه DDR5", "حافظهٔ DDR5"],
        "common": {"memory_type": "DDR5"},
    },
]

# --- Products (sku, entity slug, title_fa, price tomans, stock, warranty) ----

PRODUCTS = [
    (
        "tb-cpu-7800x3d",
        "ryzen-7-7800x3d",
        "پردازندهٔ کامپیوتر ای‌ام‌دی مدل Ryzen 7 7800X3D Tray",
        24500000,
        12,
        36,
    ),
    (
        "tb-cpu-7600",
        "ryzen-5-7600",
        "پردازندهٔ کامپیوتر ای‌ام‌دی مدل Ryzen 5 7600",
        15800000,
        30,
        36,
    ),
    (
        "tb-cpu-7950x",
        "ryzen-9-7950x",
        "پردازندهٔ کامپیوتر ای‌ام‌دی مدل Ryzen 9 7950X",
        42500000,
        5,
        36,
    ),
    (
        "tb-cpu-13400f",
        "core-i5-13400f",
        "پردازنده کامپیوتر Intel مدل Core i5-13400F",
        13500000,
        22,
        36,
    ),
    (
        "tb-cpu-14700k",
        "core-i7-14700k",
        "پردازنده کامپیوتر Intel مدل Core i7-14700K",
        29500000,
        8,
        36,
    ),
    (
        "tb-gpu-4060",
        "rtx-4060",
        "کارت گرافیک NVIDIA GeForce RTX 4060، حافظهٔ ۸ گیگابایت GDDR6",
        18900000,
        18,
        36,
    ),
    (
        "tb-gpu-4070s",
        "rtx-4070-super",
        "کارت گرافیک NVIDIA GeForce RTX 4070 SUPER، حافظهٔ ۱۲ گیگابایت GDDR6X",
        32900000,
        9,
        36,
    ),
    (
        "tb-gpu-4080s",
        "rtx-4080-super",
        "کارت گرافیک NVIDIA GeForce RTX 4080 SUPER، حافظهٔ ۱۶ گیگابایت GDDR6X",
        58900000,
        3,
        36,
    ),
    (
        "tb-gpu-7600",
        "rx-7600",
        "کارت گرافیک AMD Radeon RX 7600، حافظهٔ ۸ گیگابایت GDDR6",
        17200000,
        14,
        36,
    ),
    (
        "tb-gpu-7800xt",
        "rx-7800-xt",
        "کارت گرافیک AMD Radeon RX 7800 XT، حافظهٔ ۱۶ گیگابایت GDDR6",
        31500000,
        7,
        36,
    ),
    (
        "tb-ram-32-6000",
        "corsair-vengeance-rgb-32gb-ddr5-6000",
        "رم کامپیوتر Corsair مدل Vengeance RGB، ظرفیت ۳۲ گیگابایت DDR5-6000",
        4200000,
        40,
        60,
    ),
    (
        "tb-ram-16-6000",
        "corsair-vengeance-rgb-16gb-ddr5-6000",
        "رم کامپیوتر Corsair مدل Vengeance RGB، ظرفیت ۱۶ گیگابایت DDR5-6000",
        2450000,
        35,
        60,
    ),
    (
        "tb-ram-32-3200",
        "kingston-fury-beast-32gb-ddr4-3200",
        "رم کامپیوتر Kingston مدل FURY Beast، ظرفیت ۳۲ گیگابایت DDR4-3200",
        3800000,
        25,
        60,
    ),
    (
        "tb-mb-b650plus",
        "asus-tuf-gaming-b650-plus",
        "مادربرد ASUS مدل TUF Gaming B650-PLUS WiFi، سوکت AM5 و حافظه DDR5",
        9800000,
        16,
        36,
    ),
    (
        "tb-mb-b650tomahawk",
        "msi-mag-b650-tomahawk",
        "مادربرد MSI مدل MAG B650 Tomahawk WiFi، سوکت AM5 و حافظه DDR5",
        10500000,
        11,
        36,
    ),
    (
        "tb-mb-b760mds3h",
        "gigabyte-b760m-ds3h",
        "مادربرد GIGABYTE مدل B760M DS3H، سوکت LGA1700 و حافظه DDR5",
        6200000,
        20,
        36,
    ),
    (
        "tb-psu-rm650x",
        "corsair-rm650x",
        "پاور ۶۵۰ وات Corsair مدل RM650x 80Plus Gold",
        6100000,
        19,
        120,
    ),
    (
        "tb-psu-rm850x",
        "corsair-rm850x",
        "پاور ۸۵۰ وات Corsair مدل RM850x 80Plus Gold",
        7900000,
        13,
        120,
    ),
    (
        "tb-psu-rm450",
        "corsair-rm450",
        "پاور ۴۵۰ وات Corsair مدل RM450 80Plus Gold",
        3900000,
        17,
        60,
    ),
    ("tb-case-h5flow", "nzxt-h5-flow", "کیس NZXT مدل H5 Flow", 6200000, 10, 24),
    (
        "tb-case-lancool216",
        "lian-li-lancool-216",
        "کیس Lian Li مدل Lancool 216",
        9400000,
        6,
        24,
    ),
    ("tb-case-h7", "nzxt-h7", "کیس NZXT مدل H7", 7800000, 8, 24),
    (
        "tb-cooler-hyper212",
        "cooler-master-hyper-212",
        "خنک‌کنندهٔ پردازنده Cooler Master مدل Hyper 212 Black",
        2450000,
        26,
        60,
    ),
    (
        "tb-cooler-kraken360",
        "nzxt-kraken-360",
        "خنک‌کنندهٔ مایع NZXT مدل Kraken Elite 360 RGB",
        11500000,
        4,
        60,
    ),
    (
        "tb-ssd-990pro2tb",
        "samsung-990-pro-2tb",
        "حافظهٔ SSD Samsung مدل 990 Pro، ظرفیت ۲ ترابایت NVMe",
        4900000,
        21,
        60,
    ),
    (
        "tb-ssd-sn5801tb",
        "wd-blue-sn580-1tb",
        "حافظهٔ SSD WD مدل Blue SN580، ظرفیت ۱ ترابایت NVMe",
        2950000,
        33,
        60,
    ),
]

# --- Prebuilt PCs ------------------------------------------------------------
# (slug, title_fa, summary_fa, price, stock, [component slugs], extra specs)

PREBUILTS: list[PrebuiltSeed] = [
    {
        "slug": "tb-prebuilt-striker-1080",
        "title": "TechBase Striker 1080",
        "title_fa": "سیستم گیمینگ TechBase مدل Striker 1080، مناسب بازی 1080p",
        "summary_fa": "سیستم گیمینگ ۱۰۸۰p با فریم‌ریت بالا؛ مناسب رقابتی و استریم.",
        "price": 48900000,
        "stock": 6,
        "parts": [
            "ryzen-5-7600",
            "rtx-4060",
            "corsair-vengeance-rgb-16gb-ddr5-6000",
            "asus-tuf-gaming-b650-plus",
            "corsair-rm450",
            "nzxt-h5-flow",
            "cooler-master-hyper-212",
            "wd-blue-sn580-1tb",
        ],
        "common": {"psu_wattage": 450, "estimated_draw_w": 340},
        "extra": {
            "target_resolution": "1080p",
            "target_fps": 120,
            "os": "Windows 11",
            "monitor_included": False,
        },
    },
    {
        "slug": "tb-prebuilt-vanguard-1080",
        "title": "TechBase Vanguard 1080",
        "title_fa": "سیستم گیمینگ TechBase مدل Vanguard 1080، مناسب بازی 1080p",
        "summary_fa": "سیستم گیمینگ ۱۰۸۰p با پردازندهٔ ۸۰۰۰X3D؛ بالاترین فریم‌ریت در بازی‌های رقابتی.",
        "price": 68500000,
        "stock": 4,
        "parts": [
            "ryzen-7-7800x3d",
            "rtx-4060",
            "corsair-vengeance-rgb-32gb-ddr5-6000",
            "asus-tuf-gaming-b650-plus",
            "corsair-rm650x",
            "nzxt-h5-flow",
            "cooler-master-hyper-212",
            "samsung-990-pro-2tb",
        ],
        "common": {"psu_wattage": 650, "estimated_draw_w": 420},
        "extra": {
            "target_resolution": "1080p",
            "target_fps": 144,
            "os": "Windows 11",
            "monitor_included": False,
        },
    },
    {
        "slug": "tb-prebuilt-phantom-1440",
        "title": "TechBase Phantom 1440",
        "title_fa": "سیستم گیمینگ TechBase مدل Phantom 1440، مناسب بازی 1440p",
        "summary_fa": "سیستم گیمینگ ۱۴۴۰p با RTX 4070 SUPER؛ انتخاب متعادل برای گیمینگ جدید.",
        "price": 98900000,
        "stock": 3,
        "parts": [
            "ryzen-7-7800x3d",
            "rtx-4070-super",
            "corsair-vengeance-rgb-32gb-ddr5-6000",
            "msi-mag-b650-tomahawk",
            "corsair-rm650x",
            "lian-li-lancool-216",
            "cooler-master-hyper-212",
            "samsung-990-pro-2tb",
        ],
        "common": {"psu_wattage": 650, "estimated_draw_w": 460},
        "extra": {
            "target_resolution": "1440p",
            "target_fps": 144,
            "os": "Windows 11",
            "monitor_included": False,
        },
    },
    {
        "slug": "tb-prebuilt-valor-1440",
        "title": "TechBase Valor 1440",
        "title_fa": "سیستم گیمینگ TechBase مدل Valor 1440، مناسب بازی 1440p",
        "summary_fa": "سیستم گیمینگ ۱۴۴۰p با RTX 4070 SUPER و پردازندهٔ ۱۴۷۰۰K.",
        "price": 108500000,
        "stock": 2,
        "parts": [
            "core-i7-14700k",
            "rtx-4070-super",
            "corsair-vengeance-rgb-32gb-ddr5-6000",
            "gigabyte-b760m-ds3h",
            "corsair-rm850x",
            "nzxt-h7",
            "nzxt-kraken-360",
            "samsung-990-pro-2tb",
        ],
        "common": {"psu_wattage": 850, "estimated_draw_w": 480},
        "extra": {
            "target_resolution": "1440p",
            "target_fps": 144,
            "os": "Windows 11",
            "monitor_included": False,
        },
    },
    {
        "slug": "tb-prebuilt-apex-4k",
        "title": "TechBase Apex 4K",
        "title_fa": "سیستم گیمینگ TechBase مدل Apex 4K، مناسب بازی 4K",
        "summary_fa": "سیستم گیمینگ ۴K با RTX 4080 SUPER و ۳۲ گیگابایت حافظه.",
        "price": 159900000,
        "stock": 1,
        "parts": [
            "ryzen-9-7950x",
            "rtx-4080-super",
            "corsair-vengeance-rgb-32gb-ddr5-6000",
            "msi-mag-b650-tomahawk",
            "corsair-rm850x",
            "lian-li-lancool-216",
            "nzxt-kraken-360",
            "samsung-990-pro-2tb",
        ],
        "common": {"psu_wattage": 850, "estimated_draw_w": 700},
        "extra": {
            "target_resolution": "4k",
            "target_fps": 120,
            "os": "Windows 11 Pro",
            "monitor_included": False,
        },
    },
    {
        "slug": "tb-prebuilt-legend-1440",
        "title": "TechBase Legend 1440",
        "title_fa": "سیستم گیمینگ TechBase مدل Legend 1440، مناسب بازی 1440p",
        "summary_fa": "سیستم گیمینگ ۱۴۴۰p با AMD؛ گزینه‌ای ارزشمند برای نرخ فریم به ازای هر تومان.",
        "price": 92500000,
        "stock": 5,
        "parts": [
            "ryzen-5-7600",
            "rx-7800-xt",
            "corsair-vengeance-rgb-32gb-ddr5-6000",
            "asus-tuf-gaming-b650-plus",
            "corsair-rm650x",
            "nzxt-h5-flow",
            "cooler-master-hyper-212",
            "wd-blue-sn580-1tb",
        ],
        "common": {"psu_wattage": 650, "estimated_draw_w": 400},
        "extra": {
            "target_resolution": "1440p",
            "target_fps": 100,
            "os": "Windows 11",
            "monitor_included": False,
        },
    },
    {
        "slug": "tb-prebuilt-nomad-office",
        "title": "TechBase Nomad Office",
        "title_fa": "سیستم اداری TechBase مدل Nomad Office",
        "summary_fa": "سیستم اداری بی‌صدا با پردازندهٔ کم‌مصرف و گرافیک مجتمع.",
        "price": 27900000,
        "stock": 8,
        "parts": [
            "ryzen-5-7600",
            "corsair-vengeance-rgb-16gb-ddr5-6000",
            "asus-tuf-gaming-b650-plus",
            "corsair-rm450",
            "nzxt-h5-flow",
            "cooler-master-hyper-212",
            "wd-blue-sn580-1tb",
        ],
        "common": {"psu_wattage": 450, "estimated_draw_w": 120},
        "extra": {
            "target_resolution": "1080p",
            "target_fps": 0,
            "os": "Windows 11 Pro",
            "monitor_included": False,
            "office": True,
        },
    },
    {
        "slug": "tb-prebuilt-drifter-1080",
        "title": "TechBase Drifter 1080",
        "title_fa": "سیستم گیمینگ TechBase مدل Drifter 1080، مناسب بازی 1080p",
        "summary_fa": "سیستم گیمینگ اقتصادی ۱۰۸۰p با Radeon RX 7600.",
        "price": 39500000,
        "stock": 7,
        "parts": [
            "ryzen-5-7600",
            "rx-7600",
            "corsair-vengeance-rgb-16gb-ddr5-6000",
            "asus-tuf-gaming-b650-plus",
            "corsair-rm450",
            "nzxt-h5-flow",
            "cooler-master-hyper-212",
            "wd-blue-sn580-1tb",
        ],
        "common": {"psu_wattage": 450, "estimated_draw_w": 300},
        "extra": {
            "target_resolution": "1080p",
            "target_fps": 90,
            "os": "Windows 11",
            "monitor_included": False,
        },
    },
    {
        "slug": "tb-prebuilt-ranger-1080",
        "title": "TechBase Ranger 1080",
        "title_fa": "سیستم گیمینگ TechBase مدل Ranger 1080، مناسب بازی 1080p",
        "summary_fa": "سیستم گیمینگ ۱۰۸۰p با i5-13400F و RTX 4060؛ کاربری عمومی و گیم.",
        "price": 41500000,
        "stock": 6,
        "parts": [
            "core-i5-13400f",
            "rtx-4060",
            "corsair-vengeance-rgb-16gb-ddr5-6000",
            "gigabyte-b760m-ds3h",
            "corsair-rm450",
            "nzxt-h5-flow",
            "cooler-master-hyper-212",
            "wd-blue-sn580-1tb",
        ],
        "common": {"psu_wattage": 450, "estimated_draw_w": 320},
        "extra": {
            "target_resolution": "1080p",
            "target_fps": 100,
            "os": "Windows 11",
            "monitor_included": False,
        },
    },
    {
        "slug": "tb-prebuilt-horizon-1440",
        "title": "TechBase Horizon 1440",
        "title_fa": "سیستم گیمینگ TechBase مدل Horizon 1440، مناسب بازی 1440p",
        "summary_fa": "سیستم گیمینگ ۱۴۴۰p با RTX 4080 SUPER و ۱۶ گیگابایت حافظهٔ گرافیک.",
        "price": 145900000,
        "stock": 2,
        "parts": [
            "ryzen-7-7800x3d",
            "rtx-4080-super",
            "corsair-vengeance-rgb-32gb-ddr5-6000",
            "asus-tuf-gaming-b650-plus",
            "corsair-rm850x",
            "nzxt-h7",
            "nzxt-kraken-360",
            "samsung-990-pro-2tb",
        ],
        "common": {"psu_wattage": 850, "estimated_draw_w": 620},
        "extra": {
            "target_resolution": "1440p",
            "target_fps": 165,
            "os": "Windows 11",
            "monitor_included": False,
        },
    },
]

# --- Benchmarks (component slug, game, game_fa, resolution, preset, avg, p1_low) --

BENCHMARKS = [
    # RTX 4060
    ("rtx-4060", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1080p", "high", 78, 56),
    ("rtx-4060", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1440p", "high", 42, 31),
    ("rtx-4060", "Counter-Strike 2", "کانتر استرایک ۲", "1080p", "high", 240, 168),
    ("rtx-4060", "Elden Ring", "الدن رینگ", "1080p", "max", 88, 62),
    ("rtx-4060", "Forza Horizon 5", "فورزا هورایزن ۵", "1080p", "ultra", 112, 84),
    ("rtx-4060", "Call of Duty", "کال اف دیوتی", "1080p", "high", 145, 96),
    # RTX 4070 SUPER
    ("rtx-4070-super", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1080p", "high", 112, 82),
    ("rtx-4070-super", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1440p", "high", 68, 49),
    ("rtx-4070-super", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "4k", "high", 33, 24),
    ("rtx-4070-super", "Counter-Strike 2", "کانتر استرایک ۲", "1440p", "high", 320, 224),
    ("rtx-4070-super", "Elden Ring", "الدن رینگ", "1440p", "max", 128, 92),
    ("rtx-4070-super", "Forza Horizon 5", "فورزا هورایزن ۵", "1440p", "ultra", 158, 118),
    ("rtx-4070-super", "Call of Duty", "کال اف دیوتی", "1440p", "high", 196, 132),
    # RTX 4080 SUPER
    ("rtx-4080-super", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1440p", "high", 98, 71),
    ("rtx-4080-super", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "4k", "high", 48, 35),
    ("rtx-4080-super", "Forza Horizon 5", "فورزا هورایزن ۵", "4k", "ultra", 144, 108),
    ("rtx-4080-super", "Elden Ring", "الدن رینگ", "4k", "max", 95, 71),
    # RX 7600
    ("rx-7600", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1080p", "high", 62, 44),
    ("rx-7600", "Forza Horizon 5", "فورزا هورایزن ۵", "1080p", "ultra", 96, 71),
    ("rx-7600", "Counter-Strike 2", "کانتر استرایک ۲", "1080p", "high", 215, 152),
    # RX 7800 XT
    ("rx-7800-xt", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1080p", "high", 94, 68),
    ("rx-7800-xt", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1440p", "high", 56, 41),
    ("rx-7800-xt", "Forza Horizon 5", "فورزا هورایزن ۵", "1440p", "ultra", 142, 105),
    ("rx-7800-xt", "Counter-Strike 2", "کانتر استرایک ۲", "1440p", "high", 300, 210),
    # CPUs (CPU-limited games, no GPU noted in the rig)
    ("ryzen-7-7800x3d", "Counter-Strike 2", "کانتر استرایک ۲", "1080p", "high", 310, 235),
    ("ryzen-7-7800x3d", "Elden Ring", "الدن رینگ", "1440p", "max", 142, 104),
    ("ryzen-5-7600", "Counter-Strike 2", "کانتر استرایک ۲", "1080p", "high", 245, 180),
    ("core-i5-13400f", "Counter-Strike 2", "کانتر استرایک ۲", "1080p", "high", 232, 168),
    ("core-i7-14700k", "Counter-Strike 2", "کانتر استرایک ۲", "1080p", "high", 298, 224),
    ("ryzen-9-7950x", "Elden Ring", "الدن رینگ", "1440p", "max", 138, 101),
    # Prebuilts — system-level numbers
    ("tb-prebuilt-vanguard-1080", "Counter-Strike 2", "کانتر استرایک ۲", "1080p", "high", 305, 231),
    ("tb-prebuilt-vanguard-1080", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1080p", "high", 76, 55),
    ("tb-prebuilt-phantom-1440", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1440p", "high", 66, 48),
    ("tb-prebuilt-phantom-1440", "Forza Horizon 5", "فورزا هورایزن ۵", "1440p", "ultra", 155, 116),
    ("tb-prebuilt-apex-4k", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "4k", "high", 47, 34),
    ("tb-prebuilt-valor-1440", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1440p", "high", 64, 46),
    ("tb-prebuilt-legend-1440", "Cyberpunk 2077", "سایبرپانک ۲۰۷۷", "1440p", "high", 54, 39),
    ("tb-prebuilt-striker-1080", "Counter-Strike 2", "کانتر استرایک ۲", "1080p", "high", 236, 172),
]

# --- Compatibility rules -----------------------------------------------------

RULES: list[RuleSeed] = [
    {
        "code": "SOCKET_MATCH",
        "category_a": "cpu",
        "category_b": "motherboard",
        "description": "CPU and motherboard must share the same socket",
        "description_fa": "سوکت پردازنده و مادربرد باید یکسان باشد",
        "params": {},
        "severity": "block",
        "order": 10,
    },
    {
        "code": "RAM_TYPE_MATCH",
        "category_a": "ram",
        "category_b": "motherboard",
        "description": "Memory type (DDR4/DDR5) must match the motherboard",
        "description_fa": "نوع حافظه (DDR4/DDR5) باید با مادربرد مطابقت داشته باشد",
        "params": {},
        "severity": "block",
        "order": 20,
    },
    {
        "code": "PSU_WATTAGE",
        "category_a": "psu",
        "category_b": "prebuilt",
        "description": "PSU wattage must cover estimated draw with headroom",
        "description_fa": "توان منبع تغذیه باید با حاشیه اطمینان کافی باشد",
        "params": {"headroom_ratio": 1.25},
        "severity": "block",
        "order": 30,
    },
    {
        "code": "GPU_CLEARANCE",
        "category_a": "case",
        "category_b": "gpu",
        "description": "GPU length and cooler height must fit the case",
        "description_fa": "طول کارت گرافیک و ارتفاع خنک‌کننده باید در کیس جا شود",
        "params": {},
        "severity": "block",
        "order": 40,
    },
    {
        "code": "COOLER_SUPPORT",
        "category_a": "cooler",
        "category_b": "cpu",
        "description": "CPU cooler must support the CPU socket",
        "description_fa": "خنک‌کننده باید از سوکت پردازنده پشتیبانی کند",
        "params": {},
        "severity": "block",
        "order": 50,
    },
    {
        "code": "PSU_CONNECTORS",
        "category_a": "psu",
        "category_b": "gpu",
        "description": "PSU must provide the connectors the GPU needs",
        "description_fa": "منبع تغذیه باید کانکتورهای موردنیاز کارت گرافیک را داشته باشد",
        "params": {},
        "severity": "warn",
        "order": 60,
    },
    {
        "code": "PREBUILT_FIT",
        "category_a": "prebuilt",
        "category_b": "prebuilt",
        "description": "A prebuilt's own spec must be self-consistent",
        "description_fa": "مشخصات داخلی سیستم آماده باید با هم سازگار باشند",
        "params": {},
        "severity": "warn",
        "order": 70,
    },
]


class Command(BaseCommand):
    help = "Seed realistic demo data (CPUs, GPUs, RAM, boards, PSUs, cases, prebuilt PCs)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete existing catalog data before seeding (benchmarks and rules are re-created).",
        )
        parser.add_argument(
            "--demo-only",
            action="store_true",
            help="Skip wiping; only create what is missing (default behaviour).",
        )

    @transaction.atomic
    def handle(self, *args: object, **options: object) -> None:
        if options.get("clear"):
            self.stdout.write("Clearing existing demo data…")
            Benchmark.objects.all().delete()
            Product.objects.all().delete()
            ComponentSpec.objects.all().delete()
            Entity.objects.all().delete()
            Brand.objects.all().delete()
            Category.objects.all().delete()
            CompatibilityRule.objects.all().delete()

        brands = self._seed_brands()
        categories = self._seed_categories()
        self._seed_rules()
        self._seed_entities(brands, categories)
        self._seed_prebuilts(brands, categories)
        self._seed_products()
        self._seed_benchmarks()

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded: {Brand.objects.count()} brands, {Category.objects.count()} categories, "
                f"{Entity.objects.count()} entities, {Product.objects.count()} products, "
                f"{Benchmark.objects.count()} benchmarks, {CompatibilityRule.objects.count()} rules."
            )
        )

    # --- seeding steps ------------------------------------------------------

    def _seed_brands(self) -> dict[str, Brand]:
        result: dict[str, Brand] = {}
        for slug, name, name_fa, country in BRANDS:
            brand, _ = Brand.objects.update_or_create(
                slug=slug, defaults={"name": name, "name_fa": name_fa, "country": country}
            )
            result[slug] = brand
        return result

    def _seed_categories(self) -> dict[str, Category]:
        result: dict[str, Category] = {}
        for slug, name, name_fa, _parent in CATEGORIES:
            category, _ = Category.objects.update_or_create(
                slug=slug, defaults={"name": name, "name_fa": name_fa, "parent": None}
            )
            result[slug] = category
        return result

    def _seed_rules(self) -> None:
        for rule in RULES:
            CompatibilityRule.objects.update_or_create(
                code=rule["code"],
                defaults={
                    "category_a": rule["category_a"],
                    "category_b": rule["category_b"],
                    "description": rule["description"],
                    "description_fa": rule["description_fa"],
                    "params": rule["params"],
                    "severity": rule["severity"],
                    "order": rule["order"],
                    "enabled": True,
                },
            )

    def _seed_entities(self, brands: dict[str, Brand], categories: dict[str, Category]) -> None:
        product_titles = {slug: title for _, slug, title, *_ in PRODUCTS}
        for spec in ENTITIES:
            display_title = product_titles.get(spec["slug"], spec["title_fa"])
            aliases = list(
                dict.fromkeys(
                    [
                        *spec.get("aliases", []),
                        spec["title"],
                        spec["title_fa"],
                        display_title,
                    ]
                )
            )
            entity, _ = Entity.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "type": spec["type"],
                    "title": spec["title"],
                    "title_fa": display_title,
                    "aliases": aliases,
                    "summary_fa": spec.get("summary_fa", ""),
                    "summary": spec.get("summary", ""),
                    "status": EntityStatus.PUBLISHED,
                    "brand": brands.get(spec.get("brand", "")),
                    "category": categories.get(spec.get("category", "")),
                    # Stale-content tracking: due for review in 60 days.
                    "review_by": date.today() + timedelta(days=60),
                },
            )
            ComponentSpec.objects.update_or_create(
                entity=entity,
                defaults={
                    "category": spec["type"],
                    "common": spec.get("common", {}),
                    "extra": spec.get("extra", {}),
                },
            )

    def _seed_prebuilts(self, brands: dict[str, Brand], categories: dict[str, Category]) -> None:
        for spec in PREBUILTS:
            aliases = list(dict.fromkeys([spec["title"], spec["title_fa"]]))
            entity, _ = Entity.objects.update_or_create(
                slug=spec["slug"],
                defaults={
                    "type": EntityType.PREBUILT,
                    "title": spec["title"],
                    "title_fa": spec["title_fa"],
                    "summary_fa": spec.get("summary_fa", ""),
                    "summary": spec.get("summary_fa", ""),
                    "status": EntityStatus.PUBLISHED,
                    "brand": brands.get("amd"),  # house brand placeholder; see DECISIONS
                    "category": categories.get("prebuilts"),
                    "aliases": aliases,
                    "review_by": date.today() + timedelta(days=60),
                },
            )
            ComponentSpec.objects.update_or_create(
                entity=entity,
                defaults={
                    "category": EntityType.PREBUILT,
                    "common": {
                        **spec.get("common", {}),
                        "components": spec["parts"],
                    },
                    "extra": spec.get("extra", {}),
                },
            )

    def _seed_products(self) -> None:
        now = timezone.now()
        for sku, entity_slug, title_fa, price, stock, warranty in PRODUCTS:
            entity = Entity.objects.get(slug=entity_slug)
            Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "entity": entity,
                    "title": entity.title,
                    "title_fa": title_fa,
                    "price": Decimal(price),
                    "currency": "IRT",
                    "stock": stock,
                    "warranty_months": warranty,
                    "source": "seed",
                    "is_active": True,
                    "price_updated_at": now,
                },
            )

        for spec in PREBUILTS:
            entity = Entity.objects.get(slug=spec["slug"])
            # Older seeds used a doubled prefix ("tb-sku-prebuilt-…"); drop
            # those rows so the catalog holds one SKU per prebuilt.
            Product.objects.filter(sku__startswith="tb-sku-prebuilt-").delete()
            Product.objects.update_or_create(
                sku="tb-sku-" + spec["slug"].removeprefix("tb-prebuilt-"),
                defaults={
                    "entity": entity,
                    "title": entity.title,
                    "title_fa": spec["title_fa"],
                    "price": Decimal(spec["price"]),
                    "currency": "IRT",
                    "stock": spec["stock"],
                    "warranty_months": 24,
                    "source": "seed",
                    "is_active": True,
                    "price_updated_at": now,
                },
            )

    def _seed_benchmarks(self) -> None:
        today = date.today()
        for slug, game, game_fa, resolution, preset, avg, p1_low in BENCHMARKS:
            component = Entity.objects.get(slug=slug)
            Benchmark.objects.update_or_create(
                component=component,
                game=game,
                resolution=resolution,
                preset=preset,
                tested_at=today,
                defaults={
                    "game_fa": game_fa,
                    "avg_fps": avg,
                    "p1_low": p1_low,
                    "test_rig": {"source": "demo-seed", "note": "demo measurement"},
                    "source": "seed",
                },
            )
