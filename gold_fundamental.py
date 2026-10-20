# -*- coding: utf-8 -*-
"""تحلیل فاندامنتال خبرها برای طلا: محورهای اثرگذار، توضیح اصطلاحات، سناریوهای اگر-آنگاه.
فقط از تیتر خبرها استفاده می‌کند؛ توضیح‌ها ثابت و آموزشی‌اند، وضعیت هر محور از خبرهای زنده می‌آید."""
import re

# ---------- واژه‌نامه: (الگو، نام کوتاه، نام کامل، معنی، اثر روی طلا) ----------
GLOSSARY = [
    (r"\bFed\b|Federal Reserve", "Fed", "Federal Reserve", "بانک مرکزی آمریکا؛ نرخ بهره‌ی دلار را تعیین می‌کند.",
     "مهم‌ترین نهاد برای طلا. نرخ بهره‌ی بالاتر معمولاً طلا را پایین می‌آورد و نرخ پایین‌تر طلا را بالا می‌برد."),
    (r"\bFOMC\b", "FOMC", "Federal Open Market Committee", "کمیته‌ای در Fed که سالی ۸ بار جلسه دارد و درباره‌ی نرخ بهره تصمیم می‌گیرد.",
     "روز جلسه نوسان شدید است. مهم‌تر از خود تصمیم، لحن بیانیه و کنفرانس خبری رئیس Fed است. لحن نرم یعنی طلا بالا، لحن سخت یعنی طلا پایین."),
    (r"\bCPI\b", "CPI", "Consumer Price Index (شاخص قیمت مصرف‌کننده)", "معیار اصلی تورم؛ ماهی یک بار منتشر می‌شود.",
     "اگر عدد واقعی بالاتر از پیش‌بینی باشد، یعنی Fed سخت‌گیر می‌ماند، دلار و بازده اوراق بالا می‌رود و طلا در کوتاه‌مدت پایین می‌آید. اگر پایین‌تر باشد، طلا معمولاً بالا می‌رود."),
    (r"core (CPI|inflation|PCE)", "Core", "تورم هسته", "تورم بدون غذا و انرژی؛ Fed به آن بیشتر از تورم کل توجه می‌کند.",
     "اثرش مثل CPI است ولی وزنش در تصمیم Fed بیشتر است."),
    (r"\bPCE\b", "PCE", "Personal Consumption Expenditures", "شاخص تورم مورد علاقه‌ی Fed.",
     "مثل CPI عمل می‌کند. عدد بالاتر از انتظار برای طلا منفی است و پایین‌تر از انتظار مثبت."),
    (r"\bPPI\b", "PPI", "Producer Price Index", "تورم از دید تولیدکننده؛ پیش‌نمای CPI است.",
     "اثر ضعیف‌تر از CPI دارد، ولی اگر شوکه‌کننده باشد بازار را تکان می‌دهد."),
    (r"nonfarm|non-farm|\bNFP\b|payrolls?", "NFP", "Non-Farm Payrolls (اشتغال غیرکشاورزی)", "گزارش اشتغال آمریکا؛ معمولاً جمعه‌ی اول هر ماه ساعت ۸:۳۰ شرق آمریکا (حدود ۱۶:۰۰ تهران).",
     "از پرنوسان‌ترین رویدادهای طلاست. اشتغال قوی یعنی اقتصاد خوب و نرخ بهره بالاتر، پس طلا پایین. اشتغال ضعیف یعنی انتظار کاهش نرخ، پس طلا بالا."),
    (r"jobless claims|unemployment claims", "Jobless Claims", "درخواست بیمه‌ی بیکاری", "آمار هفتگی (پنجشنبه‌ها) از تعداد افراد تازه‌بیکار.",
     "عدد بالا یعنی بازار کار ضعیف و کمی به نفع طلا. عدد پایین یعنی بازار کار قوی و کمی علیه طلا."),
    (r"\bADP\b", "ADP", "ADP Employment", "برآورد اشتغال بخش خصوصی؛ دو روز قبل از NFP می‌آید.",
     "پیش‌نمای NFP است. اثرش کمتر ولی جهتش مثل NFP است."),
    (r"\bJOLTS\b|job openings", "JOLTS", "Job Openings and Labor Turnover Survey", "تعداد فرصت‌های شغلی باز.",
     "عدد بالا یعنی بازار کار داغ و علیه طلا. عدد پایین یعنی خنک‌شدن بازار کار و به نفع طلا."),
    (r"\bPMI\b|\bISM\b", "PMI/ISM", "Purchasing Managers' Index", "نظرسنجی از مدیران خرید؛ بالای ۵۰ یعنی رشد اقتصاد و زیر ۵۰ یعنی انقباض.",
     "عدد قوی یعنی اقتصاد خوب و کمی علیه طلا. عدد ضعیف یعنی نگرانی رکود و معمولاً به نفع طلا."),
    (r"\bGDP\b", "GDP", "Gross Domestic Product (تولید ناخالص داخلی)", "اندازه‌ی رشد اقتصاد.",
     "رشد قوی علیه طلا و رشد ضعیف به نفع آن است، چون روی انتظار نرخ بهره اثر می‌گذارد."),
    (r"retail sales", "Retail Sales", "فروش خرده‌فروشی", "معیار خرج مصرف‌کننده‌ی آمریکایی.",
     "فروش قوی یعنی اقتصاد قوی و کمی علیه طلا. فروش ضعیف کمی به نفع طلا."),
    (r"\bDXY\b|dollar index|greenback|\bdollar\b", "DXY", "US Dollar Index (شاخص دلار)", "ارزش دلار در برابر سبدی از ارزها (یورو بیشترین وزن را دارد).",
     "طلا با دلار تقویم می‌شود، پس معمولاً رابطه‌ی معکوس دارند. دلار قوی‌تر یعنی طلا برای خریداران خارجی گران‌تر می‌شود و قیمت‌اش پایین می‌آید."),
    (r"yields?|treasur(y|ies)|\bUS10Y\b|10-year", "Yield / US10Y", "بازده اوراق خزانه‌ی آمریکا", "سودی که دولت آمریکا به وام‌دهندگان می‌دهد. US10Y بازده ۱۰ ساله است.",
     "طلا سود نمی‌دهد. وقتی بازده بالا می‌رود، نگه‌داشتن اوراق جذاب‌تر می‌شود و طلا فشار می‌خورد. بازده پایین‌تر به نفع طلاست."),
    (r"real yields?|\bTIPS\b", "Real Yield", "بازده واقعی (بازده اسمی منهای تورم)", "سود واقعی اوراق بعد از کم‌کردن تورم.",
     "قوی‌ترین عامل کوتاه‌مدت طلا. بازده واقعی منفی یا در حال افت یعنی طلا بالا. بازده واقعی در حال صعود یعنی طلا پایین."),
    (r"hawkish", "Hawkish", "سخت‌گیر", "لحن بانک مرکزی که از نرخ بهره‌ی بالا یا ماندگار حرف می‌زند.",
     "علیه طلا."),
    (r"dovish", "Dovish", "نرم", "لحن بانک مرکزی که از کاهش نرخ یا حمایت از اقتصاد حرف می‌زند.",
     "به نفع طلا."),
    (r"\bQE\b|quantitative easing", "QE", "Quantitative Easing (انبساط کمی)", "بانک مرکزی اوراق می‌خرد و پول تزریق می‌کند.",
     "پول بیشتر و نرخ پایین‌تر؛ به نفع طلا."),
    (r"\bQT\b|quantitative tightening|balance sheet", "QT", "Quantitative Tightening (انقباض کمی)", "بانک مرکزی ترازنامه‌اش را کوچک می‌کند و نقدینگی می‌گیرد.",
     "علیه طلا."),
    (r"dot plot", "Dot Plot", "نمودار نقطه‌ای Fed", "پیش‌بینی هر عضو Fed از نرخ بهره‌ی آینده (فصلی).",
     "اگر نقطه‌ها کاهش‌های کمتری نشان دهند علیه طلاست، و اگر بیشتر نشان دهند به نفع آن."),
    (r"Powell|Fed chair", "Powell", "رئیس Fed", "سخنان رئیس Fed می‌تواند بازار را در چند دقیقه جابه‌جا کند.",
     "هر نشانه از کاهش نرخ برای طلا مثبت و هر نشانه از نرخ بالاتر منفی است."),
    (r"Fed minutes|FOMC minutes", "Minutes", "صورت‌جلسه‌ی FOMC", "خلاصه‌ی بحث‌های جلسه؛ سه هفته بعد از جلسه منتشر می‌شود.",
     "نشان می‌دهد اعضا چقدر به کاهش یا افزایش نرخ تمایل داشتند."),
    (r"Jackson Hole", "Jackson Hole", "نشست سالانه‌ی بانکداران مرکزی (اوت)", "محلی که رئیس Fed گاهی جهت سیاست را اعلام می‌کند.",
     "سخنرانی‌اش اغلب نوسان بزرگ ایجاد می‌کند."),
    (r"Beige Book", "Beige Book", "کتاب بژ", "گزارش Fed از وضعیت اقتصاد مناطق آمریکا.",
     "اثر کوچک؛ برای شناخت وضعیت اقتصاد مفید است."),
    (r"Treasury auction|bond auction", "Auction", "حراج اوراق خزانه", "دولت آمریکا اوراق می‌فروشد.",
     "تقاضای ضعیف یعنی بازده بالا می‌رود و طلا فشار می‌خورد. تقاضای قوی به نفع طلاست."),
    (r"\bECB\b|Lagarde", "ECB", "European Central Bank", "بانک مرکزی اروپا.",
     "اگر ECB سخت‌گیرتر شود، یورو قوی می‌شود، DXY پایین می‌آید و طلا بالا می‌رود."),
    (r"\bBoJ\b|Bank of Japan|\bBoE\b|Bank of England", "BoJ/BoE", "بانک مرکزی ژاپن/انگلیس", "تصمیم‌های آن‌ها روی ین و پوند و در نتیجه روی دلار اثر می‌گذارد.",
     "بانک مرکزی سخت‌گیرتر یعنی ارز آن‌ها قوی و دلار ضعیف‌تر می‌شود که به نفع طلاست."),
    (r"gold etfs?|\bGLD\b|\bSPDR\b|etf (inflows?|outflows?)", "Gold ETF", "صندوق‌های قابل‌معامله‌ی طلا (مثل GLD)", "سرمایه‌گذاران عادی از این راه طلا می‌خرند؛ صندوق طلای فیزیکی نگه می‌دارد.",
     "ورود پول به ETF یعنی تقاضای سرمایه‌گذاری و صعود. خروج پول یعنی فشار فروش."),
    (r"central banks? .{0,20}(buy|gold)|\bPBoC\b", "Central bank buying", "خرید طلا توسط بانک‌های مرکزی", "چین، لهستان، ترکیه، هند و چند کشور دیگر چند سال است طلا ذخیره می‌کنند.",
     "خریدار بزرگ و کم‌حساس به قیمت است؛ کف‌های قیمتی را حمایت می‌کند."),
    (r"safe[- ]haven", "Safe haven", "پناهگاه امن", "دارایی‌ای که در بحران ارزش خود را حفظ می‌کند.",
     "در ترس و بحران پول به طلا می‌آید."),
    (r"risk[- ]on|risk[- ]off", "Risk-on / Risk-off", "رغبت به ریسک / فرار از ریسک", "Risk-on یعنی بازار به سهام علاقه دارد و Risk-off یعنی از ریسک فرار می‌کند.",
     "Risk-off معمولاً به نفع طلاست، ولی در شوک نقدینگی گاهی همه‌چیز از جمله طلا فروخته می‌شود."),
    (r"stagflation", "Stagflation", "رکود تورمی", "همزمانی تورم بالا و رشد ضعیف.",
     "یکی از بهترین شرایط برای طلا در بلندمدت."),
    (r"soft landing", "Soft landing", "فرود نرم", "کاهش تورم بدون رکود.",
     "برای طلا خنثی تا کمی منفی است، چون ترس از بحران کم می‌شود."),
    (r"de-?dollariz|\bBRICS\b", "De-dollarization / BRICS", "کاهش اتکا به دلار", "کشورهایی که ذخایر خود را از دلار به طلا و ارزهای دیگر می‌برند.",
     "روند بلندمدت مثبت برای طلا."),
    (r"tariffs?|trade war", "Tariffs", "تعرفه‌های گمرکی", "مالیات بر واردات.",
     "نااطمینانی و ترس از رکود را زیاد می‌کند و معمولاً حمایتگر طلاست. اگر دلار را قوی کند، اثر برعکس می‌شود."),
    (r"debt ceiling|government shutdown", "Debt ceiling / Shutdown", "سقف بدهی / تعطیلی دولت", "اگر کنگره توافق نکند، دولت آمریکا ممکن است پرداخت‌ها را متوقف کند.",
     "نااطمینانی بالا و معمولاً به نفع طلا است. گاهی انتشار آمار اقتصادی هم عقب می‌افتد."),
    (r"\bCOMEX\b|\bLBMA\b|\bXAU\b|spot gold", "COMEX / LBMA / XAU", "بازار آتی نیویورک / بازار فیزیکی لندن / نماد طلا", "XAU قیمت لحظه‌ای (spot) و GC=F قرارداد آتی COMEX است.",
     "قیمت آتی چند دلار با spot فرق دارد؛ این تفاوت عادی است."),
    (r"\bOPEC\b|crude|brent|\boil\b", "Oil / OPEC", "نفت و اوپک", "قیمت نفت روی انتظار تورم اثر می‌گذارد.",
     "نفت گران‌تر تورم را بالا می‌برد؛ اثر دوگانه دارد. اگر Fed را سخت‌گیر کند علیه طلا است و اگر نگرانی ژئوپلیتیک باشد به نفع آن."),
    (r"breakeven|inflation expectations", "Breakeven", "تورم مورد انتظار بازار", "تفاوت بازده اوراق عادی و اوراق ضدتورم.",
     "بالا رفتن آن اگر بازده واقعی را پایین بیاورد به نفع طلاست."),
]

