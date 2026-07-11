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
