"""
Наполнение справочников: UOM, типы упаковки, бренды FMCG / супермаркетов, типы товаров.

Использование:
    python -m product_db.scripts.seed_refs
"""
import psycopg2
import psycopg2.extras

from product_db.config import settings


# ---------------------------------------------------------------------------
# UOM
# ---------------------------------------------------------------------------
_UOM = [
    ("ml",  "мл",  "l",   0.001),
    ("l",   "л",   "l",   1.0),
    ("g",   "г",   "kg",  0.001),
    ("kg",  "кг",  "kg",  1.0),
    ("pcs", "шт",  None,  None),
]

# ---------------------------------------------------------------------------
# Package types
# ---------------------------------------------------------------------------
_PACKAGE_TYPES = [
    ("PET",   "ПЭТ-бутылка"),
    ("GLASS", "Стеклянная бутылка / банка"),
    ("TETRA", "Тетрапак"),
    ("BAG",   "Пакет"),
    ("CAN",   "Жестяная банка"),
    ("BOX",   "Картонная коробка"),
    ("TUBE",  "Тюбик"),
    ("SACHET","Саше / пакетик"),
    ("WRAP",  "Обёртка"),
    ("BOTTLE","Флакон"),
]

# ---------------------------------------------------------------------------
# Brands: (canonical_name, [aliases])
# ---------------------------------------------------------------------------
_BRANDS = [
    # Напитки и вода
    ("NESTLE",            ["Nestle", "Нестле", "nestle", "НЕСТЛЕ"]),
    ("COCA-COLA",         ["Coca Cola", "CocaCola", "Кока-Кола", "Кока Кола", "coca-cola", "coca cola"]),
    ("PEPSI",             ["Pepsi", "Пепси", "PepsiCo"]),
    ("SPRITE",            ["Sprite", "Спрайт"]),
    ("FANTA",             ["Fanta", "Фанта"]),
    ("7UP",               ["7 Up", "Seven Up", "7 Ап", "Севен Ап"]),
    ("MIRINDA",           ["Mirinda", "Миринда"]),
    ("MOUNTAIN DEW",      ["Mountain Dew", "Маунтин Дью", "Mtn Dew"]),
    ("SCHWEPPES",         ["Schweppes", "Швепс", "Швеппс"]),
    ("BURN",              ["Burn", "Бёрн"]),
    ("RED BULL",          ["Red Bull", "Ред Бул", "RedBull"]),
    ("ADRENALINE RUSH",   ["Adrenaline Rush", "Адреналин Раш", "Adrenaline"]),
    ("BONAQUA",           ["BonAqua", "Бонаква", "Bon Aqua"]),
    ("AQUA MINERALE",     ["Aqua Minerale", "Аква Минерале"]),
    ("EVIAN",             ["Evian", "Эвиан"]),
    ("BORJOMI",           ["Borjomi", "Боржоми", "Borjomy"]),
    ("ESSENTUKI",         ["Essentuki", "Ессентуки"]),
    ("NARZAN",            ["Narzan", "Нарзан"]),
    ("MARVARID",          ["Marvarid", "Марварид"]),
    ("FANTOLA",           ["Fantola", "Фантола"]),
    ("ALOE VERA",         ["Aloe Vera", "Алоэ Вера", "АЛОЕ ВЕРА"]),
    ("БАЙКАЛ",            ["Байкал", "Baikal"]),
    ("MONTELLA",          ["Montella", "Монтелла"]),
    ("TROPIC",            ["Tropic", "Тропик"]),
    # Соки и нектары
    ("DOBRY",             ["Добрый", "Dobry"]),
    ("J7",                ["J7", "Джей 7"]),
    ("RICH",              ["Rich", "Рич"]),
    ("TROPICANA",         ["Tropicana", "Тропикана"]),
    ("CAPPY",             ["Cappy", "Каппи"]),
    ("PULPY",             ["Pulpy", "Палпи"]),
    # Чай и кофе
    ("LIPTON",            ["Lipton", "Липтон"]),
    ("GREENFIELD",        ["Greenfield", "Гринфилд", "Green Field"]),
    ("AHMAD TEA",         ["Ahmad Tea", "Ahmad", "Ахмад", "Ахмад Ти"]),
    ("AKBAR",             ["Akbar", "Акбар"]),
    ("TWININGS",          ["Twinings", "Твайнингс"]),
    ("RICHARD",           ["Richard", "Ричард"]),
    ("BESEDA",            ["Беседа", "Beseda"]),
    ("TESS",              ["Tess", "Тесс"]),
    ("NESCAFE",           ["Nescafe", "Нескафе", "Nescafé"]),
    ("JACOBS",            ["Jacobs", "Якобс"]),
    ("MAXWELL HOUSE",     ["Maxwell House", "Максвелл Хаус"]),
    ("CARTE NOIRE",       ["Carte Noire", "Карт Нуар"]),
    ("JARDIN",            ["Jardin", "Жардин"]),
    ("LAVAZZA",           ["Lavazza", "Лавацца"]),
    ("TCHIBO",            ["Tchibo", "Чибо"]),
    # Молочные продукты
    ("DANONE",            ["Danone", "Данон", "Даноне"]),
    ("ACTIVIA",           ["Activia", "Активиа", "Активия"]),
    ("ACTIMEL",           ["Actimel", "Актимель"]),
    ("PROSTOKVASHINO",    ["Простоквашино", "Prostokvashino", "Простоквашено"]),
    ("PRESIDENT",         ["President", "Président", "Президент"]),
    ("EPICA",             ["Epica", "Эпика"]),
    ("EHRMANN",           ["Ehrmann", "Эрманн"]),
    ("VALIO",             ["Valio", "Валио"]),
    ("HOCHLAND",          ["Hochland", "Хохланд"]),
    ("VIOLA",             ["Viola", "Виола"]),
    ("PARMALAT",          ["Parmalat", "Пармалат"]),
    ("CHUDO",             ["Чудо", "Chudo"]),
    ("AGUSHA",            ["Агуша", "Agusha"]),
    ("BIO SUT",           ["Bio Sut", "BIOSUT", "Био Сут"]),
    # Сладости и кондитерка
    ("MILKA",             ["Milka", "Милка"]),
    ("ALPEN GOLD",        ["Alpen Gold", "Альпен Голд", "AlpenGold"]),
    ("TOBLERONE",         ["Toblerone", "Тоблерон"]),
    ("NESQUIK",           ["Nesquik", "Несквик"]),
    ("KITKAT",            ["KitKat", "Kit Kat", "Кит Кат", "Киткат"]),
    ("SNICKERS",          ["Snickers", "Сникерс"]),
    ("TWIX",              ["Twix", "Твикс"]),
    ("MARS",              ["Mars", "Марс"]),
    ("BOUNTY",            ["Bounty", "Баунти"]),
    ("MILKY WAY",         ["Milky Way", "Милки Вэй", "MilkyWay"]),
    ("M&M'S",             ["M&M's", "M&Ms", "Эм энд Эмс"]),
    ("RAFFAELLO",         ["Raffaello", "Рафаэлло", "Rafaello"]),
    ("A4",               ["A4", "А4"]),
    ("FERRERO ROCHER",    ["Ferrero Rocher", "Ферреро Роше", "Ferrero"]),
    ("AFTER EIGHT",       ["After Eight", "Афтер Эйт"]),
    ("DUPLO",             ["Duplo", "Дупло"]),
    ("NUTELLA",           ["Nutella", "Нутелла"]),
    ("KINDER",            ["Kinder", "Киндер"]),
    ("TIC TAC",           ["Tic Tac", "Тик Так", "TicTac"]),
    ("OREO",              ["Oreo", "Орео"]),
    ("BARNI",             ["Barni", "Барни"]),
    ("CADBURY",           ["Cadbury", "Кэдбери"]),
    ("FRUIT-TELLA",       ["Fruit-Tella", "Fruit Tella", "Фрут-Телла"]),
    ("MELLER",            ["Meller", "Меллер"]),
    ("CHUPA CHUPS",       ["Chupa Chups", "Чупа Чупс", "ChupaChups"]),
    ("HARIBO",            ["Haribo", "Харибо"]),
    ("MENTOS",            ["Mentos", "Ментос"]),
    ("SKITTLES",          ["Skittles", "Скитлс"]),
    ("HALLS",             ["Halls", "Холлс"]),
    ("CHOCO PIE",         ["Choco Pie", "Чоко Пай", "Chocopie"]),
    ("TUC",               ["Tuc", "Тук"]),
    ("TORKU",             ["Torku", "ТОРКУ"]),
    ("BELVITA",           ["Belvita", "Белвита"]),
    ("YASHKINO",          ["Яшкино", "Yashkino"]),
    ("KORKUNOV",          ["Коркунов", "Korkunov"]),
    ("BABAEVSKY",         ["Бабаевский", "Babaevsky"]),
    ("ROT FRONT",         ["Рот Фронт", "РОТФРОНТ", "Rot Front"]),
    ("ALYONKA",           ["Алёнка", "Аленка", "Alyonka", "Alenka"]),
    # Снеки
    ("PRINGLES",          ["Pringles", "Принглс"]),
    ("FINN CRISP",        ["Finn Crisp", "Финн Крисп"]),
    ("LAY'S",             ["Lay's", "Lays", "Лэйс", "Лейс"]),
    ("DORITOS",           ["Doritos", "Доритос"]),
    ("CHEETOS",           ["Cheetos", "Читос"]),
    ("ESTRELLA",          ["Estrella", "Эстрелла"]),
    ("ORBIT",             ["Orbit", "Орбит"]),
    ("DIROL",             ["Dirol", "Дирол"]),
    # Бакалея, соусы, консервация
    ("HEINZ",             ["Heinz", "Хайнц"]),
    ("HELLMANN'S",        ["Hellmann's", "Hellmanns", "Хеллманс"]),
    ("CALVE",             ["Calve", "Calvé", "Кальве"]),
    ("KNORR",             ["Knorr", "Кнорр"]),
    ("MAGGI",             ["Maggi", "Магги"]),
    ("BONDUELLE",         ["Bonduelle", "Бондюэль"]),
    ("MAHEEV",            ["Махеев", "Махеевъ", "Maheev"]),
    ("СОЮЗ ПИЩЕПРОМ",     ["Союзпищепром", "Soyuz Pischeprom", "SoyuzPischeprom"]),
    ("МЕЛЬКОМБИНАТ",      ["Мелькомбинат", "Melkombinat"]),
    ("SLOBODA",           ["Слобода", "Sloboda"]),
    ("MAKFA",             ["Makfa", "Макфа"]),
    ("BARILLA",           ["Barilla", "Барилла"]),
    ("DARBO",             ["Darbo", "Дарбо"]),
    ("UVELKA",            ["Увелка", "Uvelka"]),
    ("YARMARKA",          ["Ярмарка", "Yarmarka"]),
    ("MISTRAL",           ["Mistral", "Мистраль"]),
    # Бытовая химия
    ("ARIEL",             ["Ariel", "Ариэль"]),
    ("TIDE",              ["Tide", "Тайд"]),
    ("PERSIL",            ["Persil", "Персил"]),
    ("FAIRY",             ["Fairy", "Фэйри"]),
    ("PRIL",              ["Pril", "Прил"]),
    ("FINISH",            ["Finish", "Финиш"]),
    ("VANISH",            ["Vanish", "Ваниш"]),
    ("CILLIT BANG",       ["Cillit Bang", "Cillit", "Силлит"]),
    ("DOMESTOS",          ["Domestos", "Доместос"]),
    ("MR. PROPER",        ["Mr. Proper", "Mr Proper", "Мистер Пропер"]),
    ("SYNERGETIC",        ["Synergetic", "Синергетик"]),
    ("SORTI",             ["Sorti", "Сорти"]),
    ("SANFOR",            ["Sanfor", "Санфор"]),
    ("SANITA",            ["Sanita", "sanita"]),
    ("BIS",               ["Bis", "bis"]),
    ("ЧИСТИН",            ["Чистин", "Chistin"]),
    ("БОЛЬШАЯ СТИРКА",    ["Bolshaya Stirka", "Большая стирка"]),
    ("ABC",               ["Abc", "abc"]),
    ("BINGO",             ["Bingo", "bingo"]),
    ("ELMA",              ["Elma", "elma"]),
    ("IRMA",              ["Irma", "irma"]),
    # Бумажные товары
    ("ZEWA",              ["Zewa", "Зева"]),
    ("PAPIA",             ["Papia", "Папия"]),
    ("KLEENEX",           ["Kleenex", "Клинекс"]),
    # Средства гигиены
    ("PAMPERS",           ["Pampers", "Памперс"]),
    ("HUGGIES",           ["Huggies", "Хаггис"]),
    ("HEAD & SHOULDERS",  ["Head & Shoulders", "Head and Shoulders", "Хэд энд Шолдерс"]),
    ("PANTENE",           ["Pantene", "Пантин", "Pantene Pro-V"]),
    ("DOVE",              ["Dove", "Дав"]),
    ("REXONA",            ["Rexona", "Рексона"]),
    ("AXE",               ["Axe", "Акс"]),
    ("GILLETTE",          ["Gillette", "Жиллетт"]),
    ("TRESEMME",          ["Tresemme", "TRESemme", "Тресемме"]),
    ("CLEAR",             ["Clear", "Клиар"]),
    ("ORAL-B",            ["Oral-B", "Oral B", "Орал Би"]),
    ("COLGATE",           ["Colgate", "Колгейт"]),
    ("SIGNAL",            ["Signal", "Сигнал"]),
    ("JOHNSON'S",         ["Johnson's", "Johnsons", "Джонсонс", "Johnson's Baby"]),
    ("NIVEA",             ["Nivea", "Нивея"]),
    ("Я САМАЯ",           ["Я Самая", "Ya Samaya", "YA SAMAYA"]),
    ("PALMOLIVE",         ["Palmolive", "Палмолив"]),
    ("FA",                ["Fa", "Фа"]),
    ("SCHAUMA",           ["Schauma", "Шаума"]),
    ("SPLAT",             ["Splat", "СПЛАТ"]),
    ("FREESTYLE",         ["Freestyle", "Free Style", "Фристайл", "free style"]),
    ("ALWAYS",            ["Always", "Allways", "All Ways", "Олвейс"]),
    ("ATIRGUL",           ["Atirgul", "Атиргул"]),
    ("ONAJON",            ["Onajon", "Онажон"]),
    # Детское питание
    ("HIPP",              ["HiPP", "Хипп", "Hipp"]),
    ("NUTRILON",          ["Nutrilon", "Нутрилон"]),
    ("NAN",               ["Nan", "Нан"]),
    ("NESTOGEN",          ["Nestogen", "Нестожен"]),
    ("FRUTO NYANYA",      ["ФрутоНяня", "Фруто Няня", "Fruto Nyanya"]),
    ("GERBER",            ["Gerber", "Гербер"]),
    # Корм для животных
    ("PEDIGREE",          ["Pedigree", "Педигри"]),
    ("WHISKAS",           ["Whiskas", "Вискас"]),
    ("FELIX",             ["Felix", "Феликс"]),
    ("SHEBA",             ["Sheba", "Шеба"]),
    ("GOURMET",           ["Gourmet", "Гурмэ"]),
    ("PURINA",            ["Purina", "Пурина"]),
    ("ROYAL CANIN",       ["Royal Canin", "Роял Канин"]),
    ("CHAPPI",            ["Chappi", "Чаппи"]),
    ("AKA UCALAR",        ["Aka Ucalar", "Aka Ukalar", "Ака Учалар", "Ака Укалар"]),
    ("BLACK BEAR",        ["Black Bear", "Блэк Бир"]),
    ("TOZA",              ["Toza", "Тоза"]),
    ("ЛАВАНСАЛЬ",         ["Лавансаль", "Lavansal", "Lavansal'"]),
    ("FORSITE",           ["Forsite", "forsite"]),
    ("KRENDA",            ["Krenda", "krenda"]),
    ("ALPENGURT",         ["Alpengurt", "Алпенгурт"]),
    ("FINI",              ["Fini", "Фини"]),
    ("RED BAND",          ["Red Band", "Ред Бэнд"]),
    ("БАЛТИМОР",          ["Балтимор", "Baltimor"]),
    ("ЧИСТАЯ ЛИНИЯ",      ["Чистая линия", "Chistaya Liniya"]),
    ("SKIN SHINE",        ["Skin Shine", "skin shine"]),
    ("ЧЕРНЫЙ ЖЕМЧУГ",     ["Черный жемчуг", "Чёрный жемчуг", "Black Pearl"]),
    ("ZULYA BARAKA",      ["Zulya Baraka", "Зуля Барака"]),
    ("ВДОХНОВЕНИЕ",       ["Вдохновение", "Vdohnovenie"]),
    ("TIGER",             ["Tiger", "Тигер"]),
    ("LIMAX",             ["Limax", "Лимакс"]),
    ("BROTHERS",          ["Brothers", "Бразерс"]),
    ("ISTANBUL",          ["Istanbul", "Стамбул"]),
    ("ДАРЫ САХАЛИНА",     ["Дары Сахалина", "Dary Sakhalina"]),
    ("ВЕСНА",             ["Весна", "Vesna"]),
    ("КОНТИ",             ["Конти", "Konti"]),
    ("KUCHENMEISTER",     ["Kuchenmeister", "Кухенмайстер"]),
    ("BUCHERON",          ["Bucheron", "Бушерон"]),
    ("NELINO KIDS",       ["Nelino Kids", "Нелино Кидс"]),
    ("CUSHY BABY",        ["Cushy Baby", "Куши Бэби"]),
    ("ПЕТРОВСКИЕ НИВЫ",   ["Петровские Нивы", "Petrovskie Nivy"]),
    ("МАЙСКИЙ",           ["Майский", "Mayskiy"]),
    ("CURTIS",            ["Curtis", "Кёртис"]),
    ("ПРИПРАВЫЧ",         ["Приправыч", "Pripravych"]),
    ("ЗАЙКА",             ["Зайка", "Zaika"]),
    ("CAPELLA",           ["Capella", "Капелла"]),
    ("OZMO",              ["Ozmo", "Озмо"]),
    ("РАХАТ",             ["Рахат", "Rakhat"]),
    ("ФИШЕ",              ["Фише", "Fishe"]),
    ("TITIZ",             ["Titiz", "Титиз"]),
    ("TORI",              ["Tori", "Тори"]),
    ("YORK",              ["York", "Йорк"]),
    ("AZER SEKER",        ["Azer Seker", "Азер Шекер"]),
    ("FABIO",             ["Fabio", "Фабио"]),
    ("LEIBNIZ",           ["Leibniz", "Лейбниц"]),
    ("MOVENPICK",         ["Mövenpick", "Movenpick", "Мовенпик"]),
    ("DR. OETKER",        ["Dr. Oetker", "Dr Oetker", "Dr.Oetker", "Доктор Эткер"]),
    ("DR. KARG",          ["Dr. Karg", "Dr Karg", "Dr.Karg"]),
    ("BORCHERS",          ["Borchers", "Борчерс"]),
    ("COPPENRATH",        ["Coppenrath", "Коппенрат"]),
    ("RITTER SPORT",      ["Ritter Sport", "Риттер Спорт"]),
    ("ANTON BERG",        ["Anton Berg", "Антон Берг"]),
    ("BAILEYS",           ["Baileys", "Бейлис"]),
    ("VILTOP",            ["Viltop", "Вилтоп"]),
    ("PASABAHCE",         ["Pasabahce", "Пашабахче"]),
    ("BIG BEAR",          ["Big Bear", "Биг Бир"]),
    ("STARLUX",           ["Starlux", "Старлюкс"]),
    ("LURE",              ["Lure", "Лур"]),
    ("ARKO",              ["Arko", "Арко"]),
    ("MR. GROCC",         ["Mr. Grocc", "MR GROCC", "Mr Grocc", "Мр Грок", "Мистер Грок"]),
    ("ОТ ОЛЕГА",          ["От Олега", "OT OLEGA"]),
    ("ВЫГОДНАЯ УБОРКА",   ["Выгодная уборка", "Vygodnaya Uborka"]),
    ("УХХ",               ["УХХ", "UXX", "Ухх"]),
]