# ---------- محورهای فاندامنتال ----------
# (id، عنوان، الگوهای صعودی، الگوهای نزولی، چرا مهم، متن هر حالت)
THEMES = [
    dict(id="fed", title="Fed و نرخ بهره",
         bull=r"rate[- ]cuts?|cuts? (interest )?rates?|dovish|easing|pause|pivot|fewer hikes",
         bear=r"rate hikes?|hikes? (interest )?rates?|hawkish|higher[- ]for[- ]longer|tightening|delay(s|ed)? (rate )?cuts?|fewer cuts?",
         why="طلا سود نمی‌دهد، پس وقتی نرخ بهره پایین می‌آید جذاب‌تر می‌شود.",
         up="بازار انتظار نرخ پایین‌تر دارد. این مهم‌ترین باد موافق طلا است و می‌تواند روند صعودی را نگه دارد.",
         down="بازار انتظار نرخ بالاتر یا ماندگار دارد. این سنگین‌ترین فشار روی طلاست؛ صعودها بدون خبر خوب ممکن است دوام نیاورند.",
         flat="خبر روشنی درباره‌ی نرخ بهره نیست. بازار منتظر داده‌ی بعدی یا جلسه‌ی Fed است."),
    dict(id="usd", title="دلار آمریکا (DXY)",
         bull=r"(dollar|dxy|greenback) (falls?|slips?|weakens?|drops?|slides?|retreats?|declines?|sinks?)|weaker dollar|dollar weakness",
         bear=r"(dollar|dxy|greenback) (rises?|gains?|strengthens?|jumps?|surges?|climbs?|rallies|advances?|firms?)|stronger dollar|dollar strength",
         why="طلا با دلار قیمت‌گذاری می‌شود و معمولاً رابطه‌ی معکوس با آن دارد.",
         up="دلار ضعیف شده است. طلا برای خریداران با ارزهای دیگر ارزان‌تر شده و تقاضا می‌تواند بیشتر شود.",
         down="دلار قوی شده است. طلا برای خریداران خارجی گران‌تر می‌شود و سقف صعود محدود می‌ماند.",
         flat="خبر مهمی درباره‌ی دلار نیست."),
    dict(id="yield", title="بازده اوراق خزانه",
         bull=r"yields? (fall|falls|drop|drops|slide|slides|tumble|tumbles|retreat|retreats|decline|declines|dip|dips)",
         bear=r"yields? (rise|rises|jump|jumps|surge|surges|climb|climbs|spike|spikes|hit|hits|advance|advances|edge up)",
         why="بازده اوراق هزینه‌ی فرصت نگه‌داشتن طلاست. رابطه‌اش با طلا معکوس است.",
         up="بازده‌ها پایین می‌آیند و نگه‌داشتن طلا ارزان‌تر می‌شود. این از صعود طلا حمایت می‌کند.",
         down="بازده‌ها بالا می‌روند و پول به سمت اوراق با سود مطمئن می‌رود. این روی طلا فشار می‌آورد.",
         flat="تغییر مهمی در بازده‌ها گزارش نشده است."),
    dict(id="infl", title="تورم (CPI / PCE)",
         bull=r"(cpi|inflation|pce) (cools?|eases?|slows?|falls?|softens?|below (forecast|expectations))|softer inflation|disinflation",
         bear=r"(cpi|inflation|pce) (rises?|jumps?|accelerat\w*|hotter|higher|above (forecast|expectations)|surges?)|hotter[- ]than[- ]expected|sticky inflation",
         why="تورم تعیین می‌کند Fed نرخ را پایین بیاورد یا نه. اثر کوتاه‌مدتش از مسیر نرخ بهره است.",
         up="تورم خنک شده و Fed فضای بیشتری برای کاهش نرخ دارد. در کوتاه‌مدت به نفع طلاست.",
         down="تورم از انتظار داغ‌تر است. Fed سخت‌گیر می‌ماند و در کوتاه‌مدت طلا فشار می‌خورد، حتی اگر در بلندمدت تورم برای طلا خوب باشد.",
         flat="خبر مهمی درباره‌ی تورم نیست."),
    dict(id="jobs", title="اشتغال و داده‌های اقتصادی",
         bull=r"(weak|weaker|soft|softer|disappointing) (jobs|payrolls|employment|data|retail sales|gdp|pmi)|payrolls (miss|disappoint|fall|slow)|jobs (miss|slow)|unemployment (rises|jumps|climbs)|jobless claims (rise|jump|climb)",
         bear=r"(strong|stronger|robust|solid|upbeat) (jobs|payrolls|employment|data|retail sales|gdp|pmi)|payrolls (beat|top|surge|jump|rise)|jobs (beat|surge|top)|unemployment (falls?|drops?|declines?)",
         why="اقتصاد قوی یعنی Fed می‌تواند نرخ را بالا نگه دارد؛ اقتصاد ضعیف یعنی کاهش نرخ نزدیک‌تر است.",
         up="داده‌ها ضعیف‌اند. بازار کاهش نرخ را زودتر انتظار دارد و این برای طلا خوب است. البته اگر ضعف شدید شود و بازار سهام بریزد، فروش فشاری هم ممکن است.",
         down="داده‌ها قوی‌اند. بازار کاهش نرخ را عقب می‌اندازد و این برای طلا بد است.",
         flat="داده‌ی اقتصادی مهمی در تیترها نیست."),
    dict(id="geo", title="ژئوپلیتیک (جنگ و تنش)",
         bull=r"escalat|invasion|invade|missile|air ?strike|military strike|drone attack|attack on|war fears|conflict widen|tensions (rise|flare|mount)|geopolitical (tension|risk)",
         bear=r"cease-?fire|peace (deal|talks|agreement)|de-?escalat|truce|tensions (ease|cool|subside)",
         why="در جنگ و ترس، پول به پناهگاه امن می‌رود و طلا یکی از مهم‌ترین آن‌هاست.",
         up="تنش بالا می‌رود و تقاضای پناهگاه امن زیاد می‌شود. معمولاً جهش سریع می‌دهد، ولی اگر تنش بالا نماند بخشی از آن برمی‌گردد.",
         down="تنش در حال کاهش است. پرمیوم ترس از قیمت طلا کم می‌شود و ممکن است اصلاح کند.",
         flat="رویداد ژئوپلیتیک تازه‌ای در تیترها نیست."),
    dict(id="demand", title="تقاضای فیزیکی و بانک‌های مرکزی",
         bull=r"central banks? (are )?(buy|buying|bought|purchas|accumulat|add)|gold etfs? (inflows?|holdings (rise|climb|increase))|etf inflows?|de-?dollariz|brics (gold|currency)",
         bear=r"gold etfs? (outflows?|holdings (fall|drop|decline))|etf outflows?|central banks? (sell|selling|sold|reduc)",
         why="خریداران بزرگ می‌توانند روند چندماهه بسازند و کف قیمتی را نگه دارند.",
         up="خریداران بزرگ یا صندوق‌ها در حال خریدند. این پشتوانه‌ی بلندمدت است و افت‌ها را عمیق نمی‌کند.",
         down="فروش یا خروج پول از صندوق‌هاست. این فشار فروش واقعی است و باید جدی گرفته شود.",
         flat="خبر تازه‌ای از خرید بانک‌های مرکزی یا ETF نیست."),
    dict(id="risk", title="ریسک بازار و رکود",
         bull=r"recession (fears?|risks?|worr|concerns?)|banking (crisis|stress|turmoil)|credit (crunch|stress)|financial (crisis|turmoil)|debt (ceiling|crisis)|government shutdown|stocks? (plunge|tumble|crash|sell-?off)",
         bear=r"risk[- ]on|stocks? (rally|surge|hit(s)? (a )?record)|equities (rally|surge)",
         why="ترس از رکود و بحران مالی تقاضای پناهگاه امن را بالا می‌برد؛ رغبت به ریسک آن را کم می‌کند.",
         up="نگرانی اقتصادی یا مالی بالا رفته و پول به سمت دارایی امن می‌آید.",
         down="بازار سهام خوب است و رغبت به ریسک بالاست، پس نیاز کمتری به پناهگاه امن حس می‌شود.",
         flat="فضای ریسک بازار خنثی است."),
    dict(id="trade", title="تعرفه و تحریم",
         bull=r"tariffs?|trade war|sanctions",
         bear=r"$^",
         why="نااطمینانی تجاری اغلب به نفع طلاست، مگر اینکه دلار را قوی کند.",
         up="جنگ تجاری یا تحریم، نااطمینانی را بالا برده است. معمولاً حمایتگر طلاست.",
         down="",
         flat="خبر تعرفه یا تحریم مهمی نیست."),
]

