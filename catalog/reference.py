"""
Statik reference ma'lumotlar — `lib/data/uzellar.ts` ning AYNAN nusxasi.
Seed buyrug'i va zapravka aniqlash (resolve) shu yerdan foydalanadi.
"""

UZELLAR = [
    {"id": "rju-toshkent", "name": "РЖУ-Тошкент", "slug": "rju-toshkent",
     "description": "Markaziy uzel", "icon": "LayoutGrid"},
    {"id": "rju-qoqon", "name": "РЖУ-Қўқон", "slug": "rju-qoqon",
     "description": "Vodiy tarmog'i", "icon": "Network"},
    {"id": "rju-buxoro", "name": "РЖУ-Бухоро", "slug": "rju-buxoro",
     "description": "Tarixiy yo'nalish", "icon": "History"},
    {"id": "rju-qongirot", "name": "РЖУ-Кунғирот", "slug": "rju-qongirot",
     "description": "Shimoliy ufq", "icon": "Compass"},
    {"id": "rju-qarshi", "name": "РЖУ-Қарши", "slug": "rju-qarshi",
     "description": "Janubiy hudud", "icon": "MapPin"},
    {"id": "rju-termiz", "name": "РЖУ-Термиз", "slug": "rju-termiz",
     "description": "Chegara stansiyasi", "icon": "Flag"},
]

ZAPRAVKALAR = [
    # РЖУ-Тошкент
    {"id": "toshkent", "uzelId": "rju-toshkent", "name": "Toshkent", "slug": "toshkent"},
    {"id": "angren", "uzelId": "rju-toshkent", "name": "Angren", "slug": "angren"},
    {"id": "sirdaryo", "uzelId": "rju-toshkent", "name": "Sirdaryo", "slug": "sirdaryo"},
    {"id": "hovos", "uzelId": "rju-toshkent", "name": "Hovos", "slug": "hovos"},
    {"id": "jizzax", "uzelId": "rju-toshkent", "name": "Jizzax", "slug": "jizzax"},
    # РЖУ-Қўқон
    {"id": "andijon", "uzelId": "rju-qoqon", "name": "Andijon", "slug": "andijon"},
    {"id": "qoqon", "uzelId": "rju-qoqon", "name": "Qoqon", "slug": "qoqon"},
    {"id": "marglon", "uzelId": "rju-qoqon", "name": "Marg'ilon", "slug": "marglon"},
    # РЖУ-Бухоро
    {"id": "samarqand", "uzelId": "rju-buxoro", "name": "Samarqand", "slug": "samarqand"},
    {"id": "ziyovuddin", "uzelId": "rju-buxoro", "name": "Ziyovuddin", "slug": "ziyovuddin"},
    {"id": "buxoro", "uzelId": "rju-buxoro", "name": "Buxoro", "slug": "buxoro"},
    {"id": "tinchlik", "uzelId": "rju-buxoro", "name": "Tinchlik", "slug": "tinchlik"},
    {"id": "uchquduq", "uzelId": "rju-buxoro", "name": "Uchquduq", "slug": "uchquduq"},
    # РЖУ-Кунғирот
    {"id": "qongirot", "uzelId": "rju-qongirot", "name": "Qo'ng'irot", "slug": "qongirot"},
    {"id": "urganch", "uzelId": "rju-qongirot", "name": "Urganch", "slug": "urganch"},
    {"id": "miskin", "uzelId": "rju-qongirot", "name": "Miskin", "slug": "miskin"},
    # РЖУ-Қарши
    {"id": "qarshi", "uzelId": "rju-qarshi", "name": "Qarshi", "slug": "qarshi"},
    # РЖУ-Термиз
    {"id": "termez", "uzelId": "rju-termiz", "name": "Termiz", "slug": "termez"},
    {"id": "darband", "uzelId": "rju-termiz", "name": "Darband", "slug": "darband"},
    {"id": "qumqurgon", "uzelId": "rju-termiz", "name": "Qumqurg'on", "slug": "qumqurgon"},
]

# Login'da zapravka nomini aniqlash uchun taxalluslar (login page bilan bir xil)
ZAPRAVKA_KEY_ALIASES = {
    "margilon": "marglon",
    "qumqorgon": "qumqurgon",
    "termiz": "termez",
}

# Seed: settings/global hujjati (app/seed/page.tsx bilan bir xil)
SETTINGS_GLOBAL = {
    "version": "1.0.0",
    "isMaintenance": False,
    "lockoutTime": 60,
    "maxAttempts": 3,
    "stansiyalar": {
        "default": [],
        "toshkent": ["Toshkent-1", "Chuqursoy", "Sergeli", "Nazarbek", "Hamza"],
    },
    "tashkilotlar": {
        "default": [],
        "toshkent": ["UTY", "Avtotrans", "O'zbekiston temir yo'llari", "Yulqurilish"],
    },
    "ijarachilar": {
        "default": [],
        "toshkent": ["Korxona1", "Korxona2", "MCHJ Trans"],
    },
    "manualFields": [
        "Ortildi", "Tranzit", "Almashuv", "Teplovozlar",
        "Karakalpakiya", "Sariog'och", "Hojidavlat",
    ],
    "manualFieldsTemplate": [
        {"key": "ortildi", "label": "Ortildi", "type": "number", "defaultValue": 0},
        {"key": "tranzit", "label": "Tranzit", "type": "number", "defaultValue": 0},
        {"key": "almashuv", "label": "Almashuv", "type": "text", "defaultValue": ""},
        {"key": "teplovozlar", "label": "Teplovozlar", "type": "text", "defaultValue": ""},
    ],
}

