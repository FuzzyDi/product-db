"""
Наполнение справочников: UOM, типы упаковки, бренды (топ-100), типы товаров (76+).

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
    # Напитки
    ("NESTLE",          ["Nestle", "Нестле", "nestle", "НЕСТЛЕ"]),
    ("COCA-COLA",       ["Coca Cola", "CocaCola", "Кока-Кола", "Кока Кола", "coca-cola", "coca cola"]),
    ("PEPSI",           ["Pepsi", "Пепси", "PepsiCo"]),
    ("SPRITE",          ["Sprite", "Спрайт"]),
    ("FANTA",           ["Fanta", "Фанта"]),
    ("7UP",             ["7 Up", "Seven Up", "7 Ап", "Севен Ап"]),
    ("SCHWEPPES",       ["Schweppes", "Швепс", "Швеппс"]),
    ("BURN",            ["Burn", "Бёрн"]),
    ("RED BULL",        ["Red Bull", "Ред Бул", "RedBull"]),
    ("BONAQUA",         ["BonAqua", "Бонаква", "Bon Aqua"]),
    ("AQUA MINERALE",   ["Aqua Minerale", "Аква Минерале"]),
    ("EVIAN",           ["Evian", "Эвиан"]),
    ("BORJOMI",         ["Borjomi", "Боржоми", "Borjomy"]),
    ("ESSENTUKI",       ["Essentuki", "Ессентуки"]),
    ("NARZAN",          ["Narzan", "Нарзан"]),
    ("MARVARID",        ["Marvarid", "Марварид"]),
    # Соки
    ("DOBRY",           ["Добрый", "Dobry"]),
    ("J7",              ["J7", "Джей 7", "Я"]),
    ("RICH",            ["Rich", "Рич"]),
    ("TROPICANA",       ["Tropicana", "Тропикана"]),
    # Чай
    ("LIPTON",          ["Lipton", "Липтон"]),
    ("GREENFIELD",      ["Greenfield", "Гринфилд", "Green Field"]),
    ("AHMAD TEA",       ["Ahmad Tea", "Ahmad", "Ахмад", "Ахмад Ти"]),
    ("AKBAR",           ["Akbar", "Акбар"]),
    ("TWININGS",        ["Twinings", "Твайнингс"]),
    ("RICHARD",         ["Richard", "Ричард"]),
    ("BESEDA",          ["Беседа", "Beseda"]),
    # Кофе
    ("NESCAFE",         ["Nescafe", "Нескафе", "Nescafé"]),
    ("JACOBS",          ["Jacobs", "Якобс"]),
    ("MAXWELL HOUSE",   ["Maxwell House", "Максвелл Хаус"]),
    ("CARTE NOIRE",     ["Carte Noire", "Карт Нуар"]),
    ("JARDIN",          ["Jardin", "Жардин"]),
    # Молочные продукты
    ("DANONE",          ["Danone", "Данон", "Данонe"]),
    ("ACTIVIA",         ["Activia", "Активиа", "Активия"]),
    ("ACTIMEL",         ["Actimel", "Актимель"]),
    ("PRESIDENT",       ["President", "Président", "Президент"]),
    ("SIMPLE",          ["Простоквашино", "Prostokvashino"]),
    # Шоколад / сладкое
    ("MILKA",           ["Milka", "Милка"]),
    ("ALPEN GOLD",      ["Alpen Gold", "Альпен Голд", "AlpenGold"]),
    ("TOBLERONE",       ["Toblerone", "Тоблерон"]),
    ("NESQUIK",         ["Nesquik", "Несквик"]),
    ("KITKAT",          ["KitKat", "Kit Kat", "Кит Кат", "Киткат"]),
    ("SNICKERS",        ["Snickers", "Сникерс"]),
    ("TWIX",            ["Twix", "Твикс"]),
    ("MARS",            ["Mars", "Марс"]),
    ("BOUNTY",          ["Bounty", "Баунти"]),
    ("MILKY WAY",       ["Milky Way", "Милки Вэй", "MilkyWay"]),
    ("M&M'S",           ["M&M's", "M&Ms", "МиМс", "Эм энд Эмс"]),
    ("RAFFAELLO",       ["Raffaello", "Рафаэлло", "Rafaello"]),
    ("FERRERO ROCHER",  ["Ferrero Rocher", "Ферреро Роше", "Ferrero"]),
    ("NUTELLA",         ["Nutella", "Нутелла"]),
    ("KINDER",          ["Kinder", "Киндер"]),
    ("TIC TAC",         ["Tic Tac", "Тик Так", "TicTac"]),
    ("OREO",            ["Oreo", "Орео"]),
    ("BARNI",           ["Barni", "Барни"]),
    ("CADBURY",         ["Cadbury", "Кэдбери"]),
    ("HARIBO",          ["Haribo", "Харибо"]),
    ("MENTOS",          ["Mentos", "Ментос"]),
    ("SKITTLES",        ["Skittles", "Скитлс"]),
    ("HALLS",           ["Halls", "Холлс"]),
    # Снеки
    ("PRINGLES",        ["Pringles", "Принглс"]),
    ("LAY'S",           ["Lay's", "Lays", "Лэйс", "Лейс"]),
    ("DORITOS",         ["Doritos", "Доритос"]),
    ("CHEETOS",         ["Cheetos", "Читос"]),
    ("ORBIT",           ["Orbit", "Орбит"]),
    ("DIROL",           ["Dirol", "Дирол"]),
    # Соусы
    ("HEINZ",           ["Heinz", "Хайнц"]),
    ("HELLMANN'S",      ["Hellmann's", "Hellmanns", "Хеллманс"]),
    ("KNORR",           ["Knorr", "Кнорр"]),
    ("MAGGI",           ["Maggi", "Магги"]),
    ("BONDUELLE",       ["Bonduelle", "Бондюэль"]),
    # Бытовая химия
    ("ARIEL",           ["Ariel", "Ариэль"]),
    ("TIDE",            ["Tide", "Тайд"]),
    ("PERSIL",          ["Persil", "Персил"]),
    ("FAIRY",           ["Fairy", "Фэйри"]),
    ("PRIL",            ["Pril", "Прил"]),
    ("FINISH",          ["Finish", "Финиш"]),
    ("VANISH",          ["Vanish", "Ваниш"]),
    ("CILLIT BANG",     ["Cillit Bang", "Cillit", "Силлит"]),
    ("DOMESTOS",        ["Domestos", "Доместос"]),
    ("MR. PROPER",      ["Mr. Proper", "Mr Proper", "Мистер Пропер"]),
    # Средства гигиены
    ("PAMPERS",         ["Pampers", "Памперс"]),
    ("HUGGIES",         ["Huggies", "Хаггис"]),
    ("HEAD & SHOULDERS",["Head & Shoulders", "Head and Shoulders", "Хэд энд Шолдерс"]),
    ("PANTENE",         ["Pantene", "Пантин", "Pantene Pro-V"]),
    ("DOVE",            ["Dove", "Дав"]),
    ("REXONA",          ["Rexona", "Рексона"]),
    ("AXE",             ["Axe", "Акс"]),
    ("GILLETTE",        ["Gillette", "Жиллетт"]),
    ("ORAL-B",          ["Oral-B", "Oral B", "Орал Би"]),
    ("COLGATE",         ["Colgate", "Колгейт"]),
    ("SIGNAL",          ["Signal", "Сигнал"]),
    ("JOHNSON'S",       ["Johnson's", "Johnsons", "Джонсонс", "Johnson's Baby"]),
    # Местные узбекские
    ("AKFA",            ["Akfa", "Акфа"]),
]

# ---------------------------------------------------------------------------
# Product types: (name_ru, [keywords_ru], name_uz_latn, name_uz_cyrl)
# ---------------------------------------------------------------------------
_PRODUCT_TYPES = [
    # Вода и напитки
    ("Вода питьевая",           ["вода", "питьевая", "минеральная", "артезианская", "природная"],
     "Ichimlik suv", "Ичимлик сув"),
    ("Напиток газированный",    ["напиток", "газированный", "газировка", "лимонад", "сода"],
     "Gazlangan ichimlik", "Газланган ичимлик"),
    ("Напиток негазированный",  ["напиток", "негазированный", "still"],
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
    ("Кофе растворимый",        ["кофе", "растворимый", "instant", "3в1", "2в1"],
     "Eruvchan qahva", "Эрувчан қаҳва"),
    ("Кофе молотый",            ["кофе", "молотый", "ground"],
     "Maydalangan qahva", "Майдаланган қаҳва"),
    ("Кофе в зёрнах",           ["кофе", "зёрнах", "зерновой", "beans"],
     "Don qahva", "Дон қаҳва"),
    ("Какао",                   ["какао", "cocoa"],
     "Kakao", "Какао"),
    # Молочные продукты
    ("Молоко",                  ["молоко", "молочный", "ультрапастеризованное", "пастеризованное"],
     "Sut", "Сут"),
    ("Кефир",                   ["кефир"],
     "Kefir", "Кефир"),
    ("Йогурт",                  ["йогурт", "yogurt"],
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
    ("Крупа рисовая",           ["рис", "крупа", "рисовая"],
     "Guruch", "Гуруч"),
    ("Крупа гречневая",         ["гречка", "гречневая", "buckwheat"],
     "Grechka", "Гречка"),
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
    ("Перец молотый",           ["перец", "молотый", "чёрный", "красный", "pepper"],
     "Qalampir", "Қалампир"),
    # Шоколад и сладости
    ("Шоколад плиточный",       ["шоколад", "chocolate", "чёрный", "молочный", "белый"],
     "Shokolad", "Шоколад"),
    ("Шоколадные конфеты",      ["конфеты", "шоколадные", "ассорти", "пралине"],
     "Shokoladli konfetlar", "Шоколадли конфетлар"),
    ("Карамель",                ["карамель", "леденцы", "caramel"],
     "Karamel", "Карамел"),
    ("Мармелад",                ["мармелад", "желейный", "жевательный", "gummy"],
     "Marmelad", "Мармелад"),
    ("Жевательная резинка",     ["жвачка", "жевательная", "резинка", "gum"],
     "Saqich", "Сақич"),
    # Печенье, вафли, выпечка
    ("Печенье",                 ["печенье", "cookies", "biscuit"],
     "Pechenye", "Печенье"),
    ("Вафли",                   ["вафли", "вафля", "wafer"],
     "Vafel", "Вафель"),
    ("Торт",                    ["торт", "пирожное", "cake"],
     "Tort", "Торт"),
    ("Хлеб",                    ["хлеб", "bread", "батон", "булка"],
     "Non", "Нон"),
    ("Хлебобулочные изделия",   ["булочка", "выпечка", "пирожок", "рогалик"],
     "Unli mahsulot", "Унли маҳсулот"),
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
    ("Консервы овощные",        ["консервы", "овощные", "горошек", "кукуруза", "фасоль"],
     "Sabzavot konservasi", "Сабзавот консерваси"),
    # Мясо и рыба
    ("Колбаса варёная",         ["колбаса", "варёная", "докторская", "молочная"],
     "Qaynatilgan kolbasa", "Қайнатилган колбаса"),
    ("Колбаса сырокопчёная",    ["колбаса", "сырокопчёная", "копчёная", "салями"],
     "Dudlangan kolbasa", "Дудланган колбаса"),
    ("Сосиски и сардельки",     ["сосиски", "сардельки", "wiener", "frankfurter"],
     "Sosiska", "Сосиска"),
    ("Рыба",                    ["рыба", "fish", "форель", "семга", "минтай", "хек"],
     "Baliq", "Балиқ"),
    # Бытовая химия
    ("Стиральный порошок",      ["порошок", "стиральный", "laundry", "washing powder"],
     "Kir yuvish kukuni", "Кир ювиш куки"),
    ("Жидкость для стирки",     ["гель", "стирки", "жидкость", "liquid detergent"],
     "Kir yuvish geli", "Кир ювиш гели"),
    ("Средство для посуды",     ["средство", "посуды", "washing up", "dishwashing"],
     "Idish yuvish vositasi", "Идиш ювиш воситаси"),
    ("Чистящее средство",       ["чистящее", "чистящий", "scrub", "абразив"],
     "Tozalash vositasi", "Тозалаш воситаси"),
    # Личная гигиена
    ("Шампунь",                 ["шампунь", "shampoo"],
     "Shampun", "Шампун"),
    ("Гель для душа",           ["гель", "душа", "shower gel", "body wash"],
     "Dush geli", "Душ гели"),
    ("Мыло туалетное",          ["мыло", "soap", "туалетное"],
     "Sovun", "Совун"),
    ("Зубная паста",            ["зубная", "паста", "toothpaste", "зубная паста"],
     "Tish pastasi", "Тиш пастаси"),
    ("Дезодорант",              ["дезодорант", "deodorant", "антиперспирант"],
     "Dezodorant", "Дезодорант"),
    ("Шампунь и кондиционер",   ["кондиционер", "бальзам", "ополаскиватель", "conditioner"],
     "Konditsioner", "Кондиционер"),
    # Детские товары
    ("Подгузники",              ["подгузники", "diapers", "nappies", "памперс"],
     "Quruq shim", "Қуруқ шим"),
    ("Детское питание",         ["детское", "питание", "пюре", "каша", "baby food"],
     "Bolalar oziq-ovqati", "Болалар озиқ-овқати"),
    # Корм для животных
    ("Корм для кошек",          ["корм", "кошек", "кошачий", "cat food"],
     "Mushuk yemi", "Мушук еми"),
    ("Корм для собак",          ["корм", "собак", "собачий", "dog food"],
     "It yemi", "Ит еми"),
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

        # Добавляем сам canonical как alias
        all_aliases = list(dict.fromkeys([canonical] + aliases))
        for alias in all_aliases:
            cur.execute(
                """
                INSERT INTO brand_aliases (brand_id, alias, source)
                VALUES (%s, %s, 'seed')
                ON CONFLICT DO NOTHING
                """,
                (brand_id, alias),
            )

    # Product types
    for row in _PRODUCT_TYPES:
        name_ru, keywords_ru, name_uz_latn, name_uz_cyrl = row
        cur.execute(
            """
            INSERT INTO product_types (name_ru, keywords_ru, name_uz_latn, name_uz_cyrl)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (name_ru, keywords_ru, name_uz_latn, name_uz_cyrl),
        )

    conn.commit()
    cur.close()
    print(f"UOM: {len(_UOM)} | Package types: {len(_PACKAGE_TYPES)} | "
          f"Brands: {len(_BRANDS)} | Product types: {len(_PRODUCT_TYPES)}")


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