# ---------- رویدادهای مهم بعدی (ثابت و آموزشی) ----------
WATCH = [
    ("NFP (اشتغال آمریکا)", "جمعه‌ی اول هر ماه، ۸:۳۰ شرق آمریکا (حدود ۱۶:۰۰ تهران)",
     "عدد بالاتر از پیش‌بینی: دلار↑ و طلا↓ . عدد پایین‌تر: دلار↓ و طلا↑ ."),
    ("CPI (تورم)", "حدود روز ۱۰ تا ۱۵ هر ماه، ۸:۳۰ شرق آمریکا",
     "تورم داغ‌تر از انتظار: طلا↓ . خنک‌تر از انتظار: طلا↑ ."),
    ("FOMC (تصمیم نرخ بهره)", "۸ بار در سال، ساعت ۱۴:۰۰ شرق آمریکا و کنفرانس خبری ۳۰ دقیقه بعد",
     "لحن نرم: طلا↑ . لحن سخت: طلا↓ . قبل از اعلام، نوسان زیاد و حرکت‌های کاذب رایج است."),
    ("PCE", "اواخر هر ماه",
     "تورم مورد علاقه‌ی Fed؛ جهت اثرش مثل CPI."),
    ("درخواست بیمه‌ی بیکاری", "هر پنجشنبه",
     "عدد بالاتر: کمی به نفع طلا."),
]