# ---------------------------------------------------------------------------
# Product types: (name_ru, [keywords_ru], name_uz_latn, name_uz_cyrl)
# ---------------------------------------------------------------------------
_PRODUCT_TYPES = [
    # Вода и напитки
    ("Вода питьевая",           ["вода", "питьевая", "минеральная", "артезианская", "природная"],
     "Ichimlik suv", "Ичимлик сув"),
    ("Напиток газированный",    ["газированный", "газировка", "лимонад", "сода"],
     "Gazlangan ichimlik", "Газланган ичимлик"),
    ("Напиток негазированный",  ["негазированный", "still"],
     "Gazlanmagan ichimlik", "Газланмаган ичимлик"),
    ("Сок фруктовый",           ["сок", "фруктовый", "яблочный", "апельсиновый", "виноградный"],
     "Meva sharbati", "Мева шарбати"),
    ("Нектар фруктовый",        ["нектар", "фруктовый"],
     "Meva nektari", "Мева нектари"),
    ("Сок томатный",            ["сок", "томатный"],
     "Pomidor sharbati", "Помидор шарбати"),
    ("Энергетический напиток",  ["энергетик", "энергетический", "energy"],
     "Energetik ichimlik", "Энергетик ичимлик"),
    ("Квас",                    ["квас"],
     "Kvas", "Квас"),
    ("Пиво",                    ["пиво", "beer", "ale", "светлое", "тёмное"],
     "Pivo", "Пиво"),
    # Чай и кофе
    ("Чай чёрный",              ["чай", "чёрный", "black", "байховый"],
     "Qora choy", "Қора чой"),
    ("Чай зелёный",             ["чай", "зелёный", "green"],
     "Yashil choy", "Яшил чой"),
    ("Чай травяной",            ["чай", "травяной", "herbal", "ромашка", "мята"],
     "O't choyi", "Ўт чойи"),
    ("Холодный чай",            ["холодный", "ice", "iced", "чайный"],
     "Sovuq choy", "Совуқ чой"),
    ("Готовый завтрак",         ["завтрак", "хлопья", "мюсли", "cereal"],
     "Tayyor nonushta", "Тайёр нонушта"),
    ("Кофе растворимый",        ["кофе", "растворимый", "instant"],
     "Eruvchan qahva", "Эрувчан қаҳва"),
    ("Кофе молотый",            ["кофе", "молотый", "ground"],
     "Maydalangan qahva", "Майдаланган қаҳва"),
    ("Кофе в зёрнах",           ["кофе", "зёрнах", "зерновой", "beans"],
     "Don qahva", "Дон қаҳва"),
    ("Какао",                   ["какао", "cocoa"],
     "Kakao", "Какао"),
    ("Цикорий",                 ["цикорий", "chicory"],
     "Tsikoriy", "Цикорий"),
    ("Взбитые сливки",          ["взбитые", "сливки", "whipped cream"],
     "Ko'pirtirilgan qaymoq", "Кўпиртирилган қаймоқ"),
    # Молочные продукты
    ("Молоко",                  ["молоко", "молочный", "ультрапастеризованное", "пастеризованное"],
     "Sut", "Сут"),
    ("Кефир",                   ["кефир"],
     "Kefir", "Кефир"),
    ("Йогурт",                  ["йогурт", "yogurt", "катык", "katyk"],
     "Yogurt", "Йогурт"),
    ("Сметана",                 ["сметана"],
     "Qaymoq", "Қаймоқ"),
    ("Творог",                  ["творог", "творожный"],
     "Tvorog", "Творог"),
    ("Масло сливочное",         ["масло", "сливочное", "butter"],
     "Sariyog'", "Сарийоғ"),
    ("Сыр твёрдый",             ["сыр", "твёрдый", "полутвёрдый", "cheese"],
     "Qattiq pishloq", "Қаттиқ пишлоқ"),
    ("Сыр плавленый",           ["сыр", "плавленый", "processed"],
     "Erigan pishloq", "Эриган пишлоқ"),
    ("Мороженое",               ["мороженое", "ice cream", "пломбир", "сорбет"],
     "Muzqaymoq", "Музқаймоқ"),
    # Масла
    ("Масло подсолнечное",      ["масло", "подсолнечное", "растительное", "sunflower"],
     "Kungaboqar moyi", "Кунгабоқар мойи"),
    ("Масло оливковое",         ["масло", "оливковое", "olive"],
     "Zaytun moyi", "Зайтун мойи"),
    ("Маргарин",                ["маргарин", "margarine"],
     "Margarin", "Маргарин"),
    # Крупы, мука, макароны
    ("Крупа рисовая",           ["рис", "рисовая"],
     "Guruch", "Гуруч"),
    ("Крупа гречневая",         ["гречка", "гречневая", "buckwheat"],
     "Grechka", "Гречка"),
    ("Крупа манная",            ["манная", "манка", "semolina"],
     "Manniy yorma", "Манний ёрма"),
    ("Овсяные хлопья",          ["овсяные", "хлопья", "овсянка", "oats"],
     "Suli", "Сули"),
    ("Мука пшеничная",          ["мука", "пшеничная", "flour"],
     "Bug'doy uni", "Буғдой уни"),
    ("Макаронные изделия",      ["макароны", "паста", "спагетти", "pasta", "лапша"],
     "Makaron", "Макарон"),
    # Сахар, соль, специи
    ("Сахар",                   ["сахар", "sugar"],
     "Shakar", "Шакар"),
    ("Соль",                    ["соль", "salt"],
     "Tuz", "Туз"),
    ("Специи и приправы",       ["специи", "приправа", "пряности", "приправы"],
     "Ziravorlar", "Зираворлар"),
    ("Перец молотый",           ["перец", "молотый", "pepper"],
     "Qalampir", "Қалампир"),
    # Шоколад и сладости
    ("Шоколад плиточный",       ["шоколад", "chocolate", "чёрный", "молочный", "белый"],
     "Shokolad", "Шоколад"),
    ("Шоколадные конфеты",      ["конфеты", "шоколадные", "пралине"],
     "Shokoladli konfetlar", "Шоколадли конфетлар"),
    ("Карамель",                ["карамель", "леденцы", "caramel"],
     "Karamel", "Карамел"),
    ("Мармелад",                ["мармелад", "желейный", "жевательный", "gummy"],
     "Marmelad", "Мармелад"),
    ("Маршмеллоу",              ["маршмелоу", "marshmallow"],
     "Marshmellou", "Маршмеллоу"),
    ("Жевательная резинка",     ["жвачка", "жевательная", "резинка", "gum"],
     "Saqich", "Сақич"),
    # Печенье, вафли, выпечка
    ("Печенье",                 ["печенье", "cookies", "biscuit"],
     "Pechenye", "Печенье"),
    ("Крекер",                  ["крекер", "cracker", "сэндвич"],
     "Kreker", "Крекер"),
    ("Вафли",                   ["вафли", "вафля", "wafer"],
     "Vafel", "Вафель"),
    ("Торт",                    ["торт", "пирожное", "cake"],
     "Tort", "Торт"),
    ("Кекс",                    ["кекс", "маффин", "muffin"],
     "Keks", "Кекс"),
    ("Хлеб",                    ["хлеб", "bread", "батон", "булка"],
     "Non", "Нон"),
    ("Хлебобулочные изделия",   ["булочка", "выпечка", "пирожок", "рогалик"],
     "Unli mahsulot", "Унли маҳсулот"),
    ("Картофельные полуфабрикаты", ["картофельные", "дольки", "wedges"],
     "Kartoshka yarim tayyor mahsulotlari", "Картошка ярим тайёр маҳсулотлари"),
    # Снеки
    ("Чипсы",                   ["чипсы", "chips"],
     "Chips", "Чипс"),
    ("Снеки и сухарики",        ["снеки", "сухарики", "crackers", "croutons"],
     "Sneklar", "Снеклар"),
    ("Орехи",                   ["орехи", "орех", "nuts", "миндаль", "кешью", "арахис"],
     "Yong'oq", "Ёнғоқ"),
    ("Попкорн",                 ["попкорн", "popcorn"],
     "Popcorn", "Попкорн"),
    # Соусы и консервация
    ("Кетчуп",                  ["кетчуп", "ketchup"],
     "Ketchup", "Кетчуп"),
    ("Майонез",                 ["майонез", "mayo", "mayonnaise"],
     "Mayonez", "Майонез"),
    ("Соус томатный",           ["соус", "томатный", "pasta sauce"],
     "Tomat sousi", "Томат соуси"),
    ("Уксус",                   ["уксус", "vinegar"],
     "Sirka", "Сирка"),
    ("Свежие овощи",            ["помидоры", "томаты", "черри", "овощи"],
     "Yangi sabzavotlar", "Янги сабзавотлар"),
    ("Горчица",                 ["горчица", "mustard"],
     "Xantal", "Хантал"),
    ("Варенье и джем",          ["варенье", "джем", "jam", "конфитюр"],
     "Murabbo", "Мурабbo"),
    ("Мёд",                     ["мёд", "honey"],
     "Asal", "Асал"),
    # Консервы
    ("Консервы рыбные",         ["консервы", "рыбные", "тунец", "сардина", "лосось"],
     "Baliq konservasi", "Балиқ консерваси"),
    ("Консервы мясные",         ["консервы", "мясные", "тушёнка", "паштет"],
     "Go'sht konservasi", "Гўшт консерваси"),
    ("Консервы овощные",        ["консервы", "овощные", "горошек", "кукуруза", "фасоль", "патиссоны"],
     "Sabzavot konservasi", "Сабзавот консерваси"),
    ("Грибы консервированные",  ["грибы", "шампиньоны", "маринованные грибы"],
     "Konservalangan qo'ziqorinlar", "Консерваланган қўзиқоринлар"),
    ("Сырок глазированный",     ["сырок", "глазир", "творожный десерт"],
     "Sirlangan tvorogli batoncha", "Сирланган творогли батонча"),
    ("Икра красная",            ["икра", "красная", "лососевая"],
     "Qizil ikra", "Қизил икра"),
    ("Сгущённое молоко",        ["сгущенка", "сгущёнка", "сгущенное", "сгущенное молоко"],
     "Quyuqlashtirilgan sut", "Қуюқлаштирилган сут"),
    # Мясо и рыба
    ("Колбаса варёная",         ["колбаса", "варёная", "докторская", "молочная"],
     "Qaynatilgan kolbasa", "Қайнатилган колбаса"),
    ("Колбаса сырокопчёная",    ["колбаса", "сырокопчёная", "копчёная", "салями"],
     "Dudlangan kolbasa", "Дудланган колбаса"),
    ("Сосиски и сардельки",     ["сосиски", "сардельки", "wiener", "frankfurter"],
     "Sosiska", "Сосиска"),
    ("Рыба",                    ["рыба", "fish", "форель", "семга", "минтай", "хек", "сельдь", "сельди", "филе"],
     "Baliq", "Балиқ"),
    # Бытовая химия
    ("Стиральный порошок",      ["порошок", "стиральный", "laundry", "washing powder"],
     "Kir yuvish kukuni", "Кир ювиш куки"),
    ("Жидкость для стирки",     ["стирки", "жидкость", "liquid detergent", "гель для стирки"],
     "Kir yuvish geli", "Кир ювиш гели"),
    ("Кондиционер для белья",   ["кондиционер", "белья", "ополаскиватель"],
     "Kir uchun konditsioner", "Кир учун кондиционер"),
    ("Пятновыводитель и отбеливатель", ["пятновыводитель", "отбеливатель", "белизна", "oxi", "action"],
     "Dog' ketkazgich va oqartirgich", "Доғ кетказгич ва оқартиргич"),
    ("Средство для посуды",     ["посуды", "dishwashing", "dish", "tablets", "посудомоечной"],
     "Idish yuvish vositasi", "Идиш ювиш воситаси"),
    ("Чистящее средство",       ["чистящее", "чистящий", "scrub", "абразив", "антижир", "antijir", "жироудалитель", "антиналет", "антиналёт", "стекол", "стёкол", "труб", "плит", "техники"],
     "Tozalash vositasi", "Тозалаш воситаси"),
    ("Бритвенный станок и кассеты", ["станок", "бритва", "кассеты", "sensor"],
     "Soqol olish dastgohi va kasseta", "Соқол олиш дастгоҳи ва кассета"),
    # Личная гигиена
    ("Шампунь",                 ["шампунь", "shampoo"],
     "Shampun", "Шампун"),
    ("Гель для душа",           ["душа", "shower gel", "body wash", "гель для душа"],
     "Dush geli", "Душ гели"),
    ("Мыло туалетное",          ["мыло", "soap", "туалетное"],
     "Sovun", "Совун"),
    ("Зубная паста",            ["зубная", "паста", "toothpaste", "зубная паста"],
     "Tish pastasi", "Тиш пастаси"),
    ("Дезодорант",              ["дезодорант", "deodorant", "антиперспирант"],
     "Dezodorant", "Дезодорант"),
    ("Шампунь и кондиционер",   ["бальзам", "ополаскиватель", "conditioner", "волос"],
     "Konditsioner", "Кондиционер"),
    ("Зубная щётка",            ["зуб", "zub", "shetka", "toothbrush"],
     "Tish cho'tkasi", "Тиш чўткаси"),
    ("Крем для рук",            ["крем", "рук", "hand cream"],
     "Qo'l kremi", "Қўл креми"),
    ("Крем для лица",           ["крем", "лица", "face cream"],
     "Yuz kremi", "Юз креми"),
    ("Маска для лица",          ["маска", "лица", "face mask"],
     "Yuz niqobi", "Юз ниқоби"),
    ("Влажные салфетки",        ["влажные", "салфетки", "очищающие", "wipes", "wet"],
     "Nam salfetkalar", "Нам салфеткалар"),
    ("Женские гигиенические прокладки", ["прокладки", "гигиен", "ultra", "night", "classic", "clasic", "sensitive", "absorb"],
     "Ayollar gigiyenik prokladkalari", "Аёллар гигиеник прокладкалари"),
    ("Бумажные салфетки",       ["салфетки", "салфетка", "универсальные", "сеточные", "рулон", "napkins"],
     "Qog'oz salfetkalar", "Қоғоз салфеткалар"),
    ("Бумажные полотенца",      ["полотенце", "полотенца", "duo", "big size"],
     "Qog'oz sochiqlar", "Қоғоз сочиқлар"),
    ("Ватные диски",            ["ватные", "диски", "диск", "cotton pads"],
     "Paxtali disklar", "Пахтали дисклар"),
    ("Носки",                   ["носки", "носок", "sock", "socks"],
     "Paypoq", "Пайпоқ"),
    ("Щётка для одежды",        ["щетка для одежды", "щётка для одежды", "одежды"],
     "Kiyim cho'tkasi", "Кийим чўткаси"),
    ("Мочалка и банная губка",  ["губка", "массажная", "мочалка"],
     "Cho'milish gubkasi", "Чўмилиш губкаси"),
    # Детские товары
    ("Подгузники",              ["подгузники", "diapers", "nappies", "памперс"],
     "Quruq shim", "Қуруқ шим"),
    ("Детское питание",         ["детское", "питание", "пюре", "каша", "baby food", "pyure", "puree", "frukt", "яблоко"],
     "Bolalar oziq-ovqati", "Болалар озиқ-овқати"),
    ("Пирог",                   ["пирог", "яблочный", "pie"],
     "Pirog", "Пирог"),
    ("Подарочный набор конфет", ["подарок", "новогодний", "набор конфет"],
     "Konfet sovg'a to'plami", "Конфет совға тўплами"),
    # Корм для животных
    ("Корм для кошек",          ["корм", "кошек", "кошачий", "cat food"],
     "Mushuk yemi", "Мушук еми"),
    ("Корм для собак",          ["корм", "собак", "собачий", "dog food"],
     "It yemi", "Ит еми"),
    ("Стаканы",                 ["стаканы", "стакан", "glass"],
     "Stakanlar", "Стаканлар"),
    ("Электрочайник",           ["электрочайник", "чайник", "kettle"],
     "Elektr choynak", "Электр чойнак"),
    ("Подарочный набор косметики", ["подарочный набор", "gift set", "3в1"],
     "Kosmetik sovg'a to'plami", "Косметик совға тўплами"),
    ("Салат готовый",           ["оливье", "винегрет", "фунчоза", "морковча", "свекла", "капуста", "салат"],
     "Tayyor salat", "Тайёр салат"),
    ("Декор для выпечки",       ["посыпка", "кондитерская посыпка", "пасха"],
     "Pishiriq bezagi", "Пишириқ безаги"),
    ("Драже",                   ["драже", "dragee"],
     "Draje", "Драже"),
    ("Хлебцы",                  ["хлебцы", "crispbread", "crisp"],
     "Non batonchalari", "Нон батончалари"),
    ("Сахарозаменитель",        ["подсластитель", "эритрит", "эритритол", "сукралоза", "sweetener"],
     "Shakar o'rnini bosuvchi", "Шакар ўрнини босувчи"),
]

