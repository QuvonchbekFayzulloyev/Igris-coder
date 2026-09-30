/**
 * Uzbek Terminology Database — comprehensive domain-specific terms
 * 
 * Covers: IT, Engineering, Science, Economics, Academic, Mathematics
 * Each term has: translation, preferred form, forbidden forms, examples
 */

import { languageStore } from './language-store';

// ═══════════════════════════════════════════════
// SEED UZBEK TERMINOLOGY
// ═══════════════════════════════════════════════

export function seedUzbekTerminology(): void {
  if (languageStore.getAllTerms().length > 0) return;

  // ─── IT & COMPUTER SCIENCE ────────────────

  const itTerms: Array<{
    term: string; def: string; en: string; ru: string; pref: string; forb: string[]; syn: string[]; abbr?: string[];
  }> = [
    { term: "mashinali o'rganish", def: "Kompyuter tizimlarining tajriba orqali o'zini yaxshilash qobiliyati", en: "machine learning", ru: "машинное обучение", pref: "mashinali o'rganish", forb: ["mashina o'rganishi", "mashinaviy o'rganish"], syn: ["MO", "suniy intellekt o'rganishi"], abbr: ["ML", "MO"] },
    { term: "chuqur o'rganish", def: "Neuron tarmoqlaridan foydalanuvchi ML usuli", en: "deep learning", ru: "глубокое обучение", pref: "chuqur o'rganish", forb: ["chuqurlik o'rganish"], syn: ["neuron tarmoqlari"], abbr: ["DL", "ChO"] },
    { term: "tabiy tilni qayta ishlash", def: "Inson tilini kompyuter tomonidan tushunish va generatsiya qilish", en: "natural language processing", ru: "обработка естественного языка", pref: "tabiy tilni qayta ishlash", forb: ["tabiy til qayta ishlash"], syn: ["Tilni qayta ishlash"], abbr: ["NLP", "TTQI"] },
    { term: "kompyuter ko'rish", def: "Rasmlarni va videolarni kompyuter tomonidan tahlil qilish", en: "computer vision", ru: "компьютерное зрение", pref: "kompyuter ko'rish", forb: ["kompyuterviy ko'rish"], syn: ["CK"], abbr: ["CV", "CK"] },
    { term: "sun'iy intellekt", def: "Inson aqlini taqlid qiluvchi kompyuter tizimlari", en: "artificial intelligence", ru: "искусственный интеллект", pref: "sun'iy intellekt", forb: ["sun'iy aql", "mas'ul intellekt"], syn: ["SI", "AI"], abbr: ["AI", "SI"] },
    { term: "neyron tarmoq", def: "Biologik neyron tarmoqlaridan ilhomlangan hisoblash modeli", en: "neural network", ru: "нейронная сеть", pref: "neyron tarmoq", forb: ["neyron tarmog'i", "neural network"], syn: ["NT"], abbr: ["NN", "NT"] },
    { term: "algoritm", def: "Muammoni hal qilish uchun aniq qadamlar ketma-ketligi", en: "algorithm", ru: "алгоритм", pref: "algoritm", forb: ["algoritim"], syn: [] },
    { term: "ma'lumotlar bazasi", def: "Tizimli ravishda saqlangan ma'lumotlar to'plami", en: "database", ru: "база данных", pref: "ma'lumotlar bazasi", forb: ["дата база", "data base"], syn: ["MB", "DB"], abbr: ["DB", "MB"] },
    { term: "API", def: "Dasturlar o'rtasida muloqot uchun interfeys", en: "Application Programming Interface", ru: "интерфейс программирования приложений", pref: "API", forb: ["api", "Api"], syn: ["dasturlash interfeysi"], abbr: ["API"] },
    { term: "frontend", def: "Veb-saytning foydalanuvchi ko'radigan qismi", en: "frontend", ru: "фронтенд", pref: "frontend", forb: ["front-end", "frondend"], syn: ["old qism", "foydalanuvchi interfeysi"] },
    { term: "backend", def: "Veb-saytning server tomonidagi qismi", en: "backend", ru: "бэкенд", pref: "backend", forb: ["back-end", "bekend"], syn: ["orqa qism", "server qismi"] },
    { term: "repository", def: "Kod saqlanadigan va versiya boshqaruv tizimi", en: "repository", ru: "репозиторий", pref: "repository", forb: ["repozitoriy", "repositoriy"], syn: ["repo", "kod bazasi"] },
    { term: "deploy", def: "Dasturni ishga tushirish muhitiga joylashtirish", en: "deployment", ru: "развертывание", pref: "deploy", forb: ["deploiment", "depoloy"], syn: ["joylashtirish", "ishga tushirish"] },
    { term: "debug", def: "Dasturdagi xatolarni topish va tuzatish", en: "debugging", ru: "отладка", pref: "debug", forb: ["debug qilish"], syn: ["xatolarni tuzatish"] },
    { term: "refactoring", def: "Kodni tuzatmasdan takroriy shaklga keltirish", en: "refactoring", ru: "рефакторинг", pref: "refactoring", forb: ["refaktoring", "refactoring qilish"], syn: ["qayta ishlash"] },
    { term: "test", def: "Dasturni to'g'riligini tekshirish", en: "testing", ru: "тестирование", pref: "test", forb: ["testing"], syn: ["sinov", "tekshirish"] },
    { term: "commit", def: "Kod o'zgarishlarini saqlash", en: "commit", ru: "коммит", pref: "commit", forb: ["comit", "komit"], syn: ["saqlash"] },
    { term: "branch", def: "Kodning alohida versiyasi", en: "branch", ru: "ветка", pref: "branch", forb: ["branche"], syn: ["tarmoq", "versiya"] },
    { term: "merge", def: "Ikkita kodni birlashtirish", en: "merge", ru: "слияние", pref: "merge", forb: ["merge qilish"], syn: ["birlashtirish"] },
    { term: "token", def: "Matnni qayta ishlash uchun bo'lak", en: "token", ru: "токен", pref: "token", forb: ["tayken"], syn: ["bo'lak"] },
    { term: "embedding", def: "Matn/rasimni vektor shaklida ifodalash", en: "embedding", ru: "эмбеддинг", pref: "embedding", forb: ["embending", "imbedding"], syn: ["vektorli ifoda"] },
    { term: "transformer", def: "Self-attention asosidagi neuron tarmoq arxitekturasi", en: "transformer", ru: "трансформер", pref: "transformer", forb: ["transformator"], syn: ["o'z e'tiborli tarmoq"] },
    { term: "fine-tuning", def: "Oldindan o'qitilgan modelni qo'shimcha ma'lumot bilan moslashtirish", en: "fine-tuning", ru: "дообучение", pref: "fine-tuning", forb: ["finetuning", "fine tunning"], syn: ["mayda sozlash", "qo'shimcha o'qitish"] },
    { term: "inference", def: "O'qitilgan modeldan bashorat olish jarayoni", en: "inference", ru: "вывод", pref: "inference", forb: ["inferens"], syn: ["bashorat", "taxmin"] },
    { term: "training", def: "Modelni ma'lumotlar asosida o'qitish", en: "training", ru: "обучение", pref: "training", forb: ["trening"], syn: ["o'qitish"] },
    { term: "dataset", def: "O'qitish yoki sinov uchun ma'lumotlar to'plami", en: "dataset", ru: "набор данных", pref: "dataset", forb: ["data set", "dataset to'plami"], syn: ["ma'lumotlar to'plami"] },
    { term: "overfitting", def: "Model sinov ma'lumotlariga yomon umumlashtirish", en: "overfitting", ru: "переобучение", pref: "overfitting", forb: ["overfit"], syn: ["ortiqcha o'qitish"] },
    { term: "loss function", def: "Model xatosini hisoblaydigan funksiya", en: "loss function", ru: "функция потерь", pref: "loss function", forb: ["loss funcsion"], syn: ["xatolik funksiyasi"] },
    { term: "gradient descent", def: "Model parametrlarini optimallashtirish algoritmi", en: "gradient descent", ru: "градиентный спуск", pref: "gradient descent", forb: ["gradient spusk"], syn: ["gradient tushishi"] },
    { term: "backpropagation", def: "Xatolikni neyron tarmoq orqali tarqatish algoritmi", en: "backpropagation", ru: "обратное распространение ошибки", pref: "backpropagation", forb: ["backprop"], syn: ["orqaga tarqatish"] },
    { term: "semantik qidiruv", def: "Ma'no asosidigan qidiruv tizimi", en: "semantic search", ru: "семантический поиск", pref: "semantik qidiruv", forb: ["semantik search"], syn: ["ma'noga asoslangan qidiruv"] },
    { term: "vektorli ma'lumotlar bazasi", def: "Vektorlarni saqlaydigan va qidiradigan DB", en: "vector database", ru: "векторная база данных", pref: "vektorli ma'lumotlar bazasi", forb: ["vector database"], syn: ["VDB"] },
    { term: "RAG", def: "Qidiruv va generatsiyani birlashtiruvchi usul", en: "Retrieval-Augmented Generation", ru: "Генерация с расширением поиска", pref: "RAG", forb: ["rag"], syn: ["qidiruvli generatsiya"] },
    { term: "LLM", def: "Katta til modellari", en: "Large Language Model", ru: "Большая языковая модель", pref: "LLM", forb: ["llm", "katta til modeli"], syn: ["katta til modeli"] },
    { term: "GPU", def: "Grafik protsessor — parallel hisoblash uchun", en: "Graphics Processing Unit", ru: "Графический процессор", pref: "GPU", forb: ["gpu"], syn: ["grafik protsessor"] },
    { term: "VRAM", def: "GPU xotirasi", en: "Video RAM", ru: "Видеопамять", pref: "VRAM", forb: ["vram"], syn: ["GPU xotirasi"] },
    { term: "API endpoint", def: "API ning ma'lum bir manzili", en: "API endpoint", ru: "конечная точка API", pref: "API endpoint", forb: ["api endpoint"], syn: ["API manzili"] },
    { term: "middleware", def: "Ikki tizim orasidagi qatlam", en: "middleware", ru: "промежуточное ПО", pref: "middleware", forb: ["midleware"], syn: ["oraliq dastur"] },
    { term: "microservice", def: "Mustaqil xizmat sifatida ishlaydigan dastur qismi", en: "microservice", ru: "микросервис", pref: "microservice", forb: ["micro service"], syn: ["kichik xizmat"] },
    { term: "container", def: "Dasturni izolyatsiya qilingan muhitda saqlash", en: "container", ru: "контейнер", pref: "container", forb: ["konteyner"], syn: ["konteyner"] },
    { term: "Kubernetes", def: "Konteynerlarni boshqarish tizimi", en: "Kubernetes", ru: "Kubernetes", pref: "Kubernetes", forb: ["kubernetes", "kube"], syn: ["K8s"] },
    { term: "Docker", def: "Konteynerlashtirish platformasi", en: "Docker", ru: "Docker", pref: "Docker", forb: ["docker"], syn: [] },
    { term: "CI/CD", def: "Avtomatik integratsiya va joylashtirish", en: "Continuous Integration/Continuous Deployment", ru: "Непрерывная интеграция/развертывание", pref: "CI/CD", forb: ["ci/cd"], syn: ["avtomatik joylashtirish"] },
    { term: "version control", def: "Kod versiyalarini boshqarish tizimi", en: "version control", ru: "контроль версий", pref: "version control", forb: ["version boshqaruv"], syn: ["versiya boshqaruvi"] },
    { term: "framework", def: "Dasturlash uchun tayyor struktura", en: "framework", ru: "фреймворк", pref: "framework", forb: ["framework"], syn: ["ramka", "tuzilma"] },
    { term: "library", def: "Tayyor funksiyalar to'plami", en: "library", ru: "библиотека", pref: "library", forb: ["librari"], syn: [" kutubxona"] },
  ];

  for (const t of itTerms) {
    languageStore.createTerm(
      'uz', t.term, t.def, 'computer_science_ai', 'it',
      { en: t.en, ru: t.ru }, t.pref, t.forb, t.syn, t.abbr || [],
      ['AKMS'], 0.9, true,
    );
  }

  // ─── ELECTRICAL ENGINEERING ───────────────

  const eeTerms: Array<{ term: string; def: string; en: string; ru: string; pref: string; forb: string[] }> = [
    { term: "tok", def: "Elektr zaryodlarining harakati", en: "current", ru: "ток", pref: "tok", forb: ["curant", "kurent"] },
    { term: "kuchlanish", def: "Elektr maydon kuchi", en: "voltage", ru: "напряжение", pref: "kuchlanish", forb: ["volьtaj"] },
    { term: "qarshilik", def: "Elektr tokiga qarshilik", en: "resistance", ru: "сопротивление", pref: "qarshilik", forb: ["resistans"] },
    { term: "sig'im", def: "Elektr zaryodini saqlash qobiliyati", en: "capacitance", ru: "ёмкость", pref: "sig'im", forb: ["kapasitans", "sig'm"] },
    { term: "kondensator", def: "Elektr zaryodini saqlash elementi", en: "capacitor", ru: "конденсатор", pref: "kondensator", forb: ["kapasitor", "kondensitor"] },
    { term: " rezistor", def: "Elektr tokiga qarshilik ko'rsatuvchi element", en: "resistor", ru: "резистор", pref: "rezistor", forb: ["resistor"] },
    { term: "indiuktor", def: "Magnit maydon energiyasini saqlash elementi", en: "inductor", ru: "индуктор", pref: "indiuktor", forb: ["inductor", "induktьор"] },
    { term: "printsipli kombinatsiyalangan zanjir", def: "Rezistor va kondensatordan tashkil topgan zanjir", en: "RC circuit", ru: "RC-схема", pref: "RC-zanjir", forb: ["RC circuit"] },
    { term: "mikrosxema", def: "Yarim o'tkazgichli qurilmada yaratilgan zanjir", en: "integrated circuit", ru: "микросхема", pref: "mikrosxema", forb: ["integрированнаясхема"] },
    { term: "plata", def: "Elektron komponentlarni o'rnatish uchun tayoqcha", en: "PCB", ru: "плата", pref: "plata", forb: ["PCB plьата"] },
    { term: "sxema", def: "Elektron qurilmalarning bog'lanish rejası", en: "schematic", ru: "схема", pref: "sxema", forb: ["shema"] },
    { term: "kuchlanish stabilizatori", def: "Chiqish kuchlanishini barqaror ushlab turuvchi zanjir", en: "voltage regulator", ru: "стабилизатор напряжения", pref: "kuchlanish stabilizatori", forb: ["volьtaj stabilizatori"] },
    { term: "mikrokontroller", def: "Kirish/chiqishlari bor mayda protsessor", en: "microcontroller", ru: "микроконтроллер", pref: "mikrokontroller", forb: ["mikrocontroller"] },
    { term: "signal", def: "Ma'lumot o'tkazuvchi elektr impulsi", en: "signal", ru: "сигнал", pref: "signal", forb: ["signьал"] },
    { term: "chastota", def: "Signarning bir sekunddagi takrorlanish soni", en: "frequency", ru: "частота", pref: "chastota", forb: ["frequency"] },
    { term: " chastotali filtrlar", def: "Ma'lum chastotalarni o'tkazuvchi zanjir", en: "frequency filter", ru: "частотный фильтр", pref: "chastotali filtrlar", forb: ["frequency filter"] },
    { term: "impedans", def: "O'zgaruvchan tok uchun umumiy qarshilik", en: "impedance", ru: "импеданс", pref: "impedans", forb: ["impedьанс"] },
    { term: "yuklama", def: "Elektr zanjiridagi foydalanuvchi qurilma", en: "load", ru: "нагрузка", pref: "yuklama", forb: ["load"] },
    { term: "manba", def: "Elektr energiyasi manbayi", en: "power source", ru: "источник питания", pref: "manba", forb: ["power source"] },
    { term: "yerga ulanish", def: "Xavfsizlik uchun yerga ulash", en: "grounding", ru: "заземление", pref: "yerga ulanish", forb: ["ground"] },
  ];

  for (const t of eeTerms) {
    languageStore.createTerm(
      'uz', t.term, t.def, 'electrical_engineering', 'engineering',
      { en: t.en, ru: t.ru }, t.pref, t.forb,
      [], [], ['AKMS'], 0.9, true,
    );
  }

  // ─── MECHANICAL ENGINEERING ───────────────

  const meTerms: Array<{ term: string; def: string; en: string; ru: string }> = [
    { term: "kuchlanish", def: "Yuklamaga qarshi qarshilik", en: "stress", ru: "напряжение" },
    { term: "deformatsiya", def: "Shakl o'zgarishi", en: "deformation", ru: "деформация" },
    { term: "yOUNG moduli", def: "Elastiklik xususiyati", en: "Young's modulus", ru: "модуль Юнга" },
    { term: "likopchaning qattiqligi", def: "Materialning qattiqligi", en: "hardness", ru: "твёрдость" },
    { term: "termik tahlil", def: "Harorat ta'sirini hisoblash", en: "thermal analysis", ru: "термический анализ" },
    { term: "Mexanik tizim", def: "Harakatlanuvchi qismlar to'plami", en: "mechanical system", ru: "механическая система" },
    { term: "CAD", def: "Kompyuter yordamida loyihalash", en: "Computer-Aided Design", ru: "автоматизированное проектирование" },
    { term: "CAM", def: "Kompyuter yordamida ishlab chiqarish", en: "Computer-Aided Manufacturing", ru: "автоматизированное производство" },
    { term: "3D modellashtirish", def: "Uch o'lchamli raqamli model yaratish", en: "3D modeling", ru: "3D-моделирование" },
    { term: "bosim", def: "Yuklama / maydon", en: "pressure", ru: "давление" },
    { term: " moment", def: "Burish kuchi", en: "torque", ru: "момент" },
    { term: "tezlik", def: "Harakat tezligi", en: "velocity", ru: "скорость" },
    { term: "tezlanish", def: "Tezlik o'zgarishi", en: "acceleration", ru: "ускорение" },
    { term: "ineritsiya", def: "Harakatga qarshilik", en: "inertia", ru: "инерция" },
    { term: "fraktsiya", def: "Yuzasi bir xil bo'lmagan siljish", en: "friction", ru: "трение" },
  ];

  for (const t of meTerms) {
    languageStore.createTerm(
      'uz', t.term, t.def, 'mechanical_engineering', 'engineering',
      { en: t.en, ru: t.ru }, t.term, [], [], [], ['AKMS'], 0.9, true,
    );
  }

  // ─── ECONOMICS & FINANCE ──────────────────

  const ecoTerms: Array<{ term: string; def: string; en: string; ru: string }> = [
    { term: "iqtisodiyot", def: "Mahsulot ishlab chiqarish va taqsimot tizimi", en: "economy", ru: "экономика" },
    { term: "inflatsiya", def: "Umumiy narxlar darajasining o'sishi", en: "inflation", ru: "инфляция" },
    { term: "deflatsiya", def: "Umumiy narxlar darajasining tushishi", en: "deflation", ru: "дефляция" },
    { term: "Valyuta kursi", def: "Bir valyutaning boshqasiga nisbatan qiymati", en: "exchange rate", ru: "обменный курс" },
    { term: "foiz stavkasi", def: "Qarz uchun to'lanadigan foiz", en: "interest rate", ru: "процентная ставка" },
    { term: " yalpi ichki mahsulot", def: "Mamlakat iqtisodiyotining umumiy hajmi", en: "Gross Domestic Product", ru: "валовой внутренний продукт" },
    { term: "byudjet", def: "Davlatning daromad va xarajatlari rejası", en: "budget", ru: "бюджет" },
    { term: "soliq", def: "Davlatga to'lanadigan majburiy to'lov", en: "tax", ru: "налог" },
    { term: "investitsiya", def: "Kapitalni foyda olish uchun joylashtirish", en: "investment", ru: "инвестиция" },
    { term: "aksiya", def: "Korxona kapitalidagi ulush", en: "stock", ru: "акция" },
    { term: "obligatsiya", def: "Qarz qog'ozi", en: "bond", ru: "облигация" },
    { term: "dividend", def: "Aksiyadorlarga to'lanadigan foyda", en: "dividend", ru: "дивиденд" },
    { term: "kapital", def: "Ishlab chiqarish uchun mablag'", en: "capital", ru: "капитал" },
    { term: "foyda", def: "Daromad minus xarajat", en: "profit", ru: "прибыль" },
    { term: "zarar", def: "Xarajat minus daromad", en: "loss", ru: "убыток" },
    { term: "moliyaviy tahlil", def: "Moliyaviy hisobotlarni tahlil qilish", en: "financial analysis", ru: "финансовый анализ" },
    { term: "risk", def: "Nomoliy natija ehtimoli", en: "risk", ru: "риск" },
    { term: "likvidlik", def: "Pulga aylanish tezligi", en: "liquidity", ru: "ликвидность" },
    { term: "rentabellik", def: "foyda ko'rsatkichi", en: "profitability", ru: "рентабельность" },
    { term: "debet", def: "Hisobning chap tomoni", en: "debit", ru: "дебет" },
    { term: "kredit", def: "Hisobning o'ng tomoni", en: "credit", ru: "кредит" },
    { term: "balans", def: "Daromad va xarajatlar tengligi", en: "balance", ru: "баланс" },
    { term: "audit", def: "Moliyaviy hisobotlarni tekshirish", en: "audit", ru: "аудит" },
    { term: "depressiya", def: "Iqtisodiyotning uzoq muddatli pasayishi", en: "recession", ru: "рецессия" },
  ];

  for (const t of ecoTerms) {
    languageStore.createTerm(
      'uz', t.term, t.def, 'economics', 'economic',
      { en: t.en, ru: t.ru }, t.term, [], [], [], ['AKMS'], 0.9, true,
    );
  }

  // ─── MATHEMATICS ─────────────────────────

  const mathTerms: Array<{ term: string; def: string; en: string; ru: string }> = [
    { term: "funksiya", def: "Har bir kirish uchun bitta chiqish qiymatini qaytaruvchi qoida", en: "function", ru: "функция" },
    { term: "egral", def: "Funksiya maydonining yig'indisi", en: "integral", ru: "интеграл" },
    { term: "hosila", def: "Funksiyaning o'zgarish tezligi", en: "derivative", ru: "производная" },
    { term: "matritsa", def: "Raqamlar jadvali", en: "matrix", ru: "матрица" },
    { term: "vektor", def: "Yo'nalish va kattalikka ega miqdor", en: "vector", ru: "вектор" },
    { term: "xususiy qiymat", def: "Matritsa xususiy vektorining qiymati", en: "eigenvalue", ru: "собственное значение" },
    { term: "optimallashtirish", def: "Eng yaxshi yechimni topish", en: "optimization", ru: "оптимизация" },
    { term: "gradient", def: "Funksiyaning eng qattiq o'sish yo'nalishi", en: "gradient", ru: "градиент" },
    { term: "statistika", def: "Ma'lumotlarni tahlil qilish fani", en: "statistics", ru: "статистика" },
    { term: "ehtimollik", def: "Hodisaning sodir bo'lish darajasi", en: "probability", ru: "вероятность" },
    { term: "reaksiya", def: "Kafolatlangan natija", en: "theorem", ru: "теорема" },
    { term: "aks", def: "Ko'rsatma isbotlash", en: "proof", ru: "доказательство" },
    { term: "chegara", def: "Funksiyaning yaqinlashuvchi qiymati", en: "limit", ru: "предел" },
    { term: "differensial tenglama", def: "Funksiyaning hosilalarini o'z ichiga oluvchi tenglama", en: "differential equation", ru: "дифференциальное уравнение" },
    { term: "lineer algebra", def: "Vektor va matritsalar nazariyasi", en: "linear algebra", ru: "линейная алгебра" },
  ];

  for (const t of mathTerms) {
    languageStore.createTerm(
      'uz', t.term, t.def, 'mathematics', 'math',
      { en: t.en, ru: t.ru }, t.term, [], [], [], ['AKMS'], 0.9, true,
    );
  }

  // ─── ACADEMIC ────────────────────────────

  const academicTerms: Array<{ term: string; def: string; en: string; ru: string }> = [
    { term: "maqola", def: "Ilmiy jurnalda nashr etilgan tadqiqot", en: "article", ru: "статья" },
    { term: "dissertatsiya", def: "Ilmiy daraja uchun yozilgan tadqiqot ishi", en: "dissertation", ru: "диссертация" },
    { term: "ilmiy maqola", def: "Tadqiqot natijalarini bayon qiluvchi hujjat", en: "research paper", ru: "научная статья" },
    { term: "adabiyotlar ro'yxati", def: "Ishlatilgan manbalar ro'yxati", en: "bibliography", ru: "библиография" },
    { term: "iqtibos", def: "Boshqa muallifning g'oyasini keltirish", en: "citation", ru: "цитирование" },
    { term: "tadqiqot", def: "Yangi bilim olish uchun tizimli izlanish", en: "research", ru: "исследование" },
    { term: "hipoteza", def: "Tadqiqot uchun taxminiy javob", en: "hypothesis", ru: "гипотеза" },
    { term: "metodologiya", def: "Tadqiqot usullari tizimi", en: "methodology", ru: "методология" },
    { term: "nativ", def: "Tadqiqot natijalari", en: "results", ru: "результаты" },
    { term: "muhokama", def: "Natijalarni tahlil qilish", en: "discussion", ru: "обсуждение" },
    { term: "xulosa", def: "Tadqiqotning umumiy natijasi", en: "conclusion", ru: "вывод" },
    { term: "annotatsiya", def: "Qisqacha mazmun", en: "abstract", ru: "аннотация" },
    { term: "kurs ishi", def: "Talaba tomonidan bajarilgan loyiha", en: "coursework", ru: "курсовая работа" },
    { term: "bitiruv malakaviy ishi", def: "Talim olish uchun yakuniy ish", en: "thesis", ru: "дипломная работа" },
    { term: "seminar", def: "Ilmiy muhokama yig'ilishi", en: "seminar", ru: "семинар" },
    { term: "konferentsiya", def: "Ilmiy yig'ilish", en: "conference", ru: "конференция" },
    { term: "jurnal", def: "Ilmiy nashr", en: "journal", ru: "журнал" },
    { term: "monografiya", def: "Bir mavzuga bag'ishlangan kitob", en: "monograph", ru: "монография" },
    { term: "darslik", def: "O'quv qo'llanma", en: "textbook", ru: "учебник" },
    { term: "ma'ruza", def: "O'qituvchining nutqi", en: "lecture", ru: "лекция" },
  ];

  for (const t of academicTerms) {
    languageStore.createTerm(
      'uz', t.term, t.def, 'academic_research', 'academic',
      { en: t.en, ru: t.ru }, t.term, [], [], [], ['AKMS'], 0.9, true,
    );
  }

  // ─── PROJECT MANAGEMENT ──────────────────

  const pmTerms: Array<{ term: string; def: string; en: string; ru: string }> = [
    { term: "loyiha", def: "Maqsadli bajariladigan ish to'plami", en: "project", ru: "проект" },
    { term: "vazifa", def: "Loyihaning alohida qismi", en: "task", ru: "задача" },
    { term: "muddat", def: "Bajarilish kerak bo'lgan sana", en: "deadline", ru: "крайний срок" },
    { term: "bosqich", def: "Loyihaning alohida davri", en: "phase", ru: "этап" },
    { term: "milodiy belgi", def: "Loyihaning muhim bosqichi", en: "milestone", ru: "веха" },
    { term: "xavf", def: "Loyihaga ta'sir qilishi mumkin bo'lgan salbiy hodisa", en: "risk", ru: "риск" },
    { term: "resurs", def: "Loyiha uchun kerakli vositalar", en: "resource", ru: "ресурс" },
    { term: "byudjet", def: "Loyiha xarajatlari rejası", en: "budget", ru: "бюджет" },
    { term: "jadvallash", def: "Loyiha bosqichlarini rejalashtirish", en: "scheduling", ru: "планирование" },
    { term: "bacharalash tuzilmasi", def: "Loyihani bajarilishi kerak bo'lgan ishlarga bo'lish", en: "Work Breakdown Structure", ru: "структура декомпозиции работ" },
    { term: "sprint", def: "Agile da qisqa muddatli ish davri", en: "sprint", ru: "спринт" },
    { term: "standup", def: "Qisqa kunlik yig'ilish", en: "standup", ru: "стендап" },
    { term: "retrospektiva", def: "Sprint oxiridagi tahlil", en: "retrospective", ru: "ретроспектива" },
    { term: "stakeholder", def: "Loyihaga qiziqqan tomon", en: "stakeholder", ru: "стейкхолдер" },
    { term: "scope", def: "Loyiha qamrovi", en: "scope", ru: "объём работ" },
  ];

  for (const t of pmTerms) {
    languageStore.createTerm(
      'uz', t.term, t.def, 'project_management', 'technical',
      { en: t.en, ru: t.ru }, t.term, [], [], [], ['AKMS'], 0.9, true,
    );
  }

  // ─── UZBEK GRAMMAR RULES ──────────────────

  // Spelling rules
  languageStore.addSpellingRule('uz', /\bg'instead\b/g.source, "g' instead", "Use o' instead of o");
  languageStore.addSpellingRule('uz', /\bdekan\b/g.source, "dekan", "Use 'dekilgan' not 'dekan'");
  languageStore.addSpellingRule('uz', /\bqiladi\b/g.source, "qiladi", "Check verb conjugation");
  languageStore.addSpellingRule('uz', /\bga\s+ega\b/g.source, "ga ega", "Double postposition");

  // Grammar rules
  languageStore.addGrammarRule(
    'uz', 'Yomonlik qoidasi',
    "O'zbek tilida fe'llar oxirida -di, -yapti, -yotgan, -gan ishlatiladi",
    /\b(\w+)\s+(qiladi|beradi|oladi|tushadi)\b/g.source,
    "Check verb tense consistency",
    'warning',
    [{ wrong: "U kitob o'qiydi", correct: "U kitob o'qiydi" }],
  );

  languageStore.addGrammarRule(
    'uz', 'Postposition qoidasi',
    "O'zbek tilida predloglar emas, postpositionlar ishlatiladi",
    /\b(davomida|uchun|haqida|bilan|gacha|keyin|oldin)\b/g.source,
    "Postposition usage",
    'info',
    [],
  );

  // ─── DOMAIN STYLE PROFILES ───────────────

  languageStore.setDomainProfile({
    domain: 'academic_research',
    language: 'uz',
    formality: 'formal',
    technicalDepth: 'expert',
    preferredTerminology: 'native',
    citationStyle: 'apa',
    sentenceLength: 'long',
    vocabulary: 'academic',
    features: {
      usePassiveVoice: true,
      useFirstPerson: false,
      useAbbreviations: true,
      useNumbersInText: true,
      maxSentenceLength: 40,
    },
  });

  languageStore.setDomainProfile({
    domain: 'software_engineering',
    language: 'uz',
    formality: 'semi_formal',
    technicalDepth: 'advanced',
    preferredTerminology: 'mixed',
    citationStyle: 'none',
    sentenceLength: 'medium',
    vocabulary: 'technical',
    features: {
      usePassiveVoice: false,
      useFirstPerson: true,
      useAbbreviations: true,
      useNumbersInText: true,
      maxSentenceLength: 25,
    },
  });

  languageStore.setDomainProfile({
    domain: 'electrical_engineering',
    language: 'uz',
    formality: 'semi_formal',
    technicalDepth: 'advanced',
    preferredTerminology: 'native',
    citationStyle: 'none',
    sentenceLength: 'medium',
    vocabulary: 'technical',
    features: {
      usePassiveVoice: true,
      useFirstPerson: false,
      useAbbreviations: true,
      useNumbersInText: true,
      maxSentenceLength: 30,
    },
  });

  languageStore.setDomainProfile({
    domain: 'economics',
    language: 'uz',
    formality: 'formal',
    technicalDepth: 'advanced',
    preferredTerminology: 'native',
    citationStyle: 'none',
    sentenceLength: 'long',
    vocabulary: 'technical',
    features: {
      usePassiveVoice: true,
      useFirstPerson: false,
      useAbbreviations: true,
      useNumbersInText: true,
      maxSentenceLength: 35,
    },
  });

  languageStore.setDomainProfile({
    domain: 'creative',
    language: 'uz',
    formality: 'informal',
    technicalDepth: 'basic',
    preferredTerminology: 'mixed',
    citationStyle: 'none',
    sentenceLength: 'short',
    vocabulary: 'standard',
    features: {
      usePassiveVoice: false,
      useFirstPerson: true,
      useAbbreviations: false,
      useNumbersInText: false,
      maxSentenceLength: 20,
    },
  });

  // ─── STYLE RULES ─────────────────────────

  languageStore.addStyleRule(
    'uz', 'academic_research',
    'Akademik matn qoidalari',
    "Akademik matnlarda rasmiy til ishlatilishi kerak",
    /\b(biz|men|siz)\b/g.source,
    'warning',
    [{ wrong: "Biz tadqiqot qildik", correct: "Tadqiqot o'tkazildi" }],
  );

  languageStore.addStyleRule(
    'uz', 'academic_research',
    'Iltifot qoidasi',
    "Akademik matnlarda iltifot ishlatish kerak emas",
    /\b(chunki|shuning uchun|lekin|garchi)\b/g.source,
    'info',
    [],
  );

  languageStore.addStyleRule(
    'uz', 'software_engineering',
    'Texnik terminlar',
    "Dasturlash terminlari inglizcha qoldirilishi mumkin",
    /\b(kod|debug|commit|branch|merge|deploy)\b/g.source,
    'info',
    [],
  );
}

export function getLanguageStats() {
  return languageStore.getStats();
}