def _count(items, pat):
    """مجموع وزن زمانی خبرهایی که با الگو می‌خوانند + بهترین نمونه."""
    tot, best = 0.0, None
    for it in items:
        if re.search(pat, it["title"], re.I):
            w = 0.5 ** (it["age_h"] / 6)
            tot += w
            if best is None or w > best[0]:
                best = (w, it)
    return tot, (best[1] if best else None)


def analyze(items, bias=0):
    """items: فهرست خبرها با title و age_h . خروجی برای ذخیره در data.json"""
    items = items or []
    themes = []
    for t in THEMES:
        bu, bu_it = _count(items, t["bull"])
        be, be_it = _count(items, t["bear"])
        net = bu - be
        if bu + be < 0.15:
            state, txt, ex = 0, t["flat"], None
        elif net > 0.12:
            state, txt, ex = 1, t["up"], bu_it
        elif net < -0.12:
            state, txt, ex = -1, t["down"] or t["flat"], be_it
        else:
            state, txt, ex = 0, "خبرهای موافق و مخالف هم‌زمان آمده‌اند؛ بازار مردد است.", bu_it or be_it
        themes.append(dict(id=t["id"], title=t["title"], state=state, why=t["why"], text=txt,
                           strength=round(abs(net), 2), example=(ex["title"] if ex else None),
                           link=(ex.get("link") if ex else None)))
    active = sorted([x for x in themes if x["state"] != 0], key=lambda x: -x["strength"])
    ups = [x for x in active if x["state"] > 0][:2]
    downs = [x for x in active if x["state"] < 0][:2]

    # خلاصه‌ی «چه اتفاقی قرار است بیفتد»
    if not active:
        outlook = "خبر فاندامنتال تعیین‌کننده‌ای در تیترها نیست. در این حالت تکنیکال و رویدادهای زمان‌بندی‌شده تعیین‌کننده‌ترند."
    else:
        parts = []
        if ups:
            parts.append("عوامل به نفع طلا: " + "، ".join(x["title"] for x in ups) + ".")
        if downs:
            parts.append("عوامل علیه طلا: " + "، ".join(x["title"] for x in downs) + ".")
        if bias >= 25:
            parts.append("جمع‌بندی: خبرها در حال حاضر بیشتر به سمت صعود طلا می‌روند، ولی تا وقتی قیمت ساختار تکنیکال را نشکسته، فقط یک عامل کمکی‌اند.")
        elif bias <= -25:
            parts.append("جمع‌بندی: خبرها در حال حاضر بیشتر به سمت فشار روی طلا می‌روند. صعودها بدون تأیید تکنیکال قابل‌اعتماد نیستند.")
        else:
            parts.append("جمع‌بندی: خبرها متعادل یا مختلط‌اند و جهت روشنی نمی‌دهند. بازار بیشتر منتظر رویداد بعدی است.")
        outlook = " ".join(parts)

    # اصطلاحات پیدا شده در تیترها
    blob = [it["title"] for it in items]
    terms, seen = [], set()
    for pat, ab, full, meaning, eff in GLOSSARY:
        if ab in seen:
            continue
        hit = next((t for t in blob if re.search(pat, t, re.I)), None)
        if hit:
            seen.add(ab)
            terms.append(dict(ab=ab, full=full, meaning=meaning, effect=eff, in_news=hit))
    terms = terms[:12]
    gloss = [dict(ab=ab, full=full, meaning=meaning, effect=eff) for _, ab, full, meaning, eff in GLOSSARY]
    watch = [dict(name=n, when=w, rule=r) for n, w, r in WATCH]
    return dict(outlook=outlook, themes=themes, terms=terms, glossary=gloss, watch=watch)