# ---------------------------------------------------------------------------
# Product type -> group MXIK map: (product_type_name_ru, mxik_group_code, confidence)
# Только для явно подтверждённых групповых кодов.
# ---------------------------------------------------------------------------
_PRODUCT_TYPE_MXIK_GROUP_MAP = [
    ("Зубная щётка", "09603002002000000", 1.0),
    ("Сахарозаменитель", "02940001006000000", 1.0),
    ("Шоколад плиточный", "01806001008000000", 1.0),
    ("Подарочный набор конфет", "01806001007000000", 1.0),
    ("Готовый завтрак", "01904001002000000", 1.0),
    ("Печенье", "01905012001000000", 1.0),
]


def seed(conn):
    cur = conn.cursor()

    # UOM
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO uom (code, name_ru, base_unit, factor)
        VALUES %s
        ON CONFLICT (code) DO NOTHING
        """,
        _UOM,
    )

    # Package types
    psycopg2.extras.execute_values(
        cur,
        "INSERT INTO package_types (code, name_ru) VALUES %s ON CONFLICT (code) DO NOTHING",
        _PACKAGE_TYPES,
    )

    # Brands + aliases
    for canonical, aliases in _BRANDS:
        cur.execute(
            """
            INSERT INTO brands (name_canonical)
            VALUES (%s)
            ON CONFLICT (name_canonical) DO NOTHING
            RETURNING id
            """,
            (canonical,),
        )
        row = cur.fetchone()
        if row:
            brand_id = row[0]
        else:
            cur.execute("SELECT id FROM brands WHERE name_canonical = %s", (canonical,))
            brand_id = cur.fetchone()[0]

        cur.execute("SELECT alias FROM brand_aliases WHERE brand_id = %s", (brand_id,))
        existing_aliases = {row[0] for row in cur.fetchall()}

        # Добавляем сам canonical как alias
        all_aliases = list(dict.fromkeys([canonical] + aliases))
        for alias in all_aliases:
            if alias in existing_aliases:
                continue
            cur.execute(
                """
                INSERT INTO brand_aliases (brand_id, alias, source)
                VALUES (%s, %s, 'seed')
                """,
                (brand_id, alias),
            )
            existing_aliases.add(alias)

    # Product types
    type_ids: dict[str, int] = {}
    for row in _PRODUCT_TYPES:
        name_ru, keywords_ru, name_uz_latn, name_uz_cyrl = row
        cur.execute("SELECT id FROM product_types WHERE name_ru = %s LIMIT 1", (name_ru,))
        existing = cur.fetchone()
        if existing:
            type_ids[name_ru] = existing[0]
            cur.execute(
                """
                UPDATE product_types
                SET keywords_ru = %s,
                    name_uz_latn = %s,
                    name_uz_cyrl = %s
                WHERE id = %s
                """,
                (keywords_ru, name_uz_latn, name_uz_cyrl, existing[0]),
            )
            continue
        cur.execute(
            """
            INSERT INTO product_types (name_ru, keywords_ru, name_uz_latn, name_uz_cyrl)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (name_ru, keywords_ru, name_uz_latn, name_uz_cyrl),
        )
        type_ids[name_ru] = cur.fetchone()[0]

    # Product type -> group MXIK map
    for product_type_name, group_code, confidence in _PRODUCT_TYPE_MXIK_GROUP_MAP:
        product_type_id = type_ids.get(product_type_name)
        if not product_type_id:
            continue
        cur.execute(
            """
            SELECT id
            FROM product_type_mxik_map
            WHERE product_type_id = %s
            LIMIT 1
            """,
            (product_type_id,),
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """
                UPDATE product_type_mxik_map
                SET mxik_group_code = %s,
                    confidence = %s
                WHERE id = %s
                """,
                (group_code, confidence, existing[0]),
            )
            continue
        cur.execute(
            """
            INSERT INTO product_type_mxik_map (product_type_id, mxik_group_code, confidence)
            VALUES (%s, %s, %s)
            """,
            (product_type_id, group_code, confidence),
        )

    conn.commit()
    cur.close()
    print(f"UOM: {len(_UOM)} | Package types: {len(_PACKAGE_TYPES)} | "
          f"Brands: {len(_BRANDS)} | Product types: {len(_PRODUCT_TYPES)} | "
          f"Type MXIK maps: {len(_PRODUCT_TYPE_MXIK_GROUP_MAP)}")


def main():
    dsn = settings.database_url_sync.replace("postgresql+psycopg2://", "postgresql://", 1)
    conn = psycopg2.connect(dsn)
    try:
        seed(conn)
        print("Справочники заполнены.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