# Seed: default questions (app/seed/page.tsx bilan bir xil)
DEFAULT_QUESTIONS = [
    {"category": "lokomotiv", "label": "1. HARAKAT TURI", "fieldKey": "harakatTuri",
     "fieldType": "dropdown", "options": ["yuk", "yolovchi", "manyovr", "xojalik", "ijara"],
     "isRequired": True, "isVisible": True, "order": 0},
    {"category": "lokomotiv", "label": "2. SERIYA", "fieldKey": "rusumi",
     "fieldType": "dropdown", "options": ["TEM2", "ChME3", "2TE10M", "TEP70BS"],
     "isRequired": True, "isVisible": True, "order": 1},
    {"category": "lokomotiv", "label": "3. LOKOMOTIV N", "fieldKey": "lokomotivNumber",
     "fieldType": "text", "options": [], "isRequired": True, "isVisible": True, "order": 2},
    {"category": "lokomotiv", "label": "4. QOLDIQ (kg)", "fieldKey": "qoldiq",
     "fieldType": "number", "options": [], "isRequired": True, "isVisible": True, "order": 3},
    {"category": "lokomotiv", "label": "5. BERILDI (kg)", "fieldKey": "qanchaBerildi",
     "fieldType": "number", "options": [], "isRequired": True, "isVisible": True, "order": 4},
    {"category": "lokomotiv", "label": "6. DIZ MASLA (kg)", "fieldKey": "dizMasla",
     "fieldType": "number", "options": [], "isRequired": True, "isVisible": True, "order": 5},
]


# ── Lokomotiv raqamlari ─────────────────────────────────────────────────────
# ТЯГА formasidagi «Локомотив рақами» maydoni uchun ruxsat etilgan raqamlar.
#
# Bu — BOSHLANG'ICH (seed) ro'yxat. Haqiqiy manba — `settings/lokomotivRaqamlari`
# hujjati (Setting modeli): admin uni API orqali o'zgartira oladi va o'sha
# qiymat ustun turadi. Bu ro'yxat faqat seed va zaxira (fallback) uchun.
#
# Frontenddagi nusxasi: lib/data/lokomotiv-raqamlari.ts — ikkalasi bir xil.
LOKOMOTIV_RAQAMLARI = [
    "003", "023", "035", "1066", "3172", "0817", "0847", "0930",
    "0932", "0956", "0959", "0960", "1103", "1109", "1111", "1500",
    "1709", "1795", "1959", "2309", "2393", "2591", "2711", "2712",
    "2774", "2776", "2777", "3035", "3037", "3091", "3152", "3200",
    "3201", "3312", "3314", "3318", "3320", "5809", "5810", "6078",
    "6082", "6101", "6104", "6294", "6295", "6316", "6373", "6374",
    "6560", "6563", "6572", "6583", "6606", "6655", "6656", "6716",
    "6770", "6773", "6793", "7050", "7078", "7083", "7084", "7086",
    "7090", "7099", "7100", "7217", "0116", "0118", "010", "1123",
    "0298", "1151", "3286", "6824", "6445", "6524", "6540", "7028",
    "4275", "4426", "4440", "4453", "4674", "4703", "5052", "5139",
    "5165", "5167", "5215", "5656", "5774", "5928", "5929", "6097",
    "6101", "6110", "046", "184", "2001", "2002", "2003", "2004",
    "2008", "002", "007", "036", "037", "038", "040", "001",
    "003", "004", "012", "014", "017", "018", "023", "024",
    "027", "2159", "2556", "5808", "6369", "6562", "6827", "7396",
    "4679", "4874", "5160", "5429", "5934", "020", "041", "003",
    "004", "0961", "2778", "3198", "6102", "6311", "6776", "7651",
    "7409", "6812", "4159", "4285", "4286", "4292", "4420", "4422",
    "4443", "4551", "4557", "4561", "4664", "4836", "4877", "5015",
    "5185", "5224", "5434", "5942", "6081", "6806", "101", "103",
    "132", "140", "160", "2005", "2006", "2007", "005", "006",
    "025", "026", "033", "039", "013", "019", "1205", "5047",
    "1716", "2308", "2310", "2557", "2710", "3256", "6313", "6662",
    "6731", "6790", "6826", "7077", "7118", "181", "0236", "2989",
    "1302", "029", "034", "042", "0964", "1105", "1963", "2306",
    "3003", "3005", "3151", "5773", "5774", "6584", "6718", "6729",
    "6825", "7057", "7087", "7091", "047", "0707", "0708", "1061",
    "1141", "1146", "1152", "1193", "2337", "2716", "3265", "3662",
    "007", "009", "021", "022", "031", "008", "032", "0473",
    "0955", "1715", "1793", "1794", "2170", "3088", "3089", "3176",
    "3199", "3315", "5775", "6103", "6370", "6490", "6561", "6607",
    "6727", "7055", "7650", "8478", "152", "015", "016", "031",
    "7420", "6541", "4556", "4818", "4834", "5029", "5171",
]
